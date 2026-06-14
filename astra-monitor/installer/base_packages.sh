#!/bin/bash
#==============================================================================
# Astra Monitor - Установка базовых пакетов
#==============================================================================

set -e

if [ "$EUID" -ne 0 ]; then
    echo "Требуются права root"
    exit 1
fi

echo "Установка базовых пакетов..."

apt update

# Проверка существования пакета
check_package() {
    apt-cache show "$1" >/dev/null 2>&1
}

# Сборка пакетов для установки
PACKAGES=(
    python3
    python3-pip
    python3-venv
    git
    curl
    wget
    unzip
    build-essential
    libpcre3
    libpcre3-dev
    zlib1g
    zlib1g-dev
    libssl-dev
    autoconf
    automake
    libtool
    pkg-config
    ffmpeg
    htop
    net-tools
)

# Установка только существующих пакетов
INSTALL_LIST=""
for pkg in "${PACKAGES[@]}"; do
    if check_package "$pkg"; then
        INSTALL_LIST="$INSTALL_LIST $pkg"
    else
        echo "Пропуск: $pkg не найден в репозитории"
    fi
done

if [ -n "$INSTALL_LIST" ]; then
    apt install -y $INSTALL_LIST
fi

echo "Базовые пакеты установлены"