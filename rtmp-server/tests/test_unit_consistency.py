"""Проверяет, что пути, зашитые в systemd-юнит-шаблоны (debian/local/units/),
совпадают с config/constants.py.

Именно рассинхрон такого рода (RTMP-порт 1935 в шести файлах против 1936
в реально задеплоенном nginx.conf) был причиной главного бага старого
приложения — GUI вечно показывал "остановлено". Этот тест — дешёвый способ
поймать повторение той же ошибки в CI до того, как она попадёт на боевой сервер.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from rtmp_server.config import constants as C

UNITS_DIR = Path(__file__).resolve().parent.parent / "debian" / "local" / "units"


class UnitFileConsistencyTests(unittest.TestCase):
    def test_nginx_rtmp_unit_matches_constants(self):
        text = (UNITS_DIR / "nginx-rtmp.service").read_text()
        self.assertIn(C.NGINX_BIN, text)
        self.assertIn(C.NGINX_PID_FILE, text)

    def test_live_server_unit_matches_constants(self):
        text = (UNITS_DIR / "live-server.service").read_text()
        self.assertIn(C.SITE_VENV, text)
        self.assertIn(C.LIVE_SERVER_SCRIPT, text)
        self.assertIn(C.LIVE_SERVER_DIR, text)

    def test_reboot_server_unit_matches_constants(self):
        text = (UNITS_DIR / "reboot-server.service").read_text()
        self.assertIn(C.SITE_VENV, text)
        self.assertIn(C.REBOOT_SERVER_SCRIPT, text)
        self.assertIn(C.REBOOT_SERVER_DIR, text)

    def test_postinst_references_same_unit_names_as_constants(self):
        text = (UNITS_DIR.parent.parent / "rtmp-server.postinst").read_text()
        for unit in C.ALL_MANAGED_UNITS:
            self.assertIn(unit, text)


if __name__ == "__main__":
    unittest.main()
