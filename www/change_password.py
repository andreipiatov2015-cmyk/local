import sqlite3
import hashlib
import secrets
import hmac

DB_FILE = "app.db"
PBKDF2_ITER = 100_000

def make_salt(n=16) -> str:
    return secrets.token_hex(n)

def hash_password(password: str, salt: str) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITER)
    return dk.hex()

def set_password(username_or_email, new_password):
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()

    salt = make_salt()
    pwd_hash = hash_password(new_password, salt)

    cur.execute("UPDATE users SET password_hash=?, password_salt=? WHERE username=? OR email=?",
                (pwd_hash, salt, username_or_email, username_or_email))
    con.commit()
    con.close()
    print(f"Пароль для {username_or_email} успешно изменён!")

if __name__ == "__main__":
    user = input("Введите username или email пользователя: ").strip()
    new_pass = input("Введите новый пароль: ").strip()
    set_password(user, new_pass)

