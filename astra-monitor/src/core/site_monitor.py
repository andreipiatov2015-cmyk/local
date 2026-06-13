#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль мониторинга сайта - отслеживание состояния веб-сервисов и компонентов
"""

import os
import json
import sqlite3
import subprocess
import requests
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path


@dataclass
class SiteComponent:
    """Компонент сайта"""
    name: str
    type: str  # python, nginx, service, file, database
    path: str
    status: str  # active, inactive, error, unknown
    is_used: bool
    description: str = ""
    details: Dict = field(default_factory=dict)
    last_check: datetime = field(default_factory=datetime.now)


@dataclass
class SiteStats:
    """Статистика сайта"""
    total_components: int
    active_components: int
    inactive_components: int
    unused_components: int
    total_entries: int
    total_presets: int
    database_size_kb: float
    log_size_mb: float


class SiteMonitor:
    """Класс для мониторинга состояния сайта"""
    
    SITE_ROOT = "/var/www"
    LIVE_SERVER_DIR = "/var/www/live-server"
    REBOOT_DIR = "/var/www/reboot"
    DB_FILE = "/var/www/live-server/app.db"
    LOG_DIR = "/var/log"
    
    def __init__(self, site_root: str = None):
        self.site_root = site_root or self.SITE_ROOT
        self.live_server_dir = site_root + "/live-server" if site_root else self.LIVE_SERVER_DIR
        self.reboot_dir = site_root + "/reboot" if site_root else self.REBOOT_DIR
        self.db_file = self.live_server_dir + "/app.db" if site_root else self.DB_FILE
    
    def get_all_components(self) -> List[SiteComponent]:
        """Получить список всех компонентов сайта с их статусом"""
        components = []
        
        # Python приложения
        components.extend(self._check_python_apps())
        
        # Nginx/RTMP
        components.extend(self._check_nginx())
        
        # Файлы конфигурации
        components.extend(self._check_config_files())
        
        # База данных
        components.extend(self._check_database())
        
        # Статические файлы и сервисы
        components.extend(self._check_static_assets())
        
        return components
    
    def _check_python_apps(self) -> List[SiteComponent]:
        """Проверить Python приложения"""
        apps = []
        
        # live-server
        live_server_path = os.path.join(self.live_server_dir, "server.py")
        live_running = self._is_process_running("server.py")
        live_port_open = self._check_port(8083)
        
        apps.append(SiteComponent(
            name="live-server",
            type="python",
            path=live_server_path,
            status="active" if live_running else "inactive",
            is_used=True,
            description="Основное Flask приложение",
            details={
                "running": live_running,
                "port_open": live_port_open,
                "port": 8083
            }
        ))
        
        # reboot server
        reboot_path = os.path.join(self.reboot_dir, "server.py")
        reboot_running = self._is_process_running("reboot", search="server.py")
        reboot_port_open = self._check_port(8084)
        
        apps.append(SiteComponent(
            name="reboot-server",
            type="python",
            path=reboot_path,
            status="active" if reboot_running else "inactive",
            is_used=True,
            description="Сервер управления трансляциями",
            details={
                "running": reboot_running,
                "port_open": reboot_port_open,
                "port": 8084
            }
        ))
        
        # start_vk.py
        start_vk_path = os.path.join(self.live_server_dir, "start_vk.py")
        vk_running = self._is_process_running("start_vk.py")
        
        apps.append(SiteComponent(
            name="vk-stream-pusher",
            type="python",
            path=start_vk_path,
            status="active" if vk_running else "inactive",
            is_used=True,
            description="Ретрансляция в VK",
            details={
                "running": vk_running,
                "lock_file": "/tmp/start_vk_stream.lock"
            }
        ))
        
        # tables_service
        tables_service_path = os.path.join(self.live_server_dir, "tables_service.py")
        tables_running = self._is_process_running("tables_service")
        
        apps.append(SiteComponent(
            name="tables-service",
            type="python",
            path=tables_service_path,
            status="active" if tables_running else "inactive",
            is_used=True,
            description="Сервис работы с таблицами",
            details={
                "running": tables_running
            }
        ))
        
        return apps
    
    def _check_nginx(self) -> List[SiteComponent]:
        """Проверить Nginx"""
        components = []
        
        # Standard nginx
        nginx_running = self._is_process_running("nginx", exact=True)
        nginx_port_80 = self._check_port(80)
        nginx_port_443 = self._check_port(443)
        
        components.append(SiteComponent(
            name="nginx",
            type="nginx",
            path="/usr/sbin/nginx",
            status="active" if nginx_running else "inactive",
            is_used=True,
            description="Основной веб-сервер",
            details={
                "running": nginx_running,
                "port_80": nginx_port_80,
                "port_443": nginx_port_443
            }
        ))
        
        # Custom nginx with RTMP
        custom_nginx_path = "/usr/local/nginx/sbin/nginx"
        custom_nginx_exists = os.path.exists(custom_nginx_path)
        custom_running = self._is_process_running("nginx", path="/usr/local/nginx")
        custom_port_8080 = self._check_port(8080)
        custom_port_8082 = self._check_port(8082)
        custom_port_1935 = self._check_port(1935)
        
        components.append(SiteComponent(
            name="nginx-rtmp",
            type="nginx",
            path=custom_nginx_path,
            status="active" if custom_running else "inactive",
            is_used=True,
            description="Nginx с RTMP модулем для стриминга",
            details={
                "exists": custom_nginx_exists,
                "running": custom_running,
                "port_http": custom_port_8080,
                "port_hls": custom_port_8082,
                "port_rtmp": custom_port_1935
            }
        ))
        
        return components
    
    def _check_config_files(self) -> List[SiteComponent]:
        """Проверить конфигурационные файлы"""
        components = []
        
        configs = [
            ("nginx.conf", "/var/www/nginx.conf", "Конфигурация Nginx"),
            ("entries.json", "/var/www/entries.json", "Данные участников"),
            ("presets.json", "/var/www/presets.json", "Пресеты раскладки"),
            ("vk_settings.json", "live-server/vk_settings.json", "Настройки VK"),
            ("stream_targets.json", "live-server/stream_targets.json", "RTMP направления"),
            ("mime.types", "/var/www/mime.types", "MIME типы"),
        ]
        
        for name, path, desc in configs:
            full_path = path if path.startswith('/') else os.path.join(self.site_root, path)
            exists = os.path.exists(full_path)
            size = os.path.getsize(full_path) if exists else 0
            
            components.append(SiteComponent(
                name=name,
                type="config",
                path=full_path,
                status="active" if exists else "missing",
                is_used=True,
                description=desc,
                details={
                    "exists": exists,
                    "size_bytes": size
                }
            ))
        
        return components
    
    def _check_database(self) -> List[SiteComponent]:
        """Проверить базу данных"""
        components = []
        
        db_exists = os.path.exists(self.db_file)
        db_size = os.path.getsize(self.db_file) if db_exists else 0
        
        # Проверка структуры БД
        tables = []
        entries_count = 0
        users_count = 0
        
        if db_exists:
            try:
                conn = sqlite3.connect(self.db_file)
                cursor = conn.cursor()
                
                # Список таблиц
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                # Количество записей
                try:
                    cursor.execute("SELECT COUNT(*) FROM entries")
                    entries_count = cursor.fetchone()[0]
                except:
                    pass
                
                try:
                    cursor.execute("SELECT COUNT(*) FROM users")
                    users_count = cursor.fetchone()[0]
                except:
                    pass
                
                conn.close()
            except Exception as e:
                pass
        
        components.append(SiteComponent(
            name="app.db",
            type="database",
            path=self.db_file,
            status="active" if db_exists else "missing",
            is_used=True,
            description="SQLite база данных",
            details={
                "exists": db_exists,
                "size_bytes": db_size,
                "size_kb": round(db_size / 1024, 2),
                "tables": tables,
                "entries_count": entries_count,
                "users_count": users_count
            }
        ))
        
        return components
    
    def _check_static_assets(self) -> List[SiteComponent]:
        """Проверить статические ресурсы"""
        components = []
        
        static_dir = os.path.join(self.live_server_dir, "static")
        templates_dir = os.path.join(self.live_server_dir, "templates")
        
        static_count = 0
        templates_count = 0
        
        if os.path.exists(static_dir):
            static_count = len([f for f in os.listdir(static_dir) 
                              if os.path.isfile(os.path.join(static_dir, f))])
        
        if os.path.exists(templates_dir):
            templates_count = len([f for f in os.listdir(templates_dir) 
                                  if f.endswith('.html')])
        
        components.append(SiteComponent(
            name="static-assets",
            type="assets",
            path=static_dir,
            status="active" if static_count > 0 else "missing",
            is_used=True,
            description="Статические файлы (CSS, JS, изображения)",
            details={
                "files_count": static_count
            }
        ))
        
        components.append(SiteComponent(
            name="templates",
            type="templates",
            path=templates_dir,
            status="active" if templates_count > 0 else "missing",
            is_used=True,
            description="HTML шаблоны",
            details={
                "templates_count": templates_count
            }
        ))
        
        return components
    
    def _is_process_running(self, name: str, search: str = None, path: str = None) -> bool:
        """Проверить запущен ли процесс"""
        try:
            result = subprocess.run(
                ['ps', 'aux'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            search_term = search or name
            
            for line in result.stdout.split('\n'):
                if search_term in line and 'grep' not in line:
                    if path:
                        if path in line:
                            return True
                    else:
                        return True
            return False
        except:
            return False
    
    def _check_port(self, port: int, host: str = "127.0.0.1") -> bool:
        """Проверить открыт ли порт"""
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        try:
            result = sock.connect_ex((host, port))
            return result == 0
        except:
            return False
        finally:
            sock.close()
    
    def get_site_stats(self) -> SiteStats:
        """Получить общую статистику сайта"""
        components = self.get_all_components()
        
        active = sum(1 for c in components if c.status == "active")
        inactive = sum(1 for c in components if c.status == "inactive")
        unused = sum(1 for c in components if not c.is_used)
        
        # Данные из БД
        entries_count = 0
        presets_count = 0
        db_size = 0
        
        if os.path.exists(self.db_file):
            db_size = os.path.getsize(self.db_file)
            try:
                conn = sqlite3.connect(self.db_file)
                cursor = conn.cursor()
                
                try:
                    cursor.execute("SELECT COUNT(*) FROM entries")
                    entries_count = cursor.fetchone()[0]
                except:
                    pass
                
                try:
                    cursor.execute("SELECT COUNT(*) FROM presets")
                    presets_count = cursor.fetchone()[0]
                except:
                    pass
                
                conn.close()
            except:
                pass
        
        # Размер логов
        log_size = 0
        for log_file in ['/var/log/live-server.log', '/var/log/nginx/access.log']:
            if os.path.exists(log_file):
                log_size += os.path.getsize(log_file)
        
        return SiteStats(
            total_components=len(components),
            active_components=active,
            inactive_components=inactive,
            unused_components=unused,
            total_entries=entries_count,
            total_presets=presets_count,
            database_size_kb=round(db_size / 1024, 2),
            log_size_mb=round(log_size / (1024 * 1024), 2)
        )
    
    def check_http_services(self) -> Dict:
        """Проверить HTTP сервисы"""
        services = {}
        ports = [
            (8083, "live-server"),
            (8084, "reboot-server"),
            (8080, "nginx-rtmp-http"),
            (8082, "nginx-rtmp-hls"),
        ]
        
        for port, name in ports:
            url = f"http://127.0.0.1:{port}"
            try:
                response = requests.get(url, timeout=2, allow_redirects=False)
                services[name] = {
                    "status": "active",
                    "http_status": response.status_code,
                    "port": port
                }
            except requests.exceptions.ConnectionError:
                services[name] = {
                    "status": "inactive",
                    "http_status": None,
                    "port": port
                }
            except Exception as e:
                services[name] = {
                    "status": "error",
                    "error": str(e),
                    "port": port
                }
        
        return services
    
    def get_vk_settings(self) -> Dict:
        """Получить настройки VK стриминга"""
        settings_file = os.path.join(self.live_server_dir, "vk_settings.json")
        
        if os.path.exists(settings_file):
            try:
                with open(settings_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def get_entries_summary(self) -> Dict:
        """Получить сводку по участникам"""
        entries_file = os.path.join(self.site_root, "entries.json")
        
        if os.path.exists(entries_file):
            try:
                with open(entries_file, 'r') as f:
                    entries = json.load(f)
                    
                filled = sum(1 for e in entries if e.get('name', '').strip())
                
                return {
                    "total": len(entries),
                    "filled": filled,
                    "empty": len(entries) - filled
                }
            except:
                pass
        
        return {"total": 0, "filled": 0, "empty": 0}
    
    def get_all_site_info(self) -> Dict:
        """Получить всю информацию о сайте"""
        components = self.get_all_components()
        stats = self.get_site_stats()
        
        return {
            'components': [c.__dict__ for c in components],
            'stats': stats.__dict__,
            'http_services': self.check_http_services(),
            'vk_settings': self.get_vk_settings(),
            'entries_summary': self.get_entries_summary()
        }