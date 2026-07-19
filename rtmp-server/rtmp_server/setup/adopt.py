"""Определение уже развёрнутого сайта/юнитов на "боевой" машине.

Запускается в начале postinst, до старта/рестарта любых юнитов.
Никогда не предполагает чистую машину: сайт на /var/www уже может
годами работать под старыми systemd-юнитами и старым /opt/astra-monitor.
Ничего не удаляет и не переименовывает разрушительно — только сообщает,
что нашёл, и там, где нужно, создаёт совместимые alias'ы.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from rtmp_server.config import constants as C


@dataclass
class EnvironmentReport:
    site_present: bool
    live_server_present: bool
    reboot_server_present: bool
    legacy_reboot_unit_present: bool
    legacy_app_present: bool
    notes: list[str] = field(default_factory=list)


def _unit_exists(unit: str) -> bool:
    result = subprocess.run(
        ["systemctl", "list-unit-files", unit], capture_output=True, text=True
    )
    return unit in result.stdout


def detect_environment() -> EnvironmentReport:
    live_server_present = Path(C.LIVE_SERVER_SCRIPT).exists()
    reboot_server_present = Path(C.REBOOT_SERVER_SCRIPT).exists()
    legacy_reboot_unit = _unit_exists(C.LEGACY_UNIT_REBOOT_SERVER) and not _unit_exists(C.UNIT_REBOOT_SERVER)
    legacy_app_present = Path(C.LEGACY_APP_INSTALL_DIR).exists()

    notes = []
    if live_server_present or reboot_server_present:
        notes.append(f"Обнаружен существующий сайт в {C.SITE_ROOT} — путь не переносится.")
    if legacy_reboot_unit:
        notes.append(
            f"Юнит {C.LEGACY_UNIT_REBOOT_SERVER} уже существует — создаю совместимый alias "
            f"{C.UNIT_REBOOT_SERVER} вместо разрушительного переименования."
        )
    if legacy_app_present:
        notes.append(
            f"Старое приложение найдено в {C.LEGACY_APP_INSTALL_DIR} — оставлено как есть, "
            f"удалите вручную после проверки новой установки."
        )

    return EnvironmentReport(
        site_present=live_server_present or reboot_server_present,
        live_server_present=live_server_present,
        reboot_server_present=reboot_server_present,
        legacy_reboot_unit_present=legacy_reboot_unit,
        legacy_app_present=legacy_app_present,
        notes=notes,
    )


def create_legacy_unit_alias() -> None:
    """systemd alias: reboot-server.service -> существующий reboot.service,
    чтобы новый код мог всегда обращаться к каноническому имени, не трогая
    юнит, который, возможно, уже кем-то используется/зависим."""
    alias_path = Path(f"/etc/systemd/system/{C.UNIT_REBOOT_SERVER}")
    if alias_path.exists() or alias_path.is_symlink():
        return
    alias_path.symlink_to(f"/etc/systemd/system/{C.LEGACY_UNIT_REBOOT_SERVER}")
    subprocess.run(["systemctl", "daemon-reload"], check=False)


def print_report(report: EnvironmentReport) -> None:
    print("=== RTMP-server: отчёт об окружении ===")
    print(f"Сайт на {C.SITE_ROOT}: {'найден' if report.site_present else 'НЕ найден'}")
    print(f"  live-server: {'есть' if report.live_server_present else 'нет'}")
    print(f"  reboot-server: {'есть' if report.reboot_server_present else 'нет'}")
    print(f"Старое приложение (astra-monitor): {'найдено' if report.legacy_app_present else 'нет'}")
    for note in report.notes:
        print(f"  * {note}")
    print("========================================")


def main() -> int:
    report = detect_environment()
    print_report(report)
    if report.legacy_reboot_unit_present:
        create_legacy_unit_alias()
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
