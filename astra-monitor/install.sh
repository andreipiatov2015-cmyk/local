#!/bin/bash
# Скрипт установки Astra Monitor на Astra Linux

set -e

echo "========================================"
echo "  Astra Monitor - Установщик"
echo "========================================"
echo ""

# Проверка root
if [ "$EUID" -ne 0" ]; then 
    echo "Ошибка: требуются права суперпользователя"
    echo "Запустите: sudo bash install.sh"
    exit 1
fi

# Определение директории
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/astra-monitor"

echo "[1/5] Установка системных зависимостей..."
apt update
apt install -y python3-pip python3-pyqt5 python3-psutil python3-gi gir1.2-gtk-3.0

echo "[2/5] Установка Python пакетов..."
pip3 install --break-system-packages psutil requests

echo "[3/5] Создание директорий..."
mkdir -p "$INSTALL_DIR"
mkdir -p /usr/bin
mkdir -p /usr/share/applications

echo "[4/5] Копирование файлов..."
cp -r "$SCRIPT_DIR/src" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/astra_monitor.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/setup.py" "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/astra_monitor.py"

echo "[5/5] Создание ссылок и ярлыков..."
# Символическая ссылка
ln -sf "$INSTALL_DIR/astra_monitor.py" /usr/bin/astra-monitor

# Desktop файл
cat > /usr/share/applications/astra-monitor.desktop << 'DESKTOP'
[Desktop Entry]
Version=1.0
Type=Application
Name=Astra Monitor
GenericName=Система мониторинга
Comment=Управление сайтом и мониторинг для Astra Linux
Exec=/usr/bin/astra-monitor
Icon=computer
Terminal=false
Categories=System;Monitor;Networking;
Keywords=monitor;system;admin;astra;website;
StartupNotify=true
DESKTOP

chmod +x /usr/share/applications/astra-monitor.desktop

echo ""
echo "========================================"
echo "  Установка завершена!"
echo "========================================"
echo ""
echo "Запуск приложения:"
echo "  astra-monitor"
echo ""
echo "Или через меню: Приложения → Система → Astra Monitor"
echo ""