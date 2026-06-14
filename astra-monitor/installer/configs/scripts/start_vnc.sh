#!/bin/bash
#==============================================================================
# Astra Monitor - Запуск VNC стека
# Xvfb + OpenBox + Chromium + x11vnc + websockify
#==============================================================================

set -e

DISPLAY_NUM=99
SCREEN_RESOLUTION="1920x1080x24"
VNC_PORT=5901
NOVNC_PORT=6080
CHROMIUM_FLAGS="--no-sandbox --disable-gpu --disable-software-rasterizer"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Kill existing processes
log "Остановка существующих VNC процессов..."
pkill -f "Xvfb :$DISPLAY_NUM" 2>/dev/null || true
pkill -f "x11vnc.*:$DISPLAY_NUM" 2>/dev/null || true
pkill -f "websockify.*$NOVNC_PORT" 2>/dev/null || true
pkill -f "chromium" 2>/dev/null || true

sleep 1

log "Запуск Xvfb..."
Xvfb :$DISPLAY_NUM -screen 0 $SCREEN_RESOLUTION -ac +extension GLX +render -noreset &

sleep 2

# Check Xvfb started
if ! pgrep -f "Xvfb :$DISPLAY_NUM" > /dev/null; then
    log "ОШИБКА: Xvfb не запустился"
    exit 1
fi

log "Xvfb запущен на дисплее :$DISPLAY_NUM"

export DISPLAY=:$DISPLAY_NUM

log "Запуск OpenBox..."
openbox &

sleep 1

log "Запуск x11vnc..."
x11vnc -display :$DISPLAY_NUM \
    -forever \
    -shared \
    -rfbport $VNC_PORT \
    -nopw \
    -bg \
    -xkb \
    -o /var/log/x11vnc.log

sleep 1

log "Запуск Websockify (noVNC proxy)..."
websockify \
    --daemon \
    --web /usr/share/novnc \
    $NOVNC_PORT \
    localhost:$VNC_PORT

sleep 1

log "VNC стек запущен!"
log "  VNC порт: $VNC_PORT"
log "  noVNC порт: $NOVNC_PORT"
log "  Дисплей: :$DISPLAY_NUM"
log ""
log "Доступ:"
log "  VNC клиент: localhost:$VNC_PORT"
log "  Браузер: http://localhost:$NOVNC_PORT/vnc.html"