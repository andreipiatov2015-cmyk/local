"""Защита от двойного запуска GUI.

Нужна, потому что теперь есть ДВА независимых способа стартовать
rtmp-server: systemd-юнит при старте графической сессии (rtmp-server-gui.service)
и ярлык на рабочем столе, который любой пользователь может кликнуть в любой
момент. Без этой защиты оба способа могут быть активны одновременно и
породить два конкурирующих окна."""

from __future__ import annotations

import os
from pathlib import Path

import psutil

LOCK_FILE = Path("/var/run/rtmp-server-gui.pid")


def acquire_or_none() -> bool:
    """True, если удалось стать единственным экземпляром (и лок-файл записан).
    False — уже есть живой процесс, новый экземпляр должен молча выйти."""
    if LOCK_FILE.exists():
        try:
            existing_pid = int(LOCK_FILE.read_text().strip())
        except (ValueError, OSError):
            existing_pid = None

        if existing_pid and psutil.pid_exists(existing_pid):
            return False
        # лок-файл протух (процесс уже мёртв) — перезаписываем

    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.write_text(str(os.getpid()))
    return True


def release() -> None:
    try:
        if LOCK_FILE.exists() and LOCK_FILE.read_text().strip() == str(os.getpid()):
            LOCK_FILE.unlink()
    except OSError:
        pass
