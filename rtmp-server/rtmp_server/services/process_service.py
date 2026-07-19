"""Сервис без systemd-юнита — короткоживущий процесс, отслеживаемый по pgrep.

Единственный такой сервис сейчас — vk-pusher (start_vk.py): он стартует
вместе с началом трансляции и не должен быть постоянным демоном/автозапуском,
поэтому намеренно не получает systemd-юнит (см. config/constants.py).
"""

from __future__ import annotations

import subprocess
import time

from rtmp_server.services.base import ServiceHandle, ServiceState, ServiceStatus


def _run(args: list[str], timeout: int = 15) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, capture_output=True, text=True, timeout=timeout, check=False
    )


class ProcessService(ServiceHandle):
    def __init__(
        self,
        name: str,
        display_name: str,
        pattern: str,
        start_argv: list[str] | None = None,
        log_file: str | None = None,
    ):
        self.name = name
        self.display_name = display_name
        self.pattern = pattern
        self.start_argv = start_argv
        self.log_file = log_file
        self.port: int | None = None

    def _find_pid(self) -> int | None:
        result = _run(["pgrep", "-f", self.pattern])
        pids = [p for p in result.stdout.split() if p.isdigit()]
        return int(pids[0]) if pids else None

    def status(self) -> ServiceStatus:
        pid = self._find_pid()
        if pid is None:
            return ServiceStatus(
                name=self.name,
                display_name=self.display_name,
                state=ServiceState.STOPPED,
                detail="не запущен (нет активной трансляции)",
            )

        uptime_seconds = self._uptime_for_pid(pid)
        return ServiceStatus(
            name=self.name,
            display_name=self.display_name,
            state=ServiceState.RUNNING,
            pid=pid,
            uptime_seconds=uptime_seconds,
            detail="активная трансляция",
        )

    @staticmethod
    def _uptime_for_pid(pid: int) -> int | None:
        try:
            with open(f"/proc/{pid}/stat") as fh:
                fields = fh.read().split()
            start_ticks = int(fields[21])
            hertz = 100
            with open("/proc/uptime") as fh:
                system_uptime = float(fh.read().split()[0])
            return int(system_uptime - start_ticks / hertz)
        except (OSError, ValueError, IndexError):
            return None

    def start(self) -> None:
        if not self.start_argv:
            raise RuntimeError(f"{self.name}: запуск вручную не поддерживается")
        if self._find_pid() is not None:
            return
        log_target = open(self.log_file, "a") if self.log_file else subprocess.DEVNULL
        subprocess.Popen(
            self.start_argv,
            stdout=log_target,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        time.sleep(0.3)

    def stop(self) -> None:
        _run(["pkill", "-f", self.pattern])

    def logs(self, lines: int = 100) -> str:
        if not self.log_file:
            return ""
        try:
            with open(self.log_file) as fh:
                return "".join(fh.readlines()[-lines:])
        except OSError:
            return ""
