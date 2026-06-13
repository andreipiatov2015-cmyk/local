#!/bin/bash
# Скрипт удаления Astra Monitor

set -e

echo "========================================"
echo "  Astra Monitor - Удаление"
echo "========================================"
echo ""

# Проверка root
if [ "$EUID" -ne 0" ]; then 
    echo "Ошибка: требуются права суперпользователя"
    echo "Запустите: sudo bash uninstall.sh"
    exit 1
fi

INSTALL_DIR="/opt/astra-monitor"

echo "Удаление Astra Monitor..."

# Удаление файлов
rm -rf "$INSTALL_DIR"
rm -f /usr/bin/astra-monitor
rm -f /usr/share/applications/astra-monitor.desktop

# Обновление кэша рабочего стола
update-desktop-database /usr/share/applications 2>/dev/null || true

echo ""
echo "========================================"
echo "  Astra Monitor удалён!"
echo "========================================"