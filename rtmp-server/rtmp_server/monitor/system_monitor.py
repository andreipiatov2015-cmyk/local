"""Системные метрики (CPU/RAM/диск/порты/процессы) через psutil.

Отличие от старого system_monitor.py: убрана таблица "известных портов"
с postgres/mysql/mongodb/redis — эта установка их не использует, и таблица
только создавала иллюзию охвата. Порты сверяются с реальным списком
управляемых сервисов из services/definitions.py.
"""

from __future__ import annotations

from dataclasses import dataclass

import psutil

from rtmp_server.config import constants as C


@dataclass
class SystemStats:
    cpu_percent: float
    cpu_count: int
    memory_percent: float
    memory_used_mb: int
    memory_total_mb: int
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    load_average: tuple[float, float, float]
    uptime_seconds: int


def get_system_stats() -> SystemStats:
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return SystemStats(
        cpu_percent=psutil.cpu_percent(interval=0.1),
        cpu_count=psutil.cpu_count() or 1,
        memory_percent=memory.percent,
        memory_used_mb=memory.used // (1024 * 1024),
        memory_total_mb=memory.total // (1024 * 1024),
        disk_percent=disk.percent,
        disk_used_gb=round(disk.used / (1024**3), 1),
        disk_total_gb=round(disk.total / (1024**3), 1),
        load_average=psutil.getloadavg(),
        uptime_seconds=int(psutil.time.time() - psutil.boot_time()),
    )


# Порты, за которыми реально следит это приложение (не произвольный список).
INTERESTING_PORTS = {
    C.RTMP_PORT: "nginx-rtmp (RTMP)",
    C.HTTP_PROXY_PORT: "nginx-rtmp (HTTP proxy)",
    C.LIVE_SERVER_PORT: "live-server",
    C.REBOOT_SERVER_PORT: "reboot-server",
}


def get_listening_ports() -> dict[int, dict]:
    """Возвращает {порт: {listening, process_name, pid}} для известных портов."""
    listening: dict[int, dict] = {}
    try:
        connections = psutil.net_connections(kind="inet")
    except (psutil.AccessDenied, PermissionError):
        connections = []

    by_port = {}
    for conn in connections:
        if conn.status == psutil.CONN_LISTEN and conn.laddr:
            by_port[conn.laddr.port] = conn.pid

    for port, label in INTERESTING_PORTS.items():
        pid = by_port.get(port)
        process_name = None
        if pid:
            try:
                process_name = psutil.Process(pid).name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                process_name = None
        listening[port] = {
            "label": label,
            "listening": port in by_port,
            "pid": pid,
            "process_name": process_name,
        }
    return listening
