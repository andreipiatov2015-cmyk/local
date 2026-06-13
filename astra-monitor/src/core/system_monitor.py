#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль системного мониторинга - получение информации о системе, портах, процессах и нагрузке
"""

import os
import re
import subprocess
import psutil
import socket
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime


@dataclass
class PortInfo:
    """Информация о сетевом порте"""
    port: int
    protocol: str
    local_address: str
    state: str  # LISTEN, ESTABLISHED, etc.
    pid: int
    name: str = ""
    service: str = ""


@dataclass
class ProcessInfo:
    """Информация о процессе"""
    pid: int
    name: str
    cmdline: str
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    status: str
    create_time: float


@dataclass
class SystemStats:
    """Статистика системы"""
    cpu_percent: float
    cpu_count: int
    memory_total_gb: float
    memory_used_gb: float
    memory_percent: float
    disk_total_gb: float
    disk_used_gb: float
    disk_percent: float
    load_average: tuple
    uptime: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ServiceStatus:
    """Статус системной службы"""
    name: str
    active: bool
    loaded: bool
    running: bool
    description: str = ""


class SystemMonitor:
    """Класс для мониторинга системных ресурсов"""
    
    # Известные порты веб-сервисов
    KNOWN_SERVICES = {
        80: ("nginx", "HTTP"),
        443: ("nginx", "HTTPS"),
        8080: ("nginx-custom", "HTTP Alt"),
        8082: ("nginx-rtmp", "HLS Stream"),
        8083: ("live-server", "Flask App"),
        8084: ("reboot-server", "Flask App"),
        1935: ("nginx-rtmp", "RTMP"),
        3000: ("node", "Node.js"),
        5000: ("flask", "Flask Dev"),
        5432: ("postgres", "PostgreSQL"),
        3306: ("mysql", "MySQL"),
        27017: ("mongodb", "MongoDB"),
        6379: ("redis", "Redis"),
        6080: ("novnc", "noVNC"),
        5901: ("x11vnc", "VNC"),
    }
    
    def __init__(self):
        self._boot_time = psutil.boot_time()
    
    def get_system_stats(self) -> SystemStats:
        """Получить общую статистику системы"""
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_count = psutil.cpu_count()
        
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Load average для Linux
        load_avg = (0.0, 0.0, 0.0)
        try:
            with open('/proc/loadavg', 'r') as f:
                parts = f.read().strip().split()
                load_avg = (float(parts[0]), float(parts[1]), float(parts[2]))
        except:
            pass
        
        # Uptime
        uptime_seconds = datetime.now().timestamp() - self._boot_time
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        mins = int((uptime_seconds % 3600) // 60)
        uptime_str = f"{days}d {hours}h {mins}m"
        
        return SystemStats(
            cpu_percent=cpu_percent,
            cpu_count=cpu_count,
            memory_total_gb=round(mem.total / (1024**3), 2),
            memory_used_gb=round(mem.used / (1024**3), 2),
            memory_percent=mem.percent,
            disk_total_gb=round(disk.total / (1024**3), 2),
            disk_used_gb=round(disk.used / (1024**3), 2),
            disk_percent=disk.percent,
            load_average=load_avg,
            uptime=uptime_str
        )
    
    def get_listening_ports(self) -> List[PortInfo]:
        """Получить список открытых портов в режиме LISTEN"""
        ports = []
        
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.status == 'LISTEN':
                    port_info = PortInfo(
                        port=conn.laddr.port,
                        protocol='tcp',
                        local_address=f"{conn.laddr.ip}:{conn.laddr.port}",
                        state='LISTEN',
                        pid=conn.pid or 0,
                        name="",
                        service=""
                    )
                    
                    # Попытка определить имя процесса
                    if port_info.pid:
                        try:
                            proc = psutil.Process(port_info.pid)
                            port_info.name = proc.name()
                        except:
                            pass
                    
                    # Определение сервиса
                    if port_info.port in self.KNOWN_SERVICES:
                        port_info.service = self.KNOWN_SERVICES[port_info.port][1]
                    
                    ports.append(port_info)
        except (psutil.AccessDenied, PermissionError):
            # Fallback через ss/netstat
            ports = self._get_ports_via_ss()
        
        return ports
    
    def _get_ports_via_ss(self) -> List[PortInfo]:
        """Fallback получение портов через ss"""
        ports = []
        try:
            result = subprocess.run(
                ['ss', '-tlnp'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            for line in result.stdout.split('\n')[1:]:
                parts = line.split()
                if len(parts) >= 4 and 'LISTEN' in parts:
                    local_addr = parts[3]
                    if ':' in local_addr:
                        port_str = local_addr.rsplit(':', 1)[-1]
                        try:
                            port = int(port_str)
                            # PID info может быть в последней колонке
                            pid_info = parts[-1] if '(' in parts[-1] else ""
                            pid_match = re.search(r'pid=(\d+)', pid_info)
                            pid = int(pid_match.group(1)) if pid_match else 0
                            
                            service = self.KNOWN_SERVICES.get(port, (None, ""))[1]
                            
                            ports.append(PortInfo(
                                port=port,
                                protocol='tcp',
                                local_address=local_addr,
                                state='LISTEN',
                                pid=pid,
                                service=service
                            ))
                        except (ValueError, IndexError):
                            continue
        except subprocess.TimeoutExpired:
            pass
        
        return ports
    
    def get_processes(self, limit: int = 20) -> List[ProcessInfo]:
        """Получить список процессов отсортированных по CPU"""
        processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 
                                         'memory_percent', 'status', 'create_time']):
            try:
                pinfo = proc.info
                mem_info = proc.memory_info()
                
                processes.append(ProcessInfo(
                    pid=pinfo['pid'],
                    name=pinfo['name'],
                    cmdline=' '.join(pinfo['cmdline']) if pinfo['cmdline'] else '',
                    cpu_percent=pinfo['cpu_percent'] or 0.0,
                    memory_percent=pinfo['memory_percent'] or 0.0,
                    memory_mb=round(mem_info.rss / (1024 * 1024), 1),
                    status=pinfo['status'],
                    create_time=pinfo['create_time']
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # Сортировка по CPU и лимит
        processes.sort(key=lambda x: x.cpu_percent, reverse=True)
        return processes[:limit]
    
    def get_service_status(self, service_name: str) -> Optional[ServiceStatus]:
        """Получить статус systemd сервиса"""
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', service_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            is_active = result.stdout.strip() == 'active'
            
            result = subprocess.run(
                ['systemctl', 'is-enabled', service_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            is_loaded = result.stdout.strip() == 'enabled'
            
            # Проверка запущен ли процесс
            running = False
            try:
                for proc in psutil.process_iter(['name', 'cmdline']):
                    if service_name.replace('.service', '') in proc.info['name'].lower():
                        running = True
                        break
            except:
                pass
            
            return ServiceStatus(
                name=service_name,
                active=is_active,
                loaded=is_loaded,
                running=running
            )
        except subprocess.TimeoutExpired:
            return None
    
    def get_network_stats(self) -> Dict:
        """Получить статистику сети"""
        net_io = psutil.net_io_counters()
        return {
            'bytes_sent': net_io.bytes_sent,
            'bytes_recv': net_io.bytes_recv,
            'packets_sent': net_io.packets_sent,
            'packets_recv': net_io.packets_recv,
            'errin': net_io.errin,
            'errout': net_io.errout,
            'dropin': net_io.dropin,
            'dropout': net_io.dropout
        }
    
    def get_cpu_per_core(self) -> List[float]:
        """Получить загрузку CPU по ядрам"""
        return psutil.cpu_percent(interval=0.1, percpu=True)
    
    def get_disk_io(self) -> Dict:
        """Получить статистику дискового ввода-вывода"""
        try:
            disk_io = psutil.disk_io_counters()
            if disk_io:
                return {
                    'read_count': disk_io.read_count,
                    'write_count': disk_io.write_count,
                    'read_bytes': disk_io.read_bytes,
                    'write_bytes': disk_io.write_bytes,
                    'read_time': disk_io.read_time,
                    'write_time': disk_io.write_time
                }
        except:
            pass
        return {}
    
    def check_port_open(self, host: str, port: int, timeout: float = 1.0) -> bool:
        """Проверить открыт ли порт"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            result = sock.connect_ex((host, port))
            return result == 0
        except socket.error:
            return False
        finally:
            sock.close()
    
    def get_all_system_info(self) -> Dict:
        """Получить всю системную информацию в одном запросе"""
        return {
            'system': self.get_system_stats().__dict__,
            'ports': [p.__dict__ for p in self.get_listening_ports()],
            'processes': [p.__dict__ for p in self.get_processes(30)],
            'network': self.get_network_stats(),
            'cpu_per_core': self.get_cpu_per_core(),
            'disk_io': self.get_disk_io()
        }