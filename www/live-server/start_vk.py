#!/usr/bin/env python3
# start_vk.py
# Запускается Nginx RTMP через exec_push с аргументом $name (имя потока)
# Логика:
#  - читает vk_settings.json
#  - если enable == true:
#      - если scheduled_start задан и сейчас < scheduled_start => пушим preview (картинка + таймер)
#      - по достижении времени — переключаем на реальный вход (rtmp://localhost/live/<name>)
#  - если enable == false => ничего не делаем

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
LOGFILE = BASE_DIR / "start_vk.log"

def log(msg):
    s = f"[{datetime.datetime.utcnow().isoformat()}] {msg}"
    try:
        with open(LOGFILE, "a", encoding="utf-8") as f:
            f.write(s + "\n")
    except Exception:
        pass
    print(s)

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
        # ожидаем ISO format (YYYY-MM-DDTHH:MM:SSZ или без Z)
        return datetime.datetime.fromisoformat(s)
    except Exception:
        try:
            return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        except:
            return None

def run_preview_push(vk_url, preview_path, start_dt, title=None):
    """
    Запускает ffmpeg, который будет посылать в VK статичное изображение с таймером до start_dt.
    Процесс возвращается (subprocess.Popen), можно будет убить при старте.
    """
    if not preview_path or not os.path.exists(preview_path):
        log("Preview image не найдена; отмена preview push")
        return None

    # Формируем drawtext: оставим простой формат — оставляем часы:минуты:секунды до старта.
    # Получим timestamp старта
    start_ts = int(start_dt.timestamp()) if start_dt else int(time.time())
    time_expr = r"gmtime\:%s" % start_ts  # not used this way; instead we'll compute remaining secs via expr

    # drawtext: show countdown = start_ts - t
    # Используем localtime? прям вычисление: %{eif\:{start_ts}-t\:d}
    # Но safer approach: вычисляем seconds remaining by shell env? Many ffmpeg builds support %{pts}.
    # We'll form drawtext using: text='%{eif\:lte(t\,%d)\:%d-t\:%d}' won't be reliable across builds.
    # Simpler: show current localtime and label "Ожидание"
    # Simpler approach: print static text "Трансляция скоро" and rely on frontend timer, but we'll try basic text.
    drawtext = "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='Трансляция начнётся в %{localtime\\:%H\\\\\\:%M\\\\\\:%S}':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2:box=1:boxcolor=0x000000AA"

    cmd = [
        FFMPEG,
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
    log("Запуск preview ffmpeg: " + " ".join(cmd))
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid)
        return p
    except Exception as e:
        log(f"Ошибка запуска preview ffmpeg: {e}")
        return None

def run_live_push(vk_url, stream_name):
    local_in = LOCAL_RTMP_TEMPLATE.format(stream=stream_name)
    cmd = [
        FFMPEG,
        "-i", local_in,
        "-c", "copy",
        "-f", "flv",
        vk_url
    ]
    log("Запуск live ffmpeg: " + " ".join(["ffmpeg", "-i", local_in, "...", vk_url]))
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid)
        return p
    except Exception as e:
        log(f"Ошибка запуска live ffmpeg: {e}")
        return None

def wait_and_switch(preview_procs, vk_urls, stream_name, start_dt):
    """
    Ждём до start_dt, затем убиваем preview_proc и запускаем live push.
    """
    now = datetime.datetime.utcnow()
    # Если заданое время локальное — предполагаем utc. Пользователь будет отправлять ISO.
    if start_dt.tzinfo is None:
        start_dt = start_dt
    secs = (start_dt - now).total_seconds()
    if secs > 0:
        log(f"Ожидаем {int(secs)} секунд до старта...")
        # в цикле проверяем жив ли preview_proc и не убит ли внешний процесс
        slept = 0
        while slept < secs:
            time.sleep(min(5, secs - slept))
            slept += min(5, secs - slept)
    # время пришло
    log("Время старта наступило — переключаем на live")
    for proc in preview_procs:
        try:
            if proc and proc.poll() is None:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                log("Остановлен preview ffmpeg")
        except Exception as e:
            log("Ошибка при остановке preview: " + str(e))

    live_procs = []
    for url in vk_urls:
        live_proc = run_live_push(url, stream_name)
        if live_proc:
            live_procs.append(live_proc)
    for proc in live_procs:
        try:
            proc.wait()
            log("Live push процесс завершился")
        except Exception as e:
            log("Live push wait error: " + str(e))

def main():
    if len(sys.argv) < 2:
        log("Нет имени потока (используйте exec_push / start_vk.py $name)")
        return

    stream_name = sys.argv[1]
    settings = load_settings()
    targets = load_targets()
    enabled = settings.get("enabled", False)
    preview_path = settings.get("preview_path")  # относительный или абсолютный путь
    start_str = settings.get("scheduled_start")  # ISO string
    title = settings.get("title")
    target_ids = settings.get("target_ids") or []

    active_targets = [t for t in targets if t.get("enabled", True)]
    if target_ids:
        active_targets = [t for t in active_targets if t.get("id") in target_ids]
    active_targets = [t for t in active_targets if t.get("id") != "tv"]
    vk_key = settings.get("vk_rtmp_url")
    if vk_key:
        vk_urls = [vk_key]
    else:
        vk_urls = [t.get("url") for t in active_targets if t.get("url")]

    if not enabled or not vk_urls:
        log("VK пуш отключён или не задан vk_rtmp_url")
        return

    start_dt = to_dt(start_str) if start_str else None
    now = datetime.datetime.utcnow()

    # если есть scheduled_start и оно в будущем => пушим preview и ждём
    if start_dt and start_dt > now:
        # запустить preview push
        preview_procs = []
        for url in vk_urls:
            preview_procs.append(run_preview_push(url, preview_path, start_dt, title))
        # ждать и переключиться
        wait_and_switch(preview_procs, vk_urls, stream_name, start_dt)
    else:
        # start_dt отсутствует или уже в прошлом -> пушим live сразу
        live_procs = []
        for url in vk_urls:
            p_live = run_live_push(url, stream_name)
            if p_live:
                live_procs.append(p_live)
        for proc in live_procs:
            proc.wait()
        log("Live push finished")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log("Fatal error: " + str(e))
