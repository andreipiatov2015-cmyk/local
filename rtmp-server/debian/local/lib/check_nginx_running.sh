#!/bin/sh
# Печатает "true", если nginx (кастомная сборка) уже запущен — вне
# зависимости от того, как именно (systemd, restart_astra.sh, вручную).
# Иначе печатает "false". Никаких побочных эффектов — только детект.
#
# Вынесено в отдельный файл специально ради тестируемости (см.
# tests/test_nginx_conflict_detection.py): именно эта проверка — граница
# между "молча стартуем новый юнит" и "конкурируем портами с уже живым
# процессом на следующей перезагрузке", баг именно здесь чуть не уронил
# рабочий сайт при первом реальном апгрейде.
set -e

NGINX_PID_FILE="${NGINX_PID_FILE:-/usr/local/nginx/logs/nginx.pid}"

if pgrep -f '/usr/local/nginx/sbin/nginx' >/dev/null 2>&1; then
    echo "true"
    exit 0
fi

if [ -f "$NGINX_PID_FILE" ] && kill -0 "$(cat "$NGINX_PID_FILE" 2>/dev/null)" 2>/dev/null; then
    echo "true"
    exit 0
fi

echo "false"
