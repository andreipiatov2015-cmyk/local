"""Публичная форма регистрации — полностью отдельный процесс.

Намеренно изолирован от основного сайта (www/live-server/server.py):
- без доступа к app.db и вообще без БД;
- единственный вход — чтение forms-экспорта (REGISTRATION_PUBLIC_FORMS_EXPORT_FILE),
  который пишет только админка;
- единственный выход — файл с зашифрованным ответом в drop-директории
  (REGISTRATION_DROP_DIR), который читает только админка.
Шифрование — nacl.public.SealedBox: этому процессу приватный ключ не
нужен и никогда не передаётся, так что даже полная компрометация этого
процесса не даёт прочитать уже отправленные ответы.
См. /root/.claude/plans/curried-weaving-hummingbird.md — полная архитектура.
"""

import base64
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone

from flask import Flask, abort, render_template, request

import nacl.public

app = Flask(__name__, template_folder="templates", static_folder="static")

FORMS_EXPORT_FILE = os.environ.get(
    "REGISTRATION_PUBLIC_FORMS_EXPORT_FILE", "/var/lib/rtmp-server/registration-public-forms.json"
)
DROP_DIR = os.environ.get("REGISTRATION_DROP_DIR", "/var/lib/rtmp-server/registration-drop")
THROTTLE_SECONDS = int(os.environ.get("REGISTRATION_PUBLIC_THROTTLE_SECONDS", "10"))

# Длина строго совпадает с secrets.token_urlsafe(16) на стороне админки —
# этим же регэкспом в nginx отличают публичную форму от остальных
# маршрутов сайта, так что здесь это не лишняя предосторожность, а то же
# самое правило, продублированное для прямых обращений мимо nginx.
SLUG_RE = re.compile(r"^[A-Za-z0-9_-]{22}$")

NUMERIC_QTYPES = {"people_count"}

# Простой троттлинг на IP — без внешних зависимостей, в памяти процесса.
# Этого достаточно только при одном воркере (как и запущено по умолчанию),
# не более того — см. план.
_last_submit_at = {}


def _throttle_blocked(ip):
    """Только проверка — не отмечает попытку. Отметка о реальной отправке
    делается отдельно, см. _mark_submitted: иначе участник, ошибившийся в
    обязательном поле, не смог бы сразу же его исправить и отправить
    заново — а бороться мы хотим с повторной спам-отправкой, а не с
    исправлением опечатки."""
    now = time.time()
    # Попутно подчищаем то, что всё равно устарело — иначе словарь растёт
    # бесконечно на долго живущем процессе.
    stale_before = now - THROTTLE_SECONDS * 10
    for k in [k for k, v in _last_submit_at.items() if v < stale_before]:
        del _last_submit_at[k]

    last = _last_submit_at.get(ip)
    return last is not None and now - last < THROTTLE_SECONDS


def _mark_submitted(ip):
    _last_submit_at[ip] = time.time()


def load_forms():
    try:
        with open(FORMS_EXPORT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"public_key_b64": None, "forms": {}}


def _client_ip():
    return request.headers.get("X-Real-IP") or request.remote_addr or "unknown"


def _get_form_or_404(slug):
    if not SLUG_RE.match(slug):
        abort(404)
    data = load_forms()
    form = data.get("forms", {}).get(slug)
    if not form:
        abort(404)
    return data, form


@app.errorhandler(404)
def not_found(_e):
    return render_template("not_found.html"), 404


@app.route("/<slug>", methods=["GET"])
def show_form(slug):
    _data, form = _get_form_or_404(slug)
    return render_template("form.html", slug=slug, title=form["title"], questions=form["questions"])


@app.route("/<slug>", methods=["POST"])
def submit_form(slug):
    data, form = _get_form_or_404(slug)
    public_key_b64 = data.get("public_key_b64")
    if not public_key_b64:
        abort(500)

    ip = _client_ip()
    if _throttle_blocked(ip):
        return render_template(
            "form.html", slug=slug, title=form["title"], questions=form["questions"],
            error="Подождите немного перед повторной отправкой.",
        ), 429

    answers = {}
    missing_labels = []
    for q in form["questions"]:
        qtype = q["qtype"]
        raw = (request.form.get(qtype) or "").strip()
        if qtype in NUMERIC_QTYPES:
            if not raw.isdigit() or int(raw) <= 0:
                missing_labels.append(q["label"])
                continue
            answers[qtype] = int(raw)
        else:
            if not raw:
                missing_labels.append(q["label"])
                continue
            answers[qtype] = raw

    if missing_labels:
        return render_template(
            "form.html", slug=slug, title=form["title"], questions=form["questions"],
            error="Заполните обязательные поля: " + ", ".join(missing_labels),
            submitted=request.form,
        ), 400

    payload = json.dumps(
        {
            "desk_id": form["desk_id"],
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "answers": answers,
        },
        ensure_ascii=False,
    ).encode("utf-8")

    public_key = nacl.public.PublicKey(base64.b64decode(public_key_b64))
    sealed = nacl.public.SealedBox(public_key).encrypt(payload)

    os.makedirs(DROP_DIR, exist_ok=True)
    filename = f"{form['desk_id']}__{uuid.uuid4().hex}.sealed"
    final_path = os.path.join(DROP_DIR, filename)
    tmp_path = final_path + ".tmp"
    with open(tmp_path, "wb") as f:
        f.write(sealed)
    os.replace(tmp_path, final_path)

    _mark_submitted(ip)
    return render_template("thanks.html", title=form["title"])


if __name__ == "__main__":
    port = int(os.environ.get("REGISTRATION_PUBLIC_PORT", "8086"))
    # Только localhost — наружу форма торчит исключительно через nginx
    # (location под случайную ссылку, см. www/nginx.conf), сама по себе
    # эта обычный Flask-процесс никогда не слушает внешний интерфейс.
    # debug=False (в отличие от live-server) — сюда может достучаться кто
    # угодно по открытой ссылке, Werkzeug-дебаггер тут недопустим.
    app.run(host="127.0.0.1", port=port, debug=False)
