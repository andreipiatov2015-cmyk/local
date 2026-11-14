"""Тест rtmp_server/site_admin/root_auth.py.

По прямому запросу владельца: раньше чувствительные действия в программе
всегда подтверждались паролем root, что на практике неудобно и небезопасно
— пароль root меняется отдельной (и не всегда объявленной) организационной
политикой, независимо от личных паролей сотрудников. Теперь подтверждение
идёт паролем того пользователя ОС, который запустил приложение через sudo
(SUDO_USER), а не обязательно root."""

from __future__ import annotations

import crypt
import os
import unittest
from unittest import mock

from rtmp_server.site_admin import root_auth


def _shadow_line(username: str, password: str) -> str:
    salt = crypt.mksalt(crypt.METHOD_SHA512)
    shadow_hash = crypt.crypt(password, salt)
    return f"{username}:{shadow_hash}:19000:0:99999:7:::\n"


class ConfirmingUsernameTests(unittest.TestCase):
    def test_uses_sudo_user_when_set(self):
        with mock.patch.dict(os.environ, {"SUDO_USER": "reimov"}):
            self.assertEqual(root_auth.confirming_username(), "reimov")

    def test_falls_back_to_root_without_sudo_user(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SUDO_USER", None)
            self.assertEqual(root_auth.confirming_username(), "root")


class VerifyConfirmingPasswordTests(unittest.TestCase):
    def _with_shadow(self, content: str):
        tmp = mock.mock_open(read_data=content)
        return mock.patch("builtins.open", tmp)

    def test_correct_password_for_sudo_user_passes(self):
        shadow = _shadow_line("reimov", "s3cret") + _shadow_line("root", "other")
        with mock.patch.dict(os.environ, {"SUDO_USER": "reimov"}), self._with_shadow(shadow):
            self.assertTrue(root_auth.verify_confirming_password("s3cret"))

    def test_root_password_no_longer_accepted_for_sudo_user(self):
        """Регрессия, которую и просили исправить: когда пользователь
        запущен через sudo, ввод пароля ROOT не должен подтверждать
        действие — должен подойти только пароль самого этого пользователя."""
        shadow = _shadow_line("reimov", "s3cret") + _shadow_line("root", "rootpass")
        with mock.patch.dict(os.environ, {"SUDO_USER": "reimov"}), self._with_shadow(shadow):
            self.assertFalse(root_auth.verify_confirming_password("rootpass"))

    def test_wrong_password_rejected(self):
        shadow = _shadow_line("reimov", "s3cret")
        with mock.patch.dict(os.environ, {"SUDO_USER": "reimov"}), self._with_shadow(shadow):
            self.assertFalse(root_auth.verify_confirming_password("wrong"))

    def test_empty_password_rejected_without_reading_shadow(self):
        with mock.patch.dict(os.environ, {"SUDO_USER": "reimov"}):
            self.assertFalse(root_auth.verify_confirming_password(""))

    def test_falls_back_to_root_without_sudo_user(self):
        shadow = _shadow_line("root", "rootpass")
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SUDO_USER", None)
            with self._with_shadow(shadow):
                self.assertTrue(root_auth.verify_confirming_password("rootpass"))

    def test_locked_account_rejected(self):
        shadow = "reimov:!:19000:0:99999:7:::\n"
        with mock.patch.dict(os.environ, {"SUDO_USER": "reimov"}), self._with_shadow(shadow):
            self.assertFalse(root_auth.verify_confirming_password("anything"))

    def test_missing_user_raises(self):
        shadow = _shadow_line("someoneelse", "x")
        with mock.patch.dict(os.environ, {"SUDO_USER": "reimov"}), self._with_shadow(shadow):
            with self.assertRaises(root_auth.AdminAuthError):
                root_auth.verify_confirming_password("anything")

    def test_permission_error_raises_admin_auth_error(self):
        with mock.patch.dict(os.environ, {"SUDO_USER": "reimov"}), mock.patch(
            "builtins.open", side_effect=PermissionError
        ):
            with self.assertRaises(root_auth.AdminAuthError):
                root_auth.verify_confirming_password("anything")


if __name__ == "__main__":
    unittest.main()
