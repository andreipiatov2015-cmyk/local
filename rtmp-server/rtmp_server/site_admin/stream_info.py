"""Информация и настройка трансляции: входящий RTMP-поток (от стримера)
и исходящий пуш в VK/OK (start_vk.py).

Важное честное ограничение: сервер физически не может изменить
разрешение/битрейт ВХОДЯЩЕГО потока — это настройки кодировщика у
стримера (OBS и т.п.), сервер только принимает и ретранслирует то, что
прислали. Здесь для входящего потока — только просмотр текущих
параметров. Управлять реально можно только исходящим перекодированием
в VK (start_vk.py вызывает ffmpeg сам, и туда можно передать целевой
битрейт/масштаб).

"Тест битрейта" — это тест ИСХОДЯЩЕГО канала самого сервера (важно для
раздачи HLS зрителям и для пуша в VK), а не канала стримера — канал
стримера с сервера в принципе не измерить.
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from rtmp_server.config import constants as C

FFPROBE = "ffprobe"


class StreamInfoError(Exception):
    pass


# ---------------------------------------------------------------------------
# Входящий поток
# ---------------------------------------------------------------------------


@dataclass
class IncomingStreamInfo:
    stream_name: str
    live: bool
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    audio_sample_rate: int | None = None
    error: str | None = None


@dataclass
class BitrateSample:
    stream_name: str
    segments_measured: int
    min_kbps: float | None
    avg_kbps: float | None
    max_kbps: float | None


def list_live_streams() -> list[str]:
    """Имена активных потоков — по факту наличия .m3u8 в HLS-директории
    (это и есть сигнал "поток реально льётся прямо сейчас")."""
    hls_dir = Path(C.HLS_DIR)
    if not hls_dir.is_dir():
        return []
    return sorted(p.stem for p in hls_dir.glob("*.m3u8"))


def _ffprobe_json(url: str, timeout: float = 8.0) -> dict:
    result = subprocess.run(
        [
            FFPROBE, "-v", "quiet", "-print_format", "json",
            "-show_streams", "-show_format",
            url,
        ],
        capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode != 0:
        raise StreamInfoError(result.stderr.strip() or "ffprobe завершился с ошибкой")
    return json.loads(result.stdout)


def probe_incoming_stream(stream_name: str) -> IncomingStreamInfo:
    hls_url = f"http://127.0.0.1:{C.HTTP_PROXY_PORT}/hls/{stream_name}.m3u8"
    try:
        data = _ffprobe_json(hls_url)
    except (StreamInfoError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        return IncomingStreamInfo(stream_name=stream_name, live=False, error=str(exc))

    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    audio = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)

    fps = None
    if video and video.get("avg_frame_rate") and video["avg_frame_rate"] != "0/0":
        num, _, den = video["avg_frame_rate"].partition("/")
        try:
            fps = round(int(num) / int(den), 2) if int(den) else None
        except (ValueError, ZeroDivisionError):
            fps = None

    return IncomingStreamInfo(
        stream_name=stream_name,
        live=True,
        width=video.get("width") if video else None,
        height=video.get("height") if video else None,
        fps=fps,
        video_codec=video.get("codec_name") if video else None,
        audio_codec=audio.get("codec_name") if audio else None,
        audio_sample_rate=int(audio["sample_rate"]) if audio and audio.get("sample_rate") else None,
    )


def measure_segment_bitrate(stream_name: str, last_n: int = 5) -> BitrateSample:
    """Приближённый битрейт входящего потока по размерам последних HLS-сегментов
    (.ts) — надёжнее, чем пытаться выжать общий bit_rate из live HLS через
    ffprobe (там это часто не заполнено для потокового плейлиста)."""
    hls_dir = Path(C.HLS_DIR)
    segments = sorted(
        hls_dir.glob(f"{stream_name}-*.ts"), key=lambda p: p.stat().st_mtime, reverse=True
    )[:last_n]

    if not segments:
        return BitrateSample(stream_name=stream_name, segments_measured=0, min_kbps=None, avg_kbps=None, max_kbps=None)

    # длительность одного HLS-фрагмента — задана в nginx.conf (hls_fragment 3) —
    # берём как разумное приближение; если сегмент по факту короче/длиннее,
    # результат будет чуть неточным, но порядок величины верный.
    fragment_seconds = 3.0
    kbps_values = [(seg.stat().st_size * 8 / 1000) / fragment_seconds for seg in segments]

    return BitrateSample(
        stream_name=stream_name,
        segments_measured=len(kbps_values),
        min_kbps=round(min(kbps_values), 1),
        avg_kbps=round(sum(kbps_values) / len(kbps_values), 1),
        max_kbps=round(max(kbps_values), 1),
    )


# ---------------------------------------------------------------------------
# Тест исходящего канала СЕРВЕРА (не стримера — см. описание модуля)
# ---------------------------------------------------------------------------


@dataclass
class BandwidthTestResult:
    ok: bool
    mbps: float | None = None
    error: str | None = None


def test_server_bandwidth(size_bytes: int = 25_000_000, timeout: float = 20.0) -> BandwidthTestResult:
    """Скачивает тестовый файл известного размера с публичного, не завязанного
    на GitHub источника (Cloudflare speed-test — тот же принцип, что и у
    fast.com/speedtest, отдельный от инфраструктуры, к которой уже были
    проблемы с доступом), измеряет фактическую скорость КАНАЛА СЕРВЕРА."""
    url = f"https://speed.cloudflare.com/__down?bytes={size_bytes}"
    try:
        start = time.monotonic()
        request = urllib.request.Request(url, headers={"User-Agent": "rtmp-server-bandwidth-test"})
        received = 0
        with urllib.request.urlopen(request, timeout=timeout) as response:
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                received += len(chunk)
                if time.monotonic() - start > timeout:
                    break
        elapsed = max(time.monotonic() - start, 0.001)
        mbps = round((received * 8 / 1_000_000) / elapsed, 2)
        return BandwidthTestResult(ok=True, mbps=mbps)
    except Exception as exc:  # сеть непредсказуема — любая ошибка не должна ронять GUI
        return BandwidthTestResult(ok=False, error=str(exc))


# ---------------------------------------------------------------------------
# Исходящий пуш в VK/OK
# ---------------------------------------------------------------------------


@dataclass
class VkTarget:
    id: str
    name: str
    url: str
    enabled: bool = True


@dataclass
class VkPushSettings:
    enabled: bool = False
    vk_rtmp_url: str = ""
    target_ids: list[str] = field(default_factory=list)
    bitrate_kbps: int | None = None  # None = без ограничения (текущее поведение start_vk.py)
    resolution_height: int | None = None  # None = как на входе, без масштабирования


def _read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")


def get_vk_settings() -> VkPushSettings:
    raw = _read_json(Path(C.VK_SETTINGS_FILE), {})
    return VkPushSettings(
        enabled=bool(raw.get("enabled", False)),
        vk_rtmp_url=raw.get("vk_rtmp_url", ""),
        target_ids=list(raw.get("target_ids") or []),
        bitrate_kbps=raw.get("bitrate_kbps"),
        resolution_height=raw.get("resolution_height"),
    )


def save_vk_settings(settings: VkPushSettings) -> None:
    """Пишет только известные нам поля, сохраняя остальные (title,
    preview_path и т.п.) — файл читает ещё и server.py, не только start_vk.py."""
    path = Path(C.VK_SETTINGS_FILE)
    raw = _read_json(path, {})
    raw["enabled"] = settings.enabled
    raw["vk_rtmp_url"] = settings.vk_rtmp_url
    raw["target_ids"] = settings.target_ids
    if settings.bitrate_kbps is not None:
        raw["bitrate_kbps"] = settings.bitrate_kbps
    else:
        raw.pop("bitrate_kbps", None)
    if settings.resolution_height is not None:
        raw["resolution_height"] = settings.resolution_height
    else:
        raw.pop("resolution_height", None)
    _write_json(path, raw)


def list_stream_targets() -> list[VkTarget]:
    raw = _read_json(Path(C.STREAM_TARGETS_FILE), [])
    return [
        VkTarget(id=t.get("id", ""), name=t.get("name", ""), url=t.get("url", ""), enabled=bool(t.get("enabled", True)))
        for t in raw
    ]


def save_stream_targets(targets: list[VkTarget]) -> None:
    _write_json(
        Path(C.STREAM_TARGETS_FILE),
        [{"id": t.id, "name": t.name, "url": t.url, "enabled": t.enabled} for t in targets],
    )


def restart_vk_push(stream_name: str) -> None:
    """Останавливает и заново запускает start_vk.py с новыми настройками.

    Не используем services.definitions.get_service("vk_pusher").start() —
    у него нет обязательного аргумента stream_name (start_vk.py без него
    сразу завершается с ошибкой), здесь запускаем правильно, с именем
    реально активного потока."""
    subprocess.run(["pkill", "-f", C.VK_PUSHER_PROCESS_PATTERN], capture_output=True)
    time.sleep(0.3)
    subprocess.Popen(
        [C.SYSTEM_PYTHON_BIN, C.VK_PUSHER_SCRIPT, stream_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        cwd=C.LIVE_SERVER_DIR,
    )
