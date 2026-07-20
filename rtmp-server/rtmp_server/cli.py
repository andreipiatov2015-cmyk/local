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
from rtmp_server.site_admin import stream_info
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
    ok = True
    for svc in targets:
        print(f"{args.action} {svc.name}...")
        try:
            getattr(svc, args.action)()
        except Exception as exc:
            print(f"  ошибка: {exc}")
            ok = False
    return 0 if ok else 1


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


def _resolve_stream_name(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    streams = stream_info.list_live_streams()
    return streams[0] if streams else None


def cmd_stream_status(args: argparse.Namespace) -> int:
    streams = stream_info.list_live_streams()
    if not streams:
        print("Активной трансляции сейчас нет")
        return 0
    for name in streams:
        print(f"поток: {name}")
    return 0


def cmd_stream_probe(args: argparse.Namespace) -> int:
    name = _resolve_stream_name(args.name)
    if not name:
        print("Активной трансляции сейчас нет")
        return 1
    info = stream_info.probe_incoming_stream(name)
    if not info.live:
        print(f"Поток {name}: недоступен ({info.error})")
        return 1
    print(f"Поток:      {info.stream_name}")
    print(f"Разрешение: {info.width}x{info.height}")
    print(f"FPS:        {info.fps}")
    print(f"Видео:      {info.video_codec}")
    print(f"Аудио:      {info.audio_codec} ({info.audio_sample_rate} Гц)")
    return 0


def cmd_stream_bitrate(args: argparse.Namespace) -> int:
    name = _resolve_stream_name(args.name)
    if not name:
        print("Активной трансляции сейчас нет")
        return 1
    sample = stream_info.measure_segment_bitrate(name)
    if not sample.segments_measured:
        print(f"Нет HLS-сегментов для потока {name}")
        return 1
    print(f"Поток {name}: ~{sample.avg_kbps} кбит/с (мин {sample.min_kbps}, макс {sample.max_kbps}, по {sample.segments_measured} сегментам)")
    return 0


def cmd_stream_test_bandwidth(args: argparse.Namespace) -> int:
    result = stream_info.test_server_bandwidth()
    if not result.ok:
        print(f"Не удалось проверить канал сервера: {result.error}")
        return 1
    print(f"Канал сервера наружу: ~{result.mbps} Мбит/с")
    return 0


def cmd_stream_vk_settings_show(args: argparse.Namespace) -> int:
    settings = stream_info.get_vk_settings()
    print(f"enabled:           {settings.enabled}")
    print(f"vk_rtmp_url:       {settings.vk_rtmp_url or '(не задан)'}")
    print(f"target_ids:        {', '.join(settings.target_ids) or '(нет)'}")
    print(f"bitrate_kbps:      {settings.bitrate_kbps if settings.bitrate_kbps is not None else '(без ограничения)'}")
    print(f"resolution_height: {settings.resolution_height if settings.resolution_height is not None else '(как на входе)'}")
    return 0


def cmd_stream_vk_settings_set(args: argparse.Namespace) -> int:
    settings = stream_info.get_vk_settings()
    if args.enable:
        settings.enabled = True
    if args.disable:
        settings.enabled = False
    if args.vk_url is not None:
        settings.vk_rtmp_url = args.vk_url
    if args.bitrate is not None:
        settings.bitrate_kbps = None if args.bitrate == 0 else args.bitrate
    if args.resolution is not None:
        settings.resolution_height = None if args.resolution == 0 else args.resolution
    stream_info.save_vk_settings(settings)
    print("Настройки VK сохранены. Применятся при следующем запуске трансляции.")
    return 0


def cmd_stream_targets_list(args: argparse.Namespace) -> int:
    for target in stream_info.list_stream_targets():
        state = "включена" if target.enabled else "выключена"
        print(f"{target.id:10s} {target.name:25s} {state:10s} {target.url}")
    return 0


def cmd_stream_targets_add(args: argparse.Namespace) -> int:
    import secrets

    targets = stream_info.list_stream_targets()
    target_id = secrets.token_hex(4)
    targets.append(stream_info.VkTarget(id=target_id, name=args.name, url=args.url, enabled=not args.disabled))
    stream_info.save_stream_targets(targets)
    print(f"Добавлена площадка id={target_id}")
    return 0


def cmd_stream_targets_edit(args: argparse.Namespace) -> int:
    targets = stream_info.list_stream_targets()
    for target in targets:
        if target.id == args.id:
            if args.name is not None:
                target.name = args.name
            if args.url is not None:
                target.url = args.url
            if args.enable:
                target.enabled = True
            if args.disable:
                target.enabled = False
            stream_info.save_stream_targets(targets)
            print(f"Площадка id={args.id} обновлена")
            return 0
    print(f"Площадка id={args.id} не найдена")
    return 1


def cmd_stream_targets_delete(args: argparse.Namespace) -> int:
    targets = stream_info.list_stream_targets()
    remaining = [t for t in targets if t.id != args.id]
    if len(remaining) == len(targets):
        print(f"Площадка id={args.id} не найдена")
        return 1
    stream_info.save_stream_targets(remaining)
    print(f"Площадка id={args.id} удалена")
    return 0


def cmd_stream_restart_vk(args: argparse.Namespace) -> int:
    name = _resolve_stream_name(args.name)
    if not name:
        print("Активной трансляции сейчас нет — перезапускать нечего")
        return 1
    stream_info.restart_vk_push(name)
    print(f"Трансляция в VK перезапущена для потока {name}")
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

    p_stream = sub.add_parser("stream", help="трансляция: входящий поток и пуш в VK/OK")
    stream_sub = p_stream.add_subparsers(dest="stream_command", required=True)

    stream_sub.add_parser("status", help="список активных потоков").set_defaults(func=cmd_stream_status)

    p_probe = stream_sub.add_parser("probe", help="параметры входящего потока (разрешение/fps/кодеки)")
    p_probe.add_argument("name", nargs="?", default=None, help="имя потока (по умолчанию — первый активный)")
    p_probe.set_defaults(func=cmd_stream_probe)

    p_bitrate = stream_sub.add_parser("bitrate", help="приближённый битрейт входящего потока по HLS-сегментам")
    p_bitrate.add_argument("name", nargs="?", default=None)
    p_bitrate.set_defaults(func=cmd_stream_bitrate)

    stream_sub.add_parser("test-bandwidth", help="тест исходящего канала сервера").set_defaults(func=cmd_stream_test_bandwidth)

    p_vk_settings = stream_sub.add_parser("vk-settings", help="настройки пуша в VK/OK")
    vk_settings_sub = p_vk_settings.add_subparsers(dest="vk_settings_command", required=True)
    vk_settings_sub.add_parser("show", help="показать текущие настройки").set_defaults(func=cmd_stream_vk_settings_show)
    p_vk_set = vk_settings_sub.add_parser("set", help="изменить настройки")
    p_vk_set.add_argument("--enable", action="store_true", help="включить пуш в VK")
    p_vk_set.add_argument("--disable", action="store_true", help="выключить пуш в VK")
    p_vk_set.add_argument("--vk-url", default=None, help="RTMP URL с ключом трансляции")
    p_vk_set.add_argument("--bitrate", type=int, default=None, help="кбит/с; 0 = без ограничения")
    p_vk_set.add_argument("--resolution", type=int, default=None, help="высота кадра; 0 = как на входе")
    p_vk_set.set_defaults(func=cmd_stream_vk_settings_set)

    p_targets = stream_sub.add_parser("targets", help="площадки вещания VK/OK")
    targets_sub = p_targets.add_subparsers(dest="targets_command", required=True)
    targets_sub.add_parser("list", help="список площадок").set_defaults(func=cmd_stream_targets_list)
    p_target_add = targets_sub.add_parser("add", help="добавить площадку")
    p_target_add.add_argument("name")
    p_target_add.add_argument("url")
    p_target_add.add_argument("--disabled", action="store_true", help="создать выключенной")
    p_target_add.set_defaults(func=cmd_stream_targets_add)
    p_target_edit = targets_sub.add_parser("edit", help="изменить площадку")
    p_target_edit.add_argument("id")
    p_target_edit.add_argument("--name", default=None)
    p_target_edit.add_argument("--url", default=None)
    p_target_edit.add_argument("--enable", action="store_true", help="включить площадку")
    p_target_edit.add_argument("--disable", action="store_true", help="выключить площадку")
    p_target_edit.set_defaults(func=cmd_stream_targets_edit)

    p_target_delete = targets_sub.add_parser("delete", help="удалить площадку")
    p_target_delete.add_argument("id")
    p_target_delete.set_defaults(func=cmd_stream_targets_delete)

    p_restart_vk = stream_sub.add_parser("restart-vk", help="перезапустить трансляцию в VK/OK")
    p_restart_vk.add_argument("name", nargs="?", default=None)
    p_restart_vk.set_defaults(func=cmd_stream_restart_vk)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
