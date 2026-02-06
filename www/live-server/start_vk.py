#!/usr/bin/env python3
import sys
import os
import json
import subprocess
import time
import datetime
from pathlib import Path
import signal

BASE_DIR = Path(__file__).resolve().parent
SETTINGS_FILE = BASE_DIR / "vk_settings.json"
TARGETS_FILE = BASE_DIR / "stream_targets.json"
FFMPEG = os.environ.get("FFMPEG_PATH", "ffmpeg")
LOCAL_RTMP_TEMPLATE = "rtmp://127.0.0.1/live/{stream}"
LOGFILE = BASE_DIR / "logs" / "start_vk.log"

LOCK_DIR = Path("/tmp")

def log(msg):
    s = f"[{datetime.datetime.utcnow().isoformat()}] {msg}"
    try:
        with open(LOGFILE, "a", encoding="utf-8") as f:
            f.write(s + "\n")
    except Exception:
        pass
    print(s, flush=True)

def load_settings():
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            log(f"Ошибка чтения настроек: {e}")
            return {}
    return {}

def load_targets():
    if TARGETS_FILE.exists():
        try:
            return json.loads(TARGETS_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            log(f"Ошибка чтения целей трансляции: {e}")
            return []
    return []

def to_dt(s):
    if not s:
        return None
    try:
        return datetime.datetime.fromisoformat(s)
    except Exception:
        try:
            return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

def acquire_lock(stream_name: str) -> Path | None:
    lock = LOCK_DIR / f"start_vk_{stream_name}.lock"
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        os.write(fd, str(os.getpid()).encode("utf-8"))
        os.close(fd)
        return lock
    except FileExistsError:
        # можно проверить жив ли PID внутри, но пока просто не запускаем второй раз
        log(f"LOCK exists ({lock}), skip запуск для {stream_name}")
        return None

def release_lock(lock: Path | None):
    if not lock:
        return
    try:
        lock.unlink()
    except FileNotFoundError:
        pass
    except Exception as e:
        log(f"Не смог удалить lock {lock}: {e}")

def popen_ffmpeg(cmd, stream_name: str, kind: str):
    """
    Запуск ffmpeg с выводом в файл, чтобы видеть ошибки VK.
    """
    fflog = BASE_DIR / "logs" / f"ffmpeg_{kind}_{stream_name}.log"
    try:
        logf = open(fflog, "a", encoding="utf-8")
    except Exception as e:
        log(f"Не могу открыть ffmpeg log {fflog}: {e}")
        logf = None

    log(f"Запуск {kind} ffmpeg: {' '.join(cmd)} (log: {fflog})")
    try:
        p = subprocess.Popen(
            cmd,
            stdout=logf if logf else None,
            stderr=logf if logf else None,
            preexec_fn=os.setsid
        )
        return p, fflog
    except Exception as e:
        log(f"Ошибка запуска ffmpeg: {e}")
        if logf:
            logf.close()
        return None, fflog

def run_preview_push(vk_url, preview_path, start_dt):
    if not preview_path or not os.path.exists(preview_path):
        log("Preview image не найдена; отмена preview push")
        return None, None

    drawtext = (
        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        "text='Трансляция скоро':fontsize=48:fontcolor=white:"
        "x=(w-text_w)/2:y=(h-text_h)/2:box=1:boxcolor=0x000000AA"
    )

    cmd = [
        FFMPEG,
        "-hide_banner",
        "-loglevel", "info",
        "-re",
        "-loop", "1",
        "-i", preview_path,
        "-vf", drawtext,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-tune", "stillimage",
        "-r", "25",
        "-g", "50",
        "-b:v", "1500k",
        "-f", "flv",
        vk_url
    ]
    return popen_ffmpeg(cmd, "preview", "preview")

def run_live_push(vk_url, stream_name):
    local_in = LOCAL_RTMP_TEMPLATE.format(stream=stream_name)
    cmd = [
        FFMPEG,
        "-hide_banner",
        "-loglevel", "info",
        # таймауты на сеть (чтобы не висеть бесконечно при проблемах)
        "-rw_timeout", "5000000",  # 5s
        "-i", local_in,
        "-c", "copy",
        "-f", "flv",
        vk_url
    ]
    return popen_ffmpeg(cmd, stream_name, "live")

def kill_proc(proc, name="proc"):
    try:
        if proc and proc.poll() is None:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            log(f"Остановлен {name} (pid={proc.pid})")
    except Exception as e:
        log(f"Ошибка при остановке {name}: {e}")

def wait_and_switch(preview_procs, vk_urls, stream_name, start_dt):
    now = datetime.datetime.utcnow()
    secs = (start_dt - now).total_seconds()
    if secs > 0:
        log(f"Ожидаем {int(secs)} секунд до старта...")
        time.sleep(secs)

    log("Время старта наступило — переключаем на live")
    for proc, _ in preview_procs:
        kill_proc(proc, "preview ffmpeg")

    live_procs = []
    for url in vk_urls:
        p, logpath = run_live_push(url, stream_name)
        if p:
            live_procs.append((p, logpath))

    for proc, logpath in live_procs:
        rc = proc.wait()
        log(f"Live ffmpeg завершился rc={rc}, log={logpath}")

def main():
    if len(sys.argv) < 2:
        log("Нет имени потока (используйте exec_push / start_vk.py $name)")
        return

    stream_name = sys.argv[1]
    lock = acquire_lock(stream_name)
    if lock is None:
        return

    try:
        settings = load_settings()
        targets = load_targets()

        enabled = settings.get("enabled", False)
        preview_path = settings.get("preview_path")
        start_str = settings.get("scheduled_start")
        target_ids = settings.get("target_ids") or []

        active_targets = [t for t in targets if t.get("enabled", True)]
        if target_ids:
            active_targets = [t for t in active_targets if t.get("id") in target_ids]

        vk_urls = [t.get("url") for t in active_targets if t.get("url")]
        if not vk_urls:
            vk_key = settings.get("vk_rtmp_url")
            if vk_key:
                vk_urls = [vk_key]

        if not enabled or not vk_urls:
            log("VK пуш отключён или цели не выбраны")
            return

        start_dt = to_dt(start_str) if start_str else None
        now = datetime.datetime.utcnow()

        if start_dt and start_dt > now:
            preview_procs = []
            for url in vk_urls:
                p, logpath = run_preview_push(url, preview_path, start_dt)
                if p:
                    preview_procs.append((p, logpath))
            wait_and_switch(preview_procs, vk_urls, stream_name, start_dt)
        else:
            live_procs = []
            for url in vk_urls:
                p, logpath = run_live_push(url, stream_name)
                if p:
                    live_procs.append((p, logpath))
            for proc, logpath in live_procs:
                rc = proc.wait()
                log(f"Live ffmpeg завершился rc={rc}, log={logpath}")

    finally:
        release_lock(lock)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log("Fatal error: " + str(e))
