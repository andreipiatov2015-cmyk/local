"""Тест управления пользователями сайта (site_admin/users.py) на временной
SQLite-базе с ТОЧНО такой же схемой, как в www/live-server/server.py —
включая проверку, что сброшенный отсюда пароль пройдёт верификацию по
алгоритму сайта (hashlib.pbkdf2_hmac, 100_000 итераций)."""

from __future__ import annotations

import hashlib
import hmac
import sqlite3
import tempfile
import unittest
from pathlib import Path

from rtmp_server.config import constants as C
from rtmp_server.site_admin import users


def site_verify_password(password: str, salt: str, password_hash: str) -> bool:
    """Копия verify_password()/hash_password() из www/live-server/server.py —
    намеренно НЕ импортируется оттуда (сайт вне зависимостей rtmp-server),
    но алгоритм должен совпадать 1-в-1."""
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000)
    return hmac.compare_digest(dk.hex(), password_hash)


SCHEMA = """
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        password_salt TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'viewer',
        is_verified INTEGER NOT NULL DEFAULT 0,
        verify_token TEXT,
        created_at TEXT,
        updated_at TEXT
    )
"""


class SiteUsersTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "app.db"

        con = sqlite3.connect(str(self.db_path))
        con.execute(SCHEMA)
        con.commit()
        con.close()

        self._orig_live_server_dir = C.LIVE_SERVER_DIR
        self._orig_site_db_file = C.SITE_DB_FILE
        # ни один из "нормальных" кандидатов не должен существовать —
        # подсовываем только наш временный файл через SITE_DB_FILE
        C.LIVE_SERVER_DIR = str(Path(self.tmp.name) / "does-not-exist")
        C.SITE_DB_FILE = str(self.db_path)

    def tearDown(self):
        C.LIVE_SERVER_DIR = self._orig_live_server_dir
        C.SITE_DB_FILE = self._orig_site_db_file
        self.tmp.cleanup()

    def test_resolve_db_path_picks_existing_candidate(self):
        self.assertEqual(users.resolve_db_path(), self.db_path)

    def test_create_adds_full_name_column_and_user(self):
        user_id = users.create_user(
            "ivanov", "ivanov@example.com", "S3cret!", full_name="Иванов Иван Иванович", role="viewer"
        )
        user = users.get_user(user_id)

        self.assertEqual(user.username, "ivanov")
        self.assertEqual(user.full_name, "Иванов Иван Иванович")
        self.assertEqual(user.role, "viewer")
        self.assertTrue(user.is_verified)

    def test_created_password_verifies_with_site_algorithm(self):
        user_id = users.create_user("petrov", "petrov@example.com", "MyPassw0rd", role="admin")

        with sqlite3.connect(str(self.db_path)) as con:
            row = con.execute(
                "SELECT password_hash, password_salt FROM users WHERE id = ?", (user_id,)
            ).fetchone()

        self.assertTrue(site_verify_password("MyPassw0rd", row[1], row[0]))
        self.assertFalse(site_verify_password("wrong-password", row[1], row[0]))

    def test_reset_password_changes_hash_and_still_verifies(self):
        user_id = users.create_user("sidorov", "sidorov@example.com", "OldPass1")
        users.reset_password(user_id, "NewPass2")

        with sqlite3.connect(str(self.db_path)) as con:
            row = con.execute(
                "SELECT password_hash, password_salt FROM users WHERE id = ?", (user_id,)
            ).fetchone()

        self.assertTrue(site_verify_password("NewPass2", row[1], row[0]))
        self.assertFalse(site_verify_password("OldPass1", row[1], row[0]))

    def test_update_user_changes_email_and_role(self):
        user_id = users.create_user("kozlov", "kozlov@example.com", "Pass12345", role="viewer")
        users.update_user(user_id, email="new@example.com", role="admin", full_name="Козлов К.К.")

        user = users.get_user(user_id)
        self.assertEqual(user.email, "new@example.com")
        self.assertEqual(user.role, "admin")
        self.assertEqual(user.full_name, "Козлов К.К.")

    def test_duplicate_username_rejected(self):
        users.create_user("dup", "dup1@example.com", "Pass12345")
        with self.assertRaises(users.SiteUsersError):
            users.create_user("dup", "dup2@example.com", "Pass12345")

    def test_invalid_role_rejected(self):
        with self.assertRaises(users.SiteUsersError):
            users.create_user("badrole", "badrole@example.com", "Pass12345", role="superadmin")

    def test_delete_user(self):
        user_id = users.create_user("todelete", "todelete@example.com", "Pass12345")
        users.delete_user(user_id)
        with self.assertRaises(users.SiteUsersError):
            users.get_user(user_id)

    def test_list_users_returns_all(self):
        users.create_user("a", "a@example.com", "Pass12345")
        users.create_user("b", "b@example.com", "Pass12345")
        result = users.list_users()
        self.assertEqual({u.username for u in result}, {"a", "b"})


if __name__ == "__main__":
    unittest.main()
