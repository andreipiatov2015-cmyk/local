import datetime as dt
import json
import os
import re
import shutil
import sqlite3
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests
from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

try:
    import openpyxl
except Exception:  # pragma: no cover
    openpyxl = None

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "app.db"
STORAGE_ROOT = Path("/var/mount_point/nfv/contest_storage")
RETENTION_DAYS = 60
MAX_TABLES_PER_USER = 10
DOWNLOAD_RETRIES = 3
MAX_FILENAME_LEN = 180

TABLE_COLUMNS = {
    "number_title": ["Название номера", "Номер", "Название"],
    "fio": ["ФИО", "Участник", "Исполнитель"],
    "team": ["Коллектив", "Команда", "Ансамбль"],
    "audio_url": ["Фонограмма", "Фонограмма ссылка"],
    "receipt_url": ["Квитанция", "Ссылка на квитанцию"],
    "consent_url": ["Согласие", "Ссылка на согласие"],
    "presentation_url": ["Презентация", "Ссылка на презентацию"],
}

app = FastAPI(title="Contest tables")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/tables-static", StaticFiles(directory=str(BASE_DIR / "static")), name="tables-static")


def db(query: str, args=(), one=False):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(query, args)
    rows = cur.fetchall()
    conn.commit()
    conn.close()
    if one:
        return rows[0] if rows else None
    return rows


def init_db():
    db(
        """
        CREATE TABLE IF NOT EXISTS email_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            code TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """
    )
    db(
        """
        CREATE TABLE IF NOT EXISTS table_workspaces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'new',
            progress INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            yandex_session_json TEXT
        )
        """
    )
    db(
        """
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
        """
    )


def now_iso() -> str:
    return dt.datetime.utcnow().isoformat()


def sanitize_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip()
    return cleaned[:MAX_FILENAME_LEN] if len(cleaned) > MAX_FILENAME_LEN else cleaned


def user_from_request(request: Request):
    user_id = request.cookies.get("tables_user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Не авторизован")
    row = db("SELECT id, email FROM users WHERE id=?", (user_id,), one=True)
    if not row:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    return row


def storage_for_table(user_id: int, table_id: int) -> Path:
    return STORAGE_ROOT / "users" / f"user_{user_id}" / "tables" / f"table_{table_id}"


def detect_columns(headers: List[str]) -> Dict[str, Optional[int]]:
    result = {k: None for k in TABLE_COLUMNS.keys()}
    for idx, h in enumerate(headers):
        h_norm = (h or "").strip().lower()
        for key, aliases in TABLE_COLUMNS.items():
            if result[key] is not None:
                continue
            for alias in aliases:
                if h_norm == alias.strip().lower():
                    result[key] = idx
                    break
    return result


def get_cell(row, idx):
    if idx is None or idx >= len(row):
        return ""
    v = row[idx]
    return "" if v is None else str(v).strip()




def _response_looks_like_html(response: requests.Response):
    ctype = (response.headers.get("Content-Type") or "").lower()
    cdisp = (response.headers.get("Content-Disposition") or "").lower()
    final_url = str(response.url or "").lower()
    body_prefix = (response.content or b"")[:512].lstrip().lower()

    if "text/html" in ctype:
        return True
    if ctype.startswith("text/") and "attachment" not in cdisp:
        return True
    if "forms.yandex.ru/u/files" in final_url and "attachment" not in cdisp and "audio" not in ctype:
        return True
    if body_prefix.startswith(b"<!doctype html") or body_prefix.startswith(b"<html"):
        return True
    return False

def download_with_retries(session: requests.Session, url: str, out_path: Path):
    last_error = None
    for _ in range(DOWNLOAD_RETRIES):
        try:
            r = session.get(url, timeout=30, allow_redirects=True)
            r.raise_for_status()
            if _response_looks_like_html(r):
                raise RuntimeError(f"received html/text instead of binary file; status={r.status_code}; final_url={r.url}")
            out_path.write_bytes(r.content)
            return
        except Exception as e:  # pragma: no cover
            last_error = str(e)
            time.sleep(1)
    raise RuntimeError(last_error or "download failed")


