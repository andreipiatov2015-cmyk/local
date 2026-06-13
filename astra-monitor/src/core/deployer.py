#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль деплоя - установка и настройка сайта на сервер
"""

import os
import re
import subprocess
import shutil
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable
from enum import Enum
from datetime import datetime


class DeployStatus(Enum):
    """Статус развёртывания"""
    IDLE = "idle"
    CHECKING = "checking"
    INSTALLING = "installing"
    CONFIGURING = "configuring"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class DeployStep:
    """Шаг установки"""
    name: str
    description: str
    status: DeployStatus
    command: str = ""
    output: str = ""
    error: str = ""
    checked: bool = False


@dataclass
class DeployResult:
    """Результат деплоя"""
    success: bool
    steps: List[DeployStep]
    message: str
    error_steps: List[str] = field(default_factory=list)


class SiteDeployer:
    """Класс для развёртывания сайта на сервере"""
    
    SITE_DIR = "/var/www"
    SITE_FILES_DIR = "/var/www/www"
    NGINX_DIR = "/etc/nginx/sites-available"
    NGINX_ENABLED = "/etc/nginx/sites-enabled"
    SYSTEMD_DIR = "/etc/systemd/system"
    
    # Возможные пути к сайту
    POSSIBLE_SITE_PATHS = [
        "/var/www",
        "/var/www/www",
        "/home/www",
        "/srv/www",
        "/opt/www",
    ]
    
    # Признаки установленного сайта
    SITE_MARKERS = [
        "live-server",
        "reboot",
        "server.py",
        "app.py",
        "flask_app",
        "www",
    ]
    
    REQUIRED_PACKAGES = [
        'nginx',
        'python3',
        'python3-pip',
        'python3-venv',
        'python3-dev',
        'ffmpeg',
        'git',
        'curl',
        'wget',
        'unzip',
    ]
    
    PYTHON_PACKAGES = [
        'flask',
        'requests',
        'psutil',
        'openpyxl',
    ]
    
    def __init__(self, site_source: str = None, progress_callback: Callable = None):
        self.site_source = site_source
        self.progress_callback = progress_callback
        self.steps_history = []
        self._site_path = None  # Кэш найденного пути
    
    def find_site_path(self) -> Optional[str]:
        """Найти путь к установленному сайту автоматически"""
        if self._site_path:
            return self._site_path
        
        # Проверяем все возможные пути
        for path in self.POSSIBLE_SITE_PATHS:
            if self._is_site_path(path):
                self._site_path = path
                return path
        
        # Ищем в домашних директориях
        home_paths = [
            os.path.expanduser("~/www"),
            os.path.expanduser("~/site"),
            os.path.expanduser("~/website"),
            os.path.expanduser("~/Desktop/www"),
            os.path.expanduser("~/Desktop/site"),
        ]
        
        for path in home_paths:
            if self._is_site_path(path):
                self._site_path = path
                return path
        
        return None
    
    def _is_site_path(self, path: str) -> bool:
        """Проверить является ли путь директорией сайта"""
        if not os.path.exists(path):
            return False
        
        # Проверяем наличие признаков сайта
        for marker in self.SITE_MARKERS:
            if marker in os.listdir(path):
                return True
        
        # Проверяем наличие Python файлов
        for root, dirs, files in os.walk(path):
            for f in files:
                if f.endswith('.py'):
                    return True
                if f == 'package.json':
                    return True
        
        return False
    
    def get_site_path(self) -> str:
        """Получить путь к сайту (найденный или заданный)"""
        if self.site_source:
            return self.site_source
        found = self.find_site_path()
        return found or self.SITE_DIR
    
    def _report(self, message: str, step: str = None):
        """Сообщить о прогрессе"""
        if self.progress_callback:
            self.progress_callback(message, step)
        print(f"[DEPLOY] {message}")
    
    def check_system(self) -> tuple:
        """Проверить систему и зависимости"""
        self._report("Проверка системы...")
        
        missing = []
        
        # Проверка пакетов
        for pkg in self.REQUIRED_PACKAGES:
            result = subprocess.run(
                ['dpkg', '-s', pkg],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                missing.append(pkg)
        
        # Проверка Python
        try:
            result = subprocess.run(
                ['python3', '--version'],
                capture_output=True,
                text=True
            )
            python_version = result.stdout.strip()
        except:
            python_version = "не найден"
        
        # Проверка Astra Linux
        is_astra = os.path.exists('/etc/astra/version')
        os_info = "Astra Linux" if is_astra else "Другой Linux"
        
        # Проверка прав root
        is_root = os.geteuid() == 0
        
        info = {
            'os': os_info,
            'is_astra': is_astra,
            'python_version': python_version,
            'is_root': is_root,
            'missing_packages': missing,
            'can_deploy': is_root and len(missing) == 0
        }
        
        self._report(f"ОС: {os_info}, Python: {python_version}, Root: {is_root}")
        
        return len(missing) == 0, info
    
    def install_dependencies(self) -> DeployStep:
        """Установить системные зависимости"""
        step = DeployStep(
            name="dependencies",
            description="Установка системных зависимостей",
            status=DeployStatus.CHECKING
        )
        
        self._report("Установка зависимостей...", step.name)
        
        try:
            # Обновление apt
            step.command = "apt update"
            result = subprocess.run(
                ['apt', 'update'],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                step.error = result.stderr
                step.status = DeployStatus.FAILED
                return step
            
            # Установка пакетов
            for pkg in self.REQUIRED_PACKAGES:
                self._report(f"Установка {pkg}...", step.name)
                result = subprocess.run(
                    ['apt', 'install', '-y', pkg],
                    capture_output=True,
                    text=True,
                    timeout=180
                )
                
                if result.returncode != 0 and 'already installed' not in result.stderr.lower():
                    step.error += f"\n{pkg}: {result.stderr[:200]}"
            
            # Установка Python пакетов
            self._report("Установка Python пакетов...", step.name)
            for pkg in self.PYTHON_PACKAGES:
                subprocess.run(
                    ['pip3', 'install', '--break-system-packages', pkg],
                    capture_output=True,
                    timeout=60
                )
            
            step.status = DeployStatus.SUCCESS
            step.output = "Все зависимости установлены"
            self._report("✓ Зависимости установлены", step.name)
            
        except subprocess.TimeoutExpired:
            step.status = DeployStatus.FAILED
            step.error = "Таймаут установки"
        except Exception as e:
            step.status = DeployStatus.FAILED
            step.error = str(e)
        
        return step
    
    def create_directories(self) -> DeployStep:
        """Создать необходимые директории"""
        step = DeployStep(
            name="directories",
            description="Создание директорий",
            status=DeployStatus.CHECKING
        )
        
        self._report("Создание директорий...", step.name)
        
        directories = [
            self.SITE_DIR,
            self.SITE_FILES_DIR,
            "/var/www/hls",
            "/var/www/live-server",
            "/var/www/reboot",
            "/var/log/live-server",
            "/var/mount_point/nfv/contest_storage",
            "/var/run/contest_vnc",
        ]
        
        try:
            for d in directories:
                os.makedirs(d, exist_ok=True)
                self._report(f"Создана: {d}", step.name)
            
            step.status = DeployStatus.SUCCESS
            step.output = f"Создано {len(directories)} директорий"
            
        except Exception as e:
            step.status = DeployStatus.FAILED
            step.error = str(e)
        
        return step
    
    def copy_site_files(self) -> DeployStep:
        """Копировать файлы сайта"""
        step = DeployStep(
            name="files",
            description="Копирование файлов сайта",
            status=DeployStatus.CHECKING
        )
        
        self._report("Копирование файлов сайта...", step.name)
        
        try:
            # Проверка источника
            source_www = os.path.join(self.site_source, "www")
            if not os.path.exists(source_www):
                source_www = self.site_source
            
            # Копирование
            if os.path.exists(source_www):
                for item in os.listdir(source_www):
                    src = os.path.join(source_www, item)
                    dst = os.path.join(self.SITE_DIR, item)
                    
                    if item.startswith('.') or item == '__pycache__':
                        continue
                    
                    if os.path.isdir(src):
                        if os.path.exists(dst):
                            shutil.rmtree(dst)
                        shutil.copytree(src, dst)
                        self._report(f"Скопирована директория: {item}", step.name)
                    else:
                        shutil.copy2(src, dst)
                        self._report(f"Скопирован файл: {item}", step.name)
            
            # Установка прав
            subprocess.run(['chmod', '-R', '755', self.SITE_DIR], check=False)
            subprocess.run(['chown', '-R', 'www-data:www-data', self.SITE_DIR], check=False)
            
            step.status = DeployStatus.SUCCESS
            step.output = "Файлы скопированы"
            
        except Exception as e:
            step.status = DeployStatus.FAILED
            step.error = str(e)
        
        return step
    
    def setup_nginx(self) -> DeployStep:
        """Настроить Nginx"""
        step = DeployStep(
            name="nginx",
            description="Настройка Nginx",
            status=DeployStatus.CHECKING
        )
        
        self._report("Настройка Nginx...", step.name)
        
        nginx_config = """server {
    listen 80;
    server_name _;
    
    client_max_body_size 100M;
    
    location / {
        proxy_pass http://127.0.0.1:8083;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 3600;
        proxy_connect_timeout 3600;
        proxy_send_timeout 3600;
    }
    
    location /hls {
        alias /var/www/hls;
        types {
            application/vnd.apple.mpegurl m3u8;
            video/mp2t ts;
        }
        add_header Cache-Control no-cache;
        add_header 'Access-Control-Allow-Origin' '*';
    }
    
    location /tables/yandex/vnc/ {
        proxy_pass http://127.0.0.1:6080/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600;
        proxy_send_timeout 3600;
    }
}
"""
        
        try:
            # Запись конфига
            config_path = os.path.join(self.NGINX_DIR, "contest-site")
            with open(config_path, 'w') as f:
                f.write(nginx_config)
            
            # Включение сайта
            enabled_path = os.path.join(self.NGINX_ENABLED, "contest-site")
            if os.path.exists(enabled_path):
                os.remove(enabled_path)
            os.symlink(config_path, enabled_path)
            
            # Тест и перезагрузка
            result = subprocess.run(
                ['nginx', '-t'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                subprocess.run(['systemctl', 'reload', 'nginx'], check=False)
                step.status = DeployStatus.SUCCESS
                step.output = "Nginx настроен"
            else:
                step.status = DeployStatus.FAILED
                step.error = result.stderr
            
        except Exception as e:
            step.status = DeployStatus.FAILED
            step.error = str(e)
        
        return step
    
    def setup_nginx_rtmp(self) -> DeployStep:
        """Установить и настроить Nginx с RTMP"""
        step = DeployStep(
            name="nginx_rtmp",
            description="Установка Nginx RTMP",
            status=DeployStatus.CHECKING
        )
        
        self._report("Установка Nginx RTMP...", step.name)
        
        # Проверка наличия RTMP модуля
        result = subprocess.run(
            ['nginx', '-V'],
            capture_output=True,
            text=True
        )
        
        has_rtmp = '--with-rtmp-module' in result.stderr or os.path.exists('/usr/local/nginx')
        
        if has_rtmp:
            step.status = DeployStatus.SKIPPED
            step.output = "Nginx RTMP уже установлен"
            return step
        
        try:
            # Установка зависимостей для сборки
            self._report("Установка инструментов сборки...", step.name)
            subprocess.run([
                'apt', 'install', '-y',
                'build-essential', 'libpcre3', 'libpcre3-dev',
                'libssl-dev', 'zlib1g-dev', 'git'
            ], timeout=120, check=False)
            
            # Клонирование RTMP модуля
            rtmp_dir = "/usr/local/src/nginx-rtmp-module"
            if not os.path.exists(rtmp_dir):
                self._report("Клонирование nginx-rtmp-module...", step.name)
                subprocess.run([
                    'git', 'clone',
                    'https://github.com/arut/nginx-rtmp-module.git',
                    rtmp_dir
                ], timeout=60, check=False)
            
            # Клонирование nginx
            nginx_version = "1.24.0"
            nginx_src = f"/usr/local/src/nginx-{nginx_version}"
            if not os.path.exists(nginx_src):
                self._report(f"Загрузка nginx-{nginx_version}...", step.name)
                subprocess.run([
                    'wget', '-q',
                    f'http://nginx.org/download/nginx-{nginx_version}.tar.gz',
                    '-O', f'/tmp/nginx-{nginx_version}.tar.gz'
                ], timeout=60, check=False)
                
                subprocess.run([
                    'tar', '-xzf', f'/tmp/nginx-{nginx_version}.tar.gz',
                    '-C', '/usr/local/src'
                ], check=False)
            
            # Сборка
            self._report("Сборка Nginx...", step.name)
            result = subprocess.run([
                './configure',
                '--prefix=/usr/local/nginx',
                '--with-http_ssl_module',
                '--with-http_stub_status_module',
                f'--add-module={rtmp_dir}'
            ], cwd=nginx_src, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                subprocess.run(['make'], cwd=nginx_src, timeout=300, check=False)
                subprocess.run(['make', 'install'], cwd=nginx_src, timeout=120, check=False)
                
                step.status = DeployStatus.SUCCESS
                step.output = "Nginx RTMP собран"
            else:
                step.status = DeployStatus.SKIPPED
                step.output = "Сборка пропущена (требует ручной настройки)"
            
        except Exception as e:
            step.status = DeployStatus.SKIPPED
            step.error = f"Пропущено: {e}"
        
        return step
    
    def create_systemd_services(self) -> List[DeployStep]:
        """Создать systemd сервисы"""
        steps = []
        
        services = [
            {
                'name': 'live-server',
                'description': 'Flask live-server application',
                'exec_start': '/usr/bin/python3 /var/www/live-server/server.py',
                'working_dir': '/var/www/live-server',
            },
            {
                'name': 'reboot-server',
                'description': 'Flask reboot-server application',
                'exec_start': '/usr/bin/python3 /var/www/reboot/server.py',
                'working_dir': '/var/www/reboot',
            }
        ]
        
        for svc in services:
            step = DeployStep(
                name=f"service_{svc['name']}",
                description=f"Создание сервиса {svc['name']}",
                status=DeployStatus.CHECKING
            )
            
            self._report(f"Создание сервиса {svc['name']}...", step.name)
            
            service_content = f"""[Unit]
