"""Тест самообновления (updates/app_updater.py) на реалистичных именах файлов.

Регрессия: apply_update() сохранял скачанный .deb под реконструированным
именем f"rtmp-server-{version}.deb", а реальный ассет релиза называется
rtmp-server_{version}-1_all.deb (подчёркивание, ревизия "-1", суффикс
"_all") — SHA256SUMS хранит чексуммы по настоящему имени файла, так что
поиск по неправильному ключу всегда возвращал "не найдено" и ложное
"чексумма не совпадает", даже когда файл был совершенно цел. Именно это
поймал владелец на реальном сервере при первой попытке самообновления."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from rtmp_server.updates import app_updater


class ApplyUpdateChecksumTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.download_dir = Path(self.tmp.name) / "download"
        self.fixtures_dir = Path(self.tmp.name) / "fixtures"
        self.fixtures_dir.mkdir()

        # Реалистичное имя ассета, как его реально публикует CI-релиз.
        self.deb_name = "rtmp-server_1.0.6-1_all.deb"
        deb_content = b"fake .deb content for test"
        (self.fixtures_dir / self.deb_name).write_bytes(deb_content)

        digest = hashlib.sha256(deb_content).hexdigest()
        (self.fixtures_dir / "SHA256SUMS").write_text(f"{digest}  {self.deb_name}\n")

        self.release = app_updater.ReleaseInfo(
            tag="v1.0.6",
            version="1.0.6",
            deb_asset_name=self.deb_name,
            deb_asset_url=f"file://{self.fixtures_dir / self.deb_name}",
            checksums_url=f"file://{self.fixtures_dir / 'SHA256SUMS'}",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def _fake_download_file(self, url: str, dest: Path, timeout: float = 60.0, on_progress=None) -> Path:
        # Подменяем реальный download_file (urllib) на копирование из
        # локальных фикстур — без сети, только проверяем логику именования.
        source = self.fixtures_dir / Path(url.replace("file://", "")).name
        dest.parent.mkdir(parents=True, exist_ok=True)
        size = source.stat().st_size
        if on_progress is not None:
            on_progress(0, size)
            on_progress(size, size)
        shutil.copy(source, dest)
        return dest

    def test_checksum_matches_with_real_asset_filename(self):
        with mock.patch.object(app_updater, "download_file", side_effect=self._fake_download_file), \
             mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(returncode=0, stderr="")
            result = app_updater.apply_update(self.release, download_dir=self.download_dir)

        self.assertTrue(result.applied, result.message)
        self.assertIn("1.0.6", result.message)
        # Файл должен был сохраниться именно под настоящим именем ассета.
        self.assertTrue((self.download_dir / self.deb_name).exists())

    def test_checksum_mismatch_still_detected(self):
        """Отдельно проверяем, что настоящее несовпадение чексуммы всё ещё ловится
        (это не тест на "всегда принимай что угодно")."""
        (self.fixtures_dir / self.deb_name).write_bytes(b"corrupted content, different from checksum")

        with mock.patch.object(app_updater, "download_file", side_effect=self._fake_download_file):
            result = app_updater.apply_update(self.release, download_dir=self.download_dir)

        self.assertFalse(result.applied)
        self.assertIn("Чексумма", result.message)

    def test_progress_callback_receives_start_and_complete(self):
        """Регрессия/фича: прогресс-бар в GUI (вкладка "Обновления") завязан
        на on_progress — без него он не мог бы показывать реальный процент."""
        calls = []

        with mock.patch.object(app_updater, "download_file", side_effect=self._fake_download_file), \
             mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(returncode=0, stderr="")
            app_updater.apply_update(
                self.release, download_dir=self.download_dir,
                on_progress=lambda done, total: calls.append((done, total)),
            )

        self.assertTrue(calls)
        first_done, first_total = calls[0]
        last_done, last_total = calls[-1]
        self.assertEqual(first_done, 0)
        self.assertGreater(first_total, 0)
        self.assertEqual(last_done, last_total)


if __name__ == "__main__":
    unittest.main()
