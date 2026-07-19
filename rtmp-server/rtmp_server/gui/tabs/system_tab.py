from __future__ import annotations

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QGridLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from rtmp_server.monitor import system_monitor


class SystemTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(2000)
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        grid = QGridLayout()

        self.cpu_bar = QProgressBar()
        self.mem_bar = QProgressBar()
        self.disk_bar = QProgressBar()
        grid.addWidget(QLabel("CPU:"), 0, 0)
        grid.addWidget(self.cpu_bar, 0, 1)
        grid.addWidget(QLabel("Память:"), 1, 0)
        grid.addWidget(self.mem_bar, 1, 1)
        grid.addWidget(QLabel("Диск:"), 2, 0)
        grid.addWidget(self.disk_bar, 2, 1)
        layout.addLayout(grid)

        self.load_label = QLabel()
        self.uptime_label = QLabel()
        layout.addWidget(self.load_label)
        layout.addWidget(self.uptime_label)

        self.ports_label = QLabel()
        self.ports_label.setWordWrap(True)
        layout.addWidget(QLabel("Порты сайта:"))
        layout.addWidget(self.ports_label)
        layout.addStretch()

    def refresh(self) -> None:
        stats = system_monitor.get_system_stats()
        self.cpu_bar.setValue(int(stats.cpu_percent))
        self.cpu_bar.setFormat(f"{stats.cpu_percent:.1f}% ({stats.cpu_count} ядер)")
        self.mem_bar.setValue(int(stats.memory_percent))
        self.mem_bar.setFormat(f"{stats.memory_percent:.1f}% ({stats.memory_used_mb}/{stats.memory_total_mb} МБ)")
        self.disk_bar.setValue(int(stats.disk_percent))
        self.disk_bar.setFormat(f"{stats.disk_percent:.1f}% ({stats.disk_used_gb}/{stats.disk_total_gb} ГБ)")

        self.load_label.setText(f"Load average: {stats.load_average}")
        hours = stats.uptime_seconds // 3600
        self.uptime_label.setText(f"Аптайм системы: {hours} ч")

        lines = []
        for port, info in system_monitor.get_listening_ports().items():
            mark = "✓" if info["listening"] else "✗"
            lines.append(f"{mark} :{port} — {info['label']}")
        self.ports_label.setText("\n".join(lines))
