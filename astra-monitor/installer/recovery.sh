#!/bin/bash
#==============================================================================
# Astra Monitor - Режим восстановления
# Проверяет и восстанавливает отсутствующие компоненты
#==============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALLER_DIR="$(dirname "$SCRIPT_DIR")"
RECOVERY_MODE=true

log() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_err() { echo -e "${RED}[ERR]${NC} $1"; }
log_step() { echo -e "\n${BLUE}========================================${NC}\n  $1\n"; }

check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_err "Требуются права root"
        exit 1
    fi
}

#==============================================================================
# Проверки компонентов
#==============================================================================

check_python3() {
    log "Проверка Python 3..."
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version)
        log "Python 3 установлен: $PYTHON_VERSION"
        return 0
    else
        log_err "Python 3 не установлен"
        return 1
    fi
}

check_nginx() {
    log "Проверка Nginx..."
    if [ -f "/usr/local/nginx/sbin/nginx" ]; then
        NGINX_VER=$(/usr/local/nginx/sbin/nginx -v 2>&1)
        log "Nginx установлен: $NGINX_VER"
        return 0
    else
        log_err "Nginx не установлен"
        return 1
    fi
}

check_nginx_running() {
    log "Проверка Nginx (запущен)..."
    if pgrep -f "/usr/local/nginx/sbin/nginx" > /dev/null; then
        log "Nginx запущен"
        return 0
    else
        log_err "Nginx не запущен"
        return 1
    fi
}

check_ffmpeg() {
    log "Проверка FFmpeg..."
    if command -v ffmpeg &> /dev/null; then
        FF_VER=$(ffmpeg -version 2>&1 | head -n1)
        log "FFmpeg установлен: $FF_VER"
        return 0
    else
        log_err "FFmpeg не установлен"
        return 1
    fi
}

check_python_venv() {
    log "Проверка Python виртуального окружения..."
    if [ -f "/var/www/.venv/bin/activate" ]; then
        log "Python venv создано"
        return 0
    else
        log_err "Python venv не найдено"
        return 1
    fi
}

check_directories() {
    log "Проверка каталогов..."
    local MISSING=0
    for dir in /var/www/live-server /var/www/reboot /var/www/hls /var/www/logs; do
        if [ -d "$dir" ]; then
            log "$dir"
        else
            log_err "$dir не существует"
            MISSING=$((MISSING + 1))
        fi
    done
    return $MISSING
}

check_services() {
    log "Проверка systemd сервисов..."
    local MISSING=0
    for svc in nginx-custom live-server reboot-server; do
        if systemctl list-unit-files | grep -q "^$svc.service"; then
            log "$svc.service зарегистрирован"
        else
            log_err "$svc.service не зарегистрирован"
            MISSING=$((MISSING + 1))
        fi
    done
    return $MISSING
}

check_ports() {
    log "Проверка портов..."
    local MISSING=0
    for port in 80 8083 8084 1935; do
        if netstat -tuln 2>/dev/null | grep -q ":$port " || ss -tuln 2>/dev/null | grep -q ":$port "; then
            log "Порт $port открыт"
        else
            log_warn "Порт $port закрыт"
            MISSING=$((MISSING + 1))
        fi
    done
    return $MISSING
}

check_vnc() {
    log "Проверка VNC стека..."
    for pkg in xvfb x11vnc novnc websockify chromium; do
        if dpkg -l | grep -q "^ii.*$pkg"; then
            log "$pkg установлен"
        else
            log_warn "$pkg не установлен"
        fi
    done
}

#==============================================================================
# Восстановление
#==============================================================================

restore_python3() {
    log_step "Восстановление Python 3"
    if [ -f "$INSTALLER_DIR/base_packages.sh" ]; then
        bash "$INSTALLER_DIR/base_packages.sh" --python-only
    else
        apt install -y python3 python3-pip python3-venv
    fi
}

restore_nginx() {
    log_step "Восстановление Nginx"
    if [ -f "$INSTALLER_DIR/nginx_build.sh" ]; then
        bash "$INSTALLER_DIR/nginx_build.sh"
    else
        log_err "Скрипт nginx_build.sh не найден"
        return 1
    fi
}

restore_nginx_config() {
    log_step "Восстановление конфигурации Nginx"
    cp "$INSTALLER_DIR/configs/nginx/nginx.conf" /usr/local/nginx/conf/nginx.conf
    cp "$INSTALLER_DIR/configs/nginx/nginx-rtmp.conf" /usr/local/nginx/conf/nginx-rtmp.conf
    log "Конфигурации скопированы"
}

restore_ffmpeg() {
    log_step "Восстановление FFmpeg"
    apt install -y ffmpeg
}

restore_python_venv() {
    log_step "Восстановление Python виртуального окружения"
    if [ -f "$INSTALLER_DIR/python_deps.sh" ]; then
        bash "$INSTALLER_DIR/python_deps.sh"
    else
        python3 -m venv /var/www/.venv
        source /var/www/.venv/bin/activate
        pip install flask flask-cors requests openpyxl pandas schedule pillow websockets
        deactivate
    fi
}

restore_directories() {
    log_step "Восстановление каталогов"
    mkdir -p /var/www/live-server
    mkdir -p /var/www/reboot
    mkdir -p /var/www/hls
    mkdir -p /var/www/logs
    mkdir -p /var/run/contest_vnc
    log "Каталоги созданы"
}

