"""Тесты services/ — в первую очередь регрессия на баг: generic "Запустить"
на вкладке "Сервисы" (или `rtmp-server-ctl start vk_pusher`) молча ничего не
делал для vk_pusher, потому что start_vk.py требует обязательный аргумент
stream_name, которого универсальный start_argv дать не может. Popen при этом
не проверяет, чем закончился запущенный процесс, так что ошибка нигде не
всплывала — кнопка просто выглядела так, будто она не работает."""

from __future__ import annotations

import unittest

from rtmp_server.services.definitions import SERVICES
from rtmp_server.services.process_service import ProcessService


class ProcessServiceStartArgvTests(unittest.TestCase):
    def test_start_without_argv_raises_clear_error_instead_of_silently_doing_nothing(self):
        svc = ProcessService(name="x", display_name="X", pattern="nomatch-pattern-xyz")
        with self.assertRaises(RuntimeError) as ctx:
            svc.start()
        self.assertIn("вкладку", str(ctx.exception))

    def test_vk_pusher_has_no_generic_start_argv(self):
        """Регрессия: vk_pusher специально не может стартовать через общий
        ServiceHandle.start()/.restart() — только через
        site_admin.stream_info.restart_vk_push(), который знает имя
        реально активного потока."""
        self.assertIsNone(SERVICES["vk_pusher"].start_argv)


if __name__ == "__main__":
    unittest.main()
