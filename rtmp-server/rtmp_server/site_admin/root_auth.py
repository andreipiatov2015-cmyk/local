"""Подтверждение действия паролем root.

RTMP-server сам уже всегда работает от root (см. debian/local/units и
sudoers-правило для беспарольного запуска ярлыка) — поэтому "подтверждение
паролем root" здесь не про повышение прав в ОС (их и так достаточно), а про
явную проверку "это точно администратор" перед чувствительными действиями:
просмотром списка пользователей сайта, сбросом пароля, изменением роли и т.п.

Проверяет введённый пароль напрямую по хешу root из /etc/shadow — без
дополнительных зависимостей и без интерактивного su/sudo (это было бы
избыточно, раз процесс и так root и может читать /etc/shadow напрямую).
"""

from __future__ import annotations

try:
    import crypt
except ImportError:  # Python 3.13+ удалил crypt из stdlib
    import legacycrypt as crypt  # type: ignore[no-redef]


class RootAuthError(Exception):
    pass


def _read_root_shadow_hash() -> str:
    try:
        with open("/etc/shadow") as fh:
            for line in fh:
                fields = line.split(":")
                if fields and fields[0] == "root":
                    return fields[1]
    except PermissionError as exc:
        raise RootAuthError(
            "Нет доступа к /etc/shadow — RTMP-server должен работать от root."
        ) from exc
    raise RootAuthError("Учётная запись root не найдена в /etc/shadow.")


def verify_root_password(password: str) -> bool:
    """True, если password совпадает с паролем root в системе.

    Явно возвращает False (не бросает) для пустого пароля или
    заблокированной учётной записи (хеш начинается с '!' или '*') —
    это не "неверный пароль", а "пароль root не задан/выключен",
    что тоже должно просто не пропускать подтверждение."""
    if not password:
        return False

    shadow_hash = _read_root_shadow_hash()
    if not shadow_hash or shadow_hash[0] in ("!", "*"):
        return False

    computed = crypt.crypt(password, shadow_hash)
    return computed == shadow_hash
