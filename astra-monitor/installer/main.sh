#!/bin/bash
#==============================================================================
# Astra Monitor - Главный установщик
# Полное развертывание сервера на чистой Astra Linux 1.8
#==============================================================================

set -e

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Конфигурация
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/astra-monitor"
APP_DIR="/var/www"
LOG_FILE="/var/log/astra-install.log"

# Версии
NGINX_VERSION="1.26.0"
NGINX_RTMP_BRANCH="master"

#==============================================================================
# Функции логирования
#==============================================================================

log() {
    echo -e "${GREEN}[INFO]${NC} $1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $1" >> "$LOG_FILE"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WARN] $1" >> "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $1" >> "$LOG_FILE"
}

log_step() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

#==============================================================================
# Проверка существования пакета
#==============================================================================

check_package() {
    apt-cache show "$1" >/dev/null 2>&1
}

#==============================================================================
# Проверки
#==============================================================================

check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "Требуются права суперпользователя"
        echo "Запустите: sudo bash $0"
        exit 1
    fi
}

check_os() {
    log "Проверка операционной системы..."
    
    if [ -f /etc/astra_version ]; then
        ASTRA_VERSION=$(cat /etc/astra_version)
        log "Обнаружена Astra Linux: $ASTRA_VERSION"
    elif [ -f /etc/debian_version ]; then
        log "Обнаружен Debian-based система"
    else
        log_warn "Система не определена, но продолжим установку"
    fi
}

#==============================================================================
# Основные компоненты
#==============================================================================

install_base_packages() {
    log_step "[1/8] Установка базовых пакетов"
    
    log "Обновление пакетного менеджера..."
    apt update
    
    log "Установка системных пакетов..."
    
    # Сборка пакетов с проверкой существования
    PACKAGES=(
        python3
        python3-pip
        python3-venv
        git
        curl
        wget
        unzip
        build-essential
        libpcre3
        libpcre3-dev
        zlib1g
        zlib1g-dev
        libssl-dev
        ffmpeg
        htop
        net-tools
    )
    
    INSTALL_LIST=""
    for pkg in "${PACKAGES[@]}"; do
        if check_package "$pkg"; then
            INSTALL_LIST="$INSTALL_LIST $pkg"
        else
            log_warn "Пропуск: $pkg не найден в репозитории"
        fi
    done
    
    if [ -n "$INSTALL_LIST" ]; then
        apt install -y $INSTALL_LIST
    fi
        
    log "Базовые пакеты установлены"
}

build_nginx() {
    log_step "[2/8] Сборка Nginx с RTMP модулем"
    
    NGINX_PREFIX="/usr/local/nginx"
    
    if [ -f "$NGINX_PREFIX/sbin/nginx" ]; then
        log "Nginx уже установлен: $NGINX_PREFIX"
        log "Версия: $($NGINX_PREFIX/sbin/nginx -v 2>&1)"
        return 0
    fi
    
    log "Установка зависимостей для сборки..."
    apt install -y \
        autoconf \
        automake \
        libtool \
        pkg-config
        
    WORK_DIR="/tmp/nginx-build"
    rm -rf "$WORK_DIR"
    mkdir -p "$WORK_DIR"
    cd "$WORK_DIR"
    
    # Скачивание nginx-rtmp модуля
    log "Клонирование nginx-rtmp-module..."
    git clone --depth=1 -b $NGINX_RTMP_BRANCH https://github.com/arut/nginx-rtmp-module.git
    
    # Скачивание nginx
    log "Скачивание Nginx $NGINX_VERSION..."
    wget -q https://nginx.org/download/nginx-$NGINX_VERSION.tar.gz
    tar -xzf nginx-$NGINX_VERSION.tar.gz
    
    cd nginx-$NGINX_VERSION
    
    log "Конфигурация Nginx..."
    ./configure \
        --prefix=$NGINX_PREFIX \
        --with-http_ssl_module \
        --with-http_v2_module \
        --with-http_flv_module \
        --with-http_mp4_module \
        --with-http_gzip_static_module \
        --add-module=../nginx-rtmp-module \
        --with-cc-opt="-Wno-deprecated-declarations"
    
    log "Компиляция Nginx (может занять 5-10 минут)..."
    make -j$(nproc)
    
    log "Установка Nginx..."
    make install
    
    # Очистка
    cd /
    rm -rf "$WORK_DIR"
    
    # Создание пользователя nginx
    id -u nginx &>/dev/null || useradd -r -s /sbin/nologin nginx
    
    log "Nginx установлен: $NGINX_PREFIX"
}

