#!/bin/bash
#==============================================================================
# Astra Monitor - Главный установщик
# Полное развертывание сервера на чистой Astra Linux 1.8
#==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Проверка root
if [ "$EUID" -ne 0 ]; then 
    echo "Ошибка: требуются права суперпользователя"
    echo "Запустите: sudo bash install.sh"
    exit 1
fi

# Выбор режима
if [ "$1" == "--recovery" ] || [ "$1" == "-r" ]; then
    # Режим восстановления
    if [ -f "$SCRIPT_DIR/installer/recovery.sh" ]; then
        exec bash "$SCRIPT_DIR/installer/recovery.sh" "$@"
    else
        echo "Ошибка: installer/recovery.sh не найден"
        exit 1
    fi
elif [ "$1" == "--check" ]; then
    # Только проверка
    if [ -f "$SCRIPT_DIR/installer/recovery.sh" ]; then
        exec bash "$SCRIPT_DIR/installer/recovery.sh" --check "$@"
    else
        echo "Ошибка: installer/recovery.sh не найден"
        exit 1
    fi
else
    # Полная установка
    if [ -f "$SCRIPT_DIR/installer/main.sh" ]; then
        exec bash "$SCRIPT_DIR/installer/main.sh" "$@"
    else
        echo "Ошибка: installer/main.sh не найден"
        exit 1
    fi
fi
