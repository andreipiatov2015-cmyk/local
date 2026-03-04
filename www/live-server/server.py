from flask import Flask, render_template, request, jsonify, redirect, url_for, session, g, make_response, send_file
import json
import os
import smtplib
from email.mime.text import MIMEText
import sqlite3
import hashlib
import hmac
import secrets
import datetime
import subprocess
import signal
import time
import threading
import shutil
import re
import uuid
from functools import wraps
from pathlib import Path

import requests


try:
    import openpyxl
except Exception:
    openpyxl = None

# Папка, где лежит server.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ------------ Загрузка .env ------------
def load_env(path=".env"):
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    os.environ[key] = value

# если у тебя .env лежит в /var/www/.env — оставляем
load_env("/var/www/.env")

# ------------ Flask ------------
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change_this_secret_key_please")

# ------------ Константы (абсолютные пути) ------------
DB_FILE = os.path.join(BASE_DIR, "app.db")
ENTRIES_FILE = os.path.join(BASE_DIR, "entries.json")
PRESETS_FILE = os.path.join(BASE_DIR, "presets.json")
VK_SETTINGS_FILE = os.path.join(BASE_DIR, "vk_settings.json")
STREAM_TARGETS_FILE = os.path.join(BASE_DIR, "stream_targets.json")
HLS_STREAM_URL = (os.environ.get("HLS_STREAM_URL") or "").strip()

STORAGE_ROOT = os.environ.get("STORAGE_ROOT", "/var/mount_point/nfv/contest_storage")
APP_DATA_ROOT = Path(os.environ.get("APP_DATA_ROOT", os.path.join(BASE_DIR, "app_data")))
RETENTION_DAYS = 60
MAX_TABLES_PER_USER = 10
DOWNLOAD_RETRIES = 3
MAX_FILENAME_LEN = 150
EXCEL_PREVIEW_LIMIT = 200
YANDEX_VNC_URL = os.environ.get("YANDEX_VNC_URL", "/tables/yandex/vnc/vnc.html?autoconnect=1&resize=scale&show_dot=0")
YANDEX_PROFILE_DIR = os.environ.get("YANDEX_PROFILE_DIR", "/var/mount_point/nfv/contest_storage/yandex_profile")
YANDEX_FORMS_TEST_URL = (os.environ.get("YANDEX_FORMS_TEST_URL") or "").strip()

MAPPING_FIELDS = {
    "municipality": "Муниципалитет",
    "institution_full_name": "Полное название учреждения",
    "head_fio": "ФИО руководителя",
    "teacher_fio": "ФИО педагога",
    "contacts": "Контактные данные",
    "email": "Email",
    "nomination": "Номинация",
    "age_category": "Возрастная категория",
    "studio_name": "Название студии",
    "participants_count": "Количество участников",
    "participant_fio": "ФИО участника(ов)",
    "number_title": "Название номера",
    "audio_url": "Фонограмма (скачивание)",
    "equipment": "Необходимое оборудование",
    "receipt_url": "Квитанция об оплате (скачивание)",
    "receipt_payer": "За кого оплата (для имени квитанции)",
    "presentation_url": "Презентация (скачивание)",
}
FILE_MAPPING_FIELDS = {"audio_url", "receipt_url", "presentation_url"}

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "noreply@example.com")

