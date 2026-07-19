"""Поведенческий тест debian/local/lib/check_nginx_running.sh.

Регрессия, которая почти уронила рабочий сайт при первом реальном
апгрейде: postinst включал и стартовал nginx-rtmp.service, даже когда
nginx уже был запущен вне systemd (старым restart_astra.sh) — при
следующей перезагрузке два экземпляра nginx дрались за порты 1936/8082
и оба падали в restart-loop. Этот скрипт — единственное место, которое
решает "уже запущен или нет", поэтому тестируем именно его, с поддельным
pgrep, без реального nginx/systemd."""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "debian" / "local" / "lib" / "check_nginx_running.sh"


class NginxConflictDetectionTests(unittest.TestCase):
    def _run(self, *, pgrep_finds_nginx: bool, pidfile_alive: bool | None = None) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()

            pgrep_exit = "0" if pgrep_finds_nginx else "1"
            (bin_dir / "pgrep").write_text(f"#!/bin/sh\nexit {pgrep_exit}\n")
            (bin_dir / "pgrep").chmod(0o755)

            env = dict(os.environ)
            env["PATH"] = f"{bin_dir}:{env['PATH']}"

            if pidfile_alive is None:
                # без pid-файла вообще (нет /usr/local/nginx на этой машине)
                env["NGINX_PID_FILE"] = str(Path(tmp) / "does-not-exist.pid")
            else:
                pid_file = Path(tmp) / "nginx.pid"
                # kill -0 $$ (наш собственный PID) — гарантированно "жив";
                # заведомо мёртвый PID для случая pidfile_alive=False
                pid_file.write_text(str(os.getpid()) if pidfile_alive else "999999999")
                env["NGINX_PID_FILE"] = str(pid_file)

            result = subprocess.run(
                ["sh", str(SCRIPT)], env=env, capture_output=True, text=True, check=True
            )
            return result.stdout.strip()

    def test_running_via_pgrep_detected(self):
        self.assertEqual(self._run(pgrep_finds_nginx=True), "true")

    def test_running_via_stale_pgrep_but_live_pidfile_detected(self):
        self.assertEqual(self._run(pgrep_finds_nginx=False, pidfile_alive=True), "true")

    def test_not_running_when_no_pgrep_and_no_pidfile(self):
        self.assertEqual(self._run(pgrep_finds_nginx=False), "false")

    def test_not_running_when_pidfile_is_stale(self):
        self.assertEqual(self._run(pgrep_finds_nginx=False, pidfile_alive=False), "false")


if __name__ == "__main__":
    unittest.main()
