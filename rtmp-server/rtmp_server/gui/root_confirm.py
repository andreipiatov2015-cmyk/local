"""Диалог подтверждения паролем перед чувствительными действиями
(редактирование пользователей сайта, сброс пароля и т.п.) — см.
rtmp_server/site_admin/root_auth.py про то, чьим именно паролем и почему."""

from __future__ import annotations

from PyQt5.QtWidgets import QInputDialog, QLineEdit, QMessageBox, QWidget

from rtmp_server.site_admin.root_auth import (
    AdminAuthError,
    confirming_username,
    verify_confirming_password,
)


def confirm_root_password(parent: QWidget, action_description: str) -> bool:
    username = confirming_username()
    password, ok = QInputDialog.getText(
        parent,
        "Подтверждение действия",
        f"Введите пароль пользователя {username}, чтобы подтвердить: {action_description}",
        QLineEdit.Password,
    )
    if not ok:
        return False

    try:
        if verify_confirming_password(password):
            return True
    except AdminAuthError as exc:
        QMessageBox.critical(parent, "Ошибка проверки пароля", str(exc))
        return False

    QMessageBox.warning(
        parent, "Неверный пароль", f"Пароль пользователя {username} не подошёл, действие отменено"
    )
    return False