# ------------ Работа с JSON ------------
def load_entries():
    if os.path.exists(ENTRIES_FILE):
        try:
            with open(ENTRIES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_entries(entries):
    os.makedirs(os.path.dirname(ENTRIES_FILE), exist_ok=True)
    with open(ENTRIES_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=4)

def clear_entries():
    entries.clear()
    save_entries(entries)

def load_presets():
    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_presets(presets):
    os.makedirs(os.path.dirname(PRESETS_FILE), exist_ok=True)
    with open(PRESETS_FILE, "w", encoding="utf-8") as f:
        json.dump(presets, f, ensure_ascii=False, indent=4)

entries = load_entries()
presets = load_presets()

# ------------ Работа с БД ------------
def query_db(query, args=(), one=False):
    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row
    cur = con.execute(query, args)
    rv = cur.fetchall()
    con.commit()
    con.close()
    return (rv[0] if rv else None) if one else rv

def init_db():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()

    # Таблица пользователей
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
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
    """)

    # Таблица мероприятий
    cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            address TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS email_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            code TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS table_workspaces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'new',
            total_count INTEGER NOT NULL DEFAULT 0,
            processed_count INTEGER NOT NULL DEFAULT 0,
            progress INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            yandex_session_json TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS table_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id INTEGER NOT NULL,
            number_title TEXT,
            fio TEXT,
            team TEXT,
            unique_key TEXT,
            audio_url TEXT,
            receipt_url TEXT,
            consent_url TEXT,
            presentation_url TEXT,
            audio_local TEXT,
            receipt_local TEXT,
            consent_local TEXT,
            presentation_local TEXT,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS yandex_connect_sessions (
            connect_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            table_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'waiting',
            error_message TEXT,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    for stmt in [
        "ALTER TABLE table_workspaces ADD COLUMN excel_headers_json TEXT",
        "ALTER TABLE table_workspaces ADD COLUMN excel_preview_rows_json TEXT",
        "ALTER TABLE table_workspaces ADD COLUMN excel_total_rows INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE table_workspaces ADD COLUMN excel_sheet_name TEXT",
        "ALTER TABLE table_workspaces ADD COLUMN mapping_json TEXT",
        "ALTER TABLE table_workspaces ADD COLUMN total_count INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE table_workspaces ADD COLUMN processed_count INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE table_workspaces ADD COLUMN last_error TEXT",
        "ALTER TABLE table_entries ADD COLUMN row_id INTEGER",
        "ALTER TABLE table_entries ADD COLUMN row_data_json TEXT",
    ]:
        try:
            cur.execute(stmt)
        except sqlite3.OperationalError:
            pass

    con.commit()
    con.close()

# ------------ Пароли и токены ------------
PBKDF2_ITER = 100_000

def make_salt(n=16): return secrets.token_hex(n)

def hash_password(password, salt):
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITER)
    return dk.hex()

def verify_password(password, salt, password_hash):
    return hmac.compare_digest(hash_password(password, salt), password_hash)

def generate_token(n_bytes=24): return secrets.token_urlsafe(n_bytes)

# ------------ Email ------------
def send_email(to_email, subject, body):
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASSWORD:
        print("\n--- EMAIL DEBUG ---")
        print("TO:", to_email)
        print("SUBJECT:", subject)
        print(body)
        print("--- END EMAIL ---\n")
        return

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print("Ошибка отправки письма:", e)

# ------------ Авторизация ------------
def get_current_user():
    if "user_id" in session:
        row = query_db("SELECT id, username, email, role, is_verified FROM users WHERE id=?", (session["user_id"],), one=True)
        return dict(row) if row else None
    return None

def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.path))
        return f(*a, **kw)
    return wrapper

def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*a, **kw):
            user = get_current_user()
            if not user or user["role"] not in roles:
                return "Доступ запрещён", 403
            return f(*a, **kw)
        return wrapper
    return decorator

# ------------ Создание админа по умолчанию ------------
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_EMAIL = "admin@local"
DEFAULT_ADMIN_PASSWORD = "Gfnhbjnjd9"

def ensure_admin_exists():
    query_db("DELETE FROM users")
    salt = make_salt()
    pwd_hash = hash_password(DEFAULT_ADMIN_PASSWORD, salt)
    now = datetime.datetime.utcnow().isoformat()
    query_db(
        "INSERT INTO users (username, email, password_hash, password_salt, role, is_verified, created_at, updated_at) VALUES (?, ?, ?, ?, 'admin', 1, ?, ?)",
        (DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_EMAIL, pwd_hash, salt, now, now)
    )
    print(f"Создан администратор: {DEFAULT_ADMIN_USERNAME} / {DEFAULT_ADMIN_PASSWORD}")


def resolve_stream_url():
    if HLS_STREAM_URL:
        return HLS_STREAM_URL
    scheme = request.headers.get("X-Forwarded-Proto", request.scheme) or "http"
    host = request.host or "127.0.0.1"
    return f"{scheme}://{host}/hls/stream.m3u8"

# ------------ Маршруты ------------
@app.route("/")
def index():
    return redirect("/login")

@app.route("/admin")
@login_required
def admin():
    return render_template("admin.html", user=get_current_user(), stream_url=resolve_stream_url())

@app.route("/staff")
@roles_required("admin")
def staff():
    users = query_db("SELECT id, username, email, role, is_verified FROM users ORDER BY id")
    return render_template("staff.html", users=users, stream_url=resolve_stream_url())

@app.route("/broadcast")
def broadcast():
    return render_template("broadcast.html", stream_url=resolve_stream_url())

@app.route("/competition")
def competition():
    return render_template("competition.html", stream_url=resolve_stream_url())

# --- Мероприятия ---
@app.route("/editor")
@login_required
def editor_list():
    return render_template("editor.html", stream_url=resolve_stream_url())

@app.route("/events")
def get_events():
    rows = query_db("SELECT * FROM events ORDER BY id DESC")
    return jsonify([dict(r) for r in rows])

@app.route("/create_event", methods=["POST"])
@login_required
def create_event():
    data = request.json
    query_db(
        "INSERT INTO events (title, address, start_date, end_date) VALUES (?, ?, ?, ?)",
        (data["title"], data["address"], data["start_date"], data["end_date"])
    )
    return jsonify({"status": "ok"})

@app.route("/editor/<int:event_id>")
@login_required
def editor_event(event_id):
    return render_template("admin.html", event_id=event_id, stream_url=resolve_stream_url())

# --- Участники / пресеты ---
@app.route("/entries")
def get_entries():
    return jsonify(entries)

@app.route("/entries/clear", methods=["POST"])
def clear_entries_route():
    clear_entries()
    return jsonify({"status": "ok", "count": 0})

@app.route("/add_entry", methods=["POST"])
def add_entry():
    data = request.json or {}
    new_id = max([entry.get("id", 0) for entry in entries], default=0) + 1
    data["id"] = new_id
    entries.append(data)
    save_entries(entries)
    return jsonify({"message": "Запись добавлена"}), 200

@app.route("/update_entry/<int:id>", methods=["PUT"])
def update_entry(id):
    data = request.json or {}
    for entry in entries:
        if entry.get("id") == id:
            entry.update(data)
            save_entries(entries)
            return jsonify({"message": "Запись обновлена"}), 200
    return jsonify({"error": "Запись не найдена"}), 404

@app.route("/delete_entry/<int:id>", methods=["DELETE"])
def delete_entry(id):
    global entries
    entries = [entry for entry in entries if entry.get("id") != id]
    save_entries(entries)
    return jsonify({"message": "Запись удалена"}), 200

@app.route("/save_all_entries", methods=["POST"])
def save_all_entries():
    data = request.json or []
    entries.clear()
    entries.extend(data)
    save_entries(entries)
    return jsonify({"message": "Все записи сохранены"}), 200

@app.route("/reorder_entries", methods=["POST"])
def reorder_entries():
    data = request.json or []
    entries.clear()
    entries.extend(data)
    save_entries(entries)
    return jsonify({"message": "Порядок обновлён"}), 200

@app.route("/presets")
def get_presets():
    return jsonify(presets)

@app.route("/save_preset", methods=["POST"])
def save_preset():
    data = request.json or {}
    presets.append(data)
    save_presets(presets)
    return jsonify({"message": "Пресет сохранён"}), 200

# --- Управление пользователями ---
@app.route("/staff/change_role/<int:user_id>", methods=["POST"])
@roles_required("admin")
def staff_change_role(user_id):
    new_role = request.form.get("role")
    if new_role not in ["admin", "editor", "viewer"]:
        return "Недопустимая роль", 400
    query_db("UPDATE users SET role=?, updated_at=? WHERE id=?", (new_role, datetime.datetime.utcnow().isoformat(), user_id))
    return redirect(url_for("staff"))

@app.route("/staff/change_password/<int:user_id>", methods=["POST"])
@roles_required("admin")
def staff_change_password(user_id):
    new_password = request.form.get("new_password")
    if not new_password:
        return "Пароль не может быть пустым", 400
    salt = make_salt()
    pwd_hash = hash_password(new_password, salt)
    query_db("UPDATE users SET password_hash=?, password_salt=?, updated_at=? WHERE id=?", (pwd_hash, salt, datetime.datetime.utcnow().isoformat(), user_id))
    return redirect(url_for("staff"))

# --- Логин / Регистрация ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username_or_email = request.form.get("username", "")
        password = request.form.get("password", "")
        row = query_db("SELECT * FROM users WHERE username=? OR email=?", (username_or_email, username_or_email), one=True)
        if not row or not verify_password(password, row["password_salt"], row["password_hash"]):
            return "Неверный логин или пароль", 401
        if row["is_verified"] != 1:
            return "Подтвердите e-mail.", 403
        session["user_id"] = row["id"]
        return redirect(url_for("admin"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "")
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if not username or not email or not password or password != confirm:
            return "Ошибка регистрации", 400
        if query_db("SELECT 1 FROM users WHERE username=? OR email=?", (username, email), one=True):
            return "Такой пользователь уже есть", 409
        salt = make_salt()
        pwd_hash = hash_password(password, salt)
        token = generate_token()
        now = datetime.datetime.utcnow().isoformat()
        query_db("INSERT INTO users (username, email, password_hash, password_salt, role, is_verified, verify_token, created_at, updated_at) VALUES (?, ?, ?, ?, 'viewer', 0, ?, ?, ?)",
                 (username, email, pwd_hash, salt, token, now, now))
        verify_link = f"{request.host_url.rstrip('/')}{url_for('verify')}?token={token}"
        send_email(email, "Подтверждение регистрации", f"Подтвердите ваш e-mail: {verify_link}")
        return "Регистрация успешна, проверьте почту", 200
    return render_template("register.html")

@app.route("/verify")
def verify():
    token = request.args.get("token", "")
    row = query_db("SELECT id FROM users WHERE verify_token=?", (token,), one=True)
    if not row:
        return "Неверный токен", 400
    query_db("UPDATE users SET is_verified=1, verify_token=NULL, updated_at=? WHERE id=?", (datetime.datetime.utcnow().isoformat(), row["id"]))
    return "E-mail подтверждён!"


def now_iso():
    return datetime.datetime.utcnow().isoformat()


def sanitize_name(name):
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", (name or "")).strip()
    if not cleaned:
        return ""
    return cleaned[:MAX_FILENAME_LEN]


def table_user_from_request():
    user_id = request.cookies.get("tables_user_id") or session.get("user_id")
    if not user_id:
        return None
    user = query_db("SELECT id, email FROM users WHERE id=?", (user_id,), one=True)
    if not user:
        return None
    session["user_id"] = user["id"]
    return user


def storage_for_table(user_id, table_id):
    return os.path.join(STORAGE_ROOT, "users", str(user_id), "tables", str(table_id))


def get_cell(row, idx):
    if idx is None or idx >= len(row):
        return ""
    v = row[idx]
    return "" if v is None else str(v).strip()


def parse_excel_preview(xlsx_path, preview_limit=EXCEL_PREVIEW_LIMIT):
    if openpyxl is None:
        raise RuntimeError("openpyxl недоступен")

    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.worksheets[0] if wb.worksheets else None
    if ws is None:
        raise RuntimeError("В Excel не найдено ни одного листа")

    rows_iter = ws.iter_rows(values_only=True)
    header_row = next(rows_iter, None)
    if header_row is None:
        return [], [], 0, ws.title

    headers = ["" if x is None else str(x).strip() for x in header_row]
    preview_rows = []
    total_rows = 0

    for row in rows_iter:
        total_rows += 1
        values = ["" if x is None else str(x).strip() for x in row]
        if len(values) < len(headers):
            values.extend([""] * (len(headers) - len(values)))
        preview_rows.append(values)
        if len(preview_rows) >= preview_limit:
            break

    for _ in rows_iter:
        total_rows += 1

    return headers, preview_rows, total_rows, ws.title


def normalize_mapping(mapping):
    if not isinstance(mapping, dict):
        return {}
    normalized = {}
    used_cols = set()
    for field in MAPPING_FIELDS.keys():
        val = mapping.get(field)
        if isinstance(val, int) and val >= 0 and val not in used_cols:
            normalized[field] = val
            used_cols.add(val)
    return normalized


def table_required_mapping_status(mapping):
    assigned_files = [f for f in FILE_MAPPING_FIELDS if f in mapping]
    if not assigned_files:
        return False, "Нужно назначить хотя бы один файловый столбец: фонограмма/квитанция/презентация"

    needs = []
    if "audio_url" in mapping or "presentation_url" in mapping:
        if "number_title" not in mapping:
            needs.append("Название номера")
        if "participant_fio" not in mapping:
            needs.append("ФИО участника(ов)")
    if "receipt_url" in mapping and "receipt_payer" not in mapping:
        needs.append("За кого оплата")

    if needs:
        return False, "Не назначены обязательные колонки: " + ", ".join(needs)
    return True, "ok"


def make_safe_basename(*parts, fallback="row"):
    raw = " - ".join([str(x).strip() for x in parts if str(x).strip()])
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", raw).strip(" .")
    if not cleaned:
        cleaned = fallback
    return cleaned[:MAX_FILENAME_LEN]


def add_row_suffix_if_needed(base_name, row_id, used_names):
    candidate = base_name
    if candidate.lower() in used_names:
        candidate = f"{base_name}-{row_id}"[:MAX_FILENAME_LEN]
    used_names.add(candidate.lower())
    return candidate


class YandexAuthRequiredError(RuntimeError):
    pass


def extension_from_url(url, fallback="bin"):
    name = url.split("?")[0].rstrip("/").split("/")[-1]
    if "." in name:
        ext = name.rsplit(".", 1)[-1].lower()
        return ext[:10]
    return fallback


def download_with_retries(req_session, url, out_path):
    last_error = None
    for _ in range(DOWNLOAD_RETRIES):
        try:
            r = req_session.get(url, timeout=30, allow_redirects=True)
            final_url = (r.url or "").lower()
            if r.status_code in (401, 403) or "passport.yandex" in final_url:
                raise YandexAuthRequiredError("Нужен вход администратора в Яндекс")
            r.raise_for_status()
            with open(out_path, "wb") as f:
                f.write(r.content)
            return
        except YandexAuthRequiredError:
            raise
        except Exception as e:
            last_error = str(e)
            time.sleep(1)
    raise RuntimeError(last_error or "download failed")


def short_error_message(exc, fallback="Ошибка обработки"):
    msg = str(exc or "").strip() or fallback
    return msg[:300]


def process_table_download(table_id, user_id):
    t = query_db("SELECT * FROM table_workspaces WHERE id=? AND user_id=?", (table_id, user_id), one=True)
    if not t:
        return

    try:
        mapping = normalize_mapping(json.loads(t["mapping_json"] or "{}"))
        ok_to_run, reason = table_required_mapping_status(mapping)
        if not ok_to_run:
            query_db(
                "UPDATE table_workspaces SET status='error', total_count=0, processed_count=0, progress=0, last_error=?, updated_at=? WHERE id=?",
                (reason, now_iso(), table_id),
            )
            return

        base = storage_for_table(user_id, table_id)
        excel_path = os.path.join(base, "meta", "original.xlsx")
        if not os.path.exists(excel_path):
            excel_path = os.path.join(base, "meta", "excel_original.xlsx")
        if not os.path.exists(excel_path) or openpyxl is None:
            query_db(
                "UPDATE table_workspaces SET status='error', total_count=0, processed_count=0, progress=0, last_error=?, updated_at=? WHERE id=?",
                ("Excel файл не найден или openpyxl недоступен", now_iso(), table_id),
            )
            return

        wb = openpyxl.load_workbook(excel_path)
        ws = wb.active
        rows = list(ws.values)
        if not rows:
            query_db(
                "UPDATE table_workspaces SET status='done', total_count=0, processed_count=0, progress=100, last_error=NULL, updated_at=? WHERE id=?",
                (now_iso(), table_id),
            )
            return

        data_rows = rows[1:]
        total = len(data_rows)
        query_db(
            "UPDATE table_workspaces SET status='running', total_count=?, processed_count=0, progress=0, last_error=NULL, updated_at=? WHERE id=?",
            (total, now_iso(), table_id),
        )

        try:
            cookies = read_yandex_cookies_from_chromium_profile()
        except Exception:
            query_db(
                "UPDATE table_workspaces SET status='error', last_error=?, updated_at=? WHERE id=?",
                ("Нужен вход администратора в Яндекс.", now_iso(), table_id),
            )
            return

        access_ok, _ = check_yandex_auth(cookies)
        if not access_ok:
            query_db(
                "UPDATE table_workspaces SET status='error', last_error=?, updated_at=? WHERE id=?",
                ("Нужен вход администратора в Яндекс.", now_iso(), table_id),
            )
            return

        req_session = requests.Session()
        apply_cookies_to_requests_session(req_session, cookies)

        for folder in ["phonograms", "receipts", "presentations", "meta"]:
            os.makedirs(os.path.join(base, folder), exist_ok=True)

        query_db("DELETE FROM table_entries WHERE table_id=?", (table_id,))

        used_names = {"phonograms": set(), "receipts": set(), "presentations": set()}
        processed_count = 0
        for i, row in enumerate(data_rows, start=1):
            row_id = i + 1
            row_values = ["" if x is None else str(x).strip() for x in row]
            row_data = {str(idx): val for idx, val in enumerate(row_values)}

            number_title = get_cell(row_values, mapping.get("number_title"))
            fio = get_cell(row_values, mapping.get("participant_fio"))
            team = get_cell(row_values, mapping.get("studio_name"))
            unique_key = f"{row_id}|{number_title}|{fio}"

            try:
                query_db(
                    """
                    INSERT INTO table_entries (table_id, row_id, number_title, fio, team, unique_key, audio_url, receipt_url, consent_url, presentation_url, audio_local, receipt_local, consent_local, presentation_local, row_data_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        table_id,
                        row_id,
                        number_title,
                        fio,
                        team,
                        unique_key,
                        get_cell(row_values, mapping.get("audio_url")),
                        get_cell(row_values, mapping.get("receipt_url")),
                        "",
                        get_cell(row_values, mapping.get("presentation_url")),
                        "",
                        "",
                        "",
                        "",
                        json.dumps(row_data, ensure_ascii=False),
                        now_iso(),
                    ),
                )
            except Exception:
                app.logger.exception("[tables_download] table_id=%s row_id=%s insert_failed", table_id, row_id)
                raise
            entry_id = query_db("SELECT last_insert_rowid() AS id", one=True)["id"]

            audio_local = ""
            receipt_local = ""
            presentation_local = ""

            audio_url = get_cell(row_values, mapping.get("audio_url"))
            if "audio_url" in mapping:
                phonogram_base = add_row_suffix_if_needed(
                    make_safe_basename(number_title, fio, fallback=f"phonogram-{row_id}"),
                    row_id,
                    used_names["phonograms"],
                )
                if audio_url:
                    ext = extension_from_url(audio_url, "mp3")
                    audio_name = f"{phonogram_base}.{ext}"
                    audio_path = os.path.join(base, "phonograms", audio_name)
                    try:
                        download_with_retries(req_session, audio_url, audio_path)
                        audio_local = os.path.join("phonograms", audio_name)
                    except YandexAuthRequiredError:
                        query_db(
                            "UPDATE table_workspaces SET status='error', last_error=?, updated_at=? WHERE id=?",
                            ("Нужен вход администратора в Яндекс.", now_iso(), table_id),
                        )
                        return
                    except Exception:
                        placeholder_name = f"{phonogram_base}.txt"
                        miss_path = os.path.join(base, "phonograms", placeholder_name)
                        with open(miss_path, "w", encoding="utf-8") as f:
                            f.write("Не удалось скачать фонограмму")
                        audio_local = os.path.join("phonograms", placeholder_name)
                else:
                    placeholder_name = f"{phonogram_base}.txt"
                    miss_path = os.path.join(base, "phonograms", placeholder_name)
                    with open(miss_path, "w", encoding="utf-8") as f:
                        f.write("Фонограмма не предоставлена")
                    audio_local = os.path.join("phonograms", placeholder_name)

            receipt_url = get_cell(row_values, mapping.get("receipt_url"))
            if receipt_url:
                payer = get_cell(row_values, mapping.get("receipt_payer"))
                receipt_base = add_row_suffix_if_needed(
                    make_safe_basename(payer, fallback=f"receipt-{row_id}"),
                    row_id,
                    used_names["receipts"],
                )
                ext = extension_from_url(receipt_url, "pdf")
                receipt_name = f"{receipt_base}.{ext}"
                receipt_path = os.path.join(base, "receipts", receipt_name)
                try:
                    download_with_retries(req_session, receipt_url, receipt_path)
                    receipt_local = os.path.join("receipts", receipt_name)
                except YandexAuthRequiredError:
                    query_db(
                        "UPDATE table_workspaces SET status='error', last_error=?, updated_at=? WHERE id=?",
                        ("Нужен вход администратора в Яндекс.", now_iso(), table_id),
                    )
                    return
                except Exception:
                    pass

            presentation_url = get_cell(row_values, mapping.get("presentation_url"))
            if presentation_url:
                presentation_base = add_row_suffix_if_needed(
                    make_safe_basename(number_title, fio, fallback=f"presentation-{row_id}"),
                    row_id,
                    used_names["presentations"],
                )
                ext = extension_from_url(presentation_url, "bin")
                presentation_name = f"{presentation_base}.{ext}"
                presentation_path = os.path.join(base, "presentations", presentation_name)
                try:
                    download_with_retries(req_session, presentation_url, presentation_path)
                    presentation_local = os.path.join("presentations", presentation_name)
                except YandexAuthRequiredError:
                    query_db(
                        "UPDATE table_workspaces SET status='error', last_error=?, updated_at=? WHERE id=?",
                        ("Нужен вход администратора в Яндекс.", now_iso(), table_id),
                    )
                    return
                except Exception:
                    pass

            query_db(
                "UPDATE table_entries SET audio_local=?, receipt_local=?, presentation_local=? WHERE id=?",
                (audio_local, receipt_local, presentation_local, entry_id),
            )

            processed_count += 1
            progress = 100 if total == 0 else int((processed_count / total) * 100)
            query_db(
                "UPDATE table_workspaces SET processed_count=?, progress=?, updated_at=? WHERE id=?",
                (processed_count, progress, now_iso(), table_id),
            )

        query_db(
            "UPDATE table_workspaces SET status='done', processed_count=?, progress=100, last_error=NULL, updated_at=? WHERE id=?",
            (processed_count, now_iso(), table_id),
        )
    except Exception as exc:
        app.logger.exception("[tables_download] table_id=%s failed", table_id)
        query_db(
            "UPDATE table_workspaces SET status='error', last_error=?, updated_at=? WHERE id=?",
            (short_error_message(exc), now_iso(), table_id),
        )


