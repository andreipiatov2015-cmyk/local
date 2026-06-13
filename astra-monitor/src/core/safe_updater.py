#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль безопасного обновления приложения через временную директорию
"""

import os
import subprocess
import shutil
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Callable
from enum import Enum


class UpdateStatus(Enum):
    """Статус обновления"""
    IDLE = "idle"
    CHECKING = "checking"
    DOWNLOADING = "downloading"
    VERIFYING = "verifying"
    APPLYING = "applying"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class UpdateResult:
    """Результат обновления"""
    success: bool
    message: str
    old_version: str = ""
    new_version: str = ""
    files_updated: List[str] = field(default_factory=list)
    error: str = ""


@dataclass
class VersionInfo:
    """Информация о версии"""
    version: str
    commit: str
    date: str = ""
    changes: List[str] = field(default_factory=list)


class SafeUpdater:
    """
    Безопасное обновление приложения через временную директорию.
    
    АЛГОРИТМ:
    1. Создать временную директорию /tmp/astra-monitor-update
    2. Клонировать новую версию туда
    3. Сравнить версии
    4. Скопировать только файлы приложения
    5. НЕ выполнять install.sh
    6. НЕ трогать nginx, ffmpeg, chromium
    7. Перезапустить только сервисы приложения
    8. Удалить временную директорию
    """
    
    # GitHub SSH URL
    GITHUB_SSH_URL = "git@github.com:andreipiatov2015-cmyk/local.git"
    
    # Папки для обновления
    UPDATE_TEMP_DIR = "/tmp/astra-monitor-update"
    APP_INSTALL_DIR = "/opt/astra-monitor"
    
    # Файлы приложения (которые нужно обновлять)
    APP_FILES = [
        "astra_monitor.py",
        "setup.py",
        "README.md",
        "Makefile",
        "install.sh",
        "uninstall.sh",
    ]
    
    # Папки приложения (которые нужно обновлять)
    APP_DIRS = [
        "src",
        "installer",
    ]
    
    def __init__(self, log_callback: Callable = None):
        self.log_callback = log_callback
        self._current_version = None
    
    def log(self, message: str):
        """Вывести сообщение в лог"""
        print(f"[SafeUpdater] {message}")
        if self.log_callback:
            self.log_callback(message)
    
    def get_current_version(self) -> str:
        """Получить текущую версию приложения"""
        version_file = os.path.join(self.APP_INSTALL_DIR, "VERSION")
        
        if os.path.exists(version_file):
            try:
                with open(version_file, 'r') as f:
                    return f.read().strip()
            except:
                pass
        
        # Пробуем получить из git
        try:
            result = subprocess.run(
                ['git', 'log', '-1', '--format=%h', '--no-walk'],
                cwd=self.APP_INSTALL_DIR,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        
        return "unknown"
    
    def get_new_version(self) -> Optional[VersionInfo]:
        """Получить информацию о новой версии из GitHub"""
        # Временная папка для проверки
        check_dir = "/tmp/astra-version-check"
        
        try:
            # Удаляем старую папку проверки
            if os.path.exists(check_dir):
                shutil.rmtree(check_dir)
            
            # Клонируем только HEAD
            self.log("Проверка новой версии...")
            result = subprocess.run(
                ['git', 'clone', '--depth=1', self.GITHUB_SSH_URL, check_dir],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                self.log(f"Ошибка проверки: {result.stderr}")
                return None
            
            # Читаем версию
            version_file = os.path.join(check_dir, "astra-monitor", "VERSION")
            if not os.path.exists(version_file):
                version_file = os.path.join(check_dir, "VERSION")
            
            version = "unknown"
            if os.path.exists(version_file):
                with open(version_file, 'r') as f:
                    version = f.read().strip()
            
            # Получаем коммит
            result = subprocess.run(
                ['git', 'log', '-1', '--format=%h %s', '--no-walk'],
                cwd=check_dir,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            commit = "unknown"
            if result.returncode == 0:
                commit = result.stdout.strip()
            
            # Удаляем временную папку
            shutil.rmtree(check_dir)
            
            return VersionInfo(
                version=version,
                commit=commit,
                date="",
                changes=[]
            )
            
        except Exception as e:
            self.log(f"Ошибка проверки версии: {e}")
            if os.path.exists(check_dir):
                shutil.rmtree(check_dir)
            return None
    
    def check_for_updates(self) -> tuple:
        """Проверить наличие обновлений"""
        self.log("Проверка обновлений...")
        
        current = self.get_current_version()
        self._current_version = current
        self.log(f"Текущая версия: {current}")
        
        new = self.get_new_version()
        
        if new is None:
            return False, "Не удалось проверить обновления", None
        
        self.log(f"Новая версия: {new.version} ({new.commit})")
        
        has_update = current != new.version and new.version != "unknown"
        
        if has_update:
            return True, f"Доступно обновление: {current} -> {new.version}", new
        
        return False, f"Установлена последняя версия: {current}", None
    
    def apply_update(self) -> UpdateResult:
        """
        Применить обновление через временную директорию.
        
        НИКОГДА не делать git pull внутри рабочей директории!
        """
        self.log("=" * 50)
        self.log("НАЧАЛО ОБНОВЛЕНИЯ")
        self.log("=" * 50)
        
        old_version = self.get_current_version()
        
        # ШАГ 1: Очищаем временную директорию
        self.log("[1/8] Очистка временной директории...")
        if os.path.exists(self.UPDATE_TEMP_DIR):
            try:
                shutil.rmtree(self.UPDATE_TEMP_DIR)
            except Exception as e:
                return UpdateResult(
                    success=False,
                    message="Не удалось очистить временную директорию",
                    error=str(e)
                )
        
        # ШАГ 2: Клонируем новую версию
        self.log("[2/8] Клонирование новой версии...")
        try:
            result = subprocess.run(
                ['git', 'clone', self.GITHUB_SSH_URL, self.UPDATE_TEMP_DIR],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                return UpdateResult(
                    success=False,
                    message="Ошибка клонирования",
                    error=result.stderr[:500]
                )
        except Exception as e:
            return UpdateResult(
                success=False,
                message="Ошибка клонирования",
                error=str(e)
            )
        
        self.log("Клонирование завершено")
        
        # ШАГ 3: Находим папку приложения в клоне
        source_app_dir = self.UPDATE_TEMP_DIR
        possible_paths = [
            os.path.join(self.UPDATE_TEMP_DIR, "astra-monitor"),
            self.UPDATE_TEMP_DIR,
        ]
        
        for path in possible_paths:
            if os.path.exists(os.path.join(path, "src")):
                source_app_dir = path
                break
        
        self.log(f"Источник: {source_app_dir}")
        
        # ШАГ 4: Проверяем версию
        self.log("[3/8] Проверка версии...")
        new_version_file = os.path.join(source_app_dir, "VERSION")
        new_version = old_version
        
        if os.path.exists(new_version_file):
            with open(new_version_file, 'r') as f:
                new_version = f.read().strip()
        
        if new_version == old_version:
            self.log("Версии совпадают, обновление не требуется")
            shutil.rmtree(self.UPDATE_TEMP_DIR)
            return UpdateResult(
                success=True,
                message="Установлена последняя версия",
                old_version=old_version,
                new_version=new_version
            )
        
        self.log(f"Обновление: {old_version} -> {new_version}")
        
        # ШАГ 5: Резервное копирование
        self.log("[4/8] Резервное копирование...")
        backup_dir = "/tmp/astra-monitor-backup"
        
        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir)
        
        if os.path.exists(self.APP_INSTALL_DIR):
            try:
                shutil.copytree(self.APP_INSTALL_DIR, backup_dir)
                self.log(f"Резервная копия: {backup_dir}")
            except Exception as e:
                self.log(f"Предупреждение: резервное копирование не удалось: {e}")
        
        # ШАГ 6: Копируем файлы приложения (НЕ системные!)
        self.log("[5/8] Копирование файлов приложения...")
        self.log("  НЕ трогаем: nginx, ffmpeg, chromium, системные зависимости")
        
        updated_files = []
        
        try:
            # Создаем резервную копию текущих файлов
            for filename in self.APP_FILES:
                src = os.path.join(source_app_dir, filename)
                dst = os.path.join(self.APP_INSTALL_DIR, filename)
                
                if os.path.exists(src):
                    # Сохраняем старую версию
                    if os.path.exists(dst):
                        backup_file = dst + ".bak"
                        shutil.copy2(dst, backup_file)
                    
                    # Копируем новую версию
                    shutil.copy2(src, dst)
                    updated_files.append(filename)
                    self.log(f"  Обновлён: {filename}")
            
            # Копируем папки приложения
            for dirname in self.APP_DIRS:
                src = os.path.join(source_app_dir, dirname)
                dst = os.path.join(self.APP_INSTALL_DIR, dirname)
                
                if os.path.exists(src):
                    # Сохраняем старую версию
                    if os.path.exists(dst):
                        shutil.move(dst, dst + ".bak")
                    
                    # Копируем новую версию
                    shutil.copytree(src, dst)
                    updated_files.append(dirname + "/")
                    self.log(f"  Обновлён: {dirname}/")
            
            # Удаляем .bak файлы после успешного обновления
            for f in os.listdir(self.APP_INSTALL_DIR):
                if f.endswith('.bak'):
                    os.remove(os.path.join(self.APP_INSTALL_DIR, f))
            
        except Exception as e:
            # Восстанавливаем из резервной копии
            self.log(f"Ошибка обновления: {e}")
            self.log("Восстановление из резервной копии...")
            
            if os.path.exists(backup_dir):
                if os.path.exists(self.APP_INSTALL_DIR):
                    shutil.rmtree(self.APP_INSTALL_DIR)
                shutil.copytree(backup_dir, self.APP_INSTALL_DIR)
            
            shutil.rmtree(self.UPDATE_TEMP_DIR)
            
            return UpdateResult(
                success=False,
                message="Ошибка обновления, выполнен откат",
                old_version=old_version,
                error=str(e)
            )
        
        # ШАГ 7: НЕ перезапускаем системные сервисы (nginx, ffmpeg и т.д.)
        self.log("[6/8] Пропуск системных сервисов")
        self.log("  Nginx - НЕ перезапускается")
        self.log("  FFmpeg - НЕ перезапускается")
        self.log("  Chromium - НЕ перезапускается")
        
        # ШАГ 8: Очищаем временную директорию
        self.log("[7/8] Очистка временных файлов...")
        
        try:
            shutil.rmtree(self.UPDATE_TEMP_DIR)
        except:
            pass
        
        # Удаляем резервную копию
        if os.path.exists(backup_dir):
            try:
                shutil.rmtree(backup_dir)
            except:
                pass
        
        self.log("[8/8] Обновление завершено")
        
        self.log("=" * 50)
        self.log("ОБНОВЛЕНИЕ ЗАВЕРШЕНО УСПЕШНО")
        self.log("=" * 50)
        
        return UpdateResult(
            success=True,
            message=f"Обновление применено: {old_version} -> {new_version}",
            old_version=old_version,
            new_version=new_version,
            files_updated=updated_files
        )
    
    def rollback(self) -> bool:
        """Откатить обновление из резервной копии"""
        backup_dir = "/tmp/astra-monitor-backup"
        
        if not os.path.exists(backup_dir):
            return False
        
        try:
            if os.path.exists(self.APP_INSTALL_DIR):
                shutil.rmtree(self.APP_INSTALL_DIR)
            shutil.copytree(backup_dir, self.APP_INSTALL_DIR)
            self.log("Откат выполнен")
            return True
        except Exception as e:
            self.log(f"Ошибка отката: {e}")
            return False