install_python_deps() {
    log_step "[3/8] Установка Python зависимостей"
    
    log "Создание виртуального окружения..."
    mkdir -p /var/www/.venv
    python3 -m venv /var/www/.venv
    
    log "Активация виртуального окружения..."
    source /var/www/.venv/bin/activate
    
    log "Обновление pip..."
    pip install --upgrade pip
    
    log "Установка Python пакетов..."
    pip install \
        flask \
        flask-cors \
        requests \
        openpyxl \
        pandas \
        schedule \
        pillow \
        websockets \
        gunicorn \
        waitress
        
    deactivate
    
    log "Python зависимости установлены"
}

create_directories() {
    log_step "[4/8] Создание каталогов"
    
    log "Создание структуры каталогов..."
    
    mkdir -p /var/www/live-server
    mkdir -p /var/www/reboot
    mkdir -p /var/www/hls
    mkdir -p /var/www/logs
    mkdir -p /var/run/contest_vnc
    mkdir -p /usr/local/nginx/conf/sites-available
    mkdir -p /usr/local/nginx/conf/sites-enabled
    
    # Копирование серверных файлов
    cp "$SCRIPT_DIR/../runtime/live-server/server.py" /var/www/live-server/
    cp "$SCRIPT_DIR/../runtime/reboot/server.py" /var/www/reboot/
    
    # Права доступа
    chown -R www-data:www-data /var/www 2>/dev/null || true
    
    log "Каталоги созданы"
}

install_configs() {
    log_step "[5/8] Установка конфигураций"
    
    log "Копирование конфигурации Nginx..."
    cp "$SCRIPT_DIR/configs/nginx/nginx.conf" /usr/local/nginx/conf/nginx.conf
    
    log "Копирование скриптов..."
    cp "$SCRIPT_DIR/configs/scripts/restart_astra.sh" /var/www/restart_astra.sh
    chmod +x /var/www/restart_astra.sh
    
    ln -sf /usr/local/nginx/conf/nginx.conf /etc/nginx-custom.conf
    
    log "Конфигурации установлены"
}

install_app() {
    log_step "[5.5/8] Установка приложения Astra Monitor"
    
    log "Копирование файлов приложения..."
    mkdir -p "$INSTALL_DIR"
    cp "$SCRIPT_DIR/../astra_monitor.py" "$INSTALL_DIR/"
    cp -r "$SCRIPT_DIR/../src" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/../VERSION" "$INSTALL_DIR/"
    
    log "Установка PyQt5..."
    pip install --break-system-packages PyQt5
    
    log "Приложение установлено"
}

install_services() {
    log_step "[6/8] Установка systemd сервисов"
    
    log "Копирование unit файлов..."
    cp "$SCRIPT_DIR/configs/systemd/"*.service /etc/systemd/system/
    
    log "Перезагрузка systemd..."
    systemctl daemon-reload
    
    log "Включение автозапуска сервисов..."
    systemctl enable nginx-custom.service 2>/dev/null || true
    
    log "Systemd сервисы установлены"
}

