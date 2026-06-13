#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль обновления - управление обновлениями сайта из git-репозитория GitHub
"""

import os
import subprocess
import shutil
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum


class UpdateStatus(Enum):
    """Статус обновления"""
    IDLE = "idle"
    CHECKING = "checking"
    DOWNLOADING = "downloading"
    APPLYING = "applying"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class GitBranch:
    """Информация о ветке"""
    name: str
    is_current: bool
    is_remote: bool


@dataclass
class GitCommit:
    """Информация о коммите"""
    hash: str
    short_hash: str
    message: str
    author: str
    date: str
    is_head: bool = False


@dataclass
class UpdateResult:
    """Результат обновления"""
    status: UpdateStatus
    message: str
    old_version: str = ""
    new_version: str = ""
    files_updated: List[str] = field(default_factory=list)
    error: str = ""


class GitUpdater:
    """Класс для управления обновлениями через git из GitHub"""
    
    # GitHub SSH URL
    GITHUB_SSH_URL = "git@github.com:andreipiatov2015-cmyk/local.git"
    
    # Возможные пути к сайту
    POSSIBLE_SITE_PATHS = [
        "/var/www",
        "/var/www/www",
        "/home/www",
        "/srv/www",
        "/opt/www",
    ]
    
    def __init__(self, repo_path: str = None, remote: str = "origin", branch: str = "main"):
        # Автоматически ищем репозиторий
        if repo_path is None:
            repo_path = self._find_repo_path()
        
        self.repo_path = repo_path
        self.remote = remote
        self.branch = branch
        self.www_path = os.path.join(repo_path, "www")
    
    def _find_repo_path(self) -> str:
        """Автоматически найти путь к git репозиторию сайта"""
        # Проверяем стандартные пути
        for path in self.POSSIBLE_SITE_PATHS:
            # Проверяем сам путь
            if os.path.exists(os.path.join(path, '.git')):
                return path
            # Проверяем вложенные папки (live-server, reboot, www)
            if os.path.exists(path):
                for item in os.listdir(path):
                    subpath = os.path.join(path, item)
                    if os.path.isdir(subpath) and os.path.exists(os.path.join(subpath, '.git')):
                        return subpath
        
        # Ищем в домашней директории
        home_paths = [
            os.path.expanduser("~/www"),
            os.path.expanduser("~/site"),
            os.path.expanduser("~/Desktop/www"),
            os.path.expanduser("~/Desktop/local"),
            os.path.expanduser("~/Desktop/local-main"),
        ]
        
        for path in home_paths:
            if os.path.exists(os.path.join(path, '.git')):
                return path
            # Проверяем www внутри
            www_path = os.path.join(path, 'www')
            if os.path.exists(os.path.join(www_path, '.git')):
                return www_path
        
        # Возвращаем /var/www по умолчанию
        return "/var/www"
    
    def _run_git(self, args: List[str], timeout: int = 30) -> subprocess.CompletedProcess:
        """Выполнить git команду"""
        cmd = ['git'] + args
        return subprocess.run(
            cmd,
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            timeout=timeout
        )
    
    def check_ssh_key(self) -> tuple:
        """Проверить наличие SSH ключа для GitHub"""
        ssh_dir = os.path.expanduser("~/.ssh")
        key_paths = [
            os.path.join(ssh_dir, "id_ed25519"),
            os.path.join(ssh_dir, "id_rsa"),
            os.path.join(ssh_dir, "github_ed25519"),
            os.path.join(ssh_dir, "github_rsa"),
        ]
        
        for key_path in key_paths:
            if os.path.exists(key_path):
                return True, key_path
        
        return False, None
    
    def generate_ssh_key(self) -> tuple:
        """Сгенерировать SSH ключ для GitHub"""
        ssh_dir = os.path.expanduser("~/.ssh")
        key_path = os.path.join(ssh_dir, "github_ed25519")
        
        try:
            os.makedirs(ssh_dir, exist_ok=True)
            
            # Генерируем ключ
            result = subprocess.run(
                ['ssh-keygen', '-t', 'ed25519', '-C', 'astra-monitor@local', '-f', key_path, '-N', ''],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # Устанавливаем права
                os.chmod(key_path, 0o600)
                os.chmod(key_path + '.pub', 0o644)
                
                # Получаем публичный ключ
                with open(key_path + '.pub', 'r') as f:
                    pub_key = f.read().strip()
                
                return True, pub_key
            
            return False, result.stderr
        
        except Exception as e:
            return False, str(e)
    
    def test_github_connection(self) -> tuple:
        """Проверить соединение с GitHub по SSH"""
        try:
            result = subprocess.run(
                ['ssh', '-T', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=10', 'git@github.com'],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            output = result.stdout + result.stderr
            
            if 'successfully authenticated' in output.lower() or 'hi ' in output.lower():
                return True, "Подключение успешно"
            elif 'permission denied' in output.lower():
                return False, "Доступ запрещён. Проверьте SSH ключ в настройках GitHub."
            else:
                return False, output[:200]
        
        except subprocess.TimeoutExpired:
            return False, "Таймаут подключения"
        except Exception as e:
            return False, str(e)
    
    def configure_git_remote(self) -> tuple:
        """Настроить remote на GitHub SSH URL"""
        if not self.is_git_repo():
            return False, "Не является git репозиторием"
        
        # Проверяем текущий remote
        result = self._run_git(['remote', '-v'])
        current_url = ""
        
        for line in result.stdout.split('\n'):
            if line.startswith('origin '):
                parts = line.split()
                if len(parts) >= 2:
                    current_url = parts[1]
                    break
        
        # Если уже настроен на GitHub, не меняем
        if 'github.com' in current_url and current_url.endswith('.git'):
            return True, f"Remote уже настроен: {current_url}"
        
        # Устанавливаем remote
        result = self._run_git(['remote', 'set-url', 'origin', self.GITHUB_SSH_URL])
        
        if result.returncode == 0:
            return True, f"Remote настроен: {self.GITHUB_SSH_URL}"
        
        # Если remote не существует, создаём
        result = self._run_git(['remote', 'add', 'origin', self.GITHUB_SSH_URL])
        
        if result.returncode == 0:
            return True, f"Remote создан: {self.GITHUB_SSH_URL}"
        
        return False, result.stderr
    
    def clone_from_github(self, target_path: str = None) -> tuple:
        """Клонировать репозиторий с GitHub по SSH"""
        if target_path is None:
            target_path = self.repo_path
        
        # Если папка уже существует
        if os.path.exists(target_path):
            if os.path.exists(os.path.join(target_path, '.git')):
                # Уже есть репозиторий, просто настраиваем remote
                old_path = self.repo_path
                self.repo_path = target_path
                result = self.configure_git_remote()
                self.repo_path = old_path
                return result
        
        try:
            os.makedirs(target_path, exist_ok=True)
            
            result = subprocess.run(
                ['git', 'clone', self.GITHUB_SSH_URL, target_path],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                self.repo_path = target_path
                return True, f"Репозиторий клонирован в {target_path}"
            
            return False, result.stderr[:500]
        
        except subprocess.TimeoutExpired:
            return False, "Таймаут клонирования"
        except Exception as e:
            return False, str(e)
    
    def sync_with_github(self) -> UpdateResult:
        """Синхронизировать с GitHub (clone если нет, pull если есть)"""
        # Проверяем SSH
        has_key, key_path = self.check_ssh_key()
        if not has_key:
            return UpdateResult(
                status=UpdateStatus.FAILED,
                message="SSH ключ не найден",
                error="no_ssh_key"
            )
        
        # Проверяем соединение
        connected, conn_msg = self.test_github_connection()
        if not connected:
            return UpdateResult(
                status=UpdateStatus.FAILED,
                message=f"Не удалось подключиться к GitHub: {conn_msg}",
                error="connection_failed"
            )
        
        # Если репозитория нет - клонируем
        if not self.is_git_repo():
            success, msg = self.clone_from_github()
            if success:
                return UpdateResult(
                    status=UpdateStatus.SUCCESS,
                    message=f"Репозиторий склонирован с GitHub: {msg}"
                )
            else:
                return UpdateResult(
                    status=UpdateStatus.FAILED,
                    message="Не удалось клонировать репозиторий",
                    error=msg
                )
        
        # Настраиваем remote на GitHub если нужно
        self.configure_git_remote()
        
        # Pull изменения
        return self.pull_changes()
    
    def is_git_repo(self) -> bool:
        """Проверить является ли папка git репозиторием"""
        # Проверяем основной путь
        if os.path.exists(os.path.join(self.repo_path, '.git')):
            return True
        
        # Проверяем www подпапку
        www_git = os.path.join(self.repo_path, 'www', '.git')
        if os.path.exists(www_git):
            return True
        
        # Проверяем live-server подпапку
        live_git = os.path.join(self.repo_path, 'live-server', '.git')
        if os.path.exists(live_git):
            return True
        
        return False
    
    def init_repo(self) -> bool:
        """Инициализировать git репозиторий"""
        if self.is_git_repo():
            return True
        
        try:
            os.makedirs(self.repo_path, exist_ok=True)
            result = self._run_git(['init'])
            if result.returncode == 0:
                result = self._run_git(['config', 'user.email', 'astra-monitor@local'])
                result = self._run_git(['config', 'user.name', 'Astra Monitor'])
                return True
        except:
            pass
        return False
    
    def get_current_branch(self) -> Optional[str]:
        """Получить текущую ветку"""
        if not self.is_git_repo():
            return None
        
        result = self._run_git(['branch', '--show-current'])
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    
    def get_branches(self) -> List[GitBranch]:
        """Получить список всех веток"""
        if not self.is_git_repo():
            return []
        
        branches = []
        current = self.get_current_branch()
        
        # Локальные ветки
        result = self._run_git(['branch'])
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                line = line.strip()
                if line:
                    name = line.lstrip('* ')
                    branches.append(GitBranch(
                        name=name,
                        is_current=name == current,
                        is_remote=False
                    ))
        
        # Удалённые ветки
        result = self._run_git(['branch', '-r'])
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                line = line.strip()
                if line and '/' in line and not any(b.name == line for b in branches):
                    branches.append(GitBranch(
                        name=line,
                        is_current=False,
                        is_remote=True
                    ))
        
        return branches
    
    def get_commits(self, count: int = 10) -> List[GitCommit]:
        """Получить историю коммитов"""
        if not self.is_git_repo():
            return []
        
        commits = []
        
        result = self._run_git(['log', f'--max-count={count}', '--pretty=format:%H|%h|%s|%an|%ai'])
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 5:
                        commits.append(GitCommit(
                            hash=parts[0],
                            short_hash=parts[1],
                            message=parts[2],
                            author=parts[3],
                            date=parts[4],
                            is_head=(parts[1] == self.get_short_head())
                        ))
        
        return commits
    
    def get_short_head(self) -> str:
        """Получить короткий хеш текущего коммита"""
        result = self._run_git(['rev-parse', '--short', 'HEAD'])
        if result.returncode == 0:
            return result.stdout.strip()
        return "unknown"
    
    def get_full_head(self) -> str:
        """Получить полный хеш текущего коммита"""
        result = self._run_git(['rev-parse', 'HEAD'])
        if result.returncode == 0:
            return result.stdout.strip()
        return "unknown"
    
    def fetch_remote(self) -> tuple:
        """Получить обновления с удалённого репозитория"""
        if not self.is_git_repo():
            return False, "Не является git репозиторием"
        
        result = self._run_git(['fetch', self.remote], timeout=60)
        if result.returncode == 0:
            return True, "Fetch выполнен"
        return False, result.stderr or "Ошибка fetch"
    
    def check_for_updates(self) -> tuple:
        """Проверить наличие обновлений"""
        if not self.is_git_repo():
            return False, "Не является git репозиторием", None
        
        # Fetch
        success, msg = self.fetch_remote()
        if not success:
            return False, msg, None
        
        # Проверка статуса
        result = self._run_git(['status', '-sb'])
        if result.returncode != 0:
            return False, result.stderr, None
        
        behind = 0
        ahead = 0
        
        for line in result.stdout.split('\n'):
            if f'{self.remote}/{self.branch}' in line:
                parts = line.split('...')
                if len(parts) >= 2:
                    status_part = parts[1].split()
                    for p in status_part:
                        if p.startswith('['):
                            # [behind 2] или [ahead 3]
                            p = p.strip('[]')
                            if 'behind' in p:
                                behind = int(p.split()[1])
                            elif 'ahead' in p:
                                ahead = int(p.split()[1])
        
        current = self.get_short_head()
        
        # Получить хеш удалённой версии
        result = self._run_git(['rev-parse', f'{self.remote}/{self.branch}'])
        remote = result.stdout.strip() if result.returncode == 0 else None
        
        has_update = behind > 0
        message = f"Коммит {current}"
        if behind > 0:
            message += f", отставание на {behind} коммит(ов)"
        if ahead > 0:
            message += f", опережение на {ahead} коммит(ов)"
        if not behind and not ahead:
            message = "Обновлений нет, локальная версия актуальна"
        
        return has_update, message, remote
    
    def pull_changes(self) -> UpdateResult:
        """Стянуть изменения из репозитория"""
        if not self.is_git_repo():
            return UpdateResult(
                status=UpdateStatus.FAILED,
                message="Не является git репозиторием",
                error="repo_not_init"
            )
        
        old_version = self.get_short_head()
        
        # Save state of www folder before update
        backup_info = self._backup_www()
        
        try:
            # Stash local changes if any
            result = self._run_git(['stash'], timeout=30)
            stash_used = result.returncode == 0 and 'No local changes' not in result.stdout
            
            # Pull
            result = self._run_git(['pull', self.remote, self.branch], timeout=120)
            
            if result.returncode != 0:
                # Restore from backup
                if backup_info:
                    self._restore_www(backup_info)
                return UpdateResult(
                    status=UpdateStatus.FAILED,
                    message="Ошибка при выполнении pull",
                    old_version=old_version,
                    error=result.stderr
                )
            
            new_version = self.get_short_head()
            files = self._get_changed_files(old_version, new_version)
            
            # Restart services after update
            self._restart_services()
            
            return UpdateResult(
                status=UpdateStatus.SUCCESS,
                message="Обновление успешно применено",
                old_version=old_version,
                new_version=new_version,
                files_updated=files
            )
            
        except subprocess.TimeoutExpired:
            if backup_info:
                self._restore_www(backup_info)
            return UpdateResult(
                status=UpdateStatus.FAILED,
                message="Таймаут при обновлении",
                old_version=old_version,
                error="timeout"
            )
        except Exception as e:
            if backup_info:
                self._restore_www(backup_info)
            return UpdateResult(
                status=UpdateStatus.FAILED,
                message="Ошибка обновления",
                old_version=old_version,
                error=str(e)
            )
    
    def _backup_www(self) -> Optional[str]:
        """Создать резервную копию www"""
        backup_dir = "/tmp/astra-monitor-backup"
        www_src = self.www_path
        backup_dst = os.path.join(backup_dir, "www_backup")
        
        if not os.path.exists(www_src):
            return None
        
        try:
            os.makedirs(backup_dir, exist_ok=True)
            
            # Remove old backup
            if os.path.exists(backup_dst):
                shutil.rmtree(backup_dst)
            
            # Create new backup
            shutil.copytree(www_src, backup_dst)
            return backup_dst
        except:
            return None
    
    def _restore_www(self, backup_path: str) -> bool:
        """Восстановить www из резервной копии"""
        backup_www = os.path.join(backup_path, "www_backup")
        
        if not os.path.exists(backup_www):
            return False
        
        try:
            # Backup current state first
            current_www = self.www_path
            if os.path.exists(current_www):
                shutil.rmtree(current_www)
            
            shutil.copytree(backup_www, current_www)
            return True
        except:
            return False
    
    def _get_changed_files(self, old: str, new: str) -> List[str]:
        """Получить список изменённых файлов"""
        result = self._run_git(['diff', '--name-only', old, new])
        if result.returncode == 0:
            return [f for f in result.stdout.split('\n') if f.strip()]
        return []
    
    def _restart_services(self):
        """Перезапустить сервисы после обновления"""
        restart_script = os.path.join(self.repo_path, "www", "restart_astra.sh")
        
        if os.path.exists(restart_script):
            try:
                subprocess.run(
                    ['/bin/bash', restart_script],
                    cwd=self.repo_path,
                    timeout=60
                )
            except:
                pass
    
    def set_branch(self, branch: str) -> tuple:
        """Переключиться на ветку"""
        if not self.is_git_repo():
            return False, "Не является git репозиторием"
        
        # Checkout
        result = self._run_git(['checkout', branch])
        if result.returncode != 0:
            return False, result.stderr
        
        # Set upstream
        result = self._run_git(['branch', '--set-upstream-to', f'{self.remote}/{branch}'])
        
        return True, f"Переключено на ветку {branch}"
    
    def clone_repo(self, url: str) -> tuple:
        """Клонировать репозиторий"""
        if os.path.exists(self.repo_path) and self.is_git_repo():
            return True, "Репозиторий уже существует"
        
        try:
            os.makedirs(self.repo_path, exist_ok=True)
            result = subprocess.run(
                ['git', 'clone', url, self.repo_path],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                return True, "Репозиторий успешно клонирован"
            return False, result.stderr
        except Exception as e:
            return False, str(e)
    
    def get_repo_info(self) -> Dict:
        """Получить информацию о репозитории"""
        if not self.is_git_repo():
            return {
                'is_repo': False,
                'path': self.repo_path
            }
        
        current = self.get_current_branch()
        head = self.get_short_head()
        full_head = self.get_full_head()
        has_update, update_msg, remote_hash = self.check_for_updates()
        
        return {
            'is_repo': True,
            'path': self.repo_path,
            'branch': current,
            'head': head,
            'full_head': full_head,
            'remote': self.remote,
            'has_update': has_update,
            'update_message': update_msg,
            'remote_hash': remote_hash,
            'branches': [b.name for b in self.get_branches()],
            'commits': [c.short_hash for c in self.get_commits(5)]
        }