#!/bin/bash
#==============================================================================
# Astra Monitor - Установка Python зависимостей
#==============================================================================

set -e

VENV_PATH="/var/www/.venv"

if [ "$EUID" -ne 0 ]; then
    echo "Требуются права root"
    exit 1
fi

echo "Установка Python зависимостей..."

# Создание виртуального окружения
echo "Создание виртуального окружения..."
mkdir -p /var/www
python3 -m venv "$VENV_PATH"

# Активация
source "$VENV_PATH/bin/activate"

# Обновление pip
echo "Обновление pip..."
pip install --upgrade pip

# Установка пакетов
echo "Установка Python пакетов..."
pip install \
    flask \
    flask-cors \
    requests \
    openpyxl \
    pandas \
    schedule \
    pillow \
    websockets \
    gunicorn \
    waitress

deactivate

echo ""
echo "Python зависимости установлены в $VENV_PATH"