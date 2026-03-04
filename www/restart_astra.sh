#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/var/www"
LIVE_SERVER="${ROOT_DIR}/live-server/server.py"
REBOOT_SERVER="${ROOT_DIR}/reboot/server.py"
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"
LIVE_SERVER_HOST="127.0.0.1"
LIVE_SERVER_PORT="8083"

# Custom nginx (with RTMP) installed manually
CUSTOM_NGINX_BIN="/usr/local/nginx/sbin/nginx"
CUSTOM_NGINX_CONF="/usr/local/nginx/conf/nginx.conf"
CUSTOM_NGINX_PID="/usr/local/nginx/logs/nginx.pid"

# ===== VNC / noVNC stack (Yandex connect) =====
VNC_RUN_DIR="/var/run/contest_vnc"
VNC_DISPLAY=":99"
VNC_SCREEN="1280x800x24"
VNC_RFB_ADDR="127.0.0.1"
VNC_RFB_PORT="5901"
NOVNC_HTTP_ADDR="127.0.0.1"
NOVNC_HTTP_PORT="6080"
NOVNC_WEB_DIR="/usr/share/novnc"

XDG_RUNTIME_DIR="/tmp/xdg-runtime-root"
CHROMIUM_PROFILE="/tmp/chromium-yandex-profile"
CHROMIUM_START_URL="${CHROMIUM_START_URL:-https://forms.yandex.ru/admin/}"

# Binaries (assume installed)
Xvfb_BIN="$(command -v Xvfb || true)"
OPENBOX_BIN="$(command -v openbox || true)"
CHROMIUM_BIN="$(command -v chromium || command -v chromium-browser || true)"
X11VNC_BIN="$(command -v x11vnc || true)"
WEBSOCKIFY_BIN="$(command -v websockify || true)"

log() {
  printf "[restart] %s\n" "$1"
}

restart_systemd_unit() {
  local unit="$1"
  if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files --type=service | awk '{print $1}' | grep -qx "${unit}"; then
    log "Перезапуск systemd: ${unit}"
    systemctl restart "${unit}"
    return 0
  fi
  return 1
}

restart_python_app() {
  local app="$1"
  local name="$2"

  if [[ ! -f "${app}" ]]; then
    log "Файл не найден: ${app}"
    return 0
  fi

  log "Останавливаю ${name} (${app})"
  pkill -f "${app}" 2>/dev/null || true

  log "Запускаю ${name} (${app})"
  nohup "${PYTHON_BIN}" "${app}" >/var/log/${name}.log 2>&1 &

  if [[ "${app}" == "${LIVE_SERVER}" ]]; then
    log "${name} должен слушать ${LIVE_SERVER_HOST}:${LIVE_SERVER_PORT}"
  fi
}

start_or_reload_custom_nginx() {
  if [[ ! -x "${CUSTOM_NGINX_BIN}" ]]; then
    log "custom nginx не найден: ${CUSTOM_NGINX_BIN} (пропускаю)"
    return 0
  fi

  log "Проверяю custom nginx (RTMP)..."

  # If pid exists and process alive -> reload
  if [[ -f "${CUSTOM_NGINX_PID}" ]]; then
    local pid
    pid="$(cat "${CUSTOM_NGINX_PID}" 2>/dev/null || true)"
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
      log "custom nginx запущен (pid=${pid}) -> reload"
      "${CUSTOM_NGINX_BIN}" -s reload || true
      return 0
    fi
  fi

  # Validate config before start
  if "${CUSTOM_NGINX_BIN}" -t -c "${CUSTOM_NGINX_CONF}" >/dev/null 2>&1; then
    log "custom nginx не запущен -> стартую"
    "${CUSTOM_NGINX_BIN}" -c "${CUSTOM_NGINX_CONF}" || true
  else
    log "custom nginx: ошибка конфига (${CUSTOM_NGINX_CONF}), не стартую"
    "${CUSTOM_NGINX_BIN}" -t -c "${CUSTOM_NGINX_CONF}" || true
  fi
}

pidfile() {
  echo "${VNC_RUN_DIR}/$1.pid"
}

stop_by_pidfile() {
  local name="$1"
  local pf
  pf="$(pidfile "${name}")"

  if [[ -f "${pf}" ]]; then
    local pid
    pid="$(cat "${pf}" 2>/dev/null || true)"
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
      log "Останавливаю ${name} (pid=${pid})"
      kill "${pid}" 2>/dev/null || true
      # give it a moment
      sleep 0.2
      kill -9 "${pid}" 2>/dev/null || true
    fi
    rm -f "${pf}" || true
  fi
}

stop_vnc_stack() {
  log "Останавливаю VNC/noVNC стек (если запущен)..."

  # Order: websockify -> x11vnc -> chromium -> openbox -> Xvfb
  stop_by_pidfile "websockify"
  stop_by_pidfile "x11vnc"
  stop_by_pidfile "chromium"
  stop_by_pidfile "openbox"
  stop_by_pidfile "xvfb"

  # Extra safety cleanup (only for our profile)
  pkill -f "${CHROMIUM_PROFILE}" 2>/dev/null || true

  # Astra pkill supports one pattern per call
  pkill -x Xvfb 2>/dev/null || true
  pkill -x openbox 2>/dev/null || true
  pkill -x x11vnc 2>/dev/null || true
  pkill -x websockify 2>/dev/null || true
  pkill -x chromium 2>/dev/null || true
  pkill -x chromium-browser 2>/dev/null || true

  # Remove stale lock/socket only if Xvfb is stopped
  if ! pgrep -x Xvfb >/dev/null 2>&1; then
    rm -f /tmp/.X99-lock /tmp/.X11-unix/X99
  fi
}