def cleanup_old_tables():
    while True:
        cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=RETENTION_DAYS)).isoformat()
        old_tables = query_db("SELECT id, user_id FROM table_workspaces WHERE created_at < ?", (cutoff,))
        for t in old_tables:
            table_id, user_id = t["id"], t["user_id"]
            query_db("DELETE FROM table_entries WHERE table_id=?", (table_id,))
            query_db("DELETE FROM table_workspaces WHERE id=?", (table_id,))
            shutil.rmtree(storage_for_table(user_id, table_id), ignore_errors=True)
        time.sleep(24 * 3600)


_tables_cleanup_started = False


def start_tables_background_jobs():
    global _tables_cleanup_started
    if _tables_cleanup_started:
        return
    os.makedirs(STORAGE_ROOT, exist_ok=True)
    APP_DATA_ROOT.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=cleanup_old_tables, daemon=True).start()
    _tables_cleanup_started = True


@app.route("/tables")
@login_required
def tables_page():
    return render_template("tables.html")


@app.route("/api/tables/send_code", methods=["POST"])
def tables_send_code():
    email = (request.form.get("email") or "").strip()
    if not email:
        return jsonify({"detail": "email обязателен"}), 400
    code = str(int(time.time()))[-6:]
    expires = (datetime.datetime.utcnow() + datetime.timedelta(minutes=10)).isoformat()
    query_db("INSERT INTO email_codes (email, code, expires_at, created_at) VALUES (?, ?, ?, ?)", (email, code, expires, now_iso()))
    print(f"[EMAIL-CODE] {email}: {code}")
    return jsonify({"status": "ok"})


