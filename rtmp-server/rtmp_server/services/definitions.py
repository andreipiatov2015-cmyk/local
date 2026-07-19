"""Таблица управляемых сервисов — строится ТОЛЬКО из config.constants.

Ровно 4 сервиса (было 9 в старом приложении, включая весь VNC-стек,
который признан неактуальным и полностью убран). Ни один порт/путь
здесь не хардкодится повторно.
"""

from __future__ import annotations

from rtmp_server.config import constants as C
from rtmp_server.services.base import ServiceHandle
from rtmp_server.services.process_service import ProcessService
from rtmp_server.services.systemd_service import SystemdService

SERVICES: dict[str, ServiceHandle] = {
    "nginx_rtmp": SystemdService(
        name="nginx_rtmp",
        display_name="nginx (RTMP + HTTP proxy)",
        unit=C.UNIT_NGINX_RTMP,
        port=C.HTTP_PROXY_PORT,
    ),
    "live_server": SystemdService(
        name="live_server",
        display_name="live-server",
        unit=C.UNIT_LIVE_SERVER,
        port=C.LIVE_SERVER_PORT,
    ),
    "reboot_server": SystemdService(
        name="reboot_server",
        display_name="reboot-server",
        unit=C.UNIT_REBOOT_SERVER,
        port=C.REBOOT_SERVER_PORT,
    ),
    "vk_pusher": ProcessService(
        name="vk_pusher",
        display_name="VK/OK трансляция (start_vk.py)",
        pattern=C.VK_PUSHER_PROCESS_PATTERN,
        start_argv=["/usr/bin/python3", C.VK_PUSHER_SCRIPT],
        log_file=f"{C.APP_LOG_DIR}/vk_pusher.log",
    ),
}


def get_service(name: str) -> ServiceHandle:
    try:
        return SERVICES[name]
    except KeyError:
        raise KeyError(f"Неизвестный сервис: {name!r}. Доступные: {list(SERVICES)}") from None


def get_all_services() -> list[ServiceHandle]:
    return list(SERVICES.values())
