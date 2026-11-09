"""Интеграция с systemd через протокол sd_notify (без внешней зависимости —
достаточно датаграммы в unix-сокет из $NOTIFY_SOCKET, который systemd сам
прокидывает в окружение юнита с Type=notify).

Даёт два эффекта:
- notify_ready() сообщает systemd, что приложение реально поднялось (а не
  просто запустился процесс) — нужно для Type=notify в юните.
- notify_watchdog(), вызываемый по таймеру из GUI-потока, даёт systemd
  способ отличить "завис" от "работает": если приложение перестанет отвечать
  (например, GUI-поток заблокирован), пинги прекратятся, и systemd убьёт и
  перезапустит процесс по истечении WatchdogSec — то, что обычный
  Restart=on-failure не ловит, потому что зависший процесс не падает и не
  возвращает ненулевой код выхода."""

from __future__ import annotations

import os
import socket


def _notify(message: str) -> None:
    addr = os.environ.get("NOTIFY_SOCKET")
    if not addr:
        return
    if addr.startswith("@"):
        addr = "\0" + addr[1:]
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            sock.connect(addr)
            sock.sendall(message.encode("utf-8"))
        finally:
            sock.close()
    except OSError:
        pass


def notify_ready() -> None:
    _notify("READY=1")


def notify_watchdog() -> None:
    _notify("WATCHDOG=1")


def notify_status(text: str) -> None:
    _notify(f"STATUS={text}")


def watchdog_interval_ms() -> int | None:
    """Половина WatchdogSec (в мс), как рекомендует systemd — или None, если
    юнит запущен без watchdog (WATCHDOG_USEC не задан, например при ручном
    запуске из ярлыка на рабочем столе мимо systemd)."""
    raw = os.environ.get("WATCHDOG_USEC")
    if not raw:
        return None
    try:
        usec = int(raw)
    except ValueError:
        return None
    if usec <= 0:
        return None
    return max(1000, (usec // 1000) // 2)
