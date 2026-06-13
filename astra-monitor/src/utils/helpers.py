#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Утилиты для Astra Monitor
"""

import os
import subprocess
from pathlib import Path


def is_root() -> bool:
    """Проверить запущен ли от root"""
    return os.geteuid() == 0


def require_root():
    """Проверить права root и выйти если их нет"""
    if not is_root():
        print("Ошибка: требуются права суперпользователя (root)")
        print("Запустите с: sudo astra-monitor")
        sys.exit(1)


def check_dependency(package: str) -> bool:
    """Проверить установлен ли пакет"""
    try:
        result = subprocess.run(
            ['dpkg', '-s', package],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except:
        return False


def install_dependencies() -> bool:
    """Установить необходимые зависимости"""
    required_packages = [
        'python3-pip',
        'python3-venv',
        'python3-pyqt5',
        'python3-psutil',
        'gir1.2-gtk-3.0',
    ]
    
    try:
        print("Обновление списка пакетов...")
        subprocess.run(['apt', 'update'], check=True)
        
        print("Установка зависимостей...")
        for package in required_packages:
            print(f"  Установка {package}...")
            subprocess.run(['apt', 'install', '-y', package], check=True)
        
        print("Установка Python пакетов...")
        subprocess.run([
            'pip3', 'install', '--user', 'psutil', 'requests'
        ], check=True)
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"Ошибка установки: {e}")
        return False
    except FileNotFoundError:
        print("Ошибка: не найден менеджер пакетов (apt)")
        return False


def get_resource_path(filename: str) -> str:
    """Получить путь к ресурсу приложения"""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(os.path.dirname(__file__), filename)


def ensure_directories():
    """Создать необходимые директории"""
    dirs = [
        '/var/www',
        '/var/log',
        '/var/run',
    ]
    
    for d in dirs:
        os.makedirs(d, exist_ok=True)


def get_desktop_entry() -> str:
    """Получить содержимое desktop файла"""
    return """[Desktop Entry]
Version=1.0
Type=Application
Name=Astra Monitor
Comment=Система мониторинга и управления сайтом
Exec=/usr/bin/astra-monitor
Icon=computer
Terminal=false
Categories=System;Monitor;
Keywords=monitor;system;admin;astra;
"""


def get_systemd_service() -> str:
    """Получить содержимое systemd сервиса"""
    return """[Unit]
Description=Astra Monitor Service
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 /opt/astra-monitor/astra_monitor.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
"""


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'install-deps':
        install_dependencies()
    elif len(sys.argv) > 1 and sys.argv[1] == 'check-deps':
        all_ok = True
        for pkg in ['python3-pyqt5', 'python3-psutil']:
            if not check_dependency(pkg):
                print(f"Отсутствует: {pkg}")
                all_ok = False
        if all_ok:
            print("Все зависимости установлены")
        sys.exit(0 if all_ok else 1)