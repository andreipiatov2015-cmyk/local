"""QThread-обёртка для действий, которые не должны блокировать GUI-поток
(старт/стоп сервисов, обновления). Опрос статуса (быстрые systemctl/psutil
вызовы) выполняется напрямую по QTimer — как и в старом приложении, это
не блокирует UI на заметное время."""

from __future__ import annotations

from typing import Callable

from PyQt5.QtCore import QThread, pyqtSignal


class WorkerThread(QThread):
    finished_ok = pyqtSignal(object)
    finished_error = pyqtSignal(str)

    def __init__(self, fn: Callable[[], object], parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:  # noqa: BLE001 — граница потока, показываем в GUI
            self.finished_error.emit(str(exc))
        else:
            self.finished_ok.emit(result)
