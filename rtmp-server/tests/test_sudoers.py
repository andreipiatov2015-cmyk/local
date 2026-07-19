"""Проверяет синтаксис debian/local/rtmp-server.sudoers через visudo -c.

postinst сам делает эту проверку перед установкой в /etc/sudoers.d (битый
sudoers-файл может сломать sudo для всей системы), но лучше поймать
опечатку здесь, в CI, чем на боевой машине владельца."""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

SUDOERS_FILE = Path(__file__).resolve().parent.parent / "debian" / "local" / "rtmp-server.sudoers"


class SudoersSyntaxTests(unittest.TestCase):
    def test_visudo_accepts_file(self):
        if shutil.which("visudo") is None:
            self.skipTest("visudo недоступен в этом окружении")

        result = subprocess.run(
            ["visudo", "-c", "-f", str(SUDOERS_FILE)], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_requiretty_disabled_for_our_command(self):
        """Без этого клик по ярлыку из графической оболочки (без tty)
        молча ничего не делает — sudo просто отказывается выполнять команду."""
        text = SUDOERS_FILE.read_text()
        self.assertIn("!requiretty", text)


if __name__ == "__main__":
    unittest.main()
