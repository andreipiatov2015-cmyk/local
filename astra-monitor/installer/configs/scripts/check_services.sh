#!/bin/bash
#==============================================================================
# Astra Monitor - Проверка работоспособности
#==============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

OK="${GREEN}✓${NC}"
FAIL="${RED}✗${NC}"
WARN="${YELLOW}!${NC}"

check_service() {
    local name=$1
    local process=$2
    local port=$3
    
    echo -n "  $name: "
    
    # Check process
    if pgrep -f "$process" > /dev/null 2>&1; then
        echo -e "$OK Запущен"
    else
        echo -e "$FAIL Не запущен"
        return 1
    fi
    
    # Check port if specified
    if [ -n "$port" ]; then
        echo -n "    Порт $port: "
        if netstat -tuln 2>/dev/null | grep -q ":$port " || ss -tuln 2>/dev/null | grep -q ":$port "; then
            echo -e "$OK Открыт"
        else
            echo -e "$WARN Закрыт/не прослушивается"
        fi
    fi
}

echo ""
echo "========================================"
echo "  Astra Monitor - Проверка системы"
echo "========================================"
echo ""

ERRORS=0

echo "Системные компоненты:"
echo "---------------------"
check_service "Python 3" "python3" || ERRORS=$((ERRORS + 1))
check_service "Nginx" "/usr/local/nginx/sbin/nginx" "80" || ERRORS=$((ERRORS + 1))
check_service "FFmpeg" "ffmpeg" || ERRORS=$((ERRORS + 1))
echo ""

echo "Python приложения:"
echo "------------------"
check_service "Live Server" "live-server" "8083" || ERRORS=$((ERRORS + 1))
check_service "Reboot Server" "reboot-server" "8084" || ERRORS=$((ERRORS + 1))
echo ""

echo "Стриминг:"
echo "---------"
check_service "RTMP" "nginx.*rtmp" "1935" || ERRORS=$((ERRORS + 1))
check_service "HLS каталог" "/var/www/hls" || ERRORS=$((ERRORS + 1))
echo ""

echo "VNC стек:"
echo "---------"
check_service "Xvfb" "Xvfb" || ERRORS=$((ERRORS + 1))
check_service "Websockify" "websockify" "6080" || ERRORS=$((ERRORS + 1))
echo ""

echo "Каталоги:"
echo "---------"
for dir in /var/www/live-server /var/www/reboot /var/www/hls /var/www/logs; do
    echo -n "  $dir: "
    if [ -d "$dir" ]; then
        echo -e "$OK Существует"
    else
        echo -e "$FAIL Отсутствует"
        ERRORS=$((ERRORS + 1))
    fi
done
echo ""

echo "========================================"
if [ $ERRORS -eq 0 ]; then
    echo -e "  ${GREEN}Все проверки пройдены!${NC}"
else
    echo -e "  ${RED}Обнаружено $ERRORS проблем${NC}"
fi
echo "========================================"
echo ""

exit $ERRORS