is_tcp_listening() {
  local port="$1"
  ss -ltn "( sport = :${port} )" 2>/dev/null | tail -n +2 | grep -q .
}

start_vnc_stack() {
  log "Запускаю VNC/noVNC стек (Яндекс-вход)..."

  mkdir -p "${VNC_RUN_DIR}"
  chmod 755 "${VNC_RUN_DIR}" || true

  if [[ -z "${Xvfb_BIN}" ]]; then
    log "Xvfb не найден (установи пакет xvfb). Пропускаю VNC стек."
    return 0
  fi
  if [[ -z "${OPENBOX_BIN}" ]]; then
    log "openbox не найден. Пропускаю VNC стек."
    return 0
  fi
  if [[ -z "${CHROMIUM_BIN}" ]]; then
    log "chromium не найден. Пропускаю VNC стек."
    return 0
  fi
  if [[ -z "${X11VNC_BIN}" ]]; then
    log "x11vnc не найден. Пропускаю VNC стек."
    return 0
  fi
  if [[ -z "${WEBSOCKIFY_BIN}" ]]; then
    log "websockify не найден. Пропускаю VNC стек."
    return 0
  fi
  if [[ ! -d "${NOVNC_WEB_DIR}" ]]; then
    log "noVNC web dir не найден: ${NOVNC_WEB_DIR}. Пропускаю VNC стек."
    return 0
  fi

  # Runtime dir for chromium (fix XDG warnings)
  mkdir -p "${XDG_RUNTIME_DIR}"
  chmod 700 "${XDG_RUNTIME_DIR}"

  # Start Xvfb
  nohup "${Xvfb_BIN}" "${VNC_DISPLAY}" -screen 0 "${VNC_SCREEN}" >/var/log/contest_xvfb.log 2>&1 &
  echo $! > "$(pidfile xvfb)"

  # Wait up to 5 seconds for X11 socket
  local x11_socket="/tmp/.X11-unix/X99"
  local i
  for i in {1..50}; do
    [[ -S "${x11_socket}" ]] && break
    sleep 0.1
  done
  if [[ ! -S "${x11_socket}" ]]; then
    log "ОШИБКА: Xvfb не поднял сокет ${x11_socket} за 5 секунд"
    return 1
  fi

  # Export DISPLAY for following processes
  export DISPLAY="${VNC_DISPLAY}"
  export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR}"

  # Start openbox
  nohup "${OPENBOX_BIN}" >/var/log/contest_openbox.log 2>&1 &
  echo $! > "$(pidfile openbox)"
  sleep 0.2

  # Start chromium (with dedicated profile)
  mkdir -p "${CHROMIUM_PROFILE}" || true
  nohup "${CHROMIUM_BIN}" \
    --no-sandbox \
    --no-first-run \
    --app="${CHROMIUM_START_URL}" \
    --window-size=420,640 \
    --window-position=10,10 \
    --disable-gpu \
    --disable-dev-shm-usage \
    --disable-software-rasterizer \
    --force-device-scale-factor=1.5 \
    --user-data-dir="${CHROMIUM_PROFILE}" \
    >/var/log/contest_chromium.log 2>&1 &
  echo $! > "$(pidfile chromium)"
  sleep 0.4

  # Start x11vnc (LOCALHOST ONLY)
  nohup "${X11VNC_BIN}" \
    -display "${VNC_DISPLAY}" \
    -forever -nopw \
    -listen "${VNC_RFB_ADDR}" -rfbport "${VNC_RFB_PORT}" \
    >/var/log/contest_x11vnc.log 2>&1 &
  echo $! > "$(pidfile x11vnc)"
  sleep 0.2

  # Ensure 6080 is free before websockify start
  if is_tcp_listening "${NOVNC_HTTP_PORT}"; then
    log "Порт ${NOVNC_HTTP_PORT} уже занят, останавливаю старый websockify"
    pkill -x websockify 2>/dev/null || true
    sleep 0.2
  fi

  # Start websockify/noVNC (LOCALHOST ONLY)
  nohup "${WEBSOCKIFY_BIN}" \
    --web="${NOVNC_WEB_DIR}" \
    "${NOVNC_HTTP_ADDR}:${NOVNC_HTTP_PORT}" \
    "${VNC_RFB_ADDR}:${VNC_RFB_PORT}" \
    >/var/log/contest_websockify.log 2>&1 &
  echo $! > "$(pidfile websockify)"

  sleep 0.3
  if ! is_tcp_listening "${VNC_RFB_PORT}"; then
    log "ОШИБКА: x11vnc не слушает порт ${VNC_RFB_PORT}"
  fi
  if ! is_tcp_listening "${NOVNC_HTTP_PORT}"; then
    log "ОШИБКА: websockify не слушает порт ${NOVNC_HTTP_PORT}"
  fi

  log "VNC/noVNC стек запущен: noVNC на ${NOVNC_HTTP_ADDR}:${NOVNC_HTTP_PORT} (proxy через nginx)"
}

log "Старт перезапуска сайта в ${ROOT_DIR}"

# 0) VNC/noVNC stack (for Yandex login via site)
stop_vnc_stack
start_vnc_stack

# 1) Custom nginx (RTMP)
start_or_reload_custom_nginx

# 2) Не трогаем systemd nginx.service, чтобы не конфликтовал с /usr/local/nginx
log "nginx.service пропускаю (использую custom nginx из /usr/local/nginx)"

# 3) Python apps (systemd если есть, иначе nohup)
restart_systemd_unit "live-server.service" || restart_python_app "${LIVE_SERVER}" "live-server"
restart_systemd_unit "reboot.service" || restart_python_app "${REBOOT_SERVER}" "reboot-server"

log "Готово"
