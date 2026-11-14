"""Тест rtmp_server/site_admin/root_auth.py.

По прямому запросу владельца: раньше чувствительные действия в программе
всегда подтверждались паролем root, что на практике неудобно и небезопасно
— пароль root меняется отдельной (и не всегда объявленной) организационной
политикой, независимо от личных паролей сотрудников. Теперь подтверждение
идёт паролем того пользователя ОС, который запустил приложение через sudo
(SUDO_USER), а не обязательно root.

Проверка пароля сделана через PAM, а не crypt()+/etc/shadow: на Astra Linux
пароли хранятся по ГОСТ-алгоритму ("$gos..."), который crypt() не понимает,
из-за чего раньше сравнение не проходило никогда, даже с верным паролем
(воспроизведено вживую на реальном сервере). Модуль PAM (пакет python3-pam)
импортируется лениво, поэтому в тестах подставляем поддельный через
sys.modules — реальный компилируется под ABI системного Python и в обычном
dev-окружении не ставится."""

from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

from rtmp_server.site_admin import root_auth


class _FakePamError(Exception):
    pass


class _FakePamSession:
    """Имитирует PAM.pam(): start/set_item/authenticate, как в PyPAM 0.4.x."""

    def __init__(self, module: "_FakePamModule") -> None:
        self._module = module
        self._items: dict[str, object] = {}

    def start(self, service: str) -> None:
        if self._module.start_should_fail:
            raise self._module.error("no such PAM service: " + service)
        self._items["service"] = service

    def set_item(self, key: str, value: object) -> None:
        self._items[key] = value

    def authenticate(self) -> None:
        if self._module.authenticate_raises is not None:
            raise self._module.authenticate_raises

        username = self._items.get(self._module.PAM_USER)
        conv = self._items.get(self._module.PAM_CONV)
        password = conv(None, [(None, None)], None)[0][0]

        if username != self._module.expected_username or password != self._module.correct_password:
            raise self._module.error("Authentication failure", 7)


class _FakePamModule:
    PAM_USER = "PAM_USER"
    PAM_CONV = "PAM_CONV"

    def __init__(
        self,
        *,
        expected_username: str,
        correct_password: str,
        start_should_fail: bool = False,
        authenticate_raises: Exception | None = None,
    ) -> None:
        self.error = _FakePamError
        self.expected_username = expected_username
        self.correct_password = correct_password
        self.start_should_fail = start_should_fail
        self.authenticate_raises = authenticate_raises

    def pam(self) -> _FakePamSession:
        return _FakePamSession(self)


class ConfirmingUsernameTests(unittest.TestCase):
    def test_uses_sudo_user_when_set(self):
        with mock.patch.dict(os.environ, {"SUDO_USER": "reimov"}):
            self.assertEqual(root_auth.confirming_username(), "reimov")

    def test_falls_back_to_root_without_sudo_user(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SUDO_USER", None)
            self.assertEqual(root_auth.confirming_username(), "root")


class VerifyConfirmingPasswordTests(unittest.TestCase):
    def _with_fake_pam(self, **kwargs):
        fake_module = _FakePamModule(**kwargs)
        return mock.patch.dict(sys.modules, {"PAM": fake_module})

    def test_correct_password_for_sudo_user_passes(self):
        with mock.patch.dict(os.environ, {"SUDO_USER": "reimov"}), self._with_fake_pam(
            expected_username="reimov", correct_password="s3cret"
        ):
            self.assertTrue(root_auth.verify_confirming_password("s3cret"))

    def test_root_password_no_longer_accepted_for_sudo_user(self):
        """Регрессия, которую и просили исправить: когда пользователь
        запущен через sudo, ввод пароля ROOT не должен подтверждать
        действие — должен подойти только пароль самого этого пользователя."""
        with mock.patch.dict(os.environ, {"SUDO_USER": "reimov"}), self._with_fake_pam(
            expected_username="reimov", correct_password="s3cret"
        ):
            self.assertFalse(root_auth.verify_confirming_password("rootpass"))

    def test_wrong_password_rejected(self):
        with mock.patch.dict(os.environ, {"SUDO_USER": "reimov"}), self._with_fake_pam(
            expected_username="reimov", correct_password="s3cret"
        ):
            self.assertFalse(root_auth.verify_confirming_password("wrong"))

    def test_empty_password_rejected_without_calling_pam(self):
        with mock.patch.dict(os.environ, {"SUDO_USER": "reimov"}):
            self.assertFalse(root_auth.verify_confirming_password(""))

    def test_falls_back_to_root_without_sudo_user(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SUDO_USER", None)
            with self._with_fake_pam(expected_username="root", correct_password="rootpass"):
                self.assertTrue(root_auth.verify_confirming_password("rootpass"))

    def test_pam_service_start_failure_raises_admin_auth_error(self):
        with mock.patch.dict(os.environ, {"SUDO_USER": "reimov"}), self._with_fake_pam(
            expected_username="reimov", correct_password="s3cret", start_should_fail=True
        ):
            with self.assertRaises(root_auth.AdminAuthError):
                root_auth.verify_confirming_password("s3cret")

    def test_unexpected_pam_exception_raises_admin_auth_error(self):
        with mock.patch.dict(os.environ, {"SUDO_USER": "reimov"}), self._with_fake_pam(
            expected_username="reimov",
            correct_password="s3cret",
            authenticate_raises=RuntimeError("libpam.so.0: cannot open shared object file"),
        ):
            with self.assertRaises(root_auth.AdminAuthError):
                root_auth.verify_confirming_password("s3cret")

    def test_missing_pam_module_raises_admin_auth_error(self):
        with mock.patch.dict(os.environ, {"SUDO_USER": "reimov"}), mock.patch.dict(
            sys.modules, {"PAM": None}
        ):
            with self.assertRaises(root_auth.AdminAuthError):
                root_auth.verify_confirming_password("anything")


if __name__ == "__main__":
    unittest.main()
