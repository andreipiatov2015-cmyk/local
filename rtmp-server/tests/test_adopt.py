"""Тест автозамены старого astra-monitor (setup/adopt.py).

Подменяет пути в config.constants на временные, чтобы не трогать реальную
файловую систему, и проверяет, что remove_legacy_app() реально убирает
всё, что должно быть убрано."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rtmp_server.config import constants as C
from rtmp_server.setup import adopt


class RemoveLegacyAppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)

        self._orig = (
            C.LEGACY_APP_INSTALL_DIR,
            C.LEGACY_APP_BINARY,
            C.LEGACY_APP_DESKTOP_FILE,
        )

        self.legacy_dir = root / "astra-monitor"
        self.legacy_dir.mkdir()
        (self.legacy_dir / "astra_monitor.py").write_text("# старое приложение")

        self.legacy_binary = root / "bin" / "astra-monitor"
        self.legacy_binary.parent.mkdir()
        self.legacy_binary.write_text("#!/bin/sh\n")

        self.legacy_desktop = root / "applications" / "astra-monitor.desktop"
        self.legacy_desktop.parent.mkdir()
        self.legacy_desktop.write_text("[Desktop Entry]\n")

        C.LEGACY_APP_INSTALL_DIR = str(self.legacy_dir)
        C.LEGACY_APP_BINARY = str(self.legacy_binary)
        C.LEGACY_APP_DESKTOP_FILE = str(self.legacy_desktop)

    def tearDown(self):
        C.LEGACY_APP_INSTALL_DIR, C.LEGACY_APP_BINARY, C.LEGACY_APP_DESKTOP_FILE = self._orig
        self.tmp.cleanup()

    def test_removes_dir_binary_and_desktop_file(self):
        removed = adopt.remove_legacy_app()

        self.assertFalse(self.legacy_dir.exists())
        self.assertFalse(self.legacy_binary.exists())
        self.assertFalse(self.legacy_desktop.exists())
        self.assertEqual(len(removed), 3)

    def test_safe_to_call_when_nothing_present(self):
        adopt.remove_legacy_app()  # первый вызов удаляет
        removed_second_time = adopt.remove_legacy_app()  # второй — уже нечего удалять

        self.assertEqual(removed_second_time, [])


if __name__ == "__main__":
    unittest.main()
