from __future__ import annotations

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rtmp_server.gui.workers import WorkerThread
from rtmp_server.services.base import ServiceState
from rtmp_server.services.definitions import get_all_services, get_service

COLUMNS = ["Сервис", "Статус", "PID", "Порт", "Uptime", "Детали"]


class ServicesTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: WorkerThread | None = None
        self._build_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(3000)
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        buttons = QHBoxLayout()
        self.btn_start = QPushButton("Запустить")
        self.btn_stop = QPushButton("Остановить")
        self.btn_restart = QPushButton("Перезапустить")
        self.btn_refresh = QPushButton("Обновить")
        for btn, action in (
            (self.btn_start, "start"),
            (self.btn_stop, "stop"),
            (self.btn_restart, "restart"),
        ):
            btn.clicked.connect(lambda _checked, a=action: self._on_action(a))
            buttons.addWidget(btn)
        self.btn_refresh.clicked.connect(self.refresh)
        buttons.addWidget(self.btn_refresh)
        buttons.addStretch()
        layout.addLayout(buttons)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(self.table)

    def _selected_service_name(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _on_action(self, action: str) -> None:
        name = self._selected_service_name()
        if not name:
            QMessageBox.warning(self, "Сервис не выбран", "Выберите сервис в таблице")
            return

        def do_action():
            getattr(get_service(name), action)()
            return None

        self._worker = WorkerThread(do_action)
        self._worker.finished_ok.connect(lambda _r: self.refresh())
        self._worker.finished_error.connect(lambda err: QMessageBox.critical(self, "Ошибка", err))
        self._worker.start()

    def refresh(self) -> None:
        services = get_all_services()
        self.table.setRowCount(len(services))
        for row, svc in enumerate(services):
            status = svc.status()
            state_item = QTableWidgetItem(status.state.value)
            if status.state == ServiceState.RUNNING:
                state_item.setForeground(Qt.darkGreen)
            elif status.state == ServiceState.FAILED:
                state_item.setForeground(Qt.red)
            else:
                state_item.setForeground(Qt.gray)

            name_item = QTableWidgetItem(status.display_name)
            name_item.setData(Qt.UserRole, svc.name)

            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, state_item)
            self.table.setItem(row, 2, QTableWidgetItem(str(status.pid or "")))
            self.table.setItem(row, 3, QTableWidgetItem(str(status.port or "")))
            uptime = f"{status.uptime_seconds}s" if status.uptime_seconds is not None else ""
            self.table.setItem(row, 4, QTableWidgetItem(uptime))
            self.table.setItem(row, 5, QTableWidgetItem(status.detail))
