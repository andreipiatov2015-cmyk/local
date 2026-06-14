#!/bin/bash
#==============================================================================
# Astra Monitor - Обновление приложения
# ВНИМАНИЕ: НЕ переустанавливает системные компоненты!
#==============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_err() { echo -e "${RED}[ERR]${NC} $1"; }

REPO_URL="https://github.com/andreipiatov2015-cmyk/local.git"
TEMP_DIR="/tmp/astra-monitor-update"
BACKUP_DIR="/var/www/.backup-astra"
CURRENT_VERSION="1.0.0"

#==============================================================================
# Проверки
#==============================================================================

check_prerequisites() {
    log "Проверка предварительных условий..."
    
    # Проверка git
    if ! command -v git &> /dev/null; then
        log_err "Git не установлен. Используйте installer для установки."
        exit 1
    fi
    
    # Проверка что это не installer машина
    if [ ! -d "/var/www" ]; then
        log_err "/var/www не существует. Используйте installer для первичной установки."
        exit 1
    fi
    
    log "Проверки пройдены"
}

#==============================================================================
# Backup
#==============================================================================

create_backup() {
    log "Создание резервной копии..."
    
    rm -rf "$BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
    
    # Backup пользовательских данных
    for file in app.db presets.json entries.json; do
        if [ -f "/var/www/$file" ]; then
            cp "/var/www/$file" "$BACKUP_DIR/"
            log "Сохранено: $file"
        fi
    done
    
    # Backup конфигураций приложения
    for dir in live-server reboot; do
        if [ -d "/var/www/$dir" ]; then
            cp -r "/var/www/$dir" "$BACKUP_DIR/" 2>/dev/null || true
        fi
    done
    
    log "Резервная копия создана: $BACKUP_DIR"
}

restore_backup() {
    log "Восстановление из резервной копии..."
    
    if [ ! -d "$BACKUP_DIR" ]; then
        log_err "Резервная копия не найдена"
        return 1
    fi
    
    # Восстановление пользовательских данных
    for file in app.db presets.json entries.json; do
        if [ -f "$BACKUP_DIR/$file" ]; then
            cp "$BACKUP_DIR/$file" "/var/www/"
            log "Восстановлено: $file"
        fi
    done
    
    log "Восстановление завершено"
}

#==============================================================================
# Обновление
#==============================================================================

clone_update() {
    log "Клонирование обновления в $TEMP_DIR..."
    
    rm -rf "$TEMP_DIR"
    mkdir -p "$TEMP_DIR"
    
    git clone --depth=1 "$REPO_URL" "$TEMP_DIR" 2>/dev/null || \
    git clone "$REPO_URL" "$TEMP_DIR"
    
    log "Репозиторий клонирован"
}

copy_app_files() {
    log "Копирование файлов приложения..."
    
    local source_dir="$TEMP_DIR/astra-monitor"
    
    if [ ! -d "$source_dir" ]; then
        log_err "Папка astra-monitor не найдена в репозитории"
        exit 1
    fi
    
    # Копирование файлов приложения
    cp -r "$source_dir/src" /var/www/live-server/ 2>/dev/null || true
    cp -r "$source_dir/src" /var/www/reboot/ 2>/dev/null || true
    
    # Копирование GUI
    mkdir -p /opt/astra-monitor
    cp -r "$source_dir"/* /opt/astra-monitor/
    
    log "Файлы скопированы"
}

restart_app_services() {
    log "Перезапуск сервисов приложения..."
    
    # Только приложения, НЕ системные сервисы
    systemctl restart live-server 2>/dev/null || true
    systemctl restart reboot-server 2>/dev/null || true
    
    log "Сервисы перезапущены"
}

cleanup() {
    log "Очистка..."
    rm -rf "$TEMP_DIR"
    log "Очистка завершена"
}

#==============================================================================
# Основная функция
#==============================================================================

main() {
    echo ""
    echo "========================================"
    echo "  Astra Monitor - Обновление"
    echo "========================================"
    echo ""
    
    check_prerequisites
    
    # Backup
    create_backup
    
    # Обновление с обработкой ошибок
    if clone_update && copy_app_files; then
        restart_app_services
        cleanup
        
        echo ""
        log "========================================"
        log "  ОБНОВЛЕНИЕ ЗАВЕРШЕНО!"
        log "========================================"
        echo ""
    else
        log_err "Ошибка обновления!"
        log "Восстановление из резервной копии..."
        restore_backup
        exit 1
    fi
}

main "$@"