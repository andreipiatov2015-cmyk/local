#!/bin/bash
# Astra Monitor - Установщик (только для локальных файлов)
# Не использует apt, не загружает из интернета
# Не трогает системные зависимости

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
PANEL_SOURCE="$SCRIPT_DIR/src"

# Проверка наличия файлов
if [ ! -d "$PANEL_SOURCE" ]; then
    echo "Ошибка: папка src не найдена в $SCRIPT_DIR"
    exit 1
fi

echo "[1/4] Проверка установленных компонентов..."

# Проверяем что НЕ переустанавливаем системные компоненты
echo "  * Nginx - пропуск (не изменяется)"
echo "  * FFmpeg - пропуск (не изменяется)"
echo "  * Chromium - пропуск (не изменяется)"

echo "[2/4] Создание директорий..."
mkdir -p "$INSTALL_DIR"
mkdir -p /usr/bin
mkdir -p /usr/share/applications

echo "[3/4] Копирование файлов приложения..."
# Копируем только файлы приложения (НЕ системные пакеты)
cp -r "$SCRIPT_DIR/src" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/astra_monitor.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/setup.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/README.md" "$INSTALL_DIR/" 2>/dev/null || true
cp "$SCRIPT_DIR/Makefile" "$INSTALL_DIR/" 2>/dev/null || true

# Создаем пакеты если есть
if [ -d "$SCRIPT_DIR/installer/packages" ]; then
    mkdir -p "$INSTALL_DIR/installer/packages"
    cp -r "$SCRIPT_DIR/installer/packages/"* "$INSTALL_DIR/installer/packages/" 2>/dev/null || true
fi

chmod +x "$INSTALL_DIR/astra_monitor.py"

echo "[4/4] Создание ссылок и ярлыков..."
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
update-desktop-database /usr/share/applications 2>/dev/null || true

echo ""
echo "========================================"
echo "  Установка завершена!"
echo "========================================"
echo ""
echo "Установленные компоненты:"
echo "  - Панель управления: $INSTALL_DIR"
echo "  - Команда: astra-monitor"
echo ""
echo "Системные компоненты НЕ изменены:"
echo "  - Nginx, FFmpeg, Chromium - сохранены как есть"
echo ""
echo "Запуск:"
echo "  astra-monitor"
echo ""
