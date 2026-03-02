#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/var/www"
LIVE_SERVER="${ROOT_DIR}/live-server/server.py"
REBOOT_SERVER="${ROOT_DIR}/reboot/server.py"
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"

# Custom nginx (with RTMP) installed manually
CUSTOM_NGINX_BIN="/usr/local/nginx/sbin/nginx"
CUSTOM_NGINX_CONF="/usr/local/nginx/conf/nginx.conf"
CUSTOM_NGINX_PID="/usr/local/nginx/logs/nginx.pid"
SYSTEM_NGINX_BIN="/usr/sbin/nginx"
SYSTEM_NGINX_CONF="/etc/nginx/nginx.conf"

VNC_PID_DIR="/var/run/contest_vnc"
XVFB_PID_FILE="${VNC_PID_DIR}/xvfb.pid"
OPENBOX_PID_FILE="${VNC_PID_DIR}/openbox.pid"
CHROMIUM_PID_FILE="${VNC_PID_DIR}/chromium.pid"
X11VNC_PID_FILE="${VNC_PID_DIR}/x11vnc.pid"
WEBSOCKIFY_PID_FILE="${VNC_PID_DIR}/websockify.pid"

VNC_DISPLAY=":99"
VNC_GEOMETRY="1280x800x24"
XDG_RUNTIME_DIR="/tmp/xdg-runtime-root"
CHROMIUM_PROFILE_DIR="/tmp/chromium-yandex-profile"
NOVNC_WEB_DIR="/usr/share/novnc"

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
}

kill_pidfile_process() {
  local pid_file="$1"
  local name="$2"

  if [[ -f "${pid_file}" ]]; then
    local pid
    pid="$(cat "${pid_file}" 2>/dev/null || true)"
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
      log "Останавливаю ${name} (pid=${pid})"
      kill "${pid}" 2>/dev/null || true
      sleep 1
      kill -9 "${pid}" 2>/dev/null || true
    fi
    rm -f "${pid_file}"
  fi
}

find_running_nginx() {
  if [[ -f "${CUSTOM_NGINX_PID}" ]]; then
    local custom_pid
    custom_pid="$(cat "${CUSTOM_NGINX_PID}" 2>/dev/null || true)"
    if [[ -n "${custom_pid}" ]] && kill -0 "${custom_pid}" 2>/dev/null; then
      echo "custom"
      return
    fi
  fi

  if pgrep -x nginx >/dev/null 2>&1; then
    local conf
    conf="$(ps -eo args | awk '/nginx: master process/ {for(i=1;i<=NF;i++) if($i=="-c") {print $(i+1); exit}}')"
    if [[ "${conf}" == "${CUSTOM_NGINX_CONF}" ]]; then
      echo "custom"
      return
    fi
    echo "system"
    return
  fi

  if [[ -x "${CUSTOM_NGINX_BIN}" ]]; then
    echo "custom"
  else
    echo "system"
  fi
}

reload_nginx() {
  local mode="$1"

  if [[ "${mode}" == "custom" ]]; then
    if [[ ! -x "${CUSTOM_NGINX_BIN}" ]]; then
      log "custom nginx не найден: ${CUSTOM_NGINX_BIN}"
      return 1
    fi

    log "Проверяю конфиг custom nginx: ${CUSTOM_NGINX_CONF}"
    "${CUSTOM_NGINX_BIN}" -t -c "${CUSTOM_NGINX_CONF}"

    if [[ -f "${CUSTOM_NGINX_PID}" ]] && kill -0 "$(cat "${CUSTOM_NGINX_PID}" 2>/dev/null || true)" 2>/dev/null; then
      log "Reload custom nginx"
      "${CUSTOM_NGINX_BIN}" -s reload
    else
      log "custom nginx не запущен -> стартую"
      "${CUSTOM_NGINX_BIN}" -c "${CUSTOM_NGINX_CONF}"
    fi
    return 0
  fi

  if [[ -x "${SYSTEM_NGINX_BIN}" ]]; then
    log "Проверяю конфиг system nginx: ${SYSTEM_NGINX_CONF}"
    "${SYSTEM_NGINX_BIN}" -t -c "${SYSTEM_NGINX_CONF}"

    if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files --type=service | awk '{print $1}' | grep -qx "nginx.service"; then
      log "Reload system nginx через systemctl"
      systemctl reload nginx
    else
      log "Reload system nginx через сигнал"
      "${SYSTEM_NGINX_BIN}" -s reload
    fi
    return 0
  fi

  log "Не найден nginx для reload"
  return 1
}

