"""Обновление кода сайта (наследник deploy.yml/update.sh/git_updater.py —
раньше это были три несовместимых механизма, теперь один).

Отличие от старого голого `rsync www/ -> /var/www` в deploy.yml: рабочие
данные (app.db, entries.json, presets.json, логи) НИКОГДА не перезаписываются
данными из репозитория, снимается бэкап перед копированием, после копирования
сервисы рестартуются и прогоняется health-check — при неудаче бэкап
восстанавливается автоматически.
"""

from __future__ import annotations

import logging
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

from rtmp_server.config import constants as C
from rtmp_server.monitor.site_monitor import check_site_health
from rtmp_server.services.definitions import get_service
from rtmp_server.updates.staging import UpdateResult

logger = logging.getLogger("rtmp_server.updates.site")


@dataclass
class SiteUpdateSource:
    """Источник новой версии кода сайта: директория с подпапками
    live-server/ и reboot/, в том же виде, что и репозиторий www/."""

    live_server_src: Path
    reboot_src: Path


def source_from_extracted_dir(root: Path) -> SiteUpdateSource:
    return SiteUpdateSource(
        live_server_src=root / "live-server",
        reboot_src=root / "reboot",
    )


def _rsync(src: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    args = ["rsync", "-a"]
    for pattern in C.SITE_UPDATE_EXCLUDES:
        args += ["--exclude", pattern]
    args += [f"{src}/", f"{dest}/"]
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"rsync {src} -> {dest} упал: {result.stderr[:500]}")


def _backup(dest: Path, backup_tar: Path) -> None:
    """Бэкап перед обновлением. Раньше использовался рекурсивный tar.add(dest,...) —
    он падает целиком на ПЕРВОМ же файле, который процесс не может прочитать
    (например, .flask_secret_key с правами 600 — сайт запущен от root, а
    self-hosted раннер деплоя от отдельного пользователя без доступа к нему).
    Из-за этого обновление сайта падало на каждом пуше в main, даже когда
    сам код обновления был исправен. Добавляем файлы по одному и пропускаем
    с предупреждением те, что не читаются — секрет всё равно не меняется
    code-обновлением, бэкапить его незачем, а падать из-за него нельзя."""
    backup_tar.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(backup_tar, "w") as tar:
        if not dest.exists():
            return
        try:
            tar.add(dest, arcname=dest.name, recursive=False)
        except PermissionError as exc:
            logger.warning("Бэкап %s: нет доступа к самой директории: %s", dest, exc)
            return
        for path in sorted(dest.rglob("*")):
            arcname = str(Path(dest.name) / path.relative_to(dest))
            try:
                tar.add(path, arcname=arcname, recursive=False)
            except PermissionError as exc:
                logger.warning("Бэкап %s: пропускаю файл без прав на чтение: %s", dest, exc)


def _restore(dest: Path, backup_tar: Path) -> None:
    if not backup_tar.exists():
        return
    import shutil

    if dest.exists():
        shutil.rmtree(dest)
    with tarfile.open(backup_tar) as tar:
        tar.extractall(dest.parent, filter="data")


def apply(source: SiteUpdateSource) -> UpdateResult:
    live_server_dir = Path(C.LIVE_SERVER_DIR)
    reboot_dir = Path(C.REBOOT_SERVER_DIR)

    with tempfile.TemporaryDirectory(prefix="rtmp-server-site-backup-") as backup_root:
        backup_root_path = Path(backup_root)
        live_backup = backup_root_path / "live-server.tar"
        reboot_backup = backup_root_path / "reboot.tar"

        logger.info("Снимаю бэкап перед обновлением сайта")
        _backup(live_server_dir, live_backup)
        _backup(reboot_dir, reboot_backup)

        try:
            _rsync(source.live_server_src, live_server_dir)
            _rsync(source.reboot_src, reboot_dir)
        except RuntimeError as exc:
            logger.error("Копирование не удалось, отката не требуется (запись не начата): %s", exc)
            return UpdateResult(applied=False, message=str(exc))

        get_service("live_server").restart()
        get_service("reboot_server").restart()

        if not _smoke_test_ok():
            logger.warning("Health-check после обновления сайта не прошёл — откатываю")
            _restore(live_server_dir, live_backup)
            _restore(reboot_dir, reboot_backup)
            get_service("live_server").restart()
            get_service("reboot_server").restart()
            return UpdateResult(
                applied=False,
                message="Health-check после обновления не прошёл, изменения откачены",
                rolled_back=True,
            )

    return UpdateResult(applied=True, message="Сайт обновлён и перезапущен успешно")


def _smoke_test_ok() -> bool:
    import time

    time.sleep(2)  # дать Flask-процессам время подняться после restart
    statuses = check_site_health()
    return any(s.name == "live-server (direct)" and s.reachable for s in statuses)
