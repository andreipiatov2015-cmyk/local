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
        # Пока не поднят трей (main() ниже решает, доступен ли он на этой
        # системе) — закрытие окна работает как обычно, то есть завершает
        # приложение. Если трей поднят, main() переключит это в False, и
        # закрытие окна будет сворачивать в трей, а не выходить.
        self.allow_close = True

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.addTab(StatusTab(), "Обзор")
        tabs.addTab(ServicesTab(), "Сервисы")
        tabs.addTab(SystemTab(), "Система")
        tabs.addTab(UsersTab(), "Пользователи сайта")
        tabs.addTab(StreamTab(), "Трансляция")
        tabs.addTab(UpdatesTab(), "Обновления")
        self.setCentralWidget(tabs)

    def closeEvent(self, event):
        if self.allow_close:
            event.accept()
            return
        # Крестик окна сворачивает в трей, а не завершает процесс —
        # приложение управляет остальными сервисами сайта и должно быть
        # под рукой постоянно, как значок громкости или сети. Настоящий
        # выход — только через пункт "Выход" в меню значка трея.
        event.ignore()
        self.hide()


def _build_tray_icon(app, window: MainWindow):
    from PyQt5.QtGui import QIcon
    from PyQt5.QtWidgets import QMenu, QStyle, QSystemTrayIcon

    if not QSystemTrayIcon.isSystemTrayAvailable():
        return None

    icon = QIcon.fromTheme("utilities-system-monitor")
    if icon.isNull():
        icon = app.style().standardIcon(QStyle.SP_ComputerIcon)

    tray = QSystemTrayIcon(icon, app)
    tray.setToolTip(f"RTMP-server {__version__}")

    def show_window():
        window.show()
        window.raise_()
        window.activateWindow()

    def quit_app():
        window.allow_close = True
        app.quit()

    menu = QMenu()
    menu.addAction("Открыть RTMP-server", show_window)
    menu.addSeparator()
    menu.addAction("Выход", quit_app)
    tray.setContextMenu(menu)

    def on_activated(reason):
        if reason not in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            return
        if window.isVisible():
            window.hide()
        else:
            show_window()

    tray.activated.connect(on_activated)
    tray.show()
    return tray


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

        tray = _build_tray_icon(app, window)
        if tray is not None:
            app.setQuitOnLastWindowClosed(False)
            window.allow_close = False

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
