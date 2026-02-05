from flask import Flask, render_template, request, jsonify, redirect, url_for, session, g
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
from functools import wraps

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
STREAM_URL = os.environ.get("HLS_STREAM_URL", "http://192.168.31.18:8080/hls/stream.m3u8")

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

# ------------ Маршруты ------------
@app.route("/")
def index():
    return redirect("/login")

@app.route("/admin")
@login_required
def admin():
    return render_template("admin.html", user=get_current_user(), stream_url=STREAM_URL)

@app.route("/staff")
@roles_required("admin")
def staff():
    users = query_db("SELECT id, username, email, role, is_verified FROM users ORDER BY id")
    return render_template("staff.html", users=users, stream_url=STREAM_URL)

@app.route("/broadcast")
def broadcast():
    return render_template("broadcast.html", stream_url=STREAM_URL)

@app.route("/competition")
def competition():
    return render_template("competition.html", stream_url=STREAM_URL)

# --- Мероприятия ---
@app.route("/editor")
@login_required
def editor_list():
    return render_template("editor.html", stream_url=STREAM_URL)

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
    return render_template("admin.html", event_id=event_id, stream_url=STREAM_URL)

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

# =====================================================
#                VK STREAMING API
# =====================================================

VK_SETTINGS_FILE = os.path.join(BASE_DIR, "vk_settings.json")
PREVIEW_PID_FILE = os.path.join(BASE_DIR, "start_vk_preview.pid")
START_VK_SCRIPT = os.path.join(BASE_DIR, "start_vk.py")  # путь к скрипту, который мы писали

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
        "preview_path": os.path.join(BASE_DIR, "static", "vk_preview.jpg")
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
            return json.load(f)
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
    default_targets = [
        {"id": "tv", "name": "Телевизоры", "url": "", "enabled": True},
        {"id": "vk-main", "name": "VK группа", "url": "", "enabled": True}
    ]
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
    settings["stream_url"] = STREAM_URL
    settings["targets"] = load_stream_targets()
    settings.setdefault("target_ids", [])
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
        "stream_url": STREAM_URL
    })

@app.route("/vk/start_now", methods=["POST"])
@login_required
@roles_required("admin", "editor")
def vk_start_now():
    s = load_vk_settings()
    title = ""
    target_ids = []

    # поддерживаем и JSON payload, и form
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        title = payload.get("title", "")
        target_ids = payload.get("target_ids") or []
    else:
        title = request.form.get("title", "")

    s["enabled"] = True
    s["scheduled_start"] = None
    if title:
        s["title"] = title
    s["target_ids"] = target_ids

    try:
        save_vk_settings(s)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Не удалось сохранить настройки: {e}"}), 500

    return jsonify({"status": "ok", "msg": "VK stream started now"})

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
@roles_required("admin", "editor")
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
@roles_required("admin", "editor")
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
if __name__ == "__main__":
    init_db()
    ensure_admin_exists()
    app.run(host="0.0.0.0", port=8082, debug=True)
