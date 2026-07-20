#!/usr/bin/env python3
import sys
import os
import json
import subprocess
import datetime
from pathlib import Path
import signal
import time

BASE_DIR = Path(__file__).resolve().parent
SETTINGS_FILE = BASE_DIR / "vk_settings.json"
TARGETS_FILE = BASE_DIR / "stream_targets.json"

FFMPEG = os.environ.get("FFMPEG_PATH", "ffmpeg")

# ВХОД: используем HLS (как в твоей рабочей ручной команде)
LOCAL_HLS_TEMPLATE = os.environ.get("LOCAL_HLS_TEMPLATE", "http://127.0.0.1:8082/hls/{stream}.m3u8")

# ЛОГИ
LOG_DIR = BASE_DIR / "logs"
START_LOG = LOG_DIR / "start_vk.log"

# LOCK: храним PID ffmpeg, чтобы не плодить процессы
LOCK_DIR = Path("/tmp")
LOCK_TEMPLATE = "start_vk_{stream}.lock"

# Защита от частых автозапусков (exec_push может дергать часто)
MIN_RESTART_SECONDS = int(os.environ.get("MIN_RESTART_SECONDS", "10"))


def log(msg: str):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    s = f"[{datetime.datetime.utcnow().isoformat()}] {msg}"
    try:
        with open(START_LOG, "a", encoding="utf-8") as f:
            f.write(s + "\n")
    except Exception:
        pass
    print(s, flush=True)


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        log(f"Ошибка чтения {path}: {e}")
        return default


def lock_path(stream: str) -> Path:
    return LOCK_DIR / LOCK_TEMPLATE.format(stream=stream)


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except Exception:
        # если прав не хватает - считаем что жив, чтобы не плодить
        return True


def read_lock(stream: str):
    p = lock_path(stream)
    if not p.exists():
        return None
    try:
        data = p.read_text(encoding="utf-8").strip().split()
        # формат: "<pid> <unix_ts>"
        pid = int(data[0])
        ts = int(data[1]) if len(data) > 1 else 0
        return pid, ts
    except Exception:
        return None


def write_lock(stream: str, pid: int):
    p = lock_path(stream)
    now = int(time.time())
    p.write_text(f"{pid} {now}\n", encoding="utf-8")


def remove_lock(stream: str):
    p = lock_path(stream)
    try:
        p.unlink(missing_ok=True)
    except Exception:
        pass


def get_vk_urls(settings: dict, targets: list):
    # приоритет: targets + target_ids, иначе vk_rtmp_url из settings
    target_ids = settings.get("target_ids") or []
    active_targets = [t for t in targets if t.get("enabled", True)]
    if target_ids:
        active_targets = [t for t in active_targets if t.get("id") in target_ids]

    urls = [t.get("url") for t in active_targets if t.get("url")]
    if urls:
        return urls

    one = settings.get("vk_rtmp_url")
    if one:
        return [one]

    return []


def popen_ffmpeg_live(stream: str, vk_url: str, settings: dict = None):
    """
    HLS -> VK с перекодированием (как твоя рабочая ручная команда)

    settings.bitrate_kbps / settings.resolution_height — опциональные поля,
    выставляемые через вкладку "Трансляция" в RTMP-server. Если не заданы —
    поведение полностью прежнее (без ограничения битрейта, без масштабирования).
    """
    settings = settings or {}
    hls_in = LOCAL_HLS_TEMPLATE.format(stream=stream)

    ff_log = LOG_DIR / f"ffmpeg_live_{stream}.log"
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    video_args = ["-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency"]

    bitrate_kbps = settings.get("bitrate_kbps")
    if bitrate_kbps:
        video_args += [
            "-b:v", f"{bitrate_kbps}k",
            "-maxrate", f"{bitrate_kbps}k",
            "-bufsize", f"{bitrate_kbps * 2}k",
        ]

    resolution_height = settings.get("resolution_height")
    if resolution_height:
        video_args += ["-vf", f"scale=-2:{resolution_height}"]

    video_args += ["-g", "60", "-keyint_min", "60", "-sc_threshold", "0", "-pix_fmt", "yuv420p"]

    cmd = [
        FFMPEG, "-hide_banner", "-loglevel", "info",
        "-re",
        "-fflags", "+genpts",
        "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "2",
        "-i", hls_in,
        *video_args,
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
        "-f", "flv",
        "-flvflags", "no_duration_filesize",
        vk_url
    ]

    log(f"Запуск ffmpeg в фоне: {' '.join(cmd)}")
    log(f"ffmpeg log: {ff_log}")

    try:
        f = open(ff_log, "a", encoding="utf-8")
    except Exception as e:
        log(f"Не могу открыть {ff_log}: {e}")
        f = None

    # ВАЖНО: не wait(), запускаем в фоне и сразу выходим
    p = subprocess.Popen(
        cmd,
        stdout=f if f else subprocess.DEVNULL,
        stderr=f if f else subprocess.DEVNULL,
        preexec_fn=os.setsid,
    )
    return p.pid


def main():
    if len(sys.argv) < 2:
        log("Нет имени потока (ожидался аргумент stream_name)")
        return 2

    stream = sys.argv[1]

    settings = load_json(SETTINGS_FILE, {})
    targets = load_json(TARGETS_FILE, [])

    enabled = bool(settings.get("enabled", False))
    if not enabled:
        log("VK пуш отключён (enabled=false) — выходим")
        return 0

    vk_urls = get_vk_urls(settings, targets)
    if not vk_urls:
        log("Нет VK URL (цели не выбраны и vk_rtmp_url пуст) — выходим")
        return 0

    # lock защита
    lk = read_lock(stream)
    if lk:
        old_pid, old_ts = lk
        if pid_alive(old_pid):
            # если только что стартовали — не дергаем
            if int(time.time()) - old_ts < MIN_RESTART_SECONDS:
                log(f"LOCK: ffmpeg уже запущен pid={old_pid}, недавно стартовал — пропуск")
                return 0
            log(f"LOCK: ffmpeg уже запущен pid={old_pid} — пропуск")
            return 0
        else:
            log(f"LOCK stale: pid={old_pid} не жив — удаляю lock")
            remove_lock(stream)

    # стартуем первый url (обычно один). если нужно мульти-пуш — можно расширить позже
    vk_url = vk_urls[0]
    pid = popen_ffmpeg_live(stream, vk_url, settings)
    write_lock(stream, pid)
    log(f"OK: ffmpeg запущен pid={pid}, stream={stream}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        log("Fatal error: " + str(e))
        raise
