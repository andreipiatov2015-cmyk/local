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

log "Старт перезапуска сайта в ${ROOT_DIR}"

# 1) Custom nginx (RTMP)
start_or_reload_custom_nginx

# 2) Не трогаем systemd nginx.service, чтобы не конфликтовал с /usr/local/nginx
log "nginx.service пропускаю (использую custom nginx из /usr/local/nginx)"

# 3) Python apps (systemd если есть, иначе nohup)
restart_systemd_unit "live-server.service" || restart_python_app "${LIVE_SERVER}" "live-server"
restart_systemd_unit "reboot.service" || restart_python_app "${REBOOT_SERVER}" "reboot-server"

log "Готово"
