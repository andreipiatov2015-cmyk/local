"""Определение уже развёрнутого сайта/юнитов на "боевой" машине +
автозамена старого astra-monitor.

Запускается в начале postinst, до старта/рестарта любых юнитов сайта.
Никогда не предполагает чистую машину: сайт на /var/www уже может годами
работать под старыми systemd-юнитами. Сайт (nginx-rtmp/live-server/
reboot-server) НИКОГДА не трогается разрушительно — только совместимые
alias'ы для юнитов при необходимости.

Старое приложение astra-monitor — другое дело: по прямому указанию
владельца новая установка должна сама находить и заменять его, а не
оставлять рядом (см. remove_legacy_app).
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
    legacy_app_removed: bool = False
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


def remove_legacy_app() -> list[str]:
    """Останавливает и полностью удаляет старую установку astra-monitor.

    Это НЕ трогает сайт (/var/www, nginx, live-server/reboot-server) —
    только сам старый admin-инструмент, который RTMP-server заменяет.
    Безопасно вызывать повторно (если уже удалено — просто ничего не делает).
    """
    removed: list[str] = []

    subprocess.run(["pkill", "-f", C.LEGACY_APP_PROCESS_PATTERN], capture_output=True)

    legacy_dir = Path(C.LEGACY_APP_INSTALL_DIR)
    if legacy_dir.exists():
        import shutil

        shutil.rmtree(legacy_dir, ignore_errors=True)
        removed.append(str(legacy_dir))

    for path_str in (C.LEGACY_APP_BINARY, C.LEGACY_APP_DESKTOP_FILE):
        path = Path(path_str)
        if path.exists() or path.is_symlink():
            path.unlink(missing_ok=True)
            removed.append(str(path))

    return removed


def print_report(report: EnvironmentReport) -> None:
    print("=== RTMP-server: отчёт об окружении ===")
    print(f"Сайт на {C.SITE_ROOT}: {'найден' if report.site_present else 'НЕ найден'}")
    print(f"  live-server: {'есть' if report.live_server_present else 'нет'}")
    print(f"  reboot-server: {'есть' if report.reboot_server_present else 'нет'}")
    print(f"Старое приложение (astra-monitor): {'найдено' if report.legacy_app_present else 'нет'}")
    if report.legacy_app_removed:
        print("  -> удалено автоматически, заменено на RTMP-server")
    for note in report.notes:
        print(f"  * {note}")
    print("========================================")


def main() -> int:
    report = detect_environment()

    if report.legacy_app_present:
        removed = remove_legacy_app()
        report.legacy_app_removed = bool(removed)
        for path in removed:
            report.notes.append(f"Удалено (старое приложение): {path}")

    print_report(report)

    if report.legacy_reboot_unit_present:
        create_legacy_unit_alias()

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
