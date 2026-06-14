#!/bin/bash
#==============================================================================
# Astra Monitor - Сборка Nginx с RTMP модулем
#==============================================================================

set -e

NGINX_VERSION="1.26.0"
NGINX_PREFIX="/usr/local/nginx"
WORK_DIR="/tmp/nginx-build"

if [ "$EUID" -ne 0 ]; then
    echo "Требуются права root"
    exit 1
fi

echo "Начало сборки Nginx $NGINX_VERSION..."

# Проверка уже установленного
if [ -f "$NGINX_PREFIX/sbin/nginx" ]; then
    echo "Nginx уже установлен: $NGINX_PREFIX"
    $NGINX_PREFIX/sbin/nginx -v
    exit 0
fi

# Установка зависимостей
echo "Установка зависимостей..."
apt install -y \
    autoconf \
    automake \
    libtool \
    pkg-config \
    libpcre3-dev \
    zlib1g-dev \
    libssl-dev

# Очистка рабочей директории
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

# Клонирование nginx-rtmp модуля
echo "Клонирование nginx-rtmp-module..."
git clone --depth=1 -b master https://github.com/arut/nginx-rtmp-module.git

# Скачивание Nginx
echo "Скачивание Nginx $NGINX_VERSION..."
wget -q https://nginx.org/download/nginx-$NGINX_VERSION.tar.gz
tar -xzf nginx-$NGINX_VERSION.tar.gz

cd nginx-$NGINX_VERSION

# Конфигурация
echo "Конфигурация Nginx..."
./configure \
    --prefix=$NGINX_PREFIX \
    --with-http_ssl_module \
    --with-http_v2_module \
    --with-http_flv_module \
    --with-http_mp4_module \
    --with-http_gzip_static_module \
    --add-module=../nginx-rtmp-module \
    --with-cc-opt="-Wno-deprecated-declarations"

# Компиляция
echo "Компиляция (может занять 5-10 минут)..."
make -j$(nproc)

# Установка
echo "Установка..."
make install

# Очистка
cd /
rm -rf "$WORK_DIR"

# Создание пользователя nginx
id -u nginx &>/dev/null || useradd -r -s /sbin/nologin nginx

echo ""
echo "Nginx успешно установлен: $NGINX_PREFIX"
$NGINX_PREFIX/sbin/nginx -v