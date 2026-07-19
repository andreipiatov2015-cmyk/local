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

        btn_check = QPushButton("Проверить обновление приложения")
        btn_check.clicked.connect(self._on_check)
        layout.addWidget(btn_check)

        self.btn_apply = QPushButton("Установить обновление приложения")
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self._on_apply)
        layout.addWidget(self.btn_apply)

        layout.addWidget(QLabel(
            "<i>Обновление сайта штатно приходит автоматически через CI при пуше в main.\n"
            "Кнопка ниже — ручной запасной путь (например, для офлайн-доставки).</i>"
        ))
        btn_site_update = QPushButton("Обновить сайт из папки...")
        btn_site_update.clicked.connect(self._on_site_update)
        layout.addWidget(btn_site_update)

        self.site_status_label = QLabel()
        layout.addWidget(self.site_status_label)
        layout.addStretch()

        self._pending_release = None

    def _on_check(self) -> None:
        def do_check():
            return app_updater.check_for_update()

        worker = WorkerThread(do_check)
        worker.finished_ok.connect(self._on_check_done)
        worker.finished_error.connect(lambda err: QMessageBox.critical(self, "Ошибка", err))
        self._worker = worker
        worker.start()

    def _on_check_done(self, release) -> None:
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

        def do_apply():
            return app_updater.apply_update(self._pending_release)

        worker = WorkerThread(do_apply)
        worker.finished_ok.connect(lambda r: self.app_status_label.setText(r.message))
        worker.finished_error.connect(lambda err: QMessageBox.critical(self, "Ошибка", err))
        self._worker = worker
        worker.start()

    def _on_site_update(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Папка с новым кодом сайта (live-server/, reboot/)")
        if not directory:
            return

        def do_apply():
            source = site_updater.source_from_extracted_dir(Path(directory))
            return site_updater.apply(source)

        worker = WorkerThread(do_apply)
        worker.finished_ok.connect(lambda r: self.site_status_label.setText(r.message))
        worker.finished_error.connect(lambda err: QMessageBox.critical(self, "Ошибка", err))
        self._worker = worker
        worker.start()
