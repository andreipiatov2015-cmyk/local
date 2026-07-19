"""HTTP health-check сайта.

В старом приложении GUI (main_window.py) вызывал `get_site_stats()` и
ожидал от `check_http_services()` тип `Dict[str, {status, http_status}]`,
а реальные методы SiteMonitor назывались `get_stats()` и возвращали
`Dict[int, bool]` — несовпадение тихо гасилось `except Exception`, и
вкладка "Сайт" никогда не показывала данные.

Здесь ровно один метод с одним чётко задокументированным типом результата —
GUI, CLI и update-движок используют его одинаково.
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request
from dataclasses import dataclass

from rtmp_server.config import constants as C


@dataclass
class EndpointStatus:
    name: str
    url: str
    reachable: bool
    http_status: int | None
    error: str | None = None


def check_site_health(timeout: float = 3.0) -> list[EndpointStatus]:
    """Проверяет все эндпоинты из config.constants.HEALTH_CHECK_ENDPOINTS."""
    results = []
    for name, (url, expected_status) in C.HEALTH_CHECK_ENDPOINTS.items():
        results.append(_check_one(name, url, timeout))
    return results


def _check_one(name: str, url: str, timeout: float) -> EndpointStatus:
    try:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return EndpointStatus(
                name=name, url=url, reachable=True, http_status=response.status
            )
    except urllib.error.HTTPError as exc:
        # сервер ответил (пусть и ошибкой) — значит, процесс жив и слушает порт
        return EndpointStatus(name=name, url=url, reachable=True, http_status=exc.code)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return EndpointStatus(
            name=name, url=url, reachable=False, http_status=None, error=str(exc)
        )


@dataclass
class SiteComponent:
    name: str
    path: str
    exists: bool


def check_site_layout() -> list[SiteComponent]:
    """Проверяет, что ожидаемые директории/файлы сайта на месте (без бизнес-логики БД)."""
    paths = {
        "live-server": C.LIVE_SERVER_SCRIPT,
        "reboot-server": C.REBOOT_SERVER_SCRIPT,
        "HLS directory": C.HLS_DIR,
        "nginx config": C.NGINX_CONF,
    }
    return [SiteComponent(name=name, path=path, exists=os.path.exists(path)) for name, path in paths.items()]
