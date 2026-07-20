"""Общий интерфейс управляемого сервиса.

Старое приложение (service_manager.py) смешивало три разных способа
определения статуса (systemd / pgrep / TCP-порт) внутри одной функции
для каждого сервиса, из-за чего логика расползалась и рассинхронизировалась
с реальными портами. Здесь — один интерфейс, две реализации
(systemd_service.py и process_service.py), никакого смешения внутри одной.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from enum import Enum


class ServiceState(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass
class ServiceStatus:
    name: str
    display_name: str
    state: ServiceState
    pid: int | None = None
    port: int | None = None
    uptime_seconds: int | None = None
    detail: str = ""


class ServiceHandle(abc.ABC):
    """Один управляемый сервис: имя, описание и жизненный цикл."""

    #: машинное имя, используется в CLI/GUI/логах (напр. "live_server")
    name: str
    #: человекочитаемое имя для GUI
    display_name: str
    #: порт, который сервис слушает (для отображения/health-check), либо None
    port: int | None = None

    @abc.abstractmethod
    def status(self) -> ServiceStatus: ...

    @abc.abstractmethod
    def start(self) -> None: ...

    @abc.abstractmethod
    def stop(self) -> None: ...

    def restart(self) -> None:
        self.stop()
        self.start()

    @abc.abstractmethod
    def logs(self, lines: int = 100) -> str: ...
