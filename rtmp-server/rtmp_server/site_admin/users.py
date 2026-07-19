"""Управление пользователями сайта напрямую через SQLite (/var/www/app.db).

Совместимо с реальной схемой из www/live-server/server.py: пароли —
PBKDF2-HMAC-SHA256, 100_000 итераций, соль 16 байт hex (та же схема,
что hash_password()/verify_password() в server.py) — сброшенный отсюда
пароль будет приниматься сайтом при логине без всяких изменений в server.py.

Пароли НЕ хранятся и не читаются в обратимом виде — только сброс на новый.
См. обсуждение с владельцем: "посмотреть пароль" заменено на "сбросить
пароль", потому что хранить пароли реверсивно небезопасно независимо от
того, что сеть локальная (особенно с учётом того, что этот же app.db уже
однажды попадал в публичный git).

Путь к БД: в коде сайта DB_FILE = <BASE_DIR>/app.db, т.е.
/var/www/live-server/app.db, но со слов владельца реальный путь —
/var/www/app.db. Чтобы не гадать и не писать не в ту базу, модуль сам
проверяет оба кандидата и использует тот, где реально есть непустая
таблица users.
"""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from rtmp_server.config import constants as C

PBKDF2_ITER = 100_000  # должно совпадать с server.py — не менять по отдельности

VALID_ROLES = ("admin", "viewer")


class SiteUsersError(Exception):
    pass


def _candidate_db_paths() -> list[Path]:
    return [
        Path(f"{C.LIVE_SERVER_DIR}/app.db"),  # то, что реально читает server.py (DB_FILE)
        Path(C.SITE_DB_FILE),  # то, что назвал владелец (/var/www/app.db)
    ]


def resolve_db_path() -> Path:
    existing = [p for p in _candidate_db_paths() if p.exists()]
    if not existing:
        checked = ", ".join(str(p) for p in _candidate_db_paths())
        raise SiteUsersError(f"Не найдена база сайта. Проверены пути: {checked}")

    with_users = []
    for path in existing:
        try:
            with closing(sqlite3.connect(str(path))) as con:
                count = con.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='users'"
                ).fetchone()[0]
                if count:
                    with_users.append(path)
        except sqlite3.Error:
            continue

    if with_users:
        return with_users[0]
    if len(existing) == 1:
        return existing[0]
    raise SiteUsersError(
        f"Найдено несколько файлов БД, но ни в одном нет таблицы users: "
        f"{', '.join(str(p) for p in existing)}"
    )


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(str(resolve_db_path()))
    con.row_factory = sqlite3.Row
    return con


def ensure_full_name_column() -> bool:
    """Добавляет колонку full_name (ФИО), если её ещё нет. Идемпотентно.
    Возвращает True, если колонку пришлось добавить."""
    with closing(_connect()) as con:
        columns = {row["name"] for row in con.execute("PRAGMA table_info(users)")}
        if "full_name" in columns:
            return False
        con.execute("ALTER TABLE users ADD COLUMN full_name TEXT")
        con.commit()
        return True


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITER).hex()


def make_salt() -> str:
    return secrets.token_hex(16)


@dataclass
class SiteUser:
    id: int
    username: str
    email: str
    full_name: str | None
    role: str
    is_verified: bool
    created_at: str | None
    updated_at: str | None


def _row_to_user(row: sqlite3.Row) -> SiteUser:
    keys = row.keys()
    return SiteUser(
        id=row["id"],
        username=row["username"],
        email=row["email"],
        full_name=row["full_name"] if "full_name" in keys else None,
        role=row["role"],
        is_verified=bool(row["is_verified"]),
        created_at=row["created_at"] if "created_at" in keys else None,
        updated_at=row["updated_at"] if "updated_at" in keys else None,
    )


def list_users() -> list[SiteUser]:
    ensure_full_name_column()
    with closing(_connect()) as con:
        rows = con.execute(
            "SELECT id, username, email, full_name, role, is_verified, created_at, updated_at "
            "FROM users ORDER BY id"
        ).fetchall()
        return [_row_to_user(r) for r in rows]


def get_user(user_id: int) -> SiteUser:
    ensure_full_name_column()
    with closing(_connect()) as con:
        row = con.execute(
            "SELECT id, username, email, full_name, role, is_verified, created_at, updated_at "
            "FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            raise SiteUsersError(f"Пользователь id={user_id} не найден")
        return _row_to_user(row)


def _now() -> str:
    import datetime

    return datetime.datetime.utcnow().isoformat()


def create_user(username: str, email: str, password: str, full_name: str = "", role: str = "viewer") -> int:
    if role not in VALID_ROLES:
        raise SiteUsersError(f"Недопустимая роль: {role!r}. Допустимо: {VALID_ROLES}")
    if not password:
        raise SiteUsersError("Пароль обязателен при создании пользователя")

    ensure_full_name_column()
    salt = make_salt()
    pwd_hash = hash_password(password, salt)
    now = _now()

    with closing(_connect()) as con:
        try:
            cur = con.execute(
                "INSERT INTO users (username, email, password_hash, password_salt, role, "
                "is_verified, full_name, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)",
                (username, email, pwd_hash, salt, role, full_name, now, now),
            )
            con.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError as exc:
            raise SiteUsersError(f"Пользователь с таким username/email уже существует: {exc}") from None


def update_user(user_id: int, *, email: str | None = None, full_name: str | None = None, role: str | None = None) -> None:
    if role is not None and role not in VALID_ROLES:
        raise SiteUsersError(f"Недопустимая роль: {role!r}. Допустимо: {VALID_ROLES}")

    ensure_full_name_column()
    fields, values = [], []
    if email is not None:
        fields.append("email = ?")
        values.append(email)
    if full_name is not None:
        fields.append("full_name = ?")
        values.append(full_name)
    if role is not None:
        fields.append("role = ?")
        values.append(role)
    if not fields:
        return

    fields.append("updated_at = ?")
    values.append(_now())
    values.append(user_id)

    with closing(_connect()) as con:
        cur = con.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", values)
        con.commit()
        if cur.rowcount == 0:
            raise SiteUsersError(f"Пользователь id={user_id} не найден")


def reset_password(user_id: int, new_password: str) -> None:
    """Сбрасывает пароль пользователя. Сам новый пароль нигде не сохраняется —
    только его PBKDF2-хеш, как это делает server.py при обычной смене пароля."""
    if not new_password:
        raise SiteUsersError("Новый пароль не может быть пустым")

    salt = make_salt()
    pwd_hash = hash_password(new_password, salt)

    with closing(_connect()) as con:
        cur = con.execute(
            "UPDATE users SET password_hash = ?, password_salt = ?, updated_at = ? WHERE id = ?",
            (pwd_hash, salt, _now(), user_id),
        )
        con.commit()
        if cur.rowcount == 0:
            raise SiteUsersError(f"Пользователь id={user_id} не найден")


def delete_user(user_id: int) -> None:
    with closing(_connect()) as con:
        cur = con.execute("DELETE FROM users WHERE id = ?", (user_id,))
        con.commit()
        if cur.rowcount == 0:
            raise SiteUsersError(f"Пользователь id={user_id} не найден")
