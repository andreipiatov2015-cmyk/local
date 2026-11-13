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
        self.assertIn(C.SYSTEM_PYTHON_BIN, text)
        self.assertIn(C.LIVE_SERVER_SCRIPT, text)
        self.assertIn(C.LIVE_SERVER_DIR, text)
        self.assertIn(C.LIVE_SERVER_LOG, text)
        self.assertIn(C.SITE_CONFIG_ENV_FILE, text)  # ключ трансляции — see stream_info.py
        self.assertNotIn(".venv", text)  # подтверждено владельцем: venv на сайте нет

    def test_reboot_server_unit_matches_constants(self):
        text = (UNITS_DIR / "reboot-server.service").read_text()
        self.assertIn(C.SYSTEM_PYTHON_BIN, text)
        self.assertIn(C.REBOOT_SERVER_SCRIPT, text)
        self.assertIn(C.REBOOT_SERVER_DIR, text)
        self.assertIn(C.REBOOT_SERVER_LOG, text)
        self.assertNotIn(".venv", text)

    def test_registration_public_unit_matches_constants(self):
        text = (UNITS_DIR / "registration-public.service").read_text()
        self.assertIn(C.SYSTEM_PYTHON_BIN, text)
        self.assertIn(C.REGISTRATION_PUBLIC_SCRIPT, text)
        self.assertIn(C.REGISTRATION_PUBLIC_DIR, text)
        self.assertIn(C.REGISTRATION_PUBLIC_LOG, text)
        # В отличие от live-server/reboot-server (root) — этот процесс
        # нарочно запущен от отдельного непривилегированного пользователя,
        # см. сам юнит-файл и config/constants.py.
        self.assertIn(f"User={C.REGISTRATION_PUBLIC_USER}", text)
        self.assertNotIn(".venv", text)

    def test_postinst_creates_registration_public_user_and_drop_dir(self):
        text = (UNITS_DIR.parent.parent / "rtmp-server.postinst").read_text()
        self.assertIn(C.REGISTRATION_PUBLIC_USER, text)
        self.assertIn(C.REGISTRATION_DROP_DIR, text)
        self.assertIn("pynacl", text)

    def test_postinst_references_same_unit_names_as_constants(self):
        text = (UNITS_DIR.parent.parent / "rtmp-server.postinst").read_text()
        for unit in C.ALL_MANAGED_UNITS:
            self.assertIn(unit, text)

    def test_hls_cleanup_timer_matches_constants(self):
        text = (UNITS_DIR / C.UNIT_HLS_CLEANUP_TIMER).read_text()
        self.assertIn(C.UNIT_HLS_CLEANUP_SERVICE, text)

    def test_hls_cleanup_service_and_timer_wired_into_postinst_prerm_postrm(self):
        base = UNITS_DIR.parent.parent
        postinst = (base / "rtmp-server.postinst").read_text()
        prerm = (base / "rtmp-server.prerm").read_text()
        postrm = (base / "rtmp-server.postrm").read_text()
        for unit in (C.UNIT_HLS_CLEANUP_SERVICE, C.UNIT_HLS_CLEANUP_TIMER):
            self.assertIn(unit, postinst)
            self.assertIn(unit, postrm)
        self.assertIn(C.UNIT_HLS_CLEANUP_TIMER, prerm)


if __name__ == "__main__":
    unittest.main()
