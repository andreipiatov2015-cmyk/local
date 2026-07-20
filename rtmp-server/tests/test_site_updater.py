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

from rtmp_server.updates.site_updater import _backup, _restore


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


if __name__ == "__main__":
    unittest.main()
