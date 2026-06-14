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

apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    wget \
    unzip \
    build-essential \
    libpcre3 \
    libpcre3-dev \
    zlib1g \
    zlib1g-dev \
    libssl-dev \
    autoconf \
    automake \
    libtool \
    pkg-config \
    ffmpeg \
    supervisor \
    htop \
    net-tools

echo "Базовые пакеты установлены"