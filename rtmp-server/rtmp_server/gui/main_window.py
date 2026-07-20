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
        self.resize(900, 600)

        tabs = QTabWidget()
        tabs.addTab(StatusTab(), "Обзор")
        tabs.addTab(ServicesTab(), "Сервисы")
        tabs.addTab(SystemTab(), "Система")
        tabs.addTab(UsersTab(), "Пользователи сайта")
        tabs.addTab(StreamTab(), "Трансляция")
        tabs.addTab(UpdatesTab(), "Обновления")
        self.setCentralWidget(tabs)


def main() -> int:
    import sys

    from PyQt5.QtWidgets import QApplication, QMessageBox

    from rtmp_server.gui import single_instance

    app = QApplication(sys.argv)

    if not single_instance.acquire_or_none():
        QMessageBox.information(
            None, "RTMP-server уже запущен",
            "RTMP-server уже открыт (автозапуск при старте сервера или другой ярлык).",
        )
        return 0

    try:
        window = MainWindow()
        window.show()
        return app.exec_()
    finally:
        single_instance.release()


if __name__ == "__main__":
    import sys

    sys.exit(main())