@app.route("/api/tables/verify_code", methods=["POST"])
def tables_verify_code():
    email = (request.form.get("email") or "").strip()
    code = (request.form.get("code") or "").strip()
    row = query_db(
        "SELECT * FROM email_codes WHERE email=? AND code=? AND used=0 ORDER BY id DESC LIMIT 1",
        (email, code),
        one=True,
    )
    if not row or row["expires_at"] < now_iso():
        return jsonify({"detail": "Неверный или просроченный код"}), 400

    query_db("UPDATE email_codes SET used=1 WHERE id=?", (row["id"],))
    user = query_db("SELECT id FROM users WHERE email=?", (email,), one=True)
    if not user:
        salt = "tables"
        base_username = (email.split("@")[0] or "tables_user").strip()
        username = base_username
        suffix = 1
        while query_db("SELECT id FROM users WHERE username=?", (username,), one=True):
            suffix += 1
            username = f"{base_username}_{suffix}"
        query_db(
            "INSERT INTO users (username, email, password_hash, password_salt, role, is_verified, created_at, updated_at) VALUES (?, ?, ?, ?, 'viewer', 1, ?, ?)",
            (username, email, salt, salt, now_iso(), now_iso()),
        )
        user = query_db("SELECT id FROM users WHERE email=?", (email,), one=True)

    session["user_id"] = user["id"]
    resp = make_response(jsonify({"status": "ok", "user_id": user["id"]}))
    resp.set_cookie("tables_user_id", str(user["id"]), httponly=True, max_age=30 * 24 * 3600)
    return resp


