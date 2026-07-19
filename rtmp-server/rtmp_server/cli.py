"""rtmp-server-ctl — безголовый вход в RTMP-server.

Используется:
  - postinst .deb-пакета (проверка окружения, первичный health-check)
  - .github/workflows/deploy.yml (site-update apply вместо голого rsync)
  - оператором вручную с консоли
  - GUI-приложением (те же функции, что и кнопки в интерфейсе)

Один код на все три сценария — раньше у обновления сайта было 3-4
несовместимых пути (git_updater.py, safe_updater.py, update.sh, rsync
в deploy.yml), теперь один.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rtmp_server import __version__
from rtmp_server.monitor import site_monitor, system_monitor
from rtmp_server.services.definitions import get_all_services, get_service
from rtmp_server.site_admin import users as site_users
from rtmp_server.updates import app_updater, site_updater


def cmd_service_status(args: argparse.Namespace) -> int:
    services = [get_service(args.name)] if args.name else get_all_services()
    for svc in services:
        status = svc.status()
        pid_part = f" pid={status.pid}" if status.pid else ""
        port_part = f" port={status.port}" if status.port else ""
        print(f"{status.name:15s} {status.state.value:10s}{pid_part}{port_part}  {status.detail}")
    return 0


def cmd_service_action(args: argparse.Namespace) -> int:
    targets = get_all_services() if args.name == "all" else [get_service(args.name)]
    for svc in targets:
        print(f"{args.action} {svc.name}...")
        getattr(svc, args.action)()
    return 0


def cmd_system_status(args: argparse.Namespace) -> int:
    stats = system_monitor.get_system_stats()
    print(f"CPU:    {stats.cpu_percent:.1f}% ({stats.cpu_count} cores)")
    print(f"Memory: {stats.memory_percent:.1f}% ({stats.memory_used_mb}/{stats.memory_total_mb} MB)")
    print(f"Disk:   {stats.disk_percent:.1f}% ({stats.disk_used_gb}/{stats.disk_total_gb} GB)")
    print(f"Load:   {stats.load_average}")
    print(f"Uptime: {stats.uptime_seconds}s")
    print()
    for port, info in system_monitor.get_listening_ports().items():
        state = "LISTENING" if info["listening"] else "closed"
        print(f"  :{port:<6} {info['label']:30s} {state}")
    return 0


def cmd_site_health(args: argparse.Namespace) -> int:
    ok = True
    for status in site_monitor.check_site_health():
        mark = "OK" if status.reachable else "FAIL"
        print(f"[{mark}] {status.name:25s} {status.url}  http_status={status.http_status}  {status.error or ''}")
        ok = ok and status.reachable
    return 0 if ok else 1


def cmd_site_update_apply(args: argparse.Namespace) -> int:
    source = site_updater.source_from_extracted_dir(Path(args.source))
    result = site_updater.apply(source)
    print(result.message)
    return 0 if result.applied else 1


def cmd_app_update_check(args: argparse.Namespace) -> int:
    release = app_updater.check_for_update()
    if release is None:
        print(f"RTMP-server актуален (версия {__version__})")
        return 0
    print(f"Доступно обновление: {__version__} -> {release.version}")
    return 10  # отдельный код для "есть обновление" — удобно для скриптов/GUI


def cmd_app_update_apply(args: argparse.Namespace) -> int:
    release = app_updater.check_for_update()
    if release is None:
        print(f"RTMP-server уже актуален (версия {__version__})")
        return 0
    result = app_updater.apply_update(release)
    print(result.message)
    return 0 if result.applied else 1


def _prompt_password(label: str) -> str:
    import getpass

    return getpass.getpass(f"{label}: ")


def cmd_site_users_list(args: argparse.Namespace) -> int:
    for user in site_users.list_users():
        verified = "verified" if user.is_verified else "unverified"
        print(f"{user.id:4d}  {user.username:20s} {user.email:30s} {user.role:8s} {verified:10s} {user.full_name or ''}")
    return 0


def cmd_site_users_add(args: argparse.Namespace) -> int:
    password = args.password or _prompt_password("Пароль нового пользователя")
    user_id = site_users.create_user(
        args.username, args.email, password, full_name=args.full_name or "", role=args.role
    )
    print(f"Создан пользователь id={user_id}")
    return 0


def cmd_site_users_edit(args: argparse.Namespace) -> int:
    site_users.update_user(args.id, email=args.email, full_name=args.full_name, role=args.role)
    print(f"Пользователь id={args.id} обновлён")
    return 0


def cmd_site_users_reset_password(args: argparse.Namespace) -> int:
    password = args.password or _prompt_password("Новый пароль")
    site_users.reset_password(args.id, password)
    print(f"Пароль пользователя id={args.id} сброшен")
    return 0


def cmd_site_users_delete(args: argparse.Namespace) -> int:
    site_users.delete_user(args.id)
    print(f"Пользователь id={args.id} удалён")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rtmp-server-ctl")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="статус сервисов сайта")
    p_status.add_argument("name", nargs="?", default=None, choices=[s.name for s in get_all_services()])
    p_status.set_defaults(func=cmd_service_status)

    for action in ("start", "stop", "restart"):
        p = sub.add_parser(action, help=f"{action} сервис(ы)")
        p.add_argument("name", choices=[*[s.name for s in get_all_services()], "all"])
        p.set_defaults(func=cmd_service_action, action=action)

    p_system = sub.add_parser("system", help="системные метрики")
    p_system.set_defaults(func=cmd_system_status)

    p_health = sub.add_parser("health", help="HTTP health-check сайта")
    p_health.set_defaults(func=cmd_site_health)

    p_site_update = sub.add_parser("site-update", help="обновление кода сайта")
    site_update_sub = p_site_update.add_subparsers(dest="site_update_command", required=True)
    p_site_apply = site_update_sub.add_parser("apply", help="применить обновление из директории")
    p_site_apply.add_argument("--source", required=True, help="директория с распакованным www/ (live-server/, reboot/)")
    p_site_apply.set_defaults(func=cmd_site_update_apply)

    p_app_update = sub.add_parser("app-update", help="самообновление RTMP-server")
    app_update_sub = p_app_update.add_subparsers(dest="app_update_command", required=True)
    app_update_sub.add_parser("check", help="проверить наличие новой версии").set_defaults(func=cmd_app_update_check)
    app_update_sub.add_parser("apply", help="скачать и установить новую версию").set_defaults(func=cmd_app_update_apply)

    p_site_users = sub.add_parser(
        "site-users",
        help="пользователи сайта (username/email/ФИО/роль; пароли только сбрасываются, не читаются)",
    )
    site_users_sub = p_site_users.add_subparsers(dest="site_users_command", required=True)

    site_users_sub.add_parser("list", help="список пользователей").set_defaults(func=cmd_site_users_list)

    p_su_add = site_users_sub.add_parser("add", help="добавить пользователя")
    p_su_add.add_argument("username")
    p_su_add.add_argument("email")
    p_su_add.add_argument("--full-name", default="", help="ФИО")
    p_su_add.add_argument("--role", default="viewer", choices=site_users.VALID_ROLES)
    p_su_add.add_argument("--password", default=None, help="если не задан — запросит интерактивно")
    p_su_add.set_defaults(func=cmd_site_users_add)

    p_su_edit = site_users_sub.add_parser("edit", help="изменить email/ФИО/роль пользователя")
    p_su_edit.add_argument("id", type=int)
    p_su_edit.add_argument("--email", default=None)
    p_su_edit.add_argument("--full-name", default=None)
    p_su_edit.add_argument("--role", default=None, choices=site_users.VALID_ROLES)
    p_su_edit.set_defaults(func=cmd_site_users_edit)

    p_su_reset = site_users_sub.add_parser("reset-password", help="сбросить пароль пользователя")
    p_su_reset.add_argument("id", type=int)
    p_su_reset.add_argument("--password", default=None, help="если не задан — запросит интерактивно")
    p_su_reset.set_defaults(func=cmd_site_users_reset_password)

    p_su_delete = site_users_sub.add_parser("delete", help="удалить пользователя")
    p_su_delete.add_argument("id", type=int)
    p_su_delete.set_defaults(func=cmd_site_users_delete)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
