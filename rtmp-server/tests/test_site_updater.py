"""Тесты updates/site_updater.py — в первую очередь регрессионный тест на
баг, из-за которого обновление сайта падало на КАЖДОМ пуше в main с мая:
_backup() использовал рекурсивный tarfile.add(), который падает целиком на
первом же файле без прав на чтение (реально — .flask_secret_key, доступный
только процессу сайта, а не пользователю self-hosted раннера). Тест
воспроизводит PermissionError через mock, не полагаясь на реальные права
доступа ОС (тесты часто гоняются от root, где chmod 000 ничего не блокирует)."""

from __future__ import annotations

import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from rtmp_server.updates.site_updater import (
    _backup,
    _extractall_compat,
    _restore,
    _rsync,
    fetch_latest_site_source,
)


class BackupPermissionErrorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.dest = self.root / "live-server"
        self.dest.mkdir()
        (self.dest / "server.py").write_text("print('ok')")
        (self.dest / ".flask_secret_key").write_text("secret")
        self.backup_tar = self.root / "backup" / "live-server.tar"

    def tearDown(self):
        self.tmp.cleanup()

    def test_backup_skips_unreadable_file_instead_of_crashing(self):
        real_add = tarfile.TarFile.add

        def flaky_add(self, name, arcname=None, recursive=True, **kwargs):
            if str(name).endswith(".flask_secret_key"):
                raise PermissionError(13, "Permission denied", str(name))
            return real_add(self, name, arcname=arcname, recursive=recursive, **kwargs)

        with mock.patch.object(tarfile.TarFile, "add", flaky_add):
            _backup(self.dest, self.backup_tar)  # не должно бросить исключение

        self.assertTrue(self.backup_tar.exists())
        with tarfile.open(self.backup_tar) as tar:
            names = tar.getnames()
        self.assertIn("live-server/server.py", names)
        self.assertNotIn("live-server/.flask_secret_key", names)

    def test_backup_and_restore_roundtrip_when_everything_readable(self):
        _backup(self.dest, self.backup_tar)

        restored_root = self.root / "restored"
        restored_root.mkdir()
        target = restored_root / "live-server"
        _restore(target, self.backup_tar)

        self.assertEqual((target / "server.py").read_text(), "print('ok')")
        self.assertEqual((target / ".flask_secret_key").read_text(), "secret")

    def test_backup_of_missing_dir_creates_empty_tar_without_error(self):
        missing = self.root / "does-not-exist"
        _backup(missing, self.backup_tar)
        self.assertTrue(self.backup_tar.exists())
        with tarfile.open(self.backup_tar) as tar:
            self.assertEqual(tar.getnames(), [])