@app.route("/api/tables", methods=["GET"])
def list_tables():
    user = table_user_from_request()
    if not user:
        return jsonify({"detail": "Не авторизован"}), 401
    rows = query_db("SELECT id, title, status, total_count, processed_count, progress, last_error, created_at, mapping_json FROM table_workspaces WHERE user_id=? ORDER BY id DESC", (user["id"],))
    connected = has_global_yandex_session()
    result = []
    for r in rows:
        item = dict(r)
        item["yandex_connected"] = connected
        item["mapping"] = normalize_mapping(json.loads(item.get("mapping_json") or "{}"))
        result.append(item)
    return jsonify(result)


@app.route("/api/tables", methods=["POST"])
def create_table():
    user = table_user_from_request()
    if not user:
        return jsonify({"detail": "Не авторизован"}), 401
    title = (request.form.get("title") or "").strip()
    if not title:
        return jsonify({"detail": "Название обязательно"}), 400
    cnt = query_db("SELECT COUNT(*) AS c FROM table_workspaces WHERE user_id=?", (user["id"],), one=True)["c"]
    if cnt >= MAX_TABLES_PER_USER:
        return jsonify({"detail": "Достигнут лимит 10 таблиц"}), 400
    ts = now_iso()
    query_db(
        "INSERT INTO table_workspaces (user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (user["id"], title, ts, ts),
    )
    return jsonify({"status": "ok"})


def apply_cookies_to_requests_session(req_session, cookies):
    for c in cookies:
        name = c.get("name")
        value = c.get("value")
        if not name or value is None:
            continue
        req_session.cookies.set(name, value, domain=c.get("domain") or ".yandex.ru", path=c.get("path") or "/")


def yandex_profile_cookie_file():
    return Path(YANDEX_PROFILE_DIR) / "Default" / "Cookies"


def read_yandex_cookies_from_chromium_profile():
    cookie_db = yandex_profile_cookie_file()
    if not cookie_db.exists():
        raise RuntimeError(f"Файл cookies Chromium не найден: {cookie_db}")

    tmp_copy = APP_DATA_ROOT / "tmp" / "yandex_cookies_read.sqlite"
    tmp_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cookie_db, tmp_copy)

    con = sqlite3.connect(str(tmp_copy))
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT host_key, name, value, path
            FROM cookies
            WHERE host_key LIKE '%yandex.ru%' OR host_key LIKE '%yandex.net%'
            """
        ).fetchall()
    finally:
        con.close()
        tmp_copy.unlink(missing_ok=True)

    cookies = []
    for row in rows:
        cookies.append(
            {
                "domain": row["host_key"],
                "name": row["name"],
                "value": row["value"],
                "path": row["path"] or "/",
            }
        )

    if not cookies:
        raise RuntimeError("В профиле Chromium не найдены cookies Яндекса")
    return cookies


def yandex_cookie_domains(cookies):
    domains = set()
    for c in cookies:
        domain = (c.get("domain") or "").strip().lower()
        if domain:
            domains.add(domain.lstrip('.'))
    return sorted(domains)


def check_yandex_auth(cookies):
    req = requests.Session()
    apply_cookies_to_requests_session(req, cookies)
    resp = req.get("https://disk.yandex.ru/client/disk", timeout=15, allow_redirects=True)
    final_url = (resp.url or "").lower()
    if resp.status_code in (401, 403) or "passport.yandex" in final_url:
        return False, resp.url or ""

    if YANDEX_FORMS_TEST_URL:
        probe = req.get(YANDEX_FORMS_TEST_URL, timeout=20, allow_redirects=True)
        probe_url = (probe.url or "").lower()
        if probe.status_code in (401, 403) or "passport.yandex" in probe_url:
            return False, probe.url or ""
    return True, resp.url or ""


def has_global_yandex_session():
    try:
        cookies = read_yandex_cookies_from_chromium_profile()
        app.logger.info(
            "[yandex_connect] cookies_count=%s domains=%s",
            len(cookies),
            ",".join(yandex_cookie_domains(cookies)),
        )
        ok, final_url = check_yandex_auth(cookies)
        if not ok:
            app.logger.info("[yandex_connect] auth_required final_url=%s", final_url)
        return ok
    except Exception as exc:
        app.logger.info("[yandex_connect] read_failed error=%s", str(exc))
        return False


def table_belongs_to_user(table_id, user_id):
    return query_db("SELECT id FROM table_workspaces WHERE id=? AND user_id=?", (table_id, user_id), one=True)


@app.route("/api/yandex/connect", methods=["POST"])
def yandex_connect():
    user = table_user_from_request()
    if not user:
        return jsonify({"detail": "Не авторизован"}), 401

    try:
        cookies = read_yandex_cookies_from_chromium_profile()
    except Exception as exc:
        app.logger.info("[yandex_connect] profile_read_failed error=%s", str(exc))
        return jsonify({"status": "need_login", "vnc_url": YANDEX_VNC_URL})

    domains = yandex_cookie_domains(cookies)
    app.logger.info("[yandex_connect] cookies_count=%s domains=%s", len(cookies), ",".join(domains))

    access_ok, final_url = check_yandex_auth(cookies)
    if not access_ok:
        app.logger.info("[yandex_connect] need_login final_url=%s", final_url)
        return jsonify({"status": "need_login", "vnc_url": YANDEX_VNC_URL})

    return jsonify({"status": "ok"})


@app.route("/api/tables/<int:table_id>/yandex/vnc/start", methods=["POST"])
def yandex_vnc_start(table_id):
    user = table_user_from_request()
    if not user:
        return jsonify({"detail": "Не авторизован"}), 401
    if not table_belongs_to_user(table_id, user["id"]):
        return jsonify({"detail": "Таблица не найдена"}), 404
    return jsonify({"vnc_url": YANDEX_VNC_URL})


@app.route("/api/tables/<int:table_id>", methods=["DELETE"])
def delete_table(table_id):
    user = table_user_from_request()
    if not user:
        return jsonify({"detail": "Не авторизован"}), 401
    table = query_db("SELECT id FROM table_workspaces WHERE id=? AND user_id=?", (table_id, user["id"]), one=True)
    if not table:
        return jsonify({"detail": "Таблица не найдена"}), 404
    query_db("DELETE FROM table_entries WHERE table_id=?", (table_id,))
    query_db("DELETE FROM table_workspaces WHERE id=?", (table_id,))
    shutil.rmtree(storage_for_table(user["id"], table_id), ignore_errors=True)
    return jsonify({"status": "ok"})


@app.route("/api/tables/<int:table_id>/excel", methods=["POST"])
def upload_excel(table_id):
    user = table_user_from_request()
    if not user:
        return jsonify({"detail": "Не авторизован"}), 401
    table = query_db("SELECT id FROM table_workspaces WHERE id=? AND user_id=?", (table_id, user["id"]), one=True)
    if not table:
        return jsonify({"detail": "Таблица не найдена"}), 404
    excel = request.files.get("excel")
    if not excel:
        return jsonify({"detail": "Файл excel обязателен"}), 400

    base = storage_for_table(user["id"], table_id)
    dst = os.path.join(base, "meta")
    os.makedirs(dst, exist_ok=True)
    for folder in ["phonograms", "receipts", "presentations"]:
        os.makedirs(os.path.join(base, folder), exist_ok=True)

    xlsx_path = os.path.join(dst, "original.xlsx")
    excel.save(xlsx_path)

    try:
        headers, preview_rows, total_rows, sheet_name = parse_excel_preview(xlsx_path)
    except Exception as exc:
        app.logger.warning("[tables_excel_preview] table_id=%s parse_failed error=%s", table_id, str(exc))
        query_db(
            "UPDATE table_workspaces SET status='error', progress=0, excel_headers_json='[]', excel_preview_rows_json='[]', excel_total_rows=0, excel_sheet_name=NULL, updated_at=? WHERE id=?",
            (now_iso(), table_id),
        )
        return jsonify({"detail": f"Excel не распознан: {str(exc)}"}), 400

    query_db("DELETE FROM table_entries WHERE table_id=?", (table_id,))

    for idx, row in enumerate(preview_rows, start=2):
        row_data = {str(i): v for i, v in enumerate(row)}
        try:
            query_db(
                """
                INSERT INTO table_entries (table_id, row_id, number_title, fio, team, unique_key, audio_url, receipt_url, consent_url, presentation_url, audio_local, receipt_local, consent_local, presentation_local, row_data_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    table_id,
                    idx,
                    "",
                    "",
                    "",
                    f"preview-{idx}",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    json.dumps(row_data, ensure_ascii=False),
                    now_iso(),
                ),
            )
        except Exception:
            app.logger.exception("[tables_excel_preview] table_id=%s row_id=%s insert_failed", table_id, idx)
            raise

    query_db(
        "UPDATE table_workspaces SET excel_headers_json=?, excel_preview_rows_json=?, excel_total_rows=?, excel_sheet_name=?, status='excel_loaded', progress=100, updated_at=? WHERE id=?",
        (
            json.dumps(headers, ensure_ascii=False),
            json.dumps(preview_rows, ensure_ascii=False),
            total_rows,
            sheet_name,
            now_iso(),
            table_id,
        ),
    )

    app.logger.info(
        "[tables_excel_preview] table_id=%s sheet=%s headers=%s preview_rows=%s total_rows=%s",
        table_id,
        sheet_name,
        len(headers),
        len(preview_rows),
        total_rows,
    )

    return jsonify(
        {
            "status": "ok",
            "table_status": "excel_loaded",
            "headers": headers,
            "rows": preview_rows,
            "total_rows": total_rows,
            "sheet": sheet_name,
        }
    )