def extension_from_url(url: str, fallback="bin") -> str:
    name = url.split("?")[0].rstrip("/").split("/")[-1]
    if "." in name:
        ext = name.rsplit(".", 1)[-1].lower()
        return ext[:10]
    return fallback


def process_table_download(table_id: int, user_id: int):
    t = db("SELECT * FROM table_workspaces WHERE id=? AND user_id=?", (table_id, user_id), one=True)
    if not t:
        return
    db("UPDATE table_workspaces SET status='processing', progress=1, updated_at=? WHERE id=?", (now_iso(), table_id))
    base = storage_for_table(user_id, table_id)
    excel_path = base / "meta" / "excel_original.xlsx"
    if not excel_path.exists() or openpyxl is None:
        db("UPDATE table_workspaces SET status='error', updated_at=? WHERE id=?", (now_iso(), table_id))
        return

    wb = openpyxl.load_workbook(excel_path)
    ws = wb.active
    rows = list(ws.values)
    if not rows:
        db("UPDATE table_workspaces SET status='done', progress=100, updated_at=? WHERE id=?", (now_iso(), table_id))
        return
    headers = [str(x).strip() if x is not None else "" for x in rows[0]]
    col = detect_columns(headers)
    data_rows = rows[1:]

    cookie_json = t["yandex_session_json"] or "{}"
    cookies = json.loads(cookie_json)
    req = requests.Session()
    if isinstance(cookies, dict):
        req.cookies.update(cookies)

    total = max(len(data_rows), 1)
    for i, row in enumerate(data_rows, start=1):
        number_title = get_cell(row, col["number_title"])
        fio = get_cell(row, col["fio"])
        team = get_cell(row, col["team"])
        unique_key = f"{number_title}|{fio}|{team}"

        exists = db("SELECT id FROM table_entries WHERE table_id=? AND unique_key=?", (table_id, unique_key), one=True)
        if exists:
            continue

        created_at = now_iso()
        db(
            """
            INSERT INTO table_entries (table_id, number_title, fio, team, unique_key, audio_url, receipt_url, consent_url, presentation_url, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                table_id,
                number_title,
                fio,
                team,
                unique_key,
                get_cell(row, col["audio_url"]),
                get_cell(row, col["receipt_url"]),
                get_cell(row, col["consent_url"]),
                get_cell(row, col["presentation_url"]),
                created_at,
            ),
        )
        entry_id = db("SELECT last_insert_rowid() AS id", one=True)["id"]
        entry_dir = base / "entries" / f"entry_{entry_id}"
        entry_dir.mkdir(parents=True, exist_ok=True)
        base_name = sanitize_name(f"{fio} — {number_title}") or f"entry_{entry_id}"

        audio_url = get_cell(row, col["audio_url"])
        audio_local = ""
        if audio_url:
            ext = extension_from_url(audio_url, "mp3")
            audio_name = f"{base_name}.{ext}"
            audio_path = entry_dir / audio_name
            try:
                download_with_retries(req, audio_url, audio_path)
                audio_local = audio_name
            except Exception:
                fail = entry_dir / "audio.txt"
                fail.write_text("Не удалось скачать фонограмму", encoding="utf-8")
                audio_local = "audio.txt"
        else:
            miss = entry_dir / "audio.txt"
            miss.write_text("Фонограмма не предоставлена", encoding="utf-8")
            audio_local = "audio.txt"

        field_map = [
            ("receipt", get_cell(row, col["receipt_url"])),
            ("consent", get_cell(row, col["consent_url"])),
            ("presentation", get_cell(row, col["presentation_url"])),
        ]
        local_values = {"receipt": "", "consent": "", "presentation": ""}
        for ftype, furl in field_map:
            if not furl:
                continue
            ext = extension_from_url(furl)
            filename = f"{base_name}.{ext}"
            out_path = entry_dir / filename
            try:
                download_with_retries(req, furl, out_path)
                local_values[ftype] = filename
            except Exception:
                pass

        db(
            "UPDATE table_entries SET audio_local=?, receipt_local=?, consent_local=?, presentation_local=? WHERE id=?",
            (audio_local, local_values["receipt"], local_values["consent"], local_values["presentation"], entry_id),
        )
        progress = int((i / total) * 100)
        db("UPDATE table_workspaces SET progress=?, updated_at=? WHERE id=?", (progress, now_iso(), table_id))

    db("UPDATE table_workspaces SET status='done', progress=100, updated_at=? WHERE id=?", (now_iso(), table_id))


def cleanup_old_tables():
    while True:
        cutoff = (dt.datetime.utcnow() - dt.timedelta(days=RETENTION_DAYS)).isoformat()
        old_tables = db("SELECT id, user_id FROM table_workspaces WHERE created_at < ?", (cutoff,))
        for t in old_tables:
            table_id, user_id = t["id"], t["user_id"]
            db("DELETE FROM table_entries WHERE table_id=?", (table_id,))
            db("DELETE FROM table_workspaces WHERE id=?", (table_id,))
            shutil.rmtree(storage_for_table(user_id, table_id), ignore_errors=True)
            print(f"[cleanup] removed table {table_id} for user {user_id}")
        time.sleep(24 * 3600)


@app.on_event("startup")
def on_startup():
    init_db()
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    thr = threading.Thread(target=cleanup_old_tables, daemon=True)
    thr.start()


@app.get("/tables", response_class=HTMLResponse)
def tables_page(request: Request):
    return templates.TemplateResponse("tables.html", {"request": request})


@app.post("/api/auth/send-code")
def send_code(email: str = Form(...)):
    code = str(int(time.time()))[-6:]
    expires = (dt.datetime.utcnow() + dt.timedelta(minutes=10)).isoformat()
    db("INSERT INTO email_codes (email, code, expires_at, created_at) VALUES (?, ?, ?, ?)", (email, code, expires, now_iso()))
    print(f"[EMAIL-CODE] {email}: {code}")
    return {"status": "ok"}


@app.post("/api/auth/verify-code")
def verify_code(email: str = Form(...), code: str = Form(...)):
    row = db(
        "SELECT * FROM email_codes WHERE email=? AND code=? AND used=0 ORDER BY id DESC LIMIT 1",
        (email, code),
        one=True,
    )
    if not row or row["expires_at"] < now_iso():
        raise HTTPException(status_code=400, detail="Неверный или просроченный код")
    db("UPDATE email_codes SET used=1 WHERE id=?", (row["id"],))
    user = db("SELECT id FROM users WHERE email=?", (email,), one=True)
    if not user:
        salt = "tables"
        db(
            "INSERT INTO users (username, email, password_hash, password_salt, role, is_verified, created_at, updated_at) VALUES (?, ?, ?, ?, 'viewer', 1, ?, ?)",
            (email.split("@")[0], email, salt, salt, now_iso(), now_iso()),
        )
        user = db("SELECT id FROM users WHERE email=?", (email,), one=True)
    resp = JSONResponse({"status": "ok", "user_id": user["id"]})
    resp.set_cookie("tables_user_id", str(user["id"]), httponly=True, max_age=30 * 24 * 3600)
    return resp


@app.post("/api/tables")
def create_table(request: Request, title: str = Form(...)):
    user = user_from_request(request)
    cnt = db("SELECT COUNT(*) AS c FROM table_workspaces WHERE user_id=?", (user["id"],), one=True)["c"]
    if cnt >= MAX_TABLES_PER_USER:
        raise HTTPException(status_code=400, detail="Достигнут лимит 10 таблиц")
    ts = now_iso()
    db(
        "INSERT INTO table_workspaces (user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (user["id"], title, ts, ts),
    )
    return {"status": "ok"}


@app.get("/api/tables")
def list_tables(request: Request):
    user = user_from_request(request)
    rows = db("SELECT id, title, status, progress, created_at FROM table_workspaces WHERE user_id=? ORDER BY id DESC", (user["id"],))
    return [dict(r) for r in rows]


@app.delete("/api/tables/{table_id}")
def delete_table(table_id: int, request: Request):
    user = user_from_request(request)
    table = db("SELECT id FROM table_workspaces WHERE id=? AND user_id=?", (table_id, user["id"]), one=True)
    if not table:
        raise HTTPException(status_code=404, detail="Таблица не найдена")
    db("DELETE FROM table_entries WHERE table_id=?", (table_id,))
    db("DELETE FROM table_workspaces WHERE id=?", (table_id,))
    shutil.rmtree(storage_for_table(user["id"], table_id), ignore_errors=True)
    return {"status": "ok"}


@app.post("/api/tables/{table_id}/excel")
def upload_excel(table_id: int, request: Request, excel: UploadFile = File(...)):
    user = user_from_request(request)
    table = db("SELECT id FROM table_workspaces WHERE id=? AND user_id=?", (table_id, user["id"]), one=True)
    if not table:
        raise HTTPException(status_code=404, detail="Таблица не найдена")
    dst = storage_for_table(user["id"], table_id) / "meta"
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "excel_original.xlsx").write_bytes(excel.file.read())
    db("UPDATE table_workspaces SET updated_at=? WHERE id=?", (now_iso(), table_id))
    return {"status": "ok"}


@app.post("/api/tables/{table_id}/connect-yandex")
def connect_yandex(table_id: int, request: Request, cookies_json: str = Form(...)):
    user = user_from_request(request)
    db(
        "UPDATE table_workspaces SET yandex_session_json=?, updated_at=? WHERE id=? AND user_id=?",
        (cookies_json, now_iso(), table_id, user["id"]),
    )
    return {"status": "ok"}


@app.post("/api/tables/{table_id}/start-download")
def start_download(table_id: int, request: Request):
    user = user_from_request(request)
    t = db("SELECT id FROM table_workspaces WHERE id=? AND user_id=?", (table_id, user["id"]), one=True)
    if not t:
        raise HTTPException(status_code=404, detail="Таблица не найдена")
    threading.Thread(target=process_table_download, args=(table_id, user["id"]), daemon=True).start()
    return {"status": "started"}


@app.get("/api/tables/{table_id}/entries")
def list_entries(table_id: int, request: Request):
    user = user_from_request(request)
    table = db("SELECT id FROM table_workspaces WHERE id=? AND user_id=?", (table_id, user["id"]), one=True)
    if not table:
        raise HTTPException(status_code=404, detail="Таблица не найдена")
    rows = db("SELECT * FROM table_entries WHERE table_id=? ORDER BY id", (table_id,))
    return [dict(r) for r in rows]


def resolve_file(entry_id: int, ftype: str):
    e = db("SELECT te.*, tw.user_id FROM table_entries te JOIN table_workspaces tw ON tw.id=te.table_id WHERE te.id=?", (entry_id,), one=True)
    if not e:
        raise HTTPException(status_code=404, detail="Entry не найден")
    col = f"{ftype}_local"
    if col not in e.keys() or not e[col]:
        raise HTTPException(status_code=404, detail="Файл не найден")
    p = storage_for_table(e["user_id"], e["table_id"]) / "entries" / f"entry_{entry_id}" / e[col]
    if not p.exists():
        raise HTTPException(status_code=404, detail="Файл отсутствует")
    return p


@app.get("/api/files/{entry_id}/{ftype}")
def get_file(entry_id: int, ftype: str, request: Request):
    user_from_request(request)
    p = resolve_file(entry_id, ftype)
    return FileResponse(str(p), filename=p.name)


@app.get("/api/preview/{entry_id}/{ftype}")
def preview_file(entry_id: int, ftype: str, request: Request):
    user_from_request(request)
    p = resolve_file(entry_id, ftype)
    ext = p.suffix.lower()
    if ext == ".mp3":
        raise HTTPException(status_code=400, detail="Для mp3 доступно только скачивание")
    if ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".txt"]:
        return FileResponse(str(p))
    raise HTTPException(status_code=400, detail="Предпросмотр не поддерживается")