Description={svc['description']}
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory={svc['working_dir']}
ExecStart={svc['exec_start']}
Restart=on-failure
RestartSec=10
StandardOutput=append:/var/log/live-server/{svc['name']}.log
StandardError=append:/var/log/live-server/{svc['name']}.log

[Install]
WantedBy=multi-user.target
"""
            
            try:
                service_path = os.path.join(self.SYSTEMD_DIR, f"{svc['name']}.service")
                with open(service_path, 'w') as f:
                    f.write(service_content)
                
                subprocess.run(['systemctl', 'daemon-reload'], check=False)
                
                step.status = DeployStatus.SUCCESS
                step.output = f"Сервис создан"
                
            except Exception as e:
                step.status = DeployStatus.FAILED
                step.error = str(e)
            
            steps.append(step)
        
        return steps
    
    def deploy(self) -> DeployResult:
        """Выполнить полное развёртывание"""
        self._report("=== Начало развёртывания ===")
        
        steps = []
        error_steps = []
        
        # 1. Проверка системы
        can_deploy, sys_info = self.check_system()
        if not can_deploy:
            if not sys_info['is_root']:
                return DeployResult(False, [], "Требуются права root", ["root_required"])
            if sys_info['missing_packages']:
                self._report(f"Отсутствуют пакеты: {sys_info['missing_packages']}")
        
        # 2. Установка зависимостей
        step = self.install_dependencies()
        steps.append(step)
        if step.status == DeployStatus.FAILED:
            error_steps.append(step.name)
        
        # 3. Создание директорий
        step = self.create_directories()
        steps.append(step)
        if step.status == DeployStatus.FAILED:
            error_steps.append(step.name)
        
        # 4. Копирование файлов
        step = self.copy_site_files()
        steps.append(step)
        if step.status == DeployStatus.FAILED:
            error_steps.append(step.name)
        
        # 5. Настройка Nginx
        step = self.setup_nginx()
        steps.append(step)
        if step.status == DeployStatus.FAILED:
            error_steps.append(step.name)
        
        # 6. Настройка Nginx RTMP
        step = self.setup_nginx_rtmp()
        steps.append(step)
        if step.status == DeployStatus.FAILED:
            error_steps.append(step.name)
        
        # 7. Systemd сервисы
        service_steps = self.create_systemd_services()
        steps.extend(service_steps)
        for s in service_steps:
            if s.status == DeployStatus.FAILED:
                error_steps.append(s.name)
        
        # Итоговый результат
        success = len(error_steps) == 0
        
        result = DeployResult(
            success=success,
            steps=steps,
            message="Развёртывание завершено" if success else f"Ошибки в шагах: {', '.join(error_steps)}",
            error_steps=error_steps
        )
        
        self._report(f"=== Развёртывание {'успешно' if success else 'завершено с ошибками'} ===")
        
        return result
    
    def start_services(self) -> tuple:
        """Запустить все сервисы сайта"""
        self._report("Запуск сервисов...")
        
        errors = []
        
        # Restart script
        restart_script = os.path.join(self.SITE_DIR, "restart_astra.sh")
        if os.path.exists(restart_script):
            result = subprocess.run(
                ['/bin/bash', restart_script],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode != 0:
                errors.append(f"restart_astra.sh: {result.stderr[:200]}")
        
        # Systemd services
        services = ['live-server.service', 'reboot-server.service']
        for svc in services:
            subprocess.run(['systemctl', 'enable', svc], check=False)
            result = subprocess.run(['systemctl', 'restart', svc], capture_output=True)
            if result.returncode != 0:
                errors.append(f"{svc}: {result.stderr[:100]}")
        
        return len(errors) == 0, errors
    
    def stop_services(self) -> tuple:
        """Остановить все сервисы сайта"""
        self._report("Остановка сервисов...")
        
        services = ['live-server.service', 'reboot-server.service']
        for svc in services:
            subprocess.run(['systemctl', 'stop', svc], check=False)
        
        # kill python processes
        subprocess.run(['pkill', '-f', 'server.py'], check=False)
        
        return True, []
    
    def restart_services(self) -> tuple:
        """Перезапустить все сервисы"""
        self._report("Перезапуск сервисов...")
        
        self.stop_services()
        return self.start_services()
    
    def get_deploy_status(self) -> Dict:
        """Получить статус развёртывания"""
        # Автоматически ищем путь к сайту
        site_path = self.find_site_path()
        
        status = {
            'deployed': site_path is not None,
            'site_path': site_path,
            'site_files': site_path is not None and os.path.exists(os.path.join(site_path, 'live-server')),
            'nginx_configured': os.path.exists(os.path.join(self.NGINX_DIR, 'contest-site')),
            'services_exist': os.path.exists(os.path.join(self.SYSTEMD_DIR, 'live-server.service')),
            'directories_ready': os.path.exists(self.SITE_DIR),
        }
        status['ready'] = all(status.values())
        return status