@app.route("/api/tables/<int:table_id>/excel_preview", methods=["GET"])
def table_excel_preview(table_id):
    user = table_user_from_request()
    if not user:
        return jsonify({"detail": "Не авторизован"}), 401
    table = query_db(
        "SELECT id, excel_headers_json, excel_preview_rows_json, excel_total_rows FROM table_workspaces WHERE id=? AND user_id=?",
        (table_id, user["id"]),
        one=True,
    )
    if not table:
        return jsonify({"detail": "Таблица не найдена"}), 404
    headers = json.loads(table["excel_headers_json"] or "[]")
    rows = json.loads(table["excel_preview_rows_json"] or "[]")
    total_rows = int(table["excel_total_rows"] or 0)
    return jsonify({"headers": headers, "rows": rows, "total_rows": total_rows, "mapping_fields": MAPPING_FIELDS})


@app.route("/api/tables/<int:table_id>/excel-data", methods=["GET"])
def table_excel_data(table_id):
    return table_excel_preview(table_id)


@app.route("/api/tables/<int:table_id>/mapping", methods=["GET"])
def get_table_mapping(table_id):
    user = table_user_from_request()
    if not user:
        return jsonify({"detail": "Не авторизован"}), 401
    table = query_db("SELECT id, mapping_json FROM table_workspaces WHERE id=? AND user_id=?", (table_id, user["id"]), one=True)
    if not table:
        return jsonify({"detail": "Таблица не найдена"}), 404
    mapping = normalize_mapping(json.loads(table["mapping_json"] or "{}"))
    can_start, reason = table_required_mapping_status(mapping)
    return jsonify({"mapping": mapping, "can_start": can_start, "reason": reason, "mapping_fields": MAPPING_FIELDS})


@app.route("/api/tables/<int:table_id>/mapping", methods=["POST"])
def set_table_mapping(table_id):
    user = table_user_from_request()
    if not user:
        return jsonify({"detail": "Не авторизован"}), 401
    table = query_db("SELECT id FROM table_workspaces WHERE id=? AND user_id=?", (table_id, user["id"]), one=True)
    if not table:
        return jsonify({"detail": "Таблица не найдена"}), 404

    payload = request.get_json(silent=True) or {}
    mapping = normalize_mapping(payload.get("mapping") if isinstance(payload, dict) else payload)
    query_db("UPDATE table_workspaces SET mapping_json=?, updated_at=? WHERE id=?", (json.dumps(mapping, ensure_ascii=False), now_iso(), table_id))
    can_start, reason = table_required_mapping_status(mapping)
    return jsonify({"status": "ok", "mapping": mapping, "can_start": can_start, "reason": reason})


@app.route("/api/tables/<int:table_id>/start-download", methods=["POST"])
def start_download(table_id):
    user = table_user_from_request()
    if not user:
        return jsonify({"detail": "Не авторизован"}), 401
    t = query_db("SELECT id FROM table_workspaces WHERE id=? AND user_id=?", (table_id, user["id"]), one=True)
    if not t:
        return jsonify({"detail": "Таблица не найдена"}), 404
    full_table = query_db("SELECT mapping_json FROM table_workspaces WHERE id=? AND user_id=?", (table_id, user["id"]), one=True)
    mapping = normalize_mapping(json.loads(full_table["mapping_json"] or "{}"))
    can_start, reason = table_required_mapping_status(mapping)
    if not can_start:
        return jsonify({"detail": reason}), 400
    if not has_global_yandex_session():
        query_db("UPDATE table_workspaces SET status='error', last_error=?, updated_at=? WHERE id=?", ("Нужен вход администратора в Яндекс", now_iso(), table_id))
        return jsonify({"status": "need_login", "detail": "Нужен вход администратора в Яндекс", "vnc_url": YANDEX_VNC_URL}), 400
    total_rows = int(query_db("SELECT excel_total_rows FROM table_workspaces WHERE id=?", (table_id,), one=True)["excel_total_rows"] or 0)
    query_db("UPDATE table_workspaces SET status='queued', total_count=?, processed_count=0, progress=0, last_error=NULL, updated_at=? WHERE id=?", (total_rows, now_iso(), table_id))
    threading.Thread(target=process_table_download, args=(table_id, user["id"]), daemon=True).start()
    return jsonify({"status": "started"})


@app.route("/api/tables/<int:table_id>/entries", methods=["GET"])
def list_table_entries(table_id):
    user = table_user_from_request()
    if not user:
        return jsonify({"detail": "Не авторизован"}), 401
    table = query_db("SELECT id FROM table_workspaces WHERE id=? AND user_id=?", (table_id, user["id"]), one=True)
    if not table:
        return jsonify({"detail": "Таблица не найдена"}), 404
    rows = query_db("SELECT * FROM table_entries WHERE table_id=? ORDER BY id", (table_id,))
    return jsonify([dict(r) for r in rows])


