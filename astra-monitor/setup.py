#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт установки Astra Monitor на Astra Linux
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path


# Цвета для терминала
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_step(msg: str):
    print(f"\n{Colors.HEADER}{Colors.BOLD}>>> {msg}{Colors.ENDC}")


def print_success(msg: str):
    print(f"{Colors.OKGREEN}✓ {msg}{Colors.ENDC}")


def print_error(msg: str):
    print(f"{Colors.FAIL}✗ {msg}{Colors.ENDC}")


def print_warning(msg: str):
    print(f"{Colors.WARNING}⚠ {msg}{Colors.ENDC}")


def run_cmd(cmd: list, check: bool = True, timeout: int = 300) -> subprocess.CompletedProcess:
    """Выполнить команду"""
    print(f"  Выполняется: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=check
        )
        if result.stdout:
            for line in result.stdout.split('\n')[:5]:
                if line.strip():
                    print(f"    {line[:80]}")
        return result
    except subprocess.CalledProcessError as e:
        print_error(f"Команда завершилась с кодом {e.returncode}")
        if e.stderr:
            print(f"    {e.stderr[:200]}")
        if check:
            raise
        return e
    except subprocess.TimeoutExpired:
        print_error("Таймаут выполнения команды")
        raise


def check_root():
    """Проверить права root"""
    if os.geteuid() != 0:
        print_error("Требуются права суперпользователя!")
        print(f"Запустите: sudo {sys.argv[0]}")
        sys.exit(1)


