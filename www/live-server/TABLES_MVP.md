# Tables MVP (FastAPI)

## Что добавлено
- Отдельный сервис на FastAPI: `tables_service.py`.
- Отдельная страница: `/tables`.
- API:
  - `POST /api/tables`
  - `GET /api/tables`
  - `DELETE /api/tables/{id}`
  - `POST /api/tables/{id}/excel`
  - `POST /api/tables/{id}/connect-yandex`
  - `POST /api/tables/{id}/start-download`
  - `GET /api/tables/{id}/entries`
  - `GET /api/files/{entry_id}/{type}`
  - `GET /api/preview/{entry_id}/{type}`
- Email code auth endpoints:
  - `POST /api/auth/send-code`
  - `POST /api/auth/verify-code`

## Запуск
```bash
cd /workspace/local/www/live-server
pip install fastapi uvicorn jinja2 python-multipart openpyxl requests
uvicorn tables_service:app --host 0.0.0.0 --port 8010
```

Открыть: `http://localhost:8010/tables`

## Хранилище
Файлы сохраняются в `/var/mount_point/nfv/contest_storage`.

## Важно
- "Подключить Яндекс" в MVP принимает cookies JSON и сохраняет его в профиль таблицы.
- Код подтверждения email печатается в stdout сервера (для dev).
- Очистка данных старше 60 дней запускается daily в background thread.
