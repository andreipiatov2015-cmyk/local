from __future__ import annotations

from PyQt5.QtWidgets import QMainWindow, QTabWidget

from rtmp_server import __version__
from rtmp_server.gui.tabs.services_tab import ServicesTab
from rtmp_server.gui.tabs.status_tab import StatusTab
from rtmp_server.gui.tabs.stream_tab import StreamTab
from rtmp_server.gui.tabs.system_tab import SystemTab
from rtmp_server.gui.tabs.updates_tab import UpdatesTab
from rtmp_server.gui.tabs.users_tab import UsersTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"RTMP-server {__version__}")
        self.resize(1100, 700)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.addTab(StatusTab(), "Обзор")
        tabs.addTab(ServicesTab(), "Сервисы")
        tabs.addTab(SystemTab(), "Система")
        tabs.addTab(UsersTab(), "Пользователи сайта")
        tabs.addTab(StreamTab(), "Трансляция")
        tabs.addTab(UpdatesTab(), "Обновления")
        self.setCentralWidget(tabs)


def main() -> int:
    import sys

    from PyQt5.QtCore import QTimer
    from PyQt5.QtWidgets import QApplication, QMessageBox

    from rtmp_server.gui import single_instance, theme, watchdog

    app = QApplication(sys.argv)
    theme.apply(app)

    if not single_instance.acquire_or_none():
        # Сообщаем systemd "готов" даже в этой ветке — иначе с Type=notify
        # юнит будет ждать READY=1 до TimeoutStartSec, хотя процесс уже
        # собирается штатно завершиться (оказалось, что он не первый).
        watchdog.notify_ready()
        QMessageBox.information(
            None, "RTMP-server уже запущен",
            "RTMP-server уже открыт (автозапуск при старте сервера или другой ярлык).",
        )
        return 0

    try:
        window = MainWindow()
        window.show()
        watchdog.notify_ready()

        interval_ms = watchdog.watchdog_interval_ms()
        if interval_ms is not None:
            watchdog_timer = QTimer(window)
            watchdog_timer.timeout.connect(watchdog.notify_watchdog)
            watchdog_timer.start(interval_ms)

        return app.exec_()
    finally:
        single_instance.release()


if __name__ == "__main__":
    import sys

    sys.exit(main())
