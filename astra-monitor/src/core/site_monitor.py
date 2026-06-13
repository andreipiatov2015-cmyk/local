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
    name: str
    type: str
    path: str
    status: str
    is_used: bool
    description: str = ""
    details: Dict = field(default_factory=dict)
    last_check: datetime = field(default_factory=datetime.now)


@dataclass
class SiteStats:
    total_components: int
    active_components: int
    inactive_components: int
    unused_components: int
    total_entries: int
    total_presets: int
    database_size_kb: float
    log_size_mb: float


class SiteMonitor:
    # Possible site paths for auto-detection
    POSSIBLE_SITE_PATHS = [
        "/var/www",
        "/var/www/www",
        "/home/www",
        "/srv/www",
        "/opt/www",
    ]

    SITE_ROOT = "/var/www"
    LIVE_SERVER_DIR = "/var/www/live-server"
    REBOOT_DIR = "/var/www/reboot"
    DB_FILE = "/var/www/live-server/app.db"
    LOG_DIR = "/var/log"

    def __init__(self, site_root: str = None):
        # Auto-detect site root if not specified
        if site_root is None:
            site_root = self._find_site_root()
        
        self.site_root = site_root
        self.live_server_dir = os.path.join(site_root, "live-server")
        self.reboot_dir = os.path.join(site_root, "reboot")
        self.db_file = os.path.join(self.live_server_dir, "app.db")

    def _find_site_root(self) -> str:
        # Check standard paths
        for path in self.POSSIBLE_SITE_PATHS:
            if os.path.exists(path):
                try:
                    for marker in ["live-server", "reboot", "www", "server.py"]:
                        if marker in os.listdir(path):
                            return path
                except:
                    pass
        
        # Check home directory
        home_paths = [
            os.path.expanduser("~/www"),
            os.path.expanduser("~/Desktop/www"),
            os.path.expanduser("~/Desktop/local"),
            os.path.expanduser("~/Desktop/local-main"),
        ]
        
        for path in home_paths:
            if os.path.exists(path):
                www_path = os.path.join(path, "www")
                if os.path.exists(www_path):
                    return www_path
                return path
        
        return self.SITE_ROOT

    def get_all_components(self) -> List[SiteComponent]:
        components = []
        
        # Python apps
        for name, path in [
            ("Live Server", self.live_server_dir),
            ("Reboot Server", self.reboot_dir),
        ]:
            if os.path.exists(path):
                status = self._check_python_app(path)
                components.append(SiteComponent(
                    name=name, type="python", path=path,
                    status=status, is_used=True,
                    description="Flask application"
                ))
        
        # Nginx
        status = self._check_nginx()
        components.append(SiteComponent(
            name="Nginx", type="nginx", path="/etc/nginx",
            status=status, is_used=True, description="Web server"
        ))
        
        # Database
        db_status = "active" if os.path.exists(self.db_file) else "inactive"
        components.append(SiteComponent(
            name="SQLite DB", type="database", path=self.db_file,
            status=db_status, is_used=True, description="App database"
        ))
        
        return components

    def _check_python_app(self, path: str) -> str:
        if not os.path.exists(path):
            return "inactive"
        
        try:
            result = subprocess.run(
                ["pgrep", "-f", path], capture_output=True, text=True
            )
            if result.returncode == 0:
                return "active"
        except:
            pass
        
        port = self._get_app_port(path)
        if port and self._check_port(port):
            return "active"
        
        return "inactive"
    
    def _get_app_port(self, path: str) -> int:
        if "live-server" in path:
            return 8083
        elif "reboot" in path:
            return 8084
        return 0
    
    def _check_nginx(self) -> str:
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "nginx"],
                capture_output=True, text=True
            )
            return "active" if result.returncode == 0 else "inactive"
        except:
            return "unknown"
    
    def _check_port(self, port: int) -> bool:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            return sock.connect_ex(("127.0.0.1", port)) == 0
        except:
            return False
        finally:
            sock.close()
    
    def get_stats(self) -> SiteStats:
        components = self.get_all_components()
        active = sum(1 for c in components if c.status == "active")
        inactive = sum(1 for c in components if c.status == "inactive")
        unused = sum(1 for c in components if not c.is_used)
        
        db_size = entries = presets = 0
        if os.path.exists(self.db_file):
            db_size = os.path.getsize(self.db_file) / 1024
            try:
                conn = sqlite3.connect(self.db_file)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM entries")
                entries = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM presets")
                presets = cursor.fetchone()[0]
                conn.close()
            except:
                pass
        
        log_size = 0
        log_dir = os.path.join(self.site_root, "logs")
        if os.path.exists(log_dir):
            for f in os.listdir(log_dir):
                fpath = os.path.join(log_dir, f)
                if os.path.isfile(fpath):
                    log_size += os.path.getsize(fpath) / (1024 * 1024)
        
        return SiteStats(
            len(components), active, inactive, unused,
            entries, presets, db_size, log_size
        )
    
    def check_http_services(self) -> Dict[int, bool]:
        ports = [8083, 8084, 8080, 8082, 80]
        return {port: self._check_port(port) for port in ports}
    
    def restart_services(self) -> bool:
        try:
            restart_script = os.path.join(self.site_root, "restart_astra.sh")
            if os.path.exists(restart_script):
                result = subprocess.run(
                    ["/bin/bash", restart_script],
                    capture_output=True, text=True, timeout=60
                )
                return result.returncode == 0
            
            subprocess.run(["systemctl", "restart", "nginx"], check=False)
            subprocess.run(["systemctl", "restart", "live-server"], check=False)
            subprocess.run(["systemctl", "restart", "reboot-server"], check=False)
            return True
        except:
            return False
