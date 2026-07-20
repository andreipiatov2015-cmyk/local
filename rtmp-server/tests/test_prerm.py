"""Поведенческий тест debian/rtmp-server.prerm: реально запускает скрипт
с поддельным systemctl (никакого настоящего systemd не требуется) и
проверяет, что сервис останавливается ТОЛЬКО при "remove", а не при
"upgrade" — именно перепутанность этих случаев убивала запущенное
GUI-приложение посреди самообновления (dpkg -i вызывает prerm с "upgrade",
а не "remove")."""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

PRERM = Path(__file__).resolve().parent.parent / "debian" / "rtmp-server.prerm"

FAKE_SYSTEMCTL = """#!/bin/sh
echo "$@" >> "$SYSTEMCTL_LOG"
exit 0
"""


class PrermBehaviorTests(unittest.TestCase):
    def _run_prerm(self, arg: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            fake_systemctl = bin_dir / "systemctl"
            fake_systemctl.write_text(FAKE_SYSTEMCTL)
            fake_systemctl.chmod(fake_systemctl.stat().st_mode | stat.S_IEXEC)

            log_file = Path(tmp) / "systemctl.log"
            env = dict(os.environ)
            env["PATH"] = f"{bin_dir}:{env['PATH']}"
            env["SYSTEMCTL_LOG"] = str(log_file)

            subprocess.run(["sh", str(PRERM), arg], env=env, check=True)
            return log_file.read_text() if log_file.exists() else ""

    def test_remove_stops_and_disables_gui_service(self):
        log = self._run_prerm("remove")
        self.assertIn("stop rtmp-server-gui.service", log)
        self.assertIn("disable rtmp-server-gui.service", log)

    def test_upgrade_does_not_touch_service(self):
        """Регрессия: dpkg вызывает prerm с 'upgrade' перед установкой новой
        версии (в том числе при самообновлении из уже запущенного GUI) —
        сервис не должен останавливаться, иначе процесс убивает сам себя."""
        log = self._run_prerm("upgrade")
        self.assertEqual(log, "")


if __name__ == "__main__":
    unittest.main()
