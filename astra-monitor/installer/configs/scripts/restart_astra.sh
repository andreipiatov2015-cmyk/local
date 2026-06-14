#!/bin/bash
#==============================================================================
# Astra Monitor - Скрипт перезапуска всех сервисов
#==============================================================================

set -e

echo "========================================"
echo "  Astra Monitor - Перезапуск сервисов"
echo "========================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_ok() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_err() {
    echo -e "${RED}[ERR]${NC} $1"
}

log_info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log_err "Требуются права root"
    exit 1
fi

echo "Остановка сервисов..."
echo ""

# Stop Flask servers
log_info "Остановка Live Server..."
systemctl stop live-server 2>/dev/null && log_ok "Live Server остановлен" || log_info "Live Server не был запущен"

log_info "Остановка Reboot Server..."
systemctl stop reboot-server 2>/dev/null && log_ok "Reboot Server остановлен" || log_info "Reboot Server не был запущен"

# Reload Nginx
log_info "Перезагрузка Nginx..."
/usr/local/nginx/sbin/nginx -s reload 2>/dev/null && log_ok "Nginx перезагружен" || log_info "Nginx не был запущен"

echo ""
echo "Запуск сервисов..."
echo ""

# Start Flask servers
log_info "Запуск Live Server..."
systemctl start live-server 2>/dev/null && sleep 1 && log_ok "Live Server запущен" || log_err "Не удалось запустить Live Server"

log_info "Запуск Reboot Server..."
systemctl start reboot-server 2>/dev/null && sleep 1 && log_ok "Reboot Server запущен" || log_err "Не удалось запустить Reboot Server"

# Start Nginx
log_info "Запуск Nginx..."
/usr/local/nginx/sbin/nginx 2>/dev/null && log_ok "Nginx запущен" || log_info "Nginx уже запущен"

echo ""
echo "========================================"
echo "  Проверка статуса"
echo "========================================"
echo ""

# Check processes
check_process() {
    local name=$1
    local pidfile=$2
    
    if [ -n "$pidfile" ] && [ -f "$pidfile" ]; then
        if kill -0 $(cat "$pidfile") 2>/dev/null; then
            log_ok "$name запущен (PID: $(cat $pidfile))"
        else
            log_err "$name не отвечает"
        fi
    elif pgrep -f "$name" > /dev/null; then
        log_ok "$name запущен"
    else
        log_err "$name не запущен"
    fi
}

# Check Nginx
check_process "Nginx" "/run/nginx.pid"

# Check Flask apps
for app in "live-server" "reboot-server"; do
    if systemctl is-active --quiet "$app" 2>/dev/null; then
        log_ok "$app запущен"
    else
        log_err "$app не запущен"
    fi
done

echo ""
echo "Перезапуск завершен!"
echo ""

# Show listening ports
echo "Открытые порты:"
netstat -tlnp 2>/dev/null | grep -E ':(80|8083|8084|1935|6080)\s' || ss -tlnp | grep -E ':(80|8083|8084|1935|6080)\s'
echo ""