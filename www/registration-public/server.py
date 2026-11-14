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
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timezone

from flask import Flask, abort, render_template, request

import nacl.public

app = Flask(__name__, template_folder="templates", static_folder="static")

# Общий лимит тела запроса — защита от мегабайтных payload'ов ДО того, как
# Flask вообще дочитает и забуферизует их в память (проверки длины
# отдельных полей ниже срабатывают уже ПОСЛЕ чтения тела, этого
# недостаточно само по себе). Werkzeug сам вернёт 413 при превышении —
# отдельного кода не требуется. 128 КиБ — с большим запасом покрывает
# team_name (≤5000 символов × до 4 байт UTF-8) и остальные поля (≤2000)
# вместе с multipart-накладными расходами.
app.config["MAX_CONTENT_LENGTH"] = 128 * 1024

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

# Лимиты длины полей — не для того, чтобы ограничить людей (длинные
# названия учреждений/коллективов — обычное дело), а чтобы отсечь заведомо
# аномальные payload'ы. team_name — отдельно пошире по явному запросу.
DEFAULT_MAX_FIELD_LEN = 2000
FIELD_MAX_LENGTHS = {"team_name": 5000}

HONEYPOT_FIELD_NAME = "website"
MIN_FILL_SECONDS = int(os.environ.get("REGISTRATION_PUBLIC_MIN_FILL_SECONDS", "2"))
# Токен живёт долго (сутки) — это не авторизационная сессия (на форме нет
# ни логина, ни кук вообще), а просто подписанная метка времени рендера
# формы: обычный участник мог открыть вкладку и не торопиться с
# заполнением. Боты, которые шлют POST не глядя на GET-ответ, токен не
# пришлют вообще — этого достаточно для цели (анти-бот, не анти-CSRF
# в классическом смысле, который здесь не нужен — нет сессии, которую
# можно было бы угнать).
TOKEN_MAX_AGE_SECONDS = int(os.environ.get("REGISTRATION_PUBLIC_TOKEN_MAX_AGE_SECONDS", str(24 * 3600)))
# Секрет только в памяти процесса — токен привязан к его жизни, рестарт
# между открытием формы и отправкой (редкий случай, обычно только при
# деплое) потребует просто обновить страницу. Файл/персистентность ради
# этого не нужны — тут не защита данных, а фильтр ботов.
_CSRF_SECRET = secrets.token_bytes(32)

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


def _make_form_token(slug):
    issued_at = str(int(time.time()))
    sig = hmac.new(_CSRF_SECRET, f"{slug}:{issued_at}".encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{issued_at}.{sig}"


def _verify_form_token(slug, token):
    """None при недействительном токене, иначе время выпуска (секунды, int)."""
    if not token or "." not in token:
        return None
    issued_at_str, _, sig = token.partition(".")
    if not issued_at_str.isdigit():
        return None
    expected = hmac.new(_CSRF_SECRET, f"{slug}:{issued_at_str}".encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    issued_at = int(issued_at_str)
    now = time.time()
    if issued_at > now + 5 or now - issued_at > TOKEN_MAX_AGE_SECONDS:
        return None
    return issued_at


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
    return render_template(
        "form.html", slug=slug, title=form["title"], questions=form["questions"],
        csrf_token=_make_form_token(slug),
    )


@app.route("/<slug>", methods=["POST"])
def submit_form(slug):
    data, form = _get_form_or_404(slug)
    public_key_b64 = data.get("public_key_b64")
    if not public_key_b64:
        abort(500)

    # Honeypot: обычный участник это поле не видит (спрятано CSS за
    # пределами экрана, не display:none — некоторые боты именно его и
    # проверяют) и не заполняет. Заполнено -> тихо делаем вид, что всё
    # прошло успешно, ничего не шифруя и не сохраняя — чтобы бот не понял,
    # что был пойман, и не стал подстраиваться.
    if (request.form.get(HONEYPOT_FIELD_NAME) or "").strip():
        return render_template("thanks.html", title=form["title"])

    issued_at = _verify_form_token(slug, request.form.get("csrf_token"))
    if issued_at is None:
        return render_template(
            "form.html", slug=slug, title=form["title"], questions=form["questions"],
            csrf_token=_make_form_token(slug),
            error="Истекло время заполнения формы — обновите страницу и заполните заново.",
        ), 400
    if time.time() - issued_at < MIN_FILL_SECONDS:
        return render_template(
            "form.html", slug=slug, title=form["title"], questions=form["questions"],
            csrf_token=_make_form_token(slug),
            error="Форма ещё не успела полностью загрузиться — попробуйте ещё раз.",
        ), 400

    ip = _client_ip()
    if _throttle_blocked(ip):
        return render_template(
            "form.html", slug=slug, title=form["title"], questions=form["questions"],
            csrf_token=_make_form_token(slug),
            error="Подождите немного перед повторной отправкой.",
        ), 429

    answers = {}
    missing_labels = []
    too_long_labels = []
    for q in form["questions"]:
        qtype = q["qtype"]
        raw = (request.form.get(qtype) or "").strip()
        max_len = FIELD_MAX_LENGTHS.get(qtype, DEFAULT_MAX_FIELD_LEN)
        if len(raw) > max_len:
            too_long_labels.append(q["label"])
            continue
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

    if too_long_labels:
        return render_template(
            "form.html", slug=slug, title=form["title"], questions=form["questions"],
            csrf_token=_make_form_token(slug),
            error="Слишком длинное значение в поле(ях): " + ", ".join(too_long_labels),
        ), 400

    if missing_labels:
        return render_template(
            "form.html", slug=slug, title=form["title"], questions=form["questions"],
            csrf_token=_make_form_token(slug),
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
