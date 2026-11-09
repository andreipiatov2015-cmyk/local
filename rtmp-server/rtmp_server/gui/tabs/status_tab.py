"""Обзорная вкладка — сводка по сервисам и HTTP-health-check сайта.

Заменяет старую вкладку "Сайт", которая вызывала несуществующие методы
SiteMonitor (get_site_stats/check_http_services с другой сигнатурой) и
падала молча из-за except Exception. Здесь используется ровно один,
согласованный API (rtmp_server.monitor.site_monitor.check_site_health)."""

from __future__ import annotations

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from rtmp_server import __version__
from rtmp_server.monitor.site_monitor import check_site_health, check_site_layout
from rtmp_server.services.definitions import get_all_services
from rtmp_server.services.base import ServiceState
from rtmp_server.site_admin import stream_info


class StatusTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(5000)
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>RTMP-server {__version__}</b>"))

        self.summary_label = QLabel()
        layout.addWidget(self.summary_label)

        layout.addWidget(QLabel("<b>Компоненты сайта:</b>"))
        self.layout_label = QLabel()
        layout.addWidget(self.layout_label)

        layout.addWidget(QLabel("<b>HTTP health-check:</b>"))
        self.health_label = QLabel()
        layout.addWidget(self.health_label)

        layout.addWidget(QLabel(
            "<b>Что вставить в OBS</b> (Настройки → Трансляция → Пользовательский сервис):"
        ))

        server_row = QHBoxLayout()
        server_row.addWidget(QLabel("1. Сервер:"))
        self.obs_server_label = QLabel(stream_info.obs_server_url())
        self.obs_server_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        server_row.addWidget(self.obs_server_label, 1)
        btn_copy_server = QPushButton("Копировать")
        btn_copy_server.clicked.connect(lambda: QApplication.clipboard().setText(self.obs_server_label.text()))
        server_row.addWidget(btn_copy_server)
        layout.addLayout(server_row)

        key_row = QHBoxLayout()
        key_row.addWidget(QLabel("2. Ключ потока:"))
        self.obs_key_label = QLabel()
        self.obs_key_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        key_row.addWidget(self.obs_key_label, 1)
        btn_copy_key = QPushButton("Копировать")
        btn_copy_key.clicked.connect(lambda: QApplication.clipboard().setText(self.obs_key_label.text()))
        key_row.addWidget(btn_copy_key)
        layout.addLayout(key_row)

        obs_note = QLabel(
            "<i>Вставьте сначала «Сервер», затем «Ключ потока», и нажмите "
            "«Начать трансляцию» в OBS. Ключ меняется на вкладке «Трансляция».</i>"
        )
        obs_note.setWordWrap(True)
        layout.addWidget(obs_note)

        layout.addStretch()

    def refresh(self) -> None:
        services = get_all_services()
        running = sum(1 for s in services if s.status().state == ServiceState.RUNNING)
        self.summary_label.setText(f"Сервисы: {running}/{len(services)} запущено")

        layout_lines = []
        for component in check_site_layout():
            mark = "✓" if component.exists else "✗ ОТСУТСТВУЕТ"
            layout_lines.append(f"{mark}  {component.name} ({component.path})")
        self.layout_label.setText("\n".join(layout_lines))

        health_lines = []
        for status in check_site_health():
            mark = "✓" if status.reachable else "✗"
            detail = f"HTTP {status.http_status}" if status.reachable else (status.error or "недоступен")
            health_lines.append(f"{mark}  {status.name} — {detail}")
        self.health_label.setText("\n".join(health_lines))

        self.obs_key_label.setText(stream_info.get_stream_key())
