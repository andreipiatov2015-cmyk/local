#!/bin/bash
# Скрипт установки Astra Monitor на Astra Linux

set -e

echo "========================================"
echo "  Astra Monitor - Установщик"
echo "========================================"
echo ""

# Проверка root
if [ "$EUID" -ne 0 ]; then 
    echo "Ошибка: требуются права суперпользователя"
    echo "Запустите: sudo bash install.sh"
    exit 1
fi

# Определение директории скрипта
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/astra-monitor"

# Проверка - сайт уже установлен?
SITE_INSTALLED=false
if [ -d "/var/www/live-server" ] && [ -f "/var/www/live-server/server.py" ]; then
    SITE_INSTALLED=true
    echo "✓ Обнаружен установленный сайт в /var/www"
fi

# Проверка - панель уже установлена?
PANEL_INSTALLED=false
if [ -f "/opt/astra-monitor/astra_monitor.py" ]; then
    PANEL_INSTALLED=true
    echo "✓ Панель управления уже установлена"
fi

echo ""

# Если сайт уже установлен - пропускаем установку зависимостей
if [ "$SITE_INSTALLED" = true ]; then
    echo "[*] Сайт уже установлен. Будут установлены только компоненты панели."
else
    echo "[1/6] Установка системных зависимостей..."
    apt update
    apt install -y python3-pip python3-pyqt5 python3-psutil python3-gi gir1.2-gtk-3.0
    
    echo "[2/6] Установка Python пакетов..."
    pip3 install --break-system-packages psutil requests 2>/dev/null || pip3 install --user psutil requests 2>/dev/null || true
fi

echo "[3/6] Создание директорий..."
mkdir -p "$INSTALL_DIR"
mkdir -p /usr/bin
mkdir -p /usr/share/applications

echo "[4/6] Копирование файлов панели..."
cp -r "$SCRIPT_DIR/src" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/astra_monitor.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/setup.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/README.md" "$INSTALL_DIR/" 2>/dev/null || true
chmod +x "$INSTALL_DIR/astra_monitor.py"

echo "[5/6] Создание ссылок и ярлыков..."
# Символическая ссылка
ln -sf "$INSTALL_DIR/astra_monitor.py" /usr/bin/astra-monitor

# Desktop файл
cat > /usr/share/applications/astra-monitor.desktop << 'DESKTOP'
[Desktop Entry]
Version=1.0
Type=Application
Name=Astra Monitor
GenericName=Панель управления сайтом
Comment=Управление сайтом и мониторинг для Astra Linux
Exec=/usr/bin/astra-monitor
Icon=computer
Terminal=false
Categories=System;Monitor;Networking;
Keywords=monitor;system;admin;astra;website;
StartupNotify=true
DESKTOP

chmod +x /usr/share/applications/astra-monitor.desktop

echo "[6/6] Обновление кэша рабочего стола..."
update-desktop-database /usr/share/applications 2>/dev/null || true

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
