"""Вкладка обновлений — сам движок в rtmp_server.updates (staging.py +
app_updater.py + site_updater.py), здесь только UI поверх него.

Обновление сайта штатно приходит через CI (.github/workflows/deploy.yml
вызывает `rtmp-server-ctl site-update apply`) — кнопка здесь нужна как
ручной/офлайн запасной путь, а не основной."""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtWidgets import (
    QFileDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rtmp_server import __version__
from rtmp_server.gui.workers import WorkerThread
from rtmp_server.updates import app_updater, site_updater


class UpdatesTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: WorkerThread | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"<b>Текущая версия RTMP-server: {__version__}</b>"))

        self.app_status_label = QLabel("Статус: не проверялось")
        layout.addWidget(self.app_status_label)

        self.btn_check = QPushButton("Проверить обновление приложения")
        self.btn_check.clicked.connect(self._on_check)
        layout.addWidget(self.btn_check)

        self.btn_apply = QPushButton("Установить обновление приложения")
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self._on_apply)
        layout.addWidget(self.btn_apply)

        layout.addWidget(QLabel(
            "<i>Обновление сайта штатно приходит автоматически через CI при пуше в main.\n"
            "Кнопка ниже — ручной запасной путь (например, для офлайн-доставки).</i>"
        ))
        self.btn_site_update = QPushButton("Обновить сайт из папки...")
        self.btn_site_update.clicked.connect(self._on_site_update)
        layout.addWidget(self.btn_site_update)

        self.site_status_label = QLabel()
        layout.addWidget(self.site_status_label)
        layout.addStretch()

        self._pending_release = None

    def _set_busy(self, *buttons: QPushButton, busy: bool) -> None:
        for btn in buttons:
            btn.setEnabled(not busy)

    def _on_check(self) -> None:
        self.app_status_label.setText("Проверяю GitHub на наличие обновления...")
        self._set_busy(self.btn_check, self.btn_apply, busy=True)

        def do_check():
            return app_updater.check_for_update()

        worker = WorkerThread(do_check)
        worker.finished_ok.connect(self._on_check_done)
        worker.finished_error.connect(self._on_check_error)
        self._worker = worker
        worker.start()

    def _on_check_error(self, err: str) -> None:
        self._set_busy(self.btn_check, self.btn_apply, busy=False)
        self.app_status_label.setText("Проверка не удалась — см. сообщение об ошибке")
        QMessageBox.critical(self, "Ошибка", err)

    def _on_check_done(self, release) -> None:
        self._set_busy(self.btn_check, busy=False)
        self._pending_release = release
        if release is None:
            self.app_status_label.setText(f"Установлена актуальная версия ({__version__})")
            self.btn_apply.setEnabled(False)
        else:
            self.app_status_label.setText(f"Доступна новая версия: {release.version}")
            self.btn_apply.setEnabled(True)

    def _on_apply(self) -> None:
        if self._pending_release is None:
            return
        confirm = QMessageBox.question(
            self, "Обновление", f"Установить версию {self._pending_release.version}?"
        )
        if confirm != QMessageBox.Yes:
            return

        # Сразу видимая обратная связь — раньше после клика ничего не
        # менялось на экране до самого завершения (иногда — минуты), и
        # выглядело так, будто кнопка вообще не сработала.
        self.app_status_label.setText(
            f"Скачивание и установка версии {self._pending_release.version}... "
            "это может занять до пары минут, окно не зависло."
        )
        self._set_busy(self.btn_check, self.btn_apply, busy=True)

        def do_apply():
            return app_updater.apply_update(self._pending_release)

        worker = WorkerThread(do_apply)
        worker.finished_ok.connect(self._on_apply_done)
        worker.finished_error.connect(self._on_apply_error)
        self._worker = worker
        worker.start()

    def _on_apply_done(self, result) -> None:
        self._set_busy(self.btn_check, self.btn_apply, busy=False)
        self.app_status_label.setText(result.message)
        if not result.applied:
            QMessageBox.warning(self, "Обновление не применено", result.message)

    def _on_apply_error(self, err: str) -> None:
        self._set_busy(self.btn_check, self.btn_apply, busy=False)
        self.app_status_label.setText("Установка не удалась — см. сообщение об ошибке")
        QMessageBox.critical(self, "Ошибка", err)

    def _on_site_update(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Папка с новым кодом сайта (live-server/, reboot/)")
        if not directory:
            return

        self.site_status_label.setText("Применяю обновление сайта...")
        self._set_busy(self.btn_site_update, busy=True)

        def do_apply():
            source = site_updater.source_from_extracted_dir(Path(directory))
            return site_updater.apply(source)

        def on_done(result):
            self._set_busy(self.btn_site_update, busy=False)
            self.site_status_label.setText(result.message)

        def on_error(err):
            self._set_busy(self.btn_site_update, busy=False)
            self.site_status_label.setText("Обновление сайта не удалось — см. сообщение об ошибке")
            QMessageBox.critical(self, "Ошибка", err)

        worker = WorkerThread(do_apply)
        worker.finished_ok.connect(on_done)
        worker.finished_error.connect(on_error)
        self._worker = worker
        worker.start()
