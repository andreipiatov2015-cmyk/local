#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/var/www"
LIVE_SERVER="${ROOT_DIR}/live-server/server.py"
REBOOT_SERVER="${ROOT_DIR}/reboot/server.py"
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"

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

log "Старт перезапуска сайта в ${ROOT_DIR}"

restart_systemd_unit "nginx.service" || log "nginx.service не найден, пропускаю"
restart_systemd_unit "live-server.service" || restart_python_app "${LIVE_SERVER}" "live-server"
restart_systemd_unit "reboot.service" || restart_python_app "${REBOOT_SERVER}" "reboot-server"

log "Готово"