class ExtractallFilterCompatTests(unittest.TestCase):
    """Регрессия: extractall(..., filter="data") (PEP 706) не поддерживается
    на системном python3 реального сервера (Astra Linux) — бэкпортировано
    только в отдельные патч-релизы 3.8-3.11, там же ловится TypeError.
    Обнаружено владельцем вживую при первой попытке "Обновить сайт" из GUI."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.archive = self.root / "test.tar"
        payload = self.root / "payload.txt"
        payload.write_text("content")
        with tarfile.open(self.archive, "w") as tar:
            tar.add(payload, arcname="payload.txt")

    def tearDown(self):
        self.tmp.cleanup()

    def test_falls_back_when_filter_kwarg_unsupported(self):
        dest = self.root / "out"
        dest.mkdir()

        real_extractall = tarfile.TarFile.extractall

        def flaky_extractall(self, path=".", members=None, *, numeric_owner=False, filter=None):
            if filter is not None:
                raise TypeError("extractall() got an unexpected keyword argument 'filter'")
            return real_extractall(self, path, members, numeric_owner=numeric_owner)

        with mock.patch.object(tarfile.TarFile, "extractall", flaky_extractall):
            with tarfile.open(self.archive) as tar:
                _extractall_compat(tar, dest)  # не должно бросить исключение

        self.assertEqual((dest / "payload.txt").read_text(), "content")

    def test_uses_filter_when_supported(self):
        dest = self.root / "out"
        dest.mkdir()
        with tarfile.open(self.archive) as tar:
            _extractall_compat(tar, dest)
        self.assertEqual((dest / "payload.txt").read_text(), "content")


class RsyncPreservesDestinationOwnershipTests(unittest.TestCase):
    """Регрессия: _rsync() использовал `rsync -a`, что переносит владельца
    и группу из src на dest. src — распакованный из GitHub архив,
    принадлежащий тому, кто запускал обновление (root), а живой сайт
    работает от www-data. Это молча переставляло владельца
    /var/www/live-server на root, из-за чего www-data терял право писать
    в свою же sqlite-базу, и сервис падал в restart-loop с "attempt to
    write a readonly database" сразу при старте."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.src = self.root / "src"
        self.dest = self.root / "dest"
        self.src.mkdir()
        self.dest.mkdir()
        # Разная длина содержимого — иначе rsync-овская быстрая проверка
        # (совпадающие размер+mtime) может решить, что файл не менялся,
        # и пропустить синхронизацию, дав ложноотрицательный результат теста.
        (self.src / "server.py").write_text("print('this is the new deployed code')")
        (self.dest / "server.py").write_text("old")

    def tearDown(self):
        self.tmp.cleanup()

    def test_rsync_does_not_change_destination_owner(self):
        import os
        import shutil

        if shutil.which("rsync") is None:
            self.skipTest("rsync не установлен в этом окружении")
        if os.geteuid() != 0:
            self.skipTest("chown к произвольному UID требует root")

        fake_uid, fake_gid = 5000, 5000  # имитируем www-data
        os.chown(self.dest, fake_uid, fake_gid)
        os.chown(self.dest / "server.py", fake_uid, fake_gid)

        _rsync(self.src, self.dest)

        dest_stat = self.dest.stat()
        self.assertEqual(dest_stat.st_uid, fake_uid)
        self.assertEqual(dest_stat.st_gid, fake_gid)
        self.assertEqual((self.dest / "server.py").read_text(), "print('this is the new deployed code')")

    def test_rsync_command_uses_no_owner_no_group_not_archive(self):
        captured = {}

        def fake_run(args, **kwargs):
            captured["args"] = args
            return mock.Mock(returncode=0, stderr="")

        with mock.patch("subprocess.run", side_effect=fake_run):
            _rsync(self.src, self.dest)

        self.assertNotIn("-a", captured["args"])
        self.assertIn("--no-owner", captured["args"])
        self.assertIn("--no-group", captured["args"])


class FetchLatestSiteSourceTests(unittest.TestCase):
    """download_file() подменяется моком — реальный сетевой запрос к GitHub
    здесь не нужен, важно только правильно распознать структуру архива
    codeload (<repo>-<branch>/www/...)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _build_fake_tarball(self, dest: Path, top_dir: str = "local-main") -> None:
        with tarfile.open(dest, "w:gz") as tar:
            live_server_py = self.root / "server.py.tmp"
            live_server_py.write_text("print('site')")
            tar.add(live_server_py, arcname=f"{top_dir}/www/live-server/server.py")
            reboot_py = self.root / "reboot_server.py.tmp"
            reboot_py.write_text("print('reboot')")
            tar.add(reboot_py, arcname=f"{top_dir}/www/reboot/server.py")

    def test_fetch_extracts_and_locates_www_under_codeload_top_dir(self):
        def fake_download(url, dest, timeout=60.0, on_progress=None):
            self._build_fake_tarball(dest)
            return dest

        with mock.patch("rtmp_server.updates.staging.download_file", side_effect=fake_download):
            source = fetch_latest_site_source(self.root / "work")

        self.assertTrue((source.live_server_src / "server.py").exists())
        self.assertTrue((source.reboot_src / "server.py").exists())

    def test_fetch_raises_clearly_on_unexpected_archive_layout(self):
        def fake_download(url, dest, timeout=60.0, on_progress=None):
            with tarfile.open(dest, "w:gz") as tar:
                stray = self.root / "stray.tmp"
                stray.write_text("x")
                tar.add(stray, arcname="one/file.txt")
                tar.add(stray, arcname="two/file.txt")
            return dest

        with mock.patch("rtmp_server.updates.staging.download_file", side_effect=fake_download):
            with self.assertRaises(RuntimeError):
                fetch_latest_site_source(self.root / "work")

    def test_fetch_passes_on_progress_through_to_download_file(self):
        """Прогресс-бар в GUI ("Обновить сайт") завязан на этот проброс —
        без него не мог бы показывать реальный процент скачивания."""
        received = {}

        def fake_download(url, dest, timeout=60.0, on_progress=None):
            received["on_progress"] = on_progress
            self._build_fake_tarball(dest)
            return dest

        marker = object()

        with mock.patch("rtmp_server.updates.staging.download_file", side_effect=fake_download):
            fetch_latest_site_source(self.root / "work", on_progress=marker)

        self.assertIs(received["on_progress"], marker)


if __name__ == "__main__":
    unittest.main()
