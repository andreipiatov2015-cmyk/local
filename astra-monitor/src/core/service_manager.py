#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль управления сервисами - start/stop/restart для сайта
"""

import os
import subprocess
import signal
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


class ServiceState(Enum):
    """Состояние сервиса"""
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class ServiceInfo:
    """Информация о сервисе"""
    name: str
    display_name: str
    state: ServiceState
    pid: int = 0
    port: int = 0
    description: str = ""
    has_systemd: bool = False
    uptime: str = ""


class ServiceManager:
    """Класс управления сервисами сайта"""
    
    SERVICES = {
        'nginx': {
            'display_name': 'Nginx',
            'description': 'Веб-сервер',
            'port': 80,
            'systemd': 'nginx.service'
        },
        'nginx_rtmp': {
            'display_name': 'Nginx RTMP',
            'description': 'RTMP стриминг сервер',
            'port': 1935,
            'systemd': None,
            'binary': '/usr/local/nginx/sbin/nginx'
        },
        'live_server': {
            'display_name': 'Live Server',
            'description': 'Основное Flask приложение',
            'port': 8083,
            'systemd': 'live-server.service',
            'process': 'server.py',
            'path': '/var/www/live-server'
        },
        'reboot_server': {
            'display_name': 'Reboot Server',
            'description': 'Сервер управления трансляциями',
            'port': 8084,
            'systemd': 'reboot-server.service',
            'process': 'server.py',
            'path': '/var/www/reboot'
        },
        'vk_pusher': {
            'display_name': 'VK Pusher',
            'description': 'Ретрансляция в VK',
            'systemd': None,
            'process': 'start_vk.py',
            'path': '/var/www/live-server'
        },
        'xvfb': {
            'display_name': 'Xvfb',
            'description': 'Виртуальный дисплей',
            'systemd': None,
            'process': 'Xvfb'
        },
        'chromium': {
            'display_name': 'Chromium',
            'description': 'Браузер для Яндекс',
            'systemd': None,
            'process': 'chromium'
        },
        'x11vnc': {
            'display_name': 'x11vnc',
            'description': 'VNC сервер',
            'port': 5901,
            'systemd': None,
            'process': 'x11vnc'
        },
        'websockify': {
            'display_name': 'websockify',
            'description': 'noVNC прокси',
            'port': 6080,
            'systemd': None,
            'process': 'websockify'
        }
    }
    
    def __init__(self):
        self._process_pids = {}
    
    def get_all_services(self) -> List[ServiceInfo]:
        """Получить информацию о всех сервисах"""
        services = []
        
        for key, config in self.SERVICES.items():
            info = self._get_service_info(key, config)
            services.append(info)
        
        return services
    
    def _get_service_info(self, key: str, config: dict) -> ServiceInfo:
        """Получить информацию об одном сервисе"""
        name = key
        display_name = config.get('display_name', key)
        description = config.get('description', '')
        port = config.get('port', 0)
        
        state = ServiceState.UNKNOWN
        pid = 0
        has_systemd = False
        uptime = ""
        
        # Проверка через systemd
        systemd_name = config.get('systemd')
        if systemd_name:
            has_systemd = True
            state, pid = self._check_systemd_service(systemd_name)
            if state == ServiceState.RUNNING:
                uptime = self._get_process_uptime(pid)
        
        # Проверка через процессы
        if state == ServiceState.UNKNOWN:
            process_name = config.get('process')
            if process_name:
                pid = self._find_process_pid(process_name)
                if pid:
                    state = ServiceState.RUNNING
                    uptime = self._get_process_uptime(pid)
                else:
                    state = ServiceState.STOPPED
        
        # Проверка порта
        if port and state == ServiceState.UNKNOWN:
            if self._check_port(port):
                state = ServiceState.RUNNING
        
        return ServiceInfo(
            name=name,
            display_name=display_name,
            state=state,
            pid=pid,
            port=port,
            description=description,
            has_systemd=has_systemd,
            uptime=uptime
        )
    
    def _check_systemd_service(self, name: str) -> tuple:
        """Проверить статус systemd сервиса"""
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', name],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            is_active = result.stdout.strip() == 'active'
            
            # Получить PID
            pid = 0
            result = subprocess.run(
                ['systemctl', 'show', name, '-p', 'MainPID', '--value'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            try:
                pid = int(result.stdout.strip())
            except:
                pass
            
            return (ServiceState.RUNNING if is_active else ServiceState.STOPPED, pid)
            
        except:
            return ServiceState.UNKNOWN, 0
    
    def _find_process_pid(self, name: str) -> int:
        """Найти PID процесса по имени"""
        try:
            result = subprocess.run(
                ['pgrep', '-f', name],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                if pids and pids[0]:
                    return int(pids[0])
        except:
            pass
        
        return 0
    
    def _check_port(self, port: int) -> bool:
        """Проверить открыт ли порт"""
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        try:
            result = sock.connect_ex(('127.0.0.1', port))
            return result == 0
        except:
            return False
        finally:
            sock.close()
    
    def _get_process_uptime(self, pid: int) -> str:
        """Получить время работы процесса"""
        try:
            with open(f'/proc/{pid}/stat', 'r') as f:
                stat = f.read().split()
                start_time = int(stat[21])
                
                # Calculate uptime from boot time
                with open('/proc/uptime', 'r') as f:
                    uptime_seconds = float(f.read().split()[0])
                
                # Get process start time (in clock ticks)
                with open('/proc/stat', 'r') as f:
                    for line in f:
                        if line.startswith('btime '):
                            boot_time = int(line.split()[1])
                            break
                
                clk_tck = os.sysconf(os.sysconf_names['SC_CLK_TCK'])
                process_uptime = uptime_seconds - (start_time / clk_tck)
                
                if process_uptime > 0:
                    hours = int(process_uptime // 3600)
                    mins = int((process_uptime % 3600) // 60)
                    return f"{hours}ч {mins}м"
        except:
            pass
        
        return ""
    
    def start_service(self, name: str) -> tuple:
        """Запустить сервис"""
        config = self.SERVICES.get(name)
        if not config:
            return False, f"Неизвестный сервис: {name}"
        
        systemd_name = config.get('systemd')
        if systemd_name:
            result = subprocess.run(
                ['systemctl', 'start', systemd_name],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return True, f"{config['display_name']} запущен"
            return False, result.stderr[:200]
        
        # Ручной запуск
        process = config.get('process')
        if process:
            # Найти скрипт запуска
            path = config.get('path', '/var/www')
            script = os.path.join(path, f"{name}.sh")
            
            if os.path.exists(script):
                subprocess.Popen(
                    ['/bin/bash', script],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return True, f"{config['display_name']} запущен"
        
        return False, "Не удалось запустить сервис"
    
    def stop_service(self, name: str) -> tuple:
        """Остановить сервис"""
        config = self.SERVICES.get(name)
        if not config:
            return False, f"Неизвестный сервис: {name}"
        
        systemd_name = config.get('systemd')
        if systemd_name:
            result = subprocess.run(
                ['systemctl', 'stop', systemd_name],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return True, f"{config['display_name']} остановлен"
            return False, result.stderr[:200]
        
        # Ручная остановка
        process = config.get('process')
        if process:
            subprocess.run(['pkill', '-f', process], check=False)
            return True, f"{config['display_name']} остановлен"
        
        return False, "Не удалось остановить сервис"
    
    def restart_service(self, name: str) -> tuple:
        """Перезапустить сервис"""
        config = self.SERVICES.get(name)
        if not config:
            return False, f"Неизвестный сервис: {name}"
        
        systemd_name = config.get('systemd')
        if systemd_name:
            result = subprocess.run(
                ['systemctl', 'restart', systemd_name],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return True, f"{config['display_name']} перезапущен"
            return False, result.stderr[:200]
        
        # Ручной перезапуск
        self.stop_service(name)
        time.sleep(1)
        return self.start_service(name)
    
    def start_all_site_services(self) -> tuple:
        """Запустить все сервисы сайта"""
        errors = []
        
        # Использовать restart script
        restart_script = '/var/www/restart_astra.sh'
        if os.path.exists(restart_script):
            result = subprocess.run(
                ['/bin/bash', restart_script],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode != 0:
                errors.append(f"restart_astra.sh: {result.stderr[:200]}")
        
        # Systemd сервисы
        for name, config in self.SERVICES.items():
            systemd_name = config.get('systemd')
            if systemd_name:
                subprocess.run(['systemctl', 'enable', systemd_name], check=False)
                result = subprocess.run(['systemctl', 'restart', systemd_name], capture_output=True)
                if result.returncode != 0:
                    errors.append(f"{config['display_name']}: не запущен")
        
        return len(errors) == 0, errors
    
    def stop_all_site_services(self) -> tuple:
        """Остановить все сервисы сайта"""
        # Systemd
        for name, config in self.SERVICES.items():
            systemd_name = config.get('systemd')
            if systemd_name:
                subprocess.run(['systemctl', 'stop', systemd_name], check=False)
        
        # Python процессы
        subprocess.run(['pkill', '-f', 'server.py'], check=False)
        subprocess.run(['pkill', '-f', 'start_vk.py'], check=False)
        
        # VNC стек
        for proc in ['Xvfb', 'openbox', 'chromium', 'x11vnc', 'websockify']:
            subprocess.run(['pkill', '-x', proc], check=False)
        
        return True, []
    
    def restart_all_site_services(self) -> tuple:
        """Перезапустить все сервисы сайта"""
        self.stop_all_site_services()
        time.sleep(2)
        return self.start_all_site_services()
    
    def get_service_logs(self, name: str, lines: int = 50) -> str:
        """Получить логи сервиса"""
        config = self.SERVICES.get(name)
        if not config:
            return f"Неизвестный сервис: {name}"
        
        log_files = [
            f"/var/log/live-server/{name}.log",
            f"/var/log/{name}.log",
            f"/var/log/nginx/error.log",
        ]
        
        for log_file in log_files:
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r') as f:
                        all_lines = f.readlines()
                        return ''.join(all_lines[-lines:])
                except:
                    pass
        
        return "Логи не найдены"
    
    def get_site_status_summary(self) -> Dict:
        """Получить сводку по всем сервисам"""
        services = self.get_all_services()
        
        running = sum(1 for s in services if s.state == ServiceState.RUNNING)
        stopped = sum(1 for s in services if s.state == ServiceState.STOPPED)
        errors = sum(1 for s in services if s.state == ServiceState.ERROR)
        
        return {
            'total': len(services),
            'running': running,
            'stopped': stopped,
            'errors': errors,
            'all_running': running == len(services),
            'services': [
                {
                    'name': s.name,
                    'display_name': s.display_name,
                    'state': s.state.value,
                    'port': s.port,
                    'pid': s.pid,
                    'uptime': s.uptime
                }
                for s in services
            ]
        }