"""
Единственный источник истины для портов, путей и имён systemd-юнитов.

Ни один другой модуль, bash-скрипт или systemd-шаблон не должен хардкодить
эти значения повторно — именно повторение одних и тех же чисел в шести
разных файлах (см. историю astra-monitor, RTMP-порт 1935 vs 1936) было
причиной большинства багов старого приложения.

Bash-шаблоны (debian/*, installer/*) рендерятся из этого файла на этапе
сборки пакета (см. rtmp_server/setup/render_templates.py), а не
переписываются руками.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Сеть / порты
# ---------------------------------------------------------------------------

# RTMP-приём потока (nginx-rtmp). Актуальное значение подтверждено реально
# задеплоенным www/nginx.conf — НЕ 1935.
RTMP_PORT = 1936

# Публичный HTTP-порт nginx (reverse-proxy перед live-server + HLS + /hls).
HTTP_PROXY_PORT = 8082

# Backend Flask-приложений (слушают только на 127.0.0.1, наружу не торчат).
LIVE_SERVER_PORT = 8083
REBOOT_SERVER_PORT = 8084

# ---------------------------------------------------------------------------
# Пути сайта (продакшен-раскладка — НЕ переносится при установке, см. adopt.py)
# ---------------------------------------------------------------------------

SITE_ROOT = "/var/www"
LIVE_SERVER_DIR = f"{SITE_ROOT}/live-server"
REBOOT_SERVER_DIR = f"{SITE_ROOT}/reboot"
HLS_DIR = f"{SITE_ROOT}/hls"
SITE_VENV = f"{SITE_ROOT}/.venv"

LIVE_SERVER_SCRIPT = f"{LIVE_SERVER_DIR}/server.py"
REBOOT_SERVER_SCRIPT = f"{REBOOT_SERVER_DIR}/server.py"
VK_PUSHER_SCRIPT = f"{LIVE_SERVER_DIR}/start_vk.py"

# ---------------------------------------------------------------------------
# Кастомная сборка nginx (Astra не поставляет nginx с RTMP-модулем)
# ---------------------------------------------------------------------------

NGINX_PREFIX = "/usr/local/nginx"
NGINX_BIN = f"{NGINX_PREFIX}/sbin/nginx"
NGINX_CONF = f"{NGINX_PREFIX}/conf/nginx.conf"
NGINX_PID_FILE = f"{NGINX_PREFIX}/logs/nginx.pid"
NGINX_VERSION_MARKER = f"{NGINX_PREFIX}/.rtmp-server-installed-version"

# ---------------------------------------------------------------------------
# Само приложение RTMP-server
# ---------------------------------------------------------------------------

APP_NAME = "rtmp-server"
APP_INSTALL_DIR = "/opt/rtmp-server"
APP_LOG_DIR = "/var/log/rtmp-server"
APP_STAGING_DIR = "/opt/rtmp-server/.staging"
APP_STATE_FILE = "/var/lib/rtmp-server/state.json"

# Старая установка (astra-monitor) — используется только adopt.py при миграции,
# новый код на неё нигде больше не ссылается.
LEGACY_APP_INSTALL_DIR = "/opt/astra-monitor"

# ---------------------------------------------------------------------------
# systemd-юниты
# ---------------------------------------------------------------------------

UNIT_NGINX_RTMP = "nginx-rtmp.service"
UNIT_LIVE_SERVER = "live-server.service"
UNIT_REBOOT_SERVER = "reboot-server.service"

# Имя юнита reboot-сервера в старых установках (adopt.py принимает его
# как есть вместо разрушительного переименования).
LEGACY_UNIT_REBOOT_SERVER = "reboot.service"

# vk-pusher намеренно НЕ systemd-юнит: процесс живёт только во время
# трансляции (запускается вручную из сайта или через exec_push nginx-rtmp),
# а не как постоянный демон. Управляется через pgrep по этому паттерну.
VK_PUSHER_PROCESS_PATTERN = "start_vk.py"

ALL_MANAGED_UNITS = (UNIT_NGINX_RTMP, UNIT_LIVE_SERVER, UNIT_REBOOT_SERVER)

# ---------------------------------------------------------------------------
# GitHub — публичный репозиторий, откуда постятся релизы с зависимостями
# ---------------------------------------------------------------------------

GITHUB_REPO = "andreipiatov2015-cmyk/local"
GITHUB_API_RELEASES_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_API_RELEASES_BY_TAG = f"https://api.github.com/repos/{GITHUB_REPO}/releases/tags/{{tag}}"

NGINX_RTMP_ASSET_NAME_TEMPLATE = "nginx-rtmp-{version}.tar.gz"
CHECKSUMS_ASSET_NAME = "SHA256SUMS"

# ---------------------------------------------------------------------------
# HTTP health-check эндпоинты (используются site_monitor.py и updates/)
# ---------------------------------------------------------------------------

HEALTH_CHECK_ENDPOINTS = {
    "nginx (public proxy)": (f"http://127.0.0.1:{HTTP_PROXY_PORT}/", 200),
    "live-server (direct)": (f"http://127.0.0.1:{LIVE_SERVER_PORT}/", None),
    "reboot-server (direct)": (f"http://127.0.0.1:{REBOOT_SERVER_PORT}/", None),
}

# ---------------------------------------------------------------------------
# Обновление кода сайта — что НИКОГДА не перезаписывается при апдейте
# (в отличие от старого deploy.yml, который делал голый rsync и мог затереть
# рабочую БД/логи текущим содержимым репозитория).
# ---------------------------------------------------------------------------

SITE_UPDATE_EXCLUDES = (
    "app.db",
    "*.log",
    "logs/",
    "__pycache__/",
    "entries.json",
    "presets.json",
    "stream_targets.json",
    "vk_settings.json",
    "column_names.json",
    "_notes/",
)
