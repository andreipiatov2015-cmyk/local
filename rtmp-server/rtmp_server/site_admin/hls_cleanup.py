"""Очистка старых HLS-сегментов трансляции по времени.

nginx-rtmp-module сам умеет подчищать HLS (hls_cleanup on в www/nginx.conf),
но делает это только пока поток активен — таймер очистки живёт внутри
контекста публикации. Как только трансляция останавливается, её последние
сегменты и .m3u8-плейлист остаются на диске навсегда — следующая попытка
очистки их уже не коснётся, потому что для неё больше нет активного потока.
При длинных трансляциях, где старые минуты специально не нужны, это
медленно и незаметно съедает место на диске.

Здесь — независимая очистка по возрасту файла, а не по состоянию потока:
сметает любой .ts/.m3u8 в HLS_DIR старше retention_seconds, вне зависимости
от того, идёт трансляция сейчас или давно закончилась. Запускается отдельным
systemd-таймером (rtmp-server-hls-cleanup.timer), не завязана на GUI."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from rtmp_server.config import constants as C

HLS_FILE_SUFFIXES = (".ts", ".m3u8")


def get_retention_seconds() -> int:
    path = Path(C.HLS_CLEANUP_CONFIG_FILE)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            value = int(data.get("retention_seconds"))
            if value > 0:
                return value
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
    return C.DEFAULT_HLS_RETENTION_SECONDS


def set_retention_seconds(value: int) -> None:
    value = int(value)
    if value <= 0:
        raise ValueError("Срок хранения должен быть положительным числом секунд")
    path = Path(C.HLS_CLEANUP_CONFIG_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"retention_seconds": value}), encoding="utf-8")


@dataclass
class CleanupResult:
    checked: int = 0
    removed: int = 0
    bytes_freed: int = 0
    errors: list[str] = field(default_factory=list)


def cleanup_once(retention_seconds: int | None = None, now: float | None = None) -> CleanupResult:
    """Удаляет .ts/.m3u8 в HLS_DIR старше retention_seconds (по mtime).

    Безопасно для активного потока: nginx непрерывно дописывает новые
    сегменты и перезаписывает плейлист текущего потока, так что их mtime
    всегда свежий, пока трансляция идёт — под очистку попадают только
    файлы, которые перестали обновляться (сегмент вышел из окна плейлиста
    или поток полностью остановился)."""
    retention = retention_seconds if retention_seconds is not None else get_retention_seconds()
    now = now if now is not None else time.time()
    hls_dir = Path(C.HLS_DIR)

    result = CleanupResult()
    if not hls_dir.is_dir():
        return result

    for path in hls_dir.iterdir():
        if path.suffix not in HLS_FILE_SUFFIXES or not path.is_file():
            continue
        result.checked += 1
        try:
            stat = path.stat()
        except OSError as exc:
            result.errors.append(f"{path.name}: {exc}")
            continue
        if now - stat.st_mtime <= retention:
            continue
        try:
            size = stat.st_size
            path.unlink()
        except OSError as exc:
            result.errors.append(f"{path.name}: {exc}")
            continue
        result.removed += 1
        result.bytes_freed += size

    return result


def hls_directory_usage_bytes() -> int:
    hls_dir = Path(C.HLS_DIR)
    if not hls_dir.is_dir():
        return 0
    total = 0
    for path in hls_dir.iterdir():
        if path.is_file():
            try:
                total += path.stat().st_size
            except OSError:
                pass
    return total
