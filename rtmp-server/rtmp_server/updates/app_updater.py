"""Самообновление RTMP-server (наследник идеи safe_updater.py).

Проверяет GitHub Releases (репозиторий публичный — без токена), сравнивает
версию с VERSION текущей установки, скачивает .deb-ассет и SHA256SUMS,
проверяет чексумму и ставит через `dpkg -i`. Никогда не трогает сайт —
это отдельный updater (site_updater.py) с отдельной зоной ответственности.
"""

from __future__ import annotations

import json
import logging
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from rtmp_server import __version__ as CURRENT_VERSION
from rtmp_server.config import constants as C
from rtmp_server.updates.staging import (
    UpdateResult,
    download_file,
    parse_sha256sums,
    verify_sha256,
)

logger = logging.getLogger("rtmp_server.updates.app")


@dataclass
class ReleaseInfo:
    tag: str
    version: str
    deb_asset_name: str
    deb_asset_url: str
    checksums_url: str


def _fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "rtmp-server-updater", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def check_for_update() -> ReleaseInfo | None:
    """Возвращает ReleaseInfo, если на GitHub есть версия новее текущей, иначе None."""
    data = _fetch_json(C.GITHUB_API_RELEASES_LATEST)
    tag = data.get("tag_name", "")
    version = tag.lstrip("v")
    if version == CURRENT_VERSION:
        return None

    assets = {asset["name"]: asset["browser_download_url"] for asset in data.get("assets", [])}
    deb_name = next((name for name in assets if name.endswith(".deb")), None)
    if not deb_name or C.CHECKSUMS_ASSET_NAME not in assets:
        logger.warning("Релиз %s не содержит .deb или %s — пропускаю", tag, C.CHECKSUMS_ASSET_NAME)
        return None

    return ReleaseInfo(
        tag=tag,
        version=version,
        deb_asset_name=deb_name,
        deb_asset_url=assets[deb_name],
        checksums_url=assets[C.CHECKSUMS_ASSET_NAME],
    )


def apply_update(release: ReleaseInfo, download_dir: Path = Path("/tmp/rtmp-server-update")) -> UpdateResult:
    download_dir.mkdir(parents=True, exist_ok=True)
    # Имя файла ДОЛЖНО совпадать с реальным именем ассета — именно под этим
    # именем оно ищется в SHA256SUMS. Раньше здесь реконструировали имя как
    # f"rtmp-server-{version}.deb", а настоящий ассет называется
    # rtmp-server_{version}-1_all.deb — несовпадение имён давало ложное
    # "чексумма не совпадает" (ключ просто не находился в словаре).
    deb_path = download_dir / release.deb_asset_name
    checksums_path = download_dir / C.CHECKSUMS_ASSET_NAME

    try:
        download_file(release.deb_asset_url, deb_path)
        download_file(release.checksums_url, checksums_path)
    except OSError as exc:
        return UpdateResult(applied=False, message=f"Не удалось скачать релиз: {exc}")

    checksums = parse_sha256sums(checksums_path.read_text())
    expected = checksums.get(deb_path.name)
    if not expected or not verify_sha256(deb_path, expected):
        return UpdateResult(applied=False, message="Чексумма .deb не совпадает — установка отменена")

    result = subprocess.run(["dpkg", "-i", str(deb_path)], capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("dpkg -i упал: %s", result.stderr)
        return UpdateResult(applied=False, message=f"dpkg -i завершился с ошибкой: {result.stderr[:500]}")

    return UpdateResult(
        applied=True,
        message=(
            f"RTMP-server обновлён до {release.version}. "
            "Закройте и снова откройте приложение (или systemctl restart "
            "rtmp-server-gui.service), чтобы увидеть новую версию — "
            "текущее окно продолжает работать со старым кодом в памяти."
        ),
    )
