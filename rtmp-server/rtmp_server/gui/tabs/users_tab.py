"""Вкладка "Пользователи сайта" — CRUD напрямую поверх БД сайта
(rtmp_server.site_admin.users), с подтверждением root-паролем перед
любым изменяющим действием.

Пароли не хранятся/не показываются в открытом виде нигде в этом приложении —
только сброс на новый (см. site_admin/users.py — намеренное решение, не
пропущенная фича)."""

from __future__ import annotations

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rtmp_server.gui.root_confirm import confirm_root_password
from rtmp_server.gui.workers import WorkerThread
from rtmp_server.site_admin import users as site_users

COLUMNS = ["ID", "Логин", "ФИО", "Email", "Роль", "Подтверждён"]


class UserFormDialog(QDialog):
    def __init__(self, parent=None, *, username="", email="", full_name="", role="viewer", ask_password=True):
        super().__init__(parent)
        self.setWindowTitle("Пользователь сайта")
        self._ask_password = ask_password

        layout = QFormLayout(self)

        self.username_edit = QLineEdit(username)
        self.username_edit.setEnabled(not username)  # логин не меняем при редактировании
        layout.addRow("Логин:", self.username_edit)

        self.full_name_edit = QLineEdit(full_name)
        layout.addRow("ФИО:", self.full_name_edit)

        self.email_edit = QLineEdit(email)
        layout.addRow("Email:", self.email_edit)

        self.role_combo = QComboBox()
        self.role_combo.addItems(list(site_users.VALID_ROLES))
        self.role_combo.setCurrentText(role)
        layout.addRow("Роль:", self.role_combo)

        if ask_password:
            self.password_edit = QLineEdit()
            self.password_edit.setEchoMode(QLineEdit.Password)
            layout.addRow("Пароль:", self.password_edit)
        else:
            self.password_edit = None

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self) -> dict:
        return {
            "username": self.username_edit.text().strip(),
            "email": self.email_edit.text().strip(),
            "full_name": self.full_name_edit.text().strip(),
            "role": self.role_combo.currentText(),
            "password": self.password_edit.text() if self.password_edit else None,
        }


class ResetPasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Сброс пароля")
        layout = QFormLayout(self)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        layout.addRow("Новый пароль:", self.password_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def password(self) -> str:
        return self.password_edit.text()


class UsersTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: WorkerThread | None = None
        self._build_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(15000)
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        buttons = QHBoxLayout()
        self.btn_add = QPushButton("Добавить")
        self.btn_edit = QPushButton("Редактировать")
        self.btn_reset = QPushButton("Сбросить пароль")
        self.btn_delete = QPushButton("Удалить")
        self.btn_refresh = QPushButton("Обновить")
        self.btn_add.clicked.connect(self._on_add)
        self.btn_edit.clicked.connect(self._on_edit)
        self.btn_reset.clicked.connect(self._on_reset_password)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_refresh.clicked.connect(self.refresh)
        for btn in (self.btn_add, self.btn_edit, self.btn_reset, self.btn_delete, self.btn_refresh):
            buttons.addWidget(btn)
        buttons.addStretch()
        layout.addLayout(buttons)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(self.table)

    def _selected_user_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.text()) if item else None

    def refresh(self) -> None:
        def do_list():
            return site_users.list_users()

        worker = WorkerThread(do_list)
        worker.finished_ok.connect(self._populate)
        worker.finished_error.connect(lambda err: QMessageBox.critical(self, "Ошибка", err))
        self._worker = worker
        worker.start()

    def _populate(self, users_list) -> None:
        self.table.setRowCount(len(users_list))
        for row, user in enumerate(users_list):
            self.table.setItem(row, 0, QTableWidgetItem(str(user.id)))
            self.table.setItem(row, 1, QTableWidgetItem(user.username))
            self.table.setItem(row, 2, QTableWidgetItem(user.full_name or ""))
            self.table.setItem(row, 3, QTableWidgetItem(user.email))
            self.table.setItem(row, 4, QTableWidgetItem(user.role))
            self.table.setItem(row, 5, QTableWidgetItem("да" if user.is_verified else "нет"))

    def _run_mutation(self, fn, on_done_message: str) -> None:
        worker = WorkerThread(fn)
        worker.finished_ok.connect(lambda _r: (self.refresh(), QMessageBox.information(self, "Готово", on_done_message)))
        worker.finished_error.connect(lambda err: QMessageBox.critical(self, "Ошибка", err))
        self._worker = worker
        worker.start()

    def _on_add(self) -> None:
        if not confirm_root_password(self, "добавление нового пользователя сайта"):
            return
        dialog = UserFormDialog(self, ask_password=True)
        if dialog.exec_() != QDialog.Accepted:
            return
        values = dialog.values()
        if not values["username"] or not values["email"] or not values["password"]:
            QMessageBox.warning(self, "Не заполнено", "Логин, email и пароль обязательны")
            return

        def do_create():
            return site_users.create_user(
                values["username"], values["email"], values["password"],
                full_name=values["full_name"], role=values["role"],
            )

        self._run_mutation(do_create, f"Пользователь {values['username']} создан")

    def _on_edit(self) -> None:
        user_id = self._selected_user_id()
        if user_id is None:
            QMessageBox.warning(self, "Пользователь не выбран", "Выберите строку в таблице")
            return
        if not confirm_root_password(self, f"редактирование пользователя id={user_id}"):
            return

        user = site_users.get_user(user_id)
        dialog = UserFormDialog(
            self, username=user.username, email=user.email,
            full_name=user.full_name or "", role=user.role, ask_password=False,
        )
        if dialog.exec_() != QDialog.Accepted:
            return
        values = dialog.values()

        def do_update():
            site_users.update_user(user_id, email=values["email"], full_name=values["full_name"], role=values["role"])
            return None

        self._run_mutation(do_update, f"Пользователь id={user_id} обновлён")

    def _on_reset_password(self) -> None:
        user_id = self._selected_user_id()
        if user_id is None:
            QMessageBox.warning(self, "Пользователь не выбран", "Выберите строку в таблице")
            return
        if not confirm_root_password(self, f"сброс пароля пользователя id={user_id}"):
            return

        dialog = ResetPasswordDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return
        new_password = dialog.password()
        if not new_password:
            QMessageBox.warning(self, "Пустой пароль", "Новый пароль не может быть пустым")
            return

        def do_reset():
            site_users.reset_password(user_id, new_password)
            return None

        self._run_mutation(do_reset, f"Пароль пользователя id={user_id} сброшен")

    def _on_delete(self) -> None:
        user_id = self._selected_user_id()
        if user_id is None:
            QMessageBox.warning(self, "Пользователь не выбран", "Выберите строку в таблице")
            return
        if not confirm_root_password(self, f"удаление пользователя id={user_id}"):
            return
        if QMessageBox.question(self, "Удалить?", f"Точно удалить пользователя id={user_id}?") != QMessageBox.Yes:
            return

        def do_delete():
            site_users.delete_user(user_id)
            return None

        self._run_mutation(do_delete, f"Пользователь id={user_id} удалён")
