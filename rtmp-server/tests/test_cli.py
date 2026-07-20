"""Тесты cli.py — регрессия: `rtmp-server-ctl start all` (или restart all)
раньше падал необработанным traceback'ом на первом же сервисе, чей
start()/stop() бросает исключение (после того как vk_pusher стал явно
поднимать RuntimeError вместо молчаливого no-op — см. test_services.py).
cmd_service_action должен ловить ошибку конкретного сервиса, печатать её и
продолжать (или хотя бы завершиться кодом ошибки без трассировки)."""

from __future__ import annotations

import unittest
from unittest import mock

from rtmp_server import cli


class FakeService:
    def __init__(self, name, fail=False):
        self.name = name
        self._fail = fail
        self.started = False

    def start(self):
        if self._fail:
            raise RuntimeError(f"{self.name}: не может стартовать")
        self.started = True


class ServiceActionErrorHandlingTests(unittest.TestCase):
    def test_start_all_does_not_crash_when_one_service_raises(self):
        services = [FakeService("a"), FakeService("b", fail=True), FakeService("c")]

        with mock.patch.object(cli, "get_all_services", return_value=services):
            args = mock.Mock()
            args.name = "all"
            args.action = "start"
            rc = cli.cmd_service_action(args)

        self.assertEqual(rc, 1)
        self.assertTrue(services[0].started)
        self.assertTrue(services[2].started)  # продолжил после ошибки на 'b'

    def test_start_all_returns_zero_when_everything_succeeds(self):
        services = [FakeService("a"), FakeService("b")]

        with mock.patch.object(cli, "get_all_services", return_value=services):
            args = mock.Mock()
            args.name = "all"
            args.action = "start"
            rc = cli.cmd_service_action(args)

        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
