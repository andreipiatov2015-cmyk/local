"""Сервис, управляемый через systemd. Все вызовы — список аргументов,
без shell=True (в старом коде была история с run_shell_command(shell=True)
для другого модуля — здесь такого паттерна нет и не будет)."""

from __future__ import annotations

import subprocess
import time

from rtmp_server.services.base import ServiceHandle, ServiceState, ServiceStatus


def _run(args: list[str], timeout: int = 15) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, capture_output=True, text=True, timeout=timeout, check=False
    )


class SystemdService(ServiceHandle):
    def __init__(self, name: str, display_name: str, unit: str, port: int | None = None):
        self.name = name
        self.display_name = display_name
        self.unit = unit
        self.port = port

    def _show_property(self, prop: str) -> str:
        result = _run(["systemctl", "show", self.unit, f"--property={prop}", "--value"])
        return result.stdout.strip()

    def status(self) -> ServiceStatus:
        active_state = self._show_property("ActiveState")
        sub_state = self._show_property("SubState")

        if active_state == "active":
            state = ServiceState.RUNNING
        elif active_state == "failed":
            state = ServiceState.FAILED
        elif active_state in ("inactive", "deactivating"):
            state = ServiceState.STOPPED
        else:
            state = ServiceState.UNKNOWN

        pid_str = self._show_property("MainPID")
        pid = int(pid_str) if pid_str.isdigit() and pid_str != "0" else None

        uptime_seconds = None
        if pid is not None:
            timestamp = self._show_property("ActiveEnterTimestampMonotonic")
            if timestamp.isdigit():
                # значение в микросекундах с момента загрузки ядра
                uptime_seconds = int(_monotonic_now_us() - int(timestamp)) // 1_000_000

        return ServiceStatus(
            name=self.name,
            display_name=self.display_name,
            state=state,
            pid=pid,
            port=self.port,
            uptime_seconds=uptime_seconds,
            detail=f"{active_state}/{sub_state}",
        )

    def start(self) -> None:
        _run(["systemctl", "start", self.unit])

    def stop(self) -> None:
        _run(["systemctl", "stop", self.unit])

    def restart(self) -> None:
        _run(["systemctl", "restart", self.unit])

    def is_enabled(self) -> bool:
        result = _run(["systemctl", "is-enabled", self.unit])
        return result.stdout.strip() == "enabled"

    def enable(self) -> None:
        _run(["systemctl", "enable", self.unit])

    def logs(self, lines: int = 100) -> str:
        result = _run(["journalctl", "-u", self.unit, "-n", str(lines), "--no-pager"], timeout=10)
        return result.stdout


def _monotonic_now_us() -> int:
    with open("/proc/uptime") as fh:
        uptime_seconds = float(fh.read().split()[0])
    return int(uptime_seconds * 1_000_000)
