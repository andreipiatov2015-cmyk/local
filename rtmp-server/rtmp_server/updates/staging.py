"""Общий движок обновлений: fetch -> verify -> stage -> swap -> smoke-test -> rollback.

Наследует идею старого safe_updater.py (единственного из четырёх старых
механизмов обновления, который действительно был безопасным — обновлял
приложение через staging в /tmp и никогда не трогал nginx/ffmpeg вслепую),
но обобщает её так, чтобы её использовали ОБА потребителя: обновление
самого RTMP-server (app_updater.py) и обновление кода сайта (site_updater.py).
Раньше это были два независимых куска логики (и ещё update.sh/git_updater.py
третьим и четвёртым способом) — теперь один проверенный путь.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
import time
import tarfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

logger = logging.getLogger("rtmp_server.updates")

DOWNLOAD_CHUNK_SIZE = 65536


class UpdateError(Exception):
    pass


class DownloadTimeoutError(UpdateError):
    pass


@dataclass
class UpdateResult:
    applied: bool
    message: str
    rolled_back: bool = False


def download_file(url: str, dest: Path, timeout: float = 60.0) -> Path:
    """Скачивает url в dest с жёстким ОБЩИМ дедлайном на всю передачу.

    urllib.request.urlopen(timeout=...) ограничивает только каждую отдельную
    операцию на сокете — если сервер отдаёт данные "по капле" (медленнее
    таймаута, но без явных пауз), каждое отдельное чтение укладывается в
    лимит, а суммарное время может растянуться на сколько угодно. Именно
    так самообновление зависало без вообще какой-либо обратной связи в GUI:
    воркер-поток просто никогда не завершался. Здесь дедлайн проверяется
    между чанками независимо от поведения отдельных чтений."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Скачивание %s -> %s", url, dest)
    deadline = time.monotonic() + timeout
    request = urllib.request.Request(url, headers={"User-Agent": "rtmp-server-updater"})
    with urllib.request.urlopen(request, timeout=timeout) as response, open(dest, "wb") as fh:
        while True:
            if time.monotonic() > deadline:
                raise DownloadTimeoutError(f"Скачивание {url} не уложилось в {timeout:.0f} сек.")
            chunk = response.read(DOWNLOAD_CHUNK_SIZE)
            if not chunk:
                break
            fh.write(chunk)
    return dest


def verify_sha256(path: Path, expected_hex: str) -> bool:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    actual = digest.hexdigest()
    if actual.lower() != expected_hex.lower():
        logger.error("Чексумма не совпадает для %s: ожидалось %s, получено %s", path, expected_hex, actual)
        return False
    return True


def parse_sha256sums(text: str) -> dict[str, str]:
    """Парсит файл вида '<hex>  <filename>' построчно."""
    result = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            result[parts[1].strip()] = parts[0].strip()
    return result


def extract_tarball(archive: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as tar:
        tar.extractall(dest_dir, filter="data")


@dataclass
class StagedSwap:
    """Атомарная (насколько возможно на обычной ФС) замена директории
    с сохранением бэкапа для отката."""

    target_dir: Path
    staging_dir: Path
    backup_dir: Path
    smoke_test: Callable[[], bool] | None = None
    post_swap: Callable[[], None] | None = None
    errors: list[str] = field(default_factory=list)

    def apply(self) -> UpdateResult:
        if not self.staging_dir.exists():
            return UpdateResult(applied=False, message=f"Staging-директория отсутствует: {self.staging_dir}")

        had_target = self.target_dir.exists()
        if self.backup_dir.exists():
            shutil.rmtree(self.backup_dir)

        try:
            if had_target:
                shutil.move(str(self.target_dir), str(self.backup_dir))
            shutil.move(str(self.staging_dir), str(self.target_dir))
        except OSError as exc:
            self._restore_backup(had_target)
            return UpdateResult(applied=False, message=f"Ошибка swap: {exc}", rolled_back=True)

        if self.post_swap is not None:
            try:
                self.post_swap()
            except Exception as exc:  # рестарт сервисов и т.п.
                logger.exception("post_swap упал")
                self._rollback(had_target)
                return UpdateResult(applied=False, message=f"post_swap упал: {exc}", rolled_back=True)

        if self.smoke_test is not None and not self._run_smoke_test():
            self._rollback(had_target)
            return UpdateResult(applied=False, message="smoke-test не прошёл после обновления", rolled_back=True)

        if self.backup_dir.exists():
            shutil.rmtree(self.backup_dir, ignore_errors=True)

        return UpdateResult(applied=True, message="Обновление применено успешно")

    def _run_smoke_test(self) -> bool:
        try:
            return bool(self.smoke_test())
        except Exception:
            logger.exception("smoke_test выбросил исключение")
            return False

    def _rollback(self, had_target: bool) -> None:
        logger.warning("Откат обновления: %s", self.target_dir)
        if self.target_dir.exists():
            shutil.rmtree(self.target_dir, ignore_errors=True)
        self._restore_backup(had_target)
        if self.post_swap is not None:
            try:
                self.post_swap()
            except Exception:
                logger.exception("post_swap при откате тоже упал — нужна ручная проверка")

    def _restore_backup(self, had_target: bool) -> None:
        if had_target and self.backup_dir.exists():
            shutil.move(str(self.backup_dir), str(self.target_dir))
