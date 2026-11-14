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
(воспроизведено вживую на реальном сервере). Модуль pam (pip-пакет
python-pam, НЕ apt-пакет python3-pam — его не оказалось в репозиториях
Astra Linux, воспроизведено вживую) импортируется лениво, поэтому в тестах
подставляем поддельный через sys.modules."""

from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

from rtmp_server.site_admin import root_auth


class _FakePamModule:
    """Имитирует pip-пакет python-pam: модуль с одной функцией
    authenticate(username, password, service=...) -> bool."""

    def __init__(self, *, expected_username, correct_password, raises=None):
        self.expected_username = expected_username
        self.correct_password = correct_password
        self.raises = raises
        self.calls = []

    def authenticate(self, username, password, service="login"):
        self.calls.append((username, password, service))
        if self.raises is not None:
            raise self.raises
        return username == self.expected_username and password == self.correct_password


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
        return fake_module, mock.patch.dict(sys.modules, {"pam": fake_module})

    def test_correct_password_for_sudo_user_passes(self):
        fake, patcher = self._with_fake_pam(expected_username="reimov", correct_password="s3cret")
        with mock.patch.dict(os.environ, {"SUDO_USER": "reimov"}), patcher:
            self.assertTrue(root_auth.verify_confirming_password("s3cret"))
        self.assertEqual(fake.calls, [("reimov", "s3cret", root_auth.PAM_SERVICE)])

    def test_root_password_no_longer_accepted_for_sudo_user(self):
        """Регрессия, которую и просили исправить: когда пользователь
        запущен через sudo, ввод пароля ROOT не должен подтверждать
        действие — должен подойти только пароль самого этого пользователя."""
        _, patcher = self._with_fake_pam(expected_username="reimov", correct_password="s3cret")
        with mock.patch.dict(os.environ, {"SUDO_USER": "reimov"}), patcher:
            self.assertFalse(root_auth.verify_confirming_password("rootpass"))

    def test_wrong_password_rejected(self):
        _, patcher = self._with_fake_pam(expected_username="reimov", correct_password="s3cret")
        with mock.patch.dict(os.environ, {"SUDO_USER": "reimov"}), patcher:
            self.assertFalse(root_auth.verify_confirming_password("wrong"))

    def test_empty_password_rejected_without_calling_pam(self):
        with mock.patch.dict(os.environ, {"SUDO_USER": "reimov"}):
            self.assertFalse(root_auth.verify_confirming_password(""))

    def test_falls_back_to_root_without_sudo_user(self):
        _, patcher = self._with_fake_pam(expected_username="root", correct_password="rootpass")
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SUDO_USER", None)
            with patcher:
                self.assertTrue(root_auth.verify_confirming_password("rootpass"))

    def test_pam_exception_raises_admin_auth_error(self):
        _, patcher = self._with_fake_pam(
            expected_username="reimov",
            correct_password="s3cret",
            raises=OSError("libpam.so.0: cannot open shared object file"),
        )
        with mock.patch.dict(os.environ, {"SUDO_USER": "reimov"}), patcher:
            with self.assertRaises(root_auth.AdminAuthError):
                root_auth.verify_confirming_password("s3cret")

    def test_missing_pam_module_raises_admin_auth_error(self):
        with mock.patch.dict(os.environ, {"SUDO_USER": "reimov"}), mock.patch.dict(
            sys.modules, {"pam": None}
        ):
            with self.assertRaises(root_auth.AdminAuthError):
                root_auth.verify_confirming_password("anything")


if __name__ == "__main__":
    unittest.main()
