"""Подтверждение действия паролем пользователя, который запустил приложение.

RTMP-server сам всегда работает от root (см. debian/local/units и
sudoers-правило для беспарольного запуска ярлыка — `sudo /usr/bin/rtmp-server`,
debian/local/rtmp-server.sudoers) — поэтому подтверждение здесь не про
повышение прав в ОС (их и так достаточно), а про явную проверку "это точно
тот, кто сейчас сидит за этой машиной" перед чувствительными действиями:
просмотром списка пользователей сайта, сбросом пароля, изменением роли и т.п.

Раньше здесь всегда спрашивался пароль root. На практике это оказалось
неудобно: пароль root меняется по отдельной организационной политике
(раз в 3 месяца, без предупреждения — ровно как это и обнаружилось вживую),
и его обладателя — не каждый сотрудник, которому нужно подтверждать такие
действия в программе. Теперь спрашиваем пароль ТОГО пользователя ОС,
который запустил приложение через sudo (sudo сам выставляет переменную
окружения SUDO_USER) — это и есть "я авторизован и у меня есть sudo", а не
"мне сообщили пароль root". Если SUDO_USER не задан (например, автозапуск
через systemd при старте графической сессии, не через sudo-ярлык) —
откатываемся на root: другого кандидата на "кто подтверждает" в этом
случае нет.

Проверяет введённый пароль напрямую по хешу пользователя из /etc/shadow —
без дополнительных зависимостей и без интерактивного su/sudo (это было бы
избыточно, раз процесс и так root и может читать /etc/shadow напрямую).
"""

from __future__ import annotations

import os

try:
    import crypt
except ImportError:  # Python 3.13+ удалил crypt из stdlib
    import legacycrypt as crypt  # type: ignore[no-redef]


class AdminAuthError(Exception):
    pass


# Вынесено в константу модуля ради тестируемости (monkeypatch в тестах),
# не ради реальной настраиваемости — путь не читается из конфига/env.
SHADOW_FILE = "/etc/shadow"


def confirming_username() -> str:
    """Чьим паролем подтверждаются чувствительные действия в этом запуске."""
    return os.environ.get("SUDO_USER") or "root"


def _read_shadow_hash(username: str) -> str:
    try:
        with open(SHADOW_FILE) as fh:
            for line in fh:
                fields = line.split(":")
                if fields and fields[0] == username:
                    return fields[1]
    except PermissionError as exc:
        raise AdminAuthError(
            "Нет доступа к /etc/shadow — RTMP-server должен работать от root."
        ) from exc
    raise AdminAuthError(f"Учётная запись {username} не найдена в /etc/shadow.")


def verify_confirming_password(password: str) -> bool:
    """True, если password совпадает с паролем пользователя из
    confirming_username().

    Явно возвращает False (не бросает) для пустого пароля или
    заблокированной учётной записи (хеш начинается с '!' или '*') —
    это не "неверный пароль", а "пароль не задан/выключен", что тоже
    должно просто не пропускать подтверждение."""
    if not password:
        return False

    shadow_hash = _read_shadow_hash(confirming_username())
    if not shadow_hash or shadow_hash[0] in ("!", "*"):
        return False

    computed = crypt.crypt(password, shadow_hash)
    return computed == shadow_hash
