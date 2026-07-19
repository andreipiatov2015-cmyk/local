from __future__ import annotations

from PyQt5.QtWidgets import QMainWindow, QTabWidget

from rtmp_server import __version__
from rtmp_server.gui.tabs.services_tab import ServicesTab
from rtmp_server.gui.tabs.status_tab import StatusTab
from rtmp_server.gui.tabs.system_tab import SystemTab
from rtmp_server.gui.tabs.updates_tab import UpdatesTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"RTMP-server {__version__}")
        self.resize(900, 600)

        tabs = QTabWidget()
        tabs.addTab(StatusTab(), "Обзор")
        tabs.addTab(ServicesTab(), "Сервисы")
        tabs.addTab(SystemTab(), "Система")
        tabs.addTab(UpdatesTab(), "Обновления")
        self.setCentralWidget(tabs)


def main() -> int:
    import sys

    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    import sys

    sys.exit(main())