def resolve_file(entry_id, ftype):
    e = query_db("SELECT te.*, tw.user_id FROM table_entries te JOIN table_workspaces tw ON tw.id=te.table_id WHERE te.id=?", (entry_id,), one=True)
    if not e:
        return None, (jsonify({"detail": "Entry не найден"}), 404)

    col = f"{ftype}_local"
    if col not in e.keys() or not e[col]:
        return None, (jsonify({"detail": "Файл не найден"}), 404)

    p = os.path.join(storage_for_table(e["user_id"], e["table_id"]), e[col])
    if not os.path.exists(p):
        return None, (jsonify({"detail": "Файл отсутствует"}), 404)
    return p, None


@app.route("/api/files/<int:entry_id>/<ftype>", methods=["GET"])
def get_file(entry_id, ftype):
    if not table_user_from_request():
        return jsonify({"detail": "Не авторизован"}), 401
    p, err = resolve_file(entry_id, ftype)
    if err:
        return err
    return send_file(p, as_attachment=True, download_name=os.path.basename(p))


@app.route("/api/preview/<int:entry_id>/<ftype>", methods=["GET"])
def preview_file(entry_id, ftype):
    if not table_user_from_request():
        return jsonify({"detail": "Не авторизован"}), 401
    p, err = resolve_file(entry_id, ftype)
    if err:
        return err
    ext = os.path.splitext(p)[1].lower()
    if ext == ".mp3":
        return jsonify({"detail": "Для mp3 доступно только скачивание"}), 400
    if ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".txt"]:
        return send_file(p, as_attachment=False)
    return jsonify({"detail": "Предпросмотр не поддерживается"}), 400


# =====================================================
#                VK STREAMING API
# =====================================================

VK_SETTINGS_FILE = os.path.join(BASE_DIR, "vk_settings.json")
PREVIEW_PID_FILE = os.path.join(BASE_DIR, "start_vk_preview.pid")
START_VK_SCRIPT = os.path.join(BASE_DIR, "start_vk.py")  # путь к скрипту, который мы писали
VK_LOCK_TEMPLATE = "/tmp/start_vk_{stream}.lock"
DEFAULT_STREAM_NAME = os.environ.get("RTMP_STREAM_NAME", "stream")


def start_preview_process():
    """Запустить start_vk.py как отдельный процесс (режим preview)."""
    # если pid-файл есть — считаем, что уже запущено
    if os.path.exists(PREVIEW_PID_FILE):
        try:
            with open(PREVIEW_PID_FILE) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            return
        except Exception:
            # старый pid мёртв — продолжим и перезапишем
            pass

    # Запускаем скрипт с произвольным аргументом (preview)
    cmd = ["/usr/bin/python3", START_VK_SCRIPT, "preview"]
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setsid)
        with open(PREVIEW_PID_FILE, "w") as f:
            f.write(str(p.pid))
    except Exception as e:
        app.logger.error("Не удалось запустить preview process: %s", e)

def stop_preview_process():
    """Остановить ранее запущенный preview процесс (если есть)."""
    if not os.path.exists(PREVIEW_PID_FILE):
        return
    try:
        with open(PREVIEW_PID_FILE) as f:
            pid = int(f.read().strip())
        # убиваем группу процессов
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except Exception:
            os.kill(pid, signal.SIGTERM)
    except Exception as e:
        app.logger.error("Ошибка при остановке preview: %s", e)
    try:
        os.remove(PREVIEW_PID_FILE)
    except:
        pass


