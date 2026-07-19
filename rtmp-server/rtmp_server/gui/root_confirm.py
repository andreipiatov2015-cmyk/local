"""Диалог подтверждения паролем root перед чувствительными действиями
(редактирование пользователей сайта, сброс пароля и т.п.) — см.
rtmp_server/site_admin/root_auth.py для того, почему это не про sudo/pkexec."""

from __future__ import annotations

from PyQt5.QtWidgets import QInputDialog, QLineEdit, QMessageBox, QWidget

from rtmp_server.site_admin.root_auth import RootAuthError, verify_root_password


def confirm_root_password(parent: QWidget, action_description: str) -> bool:
    password, ok = QInputDialog.getText(
        parent,
        "Подтверждение root",
        f"Введите пароль root, чтобы подтвердить: {action_description}",
        QLineEdit.Password,
    )
    if not ok:
        return False

    try:
        if verify_root_password(password):
            return True
    except RootAuthError as exc:
        QMessageBox.critical(parent, "Ошибка проверки пароля", str(exc))
        return False

    QMessageBox.warning(parent, "Неверный пароль", "Пароль root не подошёл, действие отменено")
    return False