restore_services() {
    log_step "Восстановление systemd сервисов"
    cp "$INSTALLER_DIR/configs/systemd/"*.service /etc/systemd/system/
    systemctl daemon-reload
    log "Сервисы зарегистрированы"
}

restore_scripts() {
    log_step "Восстановление скриптов"
    cp "$INSTALLER_DIR/configs/scripts/"*.sh /var/www/
    chmod +x /var/www/*.sh
    log "Скрипты скопированы"
}

restore_vnc() {
    log_step "Восстановление VNC стека"
    if [ -f "$INSTALLER_DIR/vnc_stack.sh" ]; then
        bash "$INSTALLER_DIR/vnc_stack.sh"
    else
        apt install -y xvfb openbox x11vnc novnc websockify chromium
    fi
}

#==============================================================================
# Полная проверка
#==============================================================================

full_check() {
    log_step "ПОЛНАЯ ПРОВЕРКА СИСТЕМЫ"
    
    local ERRORS=0
    
    echo "Системные компоненты:"
    echo "--------------------"
    check_python3 || ERRORS=$((ERRORS + 1))
    check_nginx || ERRORS=$((ERRORS + 1))
    check_ffmpeg || ERRORS=$((ERRORS + 1))
    echo ""
    
    echo "Python окружение:"
    echo "-----------------"
    check_python_venv || ERRORS=$((ERRORS + 1))
    echo ""
    
    echo "Каталоги:"
    echo "---------"
    check_directories || ERRORS=$((ERRORS + 1))
    echo ""
    
    echo "Сервисы:"
    echo "--------"
    check_services || ERRORS=$((ERRORS + 1))
    echo ""
    
    echo "Сеть:"
    echo "-----"
    check_ports || ERRORS=$((ERRORS + 1))
    echo ""
    
    echo "VNC стек:"
    echo "---------"
    check_vnc
    echo ""
    
    echo "========================================"
    if [ $ERRORS -eq 0 ]; then
        echo -e "  ${GREEN}Все компоненты в порядке${NC}"
        echo "========================================"
        return 0
    else
        echo -e "  ${RED}Обнаружено $ERRORS проблем${NC}"
        echo "========================================"
        return 1
    fi
}

#==============================================================================
# Интерактивное восстановление
#==============================================================================

interactive_restore() {
    log_step "РЕЖИМ ВОССТАНОВЛЕНИЯ"
    
    echo "Выберите действие:"
    echo "  1) Полная проверка системы"
    echo "  2) Восстановить Python"
    echo "  3) Восстановить Nginx"
    echo "  4) Восстановить FFmpeg"
    echo "  5) Восстановить каталоги"
    echo "  6) Восстановить сервисы"
    echo "  7) Восстановить VNC"
    echo "  8) Полное восстановление"
    echo "  0) Выход"
    echo ""
    read -p "Выбор: " choice
    
    case $choice in
        1) full_check ;;
        2) restore_python3; restore_python_venv ;;
        3) restore_nginx; restore_nginx_config ;;
        4) restore_ffmpeg ;;
        5) restore_directories ;;
        6) restore_services; restore_scripts ;;
        7) restore_vnc ;;
        8) 
            restore_python3
            restore_python_venv
            restore_ffmpeg
            restore_directories
            restore_nginx
            restore_nginx_config
            restore_services
            restore_scripts
            restore_vnc
            full_check
            ;;
        0) exit 0 ;;
        *) echo "Неверный выбор" ;;
    esac
}

#==============================================================================
# Автоматическое восстановление
#==============================================================================

auto_restore() {
    log_step "АВТОМАТИЧЕСКОЕ ВОССТАНОВЛЕНИЕ"
    
    # Проверяем что отсутствует
    MISSING=""
    
    check_python3 || MISSING="$MISSING python3"
    check_ffmpeg || MISSING="$MISSING ffmpeg"
    check_directories || MISSING="$MISSING directories"
    
    if [ -z "$MISSING" ]; then
        log "Все базовые компоненты на месте"
    else
        log "Отсутствует:$MISSING"
    fi
    
    # Восстанавливаем критичные компоненты
    if ! check_python3 &>/dev/null; then
        restore_python3
    fi
    
    if ! check_ffmpeg &>/dev/null; then
        restore_ffmpeg
    fi
    
    if ! check_directories &>/dev/null; then
        restore_directories
    fi
    
    if ! check_nginx &>/dev/null; then
        restore_nginx
        restore_nginx_config
    fi
    
    if ! check_python_venv &>/dev/null; then
        restore_python_venv
    fi
    
    if ! check_services &>/dev/null; then
        restore_services
        restore_scripts
    fi
    
    # Проверяем что восстановлено
    log_step "ПРОВЕРКА ПОСЛЕ ВОССТАНОВЛЕНИЯ"
    full_check
}

#==============================================================================
# Главная функция
#==============================================================================

main() {
    echo ""
    echo "========================================"
    echo "  Astra Monitor - Режим восстановления"
    echo "========================================"
    echo ""
    
    check_root
    
    if [ "$1" == "--auto" ]; then
        auto_restore
    else
        if [ "$1" == "--check" ]; then
            full_check
        else
            interactive_restore
        fi
    fi
}

main "$@"