def check_dependencies():
    """Проверить зависимости"""
    print_step("Проверка зависимостей...")
    
    required = {
        'python3': 'python3',
        'pip3': 'python3-pip',
        'pyqt5': 'python3-pyqt5',
        'psutil': 'python3-psutil',
    }
    
    missing = []
    
    for name, package in required.items():
        try:
            if name == 'pyqt5':
                result = subprocess.run(
                    ['python3', '-c', 'import PyQt5'],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode != 0:
                    missing.append(package)
            elif name == 'psutil':
                result = subprocess.run(
                    ['python3', '-c', 'import psutil'],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode != 0:
                    missing.append(package)
            else:
                result = subprocess.run(
                    ['which', name],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode != 0:
                    missing.append(package)
        except:
            missing.append(package)
    
    if missing:
        print_warning(f"Отсутствуют пакеты: {', '.join(missing)}")
        response = input("Установить автоматически? (y/n): ").strip().lower()
        if response == 'y':
            install_packages(missing)
        else:
            print_error("Невозможно продолжить без зависимостей")
            return False
    
    print_success("Все зависимости установлены")
    return True


def install_packages(packages: list):
    """Установить пакеты"""
    print_step("Установка системных пакетов...")
    
    try:
        run_cmd(['apt', 'update'])
        
        for pkg in packages:
            run_cmd(['apt', 'install', '-y', pkg])
        
        print_success("Пакеты установлены")
    except Exception as e:
        print_error(f"Ошибка установки пакетов: {e}")
        raise


def install_python_packages():
    """Установить Python пакеты через pip"""
    print_step("Установка Python пакетов...")
    
    packages = ['psutil', 'requests']
    
    for pkg in packages:
        try:
            run_cmd(['pip3', 'install', '--break-system-packages', pkg])
            print_success(f"{pkg} установлен")
        except:
            # Fallback
            try:
                run_cmd(['pip3', 'install', '--user', pkg])
                print_success(f"{pkg} установлен (--user)")
            except Exception as e:
                print_warning(f"Не удалось установить {pkg}: {e}")


def copy_application():
    """Копировать приложение"""
    print_step("Установка приложения...")
    
    install_dir = Path('/opt/astra-monitor')
    bin_dir = Path('/usr/bin')
    desktop_dir = Path('/usr/share/applications')
    
    # Создать директории
    install_dir.mkdir(parents=True, exist_ok=True)
    
    # Копировать файлы
    source_dir = Path(__file__).parent
    print(f"  Копирование из {source_dir}...")
    
    for item in ['src', 'astra_monitor.py', 'setup.py']:
        src = source_dir / item
        dst = install_dir / item
        if src.exists():
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
            print(f"  Скопировано: {item}")
    
    # Сделать главный файл исполняемым
    main_file = install_dir / 'astra_monitor.py'
    main_file.chmod(0o755)
    
    # Создать символическую ссылку
    link = bin_dir / 'astra-monitor'
    if link.exists():
        link.unlink()
    link.symlink_to(main_file)
    print_success(f"Создана ссылка: {link}")
    
    # Создать desktop файл
    desktop_file = desktop_dir / 'astra-monitor.desktop'
    desktop_content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name=Astra Monitor
GenericName=System Monitor
Comment=Система мониторинга и управления сайтом для Astra Linux
Exec=/usr/bin/astra-monitor
Icon=computer
Terminal=false
Categories=System;Monitor;Networking;
Keywords=monitor;system;admin;astra;website;
StartupNotify=true
StartupWMClass=astra-monitor
"""
    
    with open(desktop_file, 'w') as f:
        f.write(desktop_content)
    desktop_file.chmod(0o644)
    print_success(f"Создан desktop файл: {desktop_file}")
    
    # Обновить кэш рабочего стола
    try:
        run_cmd(['update-desktop-database', str(desktop_dir)], check=False)
    except:
        pass


def create_uninstaller():
    """Создать скрипт удаления"""
    print_step("Создание скрипта удаления...")
    
    uninstall_content = """#!/bin/bash
# Скрипт удаления Astra Monitor

if [ "$EUID" -ne 0 ]; then
    echo "Требуются права root"
    exit 1
fi

echo "Удаление Astra Monitor..."

# Удаление файлов
rm -rf /opt/astra-monitor
rm -f /usr/bin/astra-monitor
rm -f /usr/share/applications/astra-monitor.desktop

# Обновить кэш
update-desktop-database /usr/share/applications 2>/dev/null

echo "Astra Monitor удалён"
"""
    
    uninstall_file = Path('/opt/astra-monitor/uninstall.sh')
    with open(uninstall_file, 'w') as f:
        f.write(uninstall_content)
    uninstall_file.chmod(0o755)
    print_success(f"Создан скрипт удаления: {uninstall_file}")


def verify_installation():
    """Проверить установку"""
    print_step("Проверка установки...")
    
    checks = [
        ('/opt/astra-monitor/astra_monitor.py', 'Основной файл'),
        ('/opt/astra-monitor/src/core', 'Модули'),
        ('/usr/bin/astra-monitor', 'Исполняемый файл'),
        ('/usr/share/applications/astra-monitor.desktop', 'Desktop файл'),
    ]
    
    all_ok = True
    for path, desc in checks:
        if Path(path).exists():
            print_success(f"{desc}: {path}")
        else:
            print_error(f"{desc}: {path} - НЕ НАЙДЕН")
            all_ok = False
    
    return all_ok


def main():
    """Главная функция установки"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}")
    print("=" * 50)
    print("   Astra Monitor - Установщик")
    print("   Система мониторинга для Astra Linux")
    print("=" * 50)
    print(f"{Colors.ENDC}\n")
    
    try:
        check_root()
        
        # Проверка зависимостей
        if not check_dependencies():
            sys.exit(1)
        
        # Установка Python пакетов
        install_python_packages()
        
        # Копирование приложения
        copy_application()
        
        # Создание деинсталлятора
        create_uninstaller()
        
        # Проверка
        if verify_installation():
            print(f"\n{Colors.OKGREEN}{Colors.BOLD}")
            print("=" * 50)
            print("   Установка завершена успешно!")
            print("=" * 50)
            print(f"{Colors.ENDC}")
            print("\nЗапуск:")
            print("  astra-monitor")
            print("\nИли через меню приложений.")
        else:
            print_error("Установка завершена с предупреждениями")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\nУстановка прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print_error(f"Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()