stop_vnc_stack() {
  log "Останавливаю VNC stack"
  mkdir -p "${VNC_PID_DIR}"

  kill_pidfile_process "${WEBSOCKIFY_PID_FILE}" "websockify"
  kill_pidfile_process "${X11VNC_PID_FILE}" "x11vnc"
  kill_pidfile_process "${CHROMIUM_PID_FILE}" "chromium"
  kill_pidfile_process "${OPENBOX_PID_FILE}" "openbox"
  kill_pidfile_process "${XVFB_PID_FILE}" "Xvfb"

  pkill -f "websockify .*127.0.0.1:6080" 2>/dev/null || true
  pkill -f "x11vnc .* -rfbport 5901" 2>/dev/null || true
  pkill -f "chromium.*${CHROMIUM_PROFILE_DIR}" 2>/dev/null || true
  pkill -f "openbox" 2>/dev/null || true
  pkill -f "Xvfb ${VNC_DISPLAY}" 2>/dev/null || true
}

start_vnc_stack() {
  log "Запускаю VNC stack"

  mkdir -p "${VNC_PID_DIR}" "${XDG_RUNTIME_DIR}" "${CHROMIUM_PROFILE_DIR}"
  chmod 700 "${XDG_RUNTIME_DIR}"

  export DISPLAY="${VNC_DISPLAY}"
  export XDG_RUNTIME_DIR

  nohup Xvfb "${VNC_DISPLAY}" -screen 0 "${VNC_GEOMETRY}" >/var/log/xvfb-yandex.log 2>&1 &
  echo $! > "${XVFB_PID_FILE}"
  sleep 1

  nohup openbox >/var/log/openbox-yandex.log 2>&1 &
  echo $! > "${OPENBOX_PID_FILE}"

  nohup chromium \
    --user-data-dir="${CHROMIUM_PROFILE_DIR}" \
    --no-sandbox \
    --disable-gpu \
    --disable-dev-shm-usage \
    --new-window "https://passport.yandex.ru" >/var/log/chromium-yandex.log 2>&1 &
  echo $! > "${CHROMIUM_PID_FILE}"

  nohup x11vnc \
    -display "${VNC_DISPLAY}" \
    -forever \
    -nopw \
    -listen 127.0.0.1 \
    -rfbport 5901 >/var/log/x11vnc-yandex.log 2>&1 &
  echo $! > "${X11VNC_PID_FILE}"

  nohup websockify \
    --web="${NOVNC_WEB_DIR}" \
    127.0.0.1:6080 \
    127.0.0.1:5901 >/var/log/websockify-yandex.log 2>&1 &
  echo $! > "${WEBSOCKIFY_PID_FILE}"
}

log "Старт перезапуска сайта в ${ROOT_DIR}"

NGINX_MODE="$(find_running_nginx)"
log "Обнаружен режим nginx: ${NGINX_MODE}"

stop_vnc_stack
start_vnc_stack

# Python apps (systemd если есть, иначе nohup)
restart_systemd_unit "live-server.service" || restart_python_app "${LIVE_SERVER}" "live-server"
restart_systemd_unit "reboot.service" || restart_python_app "${REBOOT_SERVER}" "reboot-server"

reload_nginx "${NGINX_MODE}"

log "Готово"