def load_vk_settings():
    # если файла нет — возвращаем дефолт и создаём его
    default = {
        "enabled": False,
        "vk_rtmp_url": "",
        "scheduled_start": None,
        "title": "",
        "target_ids": [],
        "preview_path": os.path.join(BASE_DIR, "static", "vk_preview.jpg"),
        "show_preview": False
    }
    if not os.path.exists(VK_SETTINGS_FILE):
        try:
            os.makedirs(os.path.dirname(VK_SETTINGS_FILE), exist_ok=True)
            with open(VK_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(default, f, ensure_ascii=False, indent=4)
        except Exception:
            pass
        return default

    try:
        with open(VK_SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            data.setdefault("show_preview", False)
            data.setdefault("preview_path", os.path.join(BASE_DIR, "static", "vk_preview.jpg"))
            return data
    except Exception:
        # если файл кривой — перезаписываем дефолтом
        try:
            with open(VK_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(default, f, ensure_ascii=False, indent=4)
        except Exception:
            pass
        return default

def save_vk_settings(data):
    try:
        os.makedirs(os.path.dirname(VK_SETTINGS_FILE), exist_ok=True)
        with open(VK_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        # В лог можно записать, но мы возвращаем ошибку клиенту
        raise

def load_stream_targets():
    default_targets = []
    if not os.path.exists(STREAM_TARGETS_FILE):
        try:
            with open(STREAM_TARGETS_FILE, "w", encoding="utf-8") as f:
                json.dump(default_targets, f, ensure_ascii=False, indent=4)
        except Exception:
            pass
        return default_targets
    try:
        with open(STREAM_TARGETS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default_targets

def save_stream_targets(targets):
    os.makedirs(os.path.dirname(STREAM_TARGETS_FILE), exist_ok=True)
    with open(STREAM_TARGETS_FILE, "w", encoding="utf-8") as f:
        json.dump(targets, f, ensure_ascii=False, indent=4)

def preview_url_for(settings):
    preview_path = settings.get("preview_path")
    if not preview_path:
        return ""
    if not os.path.isabs(preview_path):
        preview_path = os.path.join(BASE_DIR, preview_path)
    static_dir = os.path.join(BASE_DIR, "static")
    try:
        if os.path.commonpath([static_dir, preview_path]) == static_dir:
            return "/static/" + os.path.basename(preview_path)
    except ValueError:
        return ""
    return preview_path

@app.route("/vk/status", methods=["GET"])
@login_required
def vk_status():
    settings = load_vk_settings()
    settings["preview_url"] = preview_url_for(settings)
    settings["stream_url"] = resolve_stream_url()
    settings["targets"] = load_stream_targets()
    settings.setdefault("target_ids", [])
    settings.setdefault("show_preview", False)
    return jsonify(settings)

@app.route("/vk/register_key", methods=["POST"])
@login_required
@roles_required("admin", "editor")
def vk_register_key():
    data = request.get_json(silent=True) or {}
    vk_rtmp_url = (data.get("vk_rtmp_url") or "").strip()
    if not vk_rtmp_url:
        return jsonify({"status": "error", "message": "Ключ обязателен"}), 400
    settings = load_vk_settings()
    settings["vk_rtmp_url"] = vk_rtmp_url
    try:
        save_vk_settings(settings)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Не удалось сохранить ключ: {e}"}), 500
    return jsonify({"status": "ok"})

@app.route("/vk/public_status", methods=["GET"])
def vk_public_status():
    settings = load_vk_settings()
    return jsonify({
        "enabled": settings.get("enabled", False),
        "preview_url": preview_url_for(settings),
        "stream_url": resolve_stream_url(),
        "show_preview": settings.get("show_preview", False)
    })

@app.route("/vk/preview", methods=["POST"])
@login_required
@roles_required("admin", "editor")
def vk_preview_upload():
    file = request.files.get("image")
    if not file:
        return jsonify({"status": "error", "message": "Файл не выбран"}), 400

    s = load_vk_settings()
    try:
        preview_dir = os.path.join(BASE_DIR, "static")
        os.makedirs(preview_dir, exist_ok=True)
        preview_path = os.path.join(preview_dir, "vk_preview.jpg")
        file.save(preview_path)
        s["preview_path"] = preview_path
        save_vk_settings(s)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Не удалось сохранить превью: {e}"}), 500

    return jsonify({"status": "ok", "preview_url": preview_url_for(s)})

@app.route("/vk/preview_visibility", methods=["POST"])
@login_required
@roles_required("admin", "editor")
def vk_preview_visibility():
    data = request.get_json(silent=True) or {}
    show_preview = bool(data.get("show_preview"))
    s = load_vk_settings()
    s["show_preview"] = show_preview
    try:
        save_vk_settings(s)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Не удалось сохранить настройки: {e}"}), 500
    return jsonify({"status": "ok", "show_preview": s.get("show_preview", False)})

def _start_vk_process(stream_name):
    cmd = ["/usr/bin/python3", START_VK_SCRIPT, stream_name]
    run_as_nobody = bool(os.environ.get("VK_START_AS_NOBODY", "1") == "1")
    if run_as_nobody:
        cmd = ["sudo", "-u", "nobody", *cmd]

    p = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=os.setsid,
    )
    return p, cmd


@app.route("/vk/start_now", methods=["POST"])
@login_required
def vk_start_now():
    s = load_vk_settings()
    title = ""
    target_ids = []

    if request.is_json:
        payload = request.get_json(silent=True) or {}
        title = payload.get("title", "")
        target_ids = payload.get("target_ids") or []
    else:
        title = request.form.get("title", "")

    selected_target = None
    targets = load_stream_targets()
    if target_ids:
        selected_target = next((t for t in targets if t.get("id") == target_ids[0]), None)

    s["enabled"] = True
    s["scheduled_start"] = None
    if title:
        s["title"] = title
    s["target_ids"] = target_ids
    s["show_preview"] = False

    try:
        save_vk_settings(s)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Не удалось сохранить настройки: {e}"}), 500

    stream_name = DEFAULT_STREAM_NAME
    lock_file = VK_LOCK_TEMPLATE.format(stream=stream_name)
    lock_removed = False
    try:
        if os.path.exists(lock_file):
            os.remove(lock_file)
            lock_removed = True
    except Exception as e:
        return jsonify({"status": "error", "message": f"Не удалось снять lock {lock_file}: {e}"}), 500

    try:
        proc, cmd = _start_vk_process(stream_name)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Не удалось запустить ретрансляцию: {e}"}), 500

    return jsonify({
        "status": "ok",
        "ok": True,
        "msg": "VK stream start requested",
        "stream_name": stream_name,
        "target": selected_target,
        "target_ids": target_ids,
        "lock_removed": lock_removed,
        "pid": proc.pid,
        "command": cmd,
    })


@app.route("/vk/stop", methods=["POST"])
@login_required
@roles_required("admin", "editor")
def vk_stop():
    s = load_vk_settings()
    s["enabled"] = False
    s["scheduled_start"] = None
    try:
        save_vk_settings(s)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Не удалось сохранить настройки: {e}"}), 500
    return jsonify({"status": "ok", "msg": "VK streaming stopped"})

@app.route("/vk/schedule", methods=["POST"])
@login_required
@roles_required("admin", "editor")
def vk_schedule():
    s = load_vk_settings()

    title = ""
    date = ""
    time_val = ""
    target_ids = []

    # поддерживаем два варианта: multipart/form-data (с файлом) и application/json
    if request.content_type and request.content_type.startswith("application/json"):
        body = request.get_json(silent=True) or {}
        title = body.get("title", "")
        iso = body.get("iso") or body.get("scheduled_start")
        target_ids = body.get("target_ids") or []
        if iso:
            scheduled = iso
        else:
            date = body.get("date", "")
            time_val = body.get("time", "")
    else:
        # multipart/form-data или обычная форма
        try:
            title = request.form.get("title", "")
            date = request.form.get("date", "")
            time_val = request.form.get("time", "")
            target_ids = request.form.getlist("target_ids")
        except Exception:
            # если парсинг формы упал — вернём ошибку
            return jsonify({"status": "error", "message": "Ошибка при чтении формы"}), 400

    if 'scheduled' in locals():
        pass  # уже есть
    else:
        if date and time_val:
            scheduled = f"{date}T{time_val}:00"
        else:
            now = datetime.datetime.utcnow() + datetime.timedelta(minutes=1)
            scheduled = now.isoformat()

    # Превью (если пришёл файл)
    if request.files:
        file = request.files.get("image")
    else:
        file = None

    if file:
        try:
            preview_dir = os.path.join(BASE_DIR, "static")
            os.makedirs(preview_dir, exist_ok=True)
            preview_path = os.path.join(preview_dir, "vk_preview.jpg")
            file.save(preview_path)
            s["preview_path"] = preview_path
        except Exception as e:
            return jsonify({"status": "error", "message": f"Не удалось сохранить превью: {e}"}), 500

    s["title"] = title
    s["scheduled_start"] = scheduled
    s["enabled"] = True
    s["target_ids"] = target_ids
    s["show_preview"] = False

    try:
        save_vk_settings(s)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Не удалось сохранить настройки: {e}"}), 500

    return jsonify({"status": "ok", "scheduled": scheduled})

@app.route("/vk/targets", methods=["POST"])
@login_required
@roles_required("admin", "editor")
def vk_targets():
    data = request.get_json(silent=True) or {}
    target_ids = data.get("target_ids") or []
    s = load_vk_settings()
    s["target_ids"] = target_ids
    try:
        save_vk_settings(s)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Не удалось сохранить настройки: {e}"}), 500
    return jsonify({"status": "ok"})

@app.route("/stream/targets", methods=["GET", "POST"])
@login_required
def stream_targets():
    if request.method == "GET":
        return jsonify(load_stream_targets())

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    url_val = (data.get("url") or "").strip()
    if not name:
        return jsonify({"status": "error", "message": "Название обязательно"}), 400
    targets = load_stream_targets()
    target_id = secrets.token_hex(4)
    targets.append({"id": target_id, "name": name, "url": url_val, "enabled": True})
    save_stream_targets(targets)
    return jsonify({"status": "ok", "target": {"id": target_id, "name": name, "url": url_val, "enabled": True}})

@app.route("/stream/targets/<target_id>", methods=["PUT", "DELETE"])
@login_required
def stream_targets_update(target_id):
    targets = load_stream_targets()
    target = next((t for t in targets if t.get("id") == target_id), None)
    if not target:
        return jsonify({"status": "error", "message": "Цель не найдена"}), 404

    if request.method == "DELETE":
        targets = [t for t in targets if t.get("id") != target_id]
        save_stream_targets(targets)
        return jsonify({"status": "ok"})

    data = request.get_json(silent=True) or {}
    target["name"] = (data.get("name") or target["name"]).strip()
    target["url"] = (data.get("url") or target["url"]).strip()
    if "enabled" in data:
        target["enabled"] = bool(data.get("enabled"))
    save_stream_targets(targets)
    return jsonify({"status": "ok", "target": target})

# =====================================================
#                   END VK STREAMING
# =====================================================

# ------------ Запуск ------------
init_db()
start_tables_background_jobs()

if __name__ == "__main__":
    ensure_admin_exists()
    app.run(host="127.0.0.1", port=8083, debug=True)
