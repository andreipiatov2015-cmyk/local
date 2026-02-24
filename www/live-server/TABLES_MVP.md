# Tables MVP (встроено в основной Flask-сервер)

## Что добавлено
- Функциональность таблиц заявок встроена в `server.py` (основной сервер админки).
- Страница: `/tables` (шаблон `templates/tables.html`).
- Статика: `/static/tables.js`, `/static/tables.css`.
- API:
  - `GET /api/tables`
  - `POST /api/tables`
  - `DELETE /api/tables/{id}`
  - `POST /api/tables/{id}/excel`
  - `POST /api/tables/{id}/connect-yandex`
  - `POST /api/tables/{id}/start-download`
  - `GET /api/tables/{id}/entries`
  - `GET /api/files/{entry_id}/{type}`
  - `GET /api/preview/{entry_id}/{type}`

## Запуск
Запускается только основной сервер:

```bash
cd /workspace/local/www/live-server
python3 server.py
```

Открыть:
- `http://localhost:8082/` — админка
- `http://localhost:8082/tables` — таблицы заявок

## Хранилище
Файлы сохраняются в `STORAGE_ROOT` (по умолчанию `/var/mount_point/nfv/contest_storage`).

## Важно
- Отдельный `tables_service.py` оставлен в репозитории как архив, но не используется в маршрутизации основного сервера.
- Используется общая авторизация сайта (те же сессии, что и у админки), отдельного логина на `/tables` нет.
- Очистка данных старше 60 дней запускается в фоне в процессе основного сервера.
