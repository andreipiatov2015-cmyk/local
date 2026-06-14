#!/bin/bash
#==============================================================================
# Astra Monitor - Установка VNC стека
#==============================================================================

set -e

if [ "$EUID" -ne 0 ]; then
    echo "Требуются права root"
    exit 1
fi

echo "Установка VNC стека..."

# Проверка существования пакета
check_package() {
    apt-cache show "$1" >/dev/null 2>&1
}

# Установка базовых VNC пакетов
VNC_PACKAGES="xvfb openbox x11vnc novnc websockify"

# Добавить chromium
VNC_PACKAGES="$VNC_PACKAGES chromium"

# Добавить chromium-sandbox если доступен
if check_package "chromium-sandbox"; then
    VNC_PACKAGES="$VNC_PACKAGES chromium-sandbox"
    echo "chromium-sandbox доступен - будет установлен"
else
    echo "chromium-sandbox не найден - пропуск"
fi

apt install -y $VNC_PACKAGES

# Копирование скрипта запуска
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/configs/scripts/start_vnc.sh" ]; then
    cp "$SCRIPT_DIR/configs/scripts/start_vnc.sh" /var/www/start_vnc.sh
    chmod +x /var/www/start_vnc.sh
fi

# Создание systemd сервиса
cat > /etc/systemd/system/vnc-stack.service << 'EOF'
[Unit]
Description=Astra Monitor - VNC Stack
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
systemctl enable vnc-stack.service

echo ""
echo "VNC стек установлен"
echo "Для запуска: systemctl start vnc-stack"
echo "Или: /var/www/start_vnc.sh"