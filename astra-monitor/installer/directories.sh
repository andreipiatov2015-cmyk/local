#!/bin/bash
#==============================================================================
# Astra Monitor - Создание каталогов
#==============================================================================

set -e

if [ "$EUID" -ne 0 ]; then
    echo "Требуются права root"
    exit 1
fi

echo "Создание каталогов..."

# Основные каталоги приложений
mkdir -p /var/www/live-server
mkdir -p /var/www/reboot
mkdir -p /var/www/hls
mkdir -p /var/www/logs
mkdir -p /var/www/recordings

# Каталоги для Nginx
mkdir -p /usr/local/nginx/conf/sites-available
mkdir -p /usr/local/nginx/conf/sites-enabled
mkdir -p /var/log/nginx

# Каталоги для VNC
mkdir -p /var/run/contest_vnc

# Каталоги для Supervisor
mkdir -p /etc/supervisor/conf.d

# Права доступа
chown -R www-data:www-data /var/www 2>/dev/null || true

echo "Каталоги созданы:"
ls -la /var/www/