install_vnc_stack() {
    log_step "[7/8] Установка VNC стека"
    
    log "Установка VNC пакетов..."
    
    # Базовые VNC пакеты
    VNC_PACKAGES="xvfb openbox x11vnc novnc websockify"
    
    # Chromium
    VNC_PACKAGES="$VNC_PACKAGES chromium"
    
    # Chromium-sandbox если доступен
    if check_package "chromium-sandbox"; then
        VNC_PACKAGES="$VNC_PACKAGES chromium-sandbox"
        log "chromium-sandbox доступен"
    else
        log_warn "chromium-sandbox не найден в репозитории - пропуск"
    fi
    
    apt install -y $VNC_PACKAGES
    
    log "Копирование VNC скриптов..."
    cp "$SCRIPT_DIR/configs/scripts/start_vnc.sh" /var/www/start_vnc.sh
    chmod +x /var/www/start_vnc.sh
    
    # Создание systemd сервиса для VNC
    cat > /etc/systemd/system/vnc-stack.service << 'EOF'
[Unit]
Description=VNC Stack (Xvfb + Chromium)
After=network.target

[Service]
Type=simple
User=root
ExecStart=/var/www/start_vnc.sh
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable vnc-stack.service 2>/dev/null || true
    
    log "VNC стек установлен"
}

start_services() {
    log_step "[8/8] Запуск сервисов"
    
    log "Остановка старого Nginx..."
    /usr/local/nginx/sbin/nginx -s stop 2>/dev/null || pkill -f "nginx.*master" 2>/dev/null || true
    sleep 1
    
    log "Запуск Nginx..."
    /usr/local/nginx/sbin/nginx
    
    log "Сервисы запущены"
}

#==============================================================================
# Проверка работоспособности
#==============================================================================

verify_installation() {
    log_step "ПРОВЕРКА УСТАНОВКИ"
    
    FAILED=0
    
    # Nginx
    log "Проверка Nginx..."
    if pgrep -f "/usr/local/nginx/sbin/nginx" > /dev/null; then
        log "  ✓ Nginx запущен"
    else
        log_error "  ✗ Nginx не запущен"
        FAILED=$((FAILED + 1))
    fi
    
    # Ports
    log "Проверка портов..."
    for port in 80 1935 6080; do
        if netstat -tuln 2>/dev/null | grep -q ":$port " || ss -tuln 2>/dev/null | grep -q ":$port "; then
            log "  ✓ Порт $port открыт"
        else
            log_warn "  - Порт $port не прослушивается"
        fi
    done
    
    # FFmpeg
    log "Проверка FFmpeg..."
    if command -v ffmpeg &> /dev/null; then
        FF_VERSION=$(ffmpeg -version 2>&1 | head -n1)
        log "  ✓ FFmpeg: $FF_VERSION"
    else
        log_error "  ✗ FFmpeg не найден"
        FAILED=$((FAILED + 1))
    fi
    
    # Python venv
    log "Проверка Python окружения..."
    if [ -f /var/www/.venv/bin/activate ]; then
        log "  ✓ Python виртуальное окружение создано"
    else
        log_error "  ✗ Python виртуальное окружение не найдено"
        FAILED=$((FAILED + 1))
    fi
    
    # Каталоги
    log "Проверка каталогов..."
    for dir in /var/www/live-server /var/www/reboot /var/www/hls; do
        if [ -d "$dir" ]; then
            log "  ✓ $dir"
        else
            log_error "  ✗ $dir не создан"
            FAILED=$((FAILED + 1))
        fi
    done
    
    echo ""
    if [ $FAILED -eq 0 ]; then
        log "========================================"
        log "  УСТАНОВКА ЗАВЕРШЕНА УСПЕШНО!"
        log "========================================"
        return 0
    else
        log_error "Установка завершена с $FAILED ошибками"
        return 1
    fi
}

#==============================================================================
# Главная функция
#==============================================================================

main() {
    echo ""
    echo "========================================"
    echo "  Astra Monitor - Установщик сервера"
    echo "  Версия: 2.0"
    echo "========================================"
    echo ""
    
    check_root
    check_os
    
    # Создание лог файла
    mkdir -p "$(dirname "$LOG_FILE")"
    touch "$LOG_FILE"
    
    # Установка компонентов
    install_base_packages
    build_nginx
    install_python_deps
    create_directories
    install_configs
    install_app
    install_services
    install_vnc_stack
    start_services
    
    # Проверка
    verify_installation
    
    echo ""
    echo "Для запуска панели управления:"
    echo "  python3 /opt/astra-monitor/astra_monitor.py"
    echo ""
}

# Запуск
main "$@"