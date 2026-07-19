"""Обзорная вкладка — сводка по сервисам и HTTP-health-check сайта.

Заменяет старую вкладку "Сайт", которая вызывала несуществующие методы
SiteMonitor (get_site_stats/check_http_services с другой сигнатурой) и
падала молча из-за except Exception. Здесь используется ровно один,
согласованный API (rtmp_server.monitor.site_monitor.check_site_health)."""

from __future__ import annotations

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget

from rtmp_server import __version__
from rtmp_server.monitor.site_monitor import check_site_health, check_site_layout
from rtmp_server.services.definitions import get_all_services
from rtmp_server.services.base import ServiceState


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
