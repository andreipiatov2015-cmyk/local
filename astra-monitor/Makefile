# Makefile для Astra Monitor

.PHONY: all install uninstall clean test run deps debian

# Переменные
INSTALL_DIR = /opt/astra-monitor
BIN_LINK = /usr/bin/astra-monitor
DESKTOP_FILE = /usr/share/applications/astra-monitor.desktop

all: test
	@echo "Для установки запустите: sudo make install"

install:
	@echo "Установка Astra Monitor..."
	@if [ "$$(id -u)" -ne 0 ]; then \
		echo "Ошибка: требуются права root"; \
		echo "Запустите: sudo make install"; \
		exit 1; \
	fi
	@mkdir -p $(INSTALL_DIR)
	@cp -r src astra_monitor.py setup.py $(INSTALL_DIR)/
	@chmod +x $(INSTALL_DIR)/astra_monitor.py
	@ln -sf $(INSTALL_DIR)/astra_monitor.py $(BIN_LINK)
	@echo '[Desktop Entry]
Version=1.0
Type=Application
Name=Astra Monitor
Comment=Система мониторинга и управления сайтом
Exec=/usr/bin/astra-monitor
Icon=computer
Terminal=false
Categories=System;Monitor;
Keywords=monitor;system;admin;astra;
' > $(DESKTOP_FILE)
	@chmod +x $(DESKTOP_FILE)
	@echo "Установка завершена!"
	@echo "Запуск: astra-monitor"

uninstall:
	@echo "Удаление Astra Monitor..."
	@if [ "$$(id -u)" -ne 0 ]; then \
		echo "Ошибка: требуются права root"; \
		exit 1; \
	fi
	@rm -rf $(INSTALL_DIR)
	@rm -f $(BIN_LINK)
	@rm -f $(DESKTOP_FILE)
	@echo "Astra Monitor удалён"

deps:
	@echo "Установка зависимостей..."
	@apt update
	@apt install -y python3-pip python3-pyqt5 python3-psutil python3-gi
	@pip3 install --break-system-packages psutil requests
	@echo "Зависимости установлены"

run:
	@python3 astra_monitor.py

test:
	@echo "Проверка синтаксиса..."
	@python3 -m py_compile astra_monitor.py
	@python3 -m py_compile src/core/system_monitor.py
	@python3 -m py_compile src/core/site_monitor.py
	@python3 -m py_compile src/core/git_updater.py
	@python3 -m py_compile src/gui/main_window.py
	@echo "Проверка зависимостей..."
	@python3 -c "import PyQt5; print('  PyQt5: OK')"
	@python3 -c "import psutil; print('  psutil: OK')"
	@python3 -c "import requests; print('  requests: OK')"
	@echo "Все проверки пройдены!"

clean:
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Очистка завершена"

debian:
	@echo "Сборка deb-пакета..."
	@mkdir -p debian-package/DEBIAN
	@mkdir -p debian-package/usr/bin
	@mkdir -p debian-package/usr/share/applications
	@mkdir -p debian-package/opt/astra-monitor
	@cp -r src astra_monitor.py setup.py debian-package/opt/astra-monitor/
	@echo '#!/bin/bash' > debian-package/usr/bin/astra-monitor
	@echo 'exec python3 /opt/astra-monitor/astra_monitor.py' >> debian-package/usr/bin/astra-monitor
	@chmod +x debian-package/usr/bin/astra-monitor
	@cp debian/control debian-package/DEBIAN/
	@echo '[Desktop Entry]
Version=1.0
Type=Application
Name=Astra Monitor
Exec=/usr/bin/astra-monitor
Icon=computer
Categories=System;Monitor;
' > debian-package/usr/share/applications/astra-monitor.desktop
	@dpkg-deb --build debian-package astra-monitor.deb
	@echo "Пакет создан: astra-monitor.deb"

help:
	@echo "Astra Monitor - Makefile"
	@echo ""
	@echo "Цели:"
	@echo "  make install    - Установить приложение"
	@echo "  make uninstall  - Удалить приложение"
	@echo "  make deps       - Установить зависимости"
	@echo "  make run        - Запустить приложение"
	@echo "  make test       - Проверить код и зависимости"
	@echo "  make clean      - Очистить временные файлы"
	@echo "  make debian     - Собрать deb-пакет"
	@echo "  make help       - Показать эту справку"