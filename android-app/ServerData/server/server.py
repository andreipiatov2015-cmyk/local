#!/usr/bin/env python3
"""
Пример простого сервера для приложения «Данные сервера».

Без внешних библиотек, нужен только Python 3.8+.
Данные берутся из файла data.json рядом со скриптом и перечитываются
при каждом запросе: изменили файл — приложение увидит изменения
при следующем обновлении.

Запуск:
    python3 server.py              # порт 8000
    python3 server.py 9000         # другой порт

Вместо data.json можно брать данные из своей программы/базы —
достаточно переписать функцию load_items().
"""

import json
import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data.json")
SERVER_NAME = "Мой сервер"
API_VERSION = "1.0"


def load_items():
    """Вернуть (список записей, время изменения данных в ISO-формате)."""
    with open(DATA_FILE, encoding="utf-8") as f:
        items = json.load(f)
    mtime = os.path.getmtime(DATA_FILE)
    updated = datetime.fromtimestamp(mtime, tz=timezone.utc).astimezone().isoformat(timespec="seconds")
    return items, updated


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0].rstrip("/")
        try:
            if path == "/api/info":
                _, updated = load_items()
                self._send_json(200, {"name": SERVER_NAME, "version": API_VERSION, "updated_at": updated})
            elif path == "/api/items":
                items, updated = load_items()
                self._send_json(200, {"updated_at": updated, "items": items})
            elif path.startswith("/api/items/"):
                item_id = path[len("/api/items/"):]
                items, _ = load_items()
                for item in items:
                    if str(item.get("id")) == item_id:
                        self._send_json(200, item)
                        return
                self._send_json(404, {"error": "not found"})
            else:
                self._send_json(404, {"error": "not found"})
        except Exception as e:  # чтобы приложение получило понятный код ошибки
            self._send_json(500, {"error": str(e)})


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Сервер запущен: http://0.0.0.0:{port}  (Ctrl+C — остановить)")
    print(f"Проверка: http://localhost:{port}/api/items")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
