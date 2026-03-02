# Tables MVP (встроено в основной Flask-сервер)

## Что добавлено
- Функциональность таблиц заявок встроена в `server.py` (основной сервер админки).
- Страница: `/tables` (шаблон `templates/tables.html`).
- Статика: `/static/tables.js`, `/static/tables.css`.
- API:
  - `POST /api/tables/send_code`
  - `POST /api/tables/verify_code`
  - `GET /api/tables`
  - `POST /api/tables`
  - `DELETE /api/tables/{id}`
  - `POST /api/tables/{id}/excel`
  - `POST /api/tables/{id}/yandex/connect/start`
  - `GET /tables/yandex/connect/{connect_id}`
  - `GET /api/tables/{id}/yandex/connect/status?connect_id=...`
  - `POST /api/yandex/connect/{connect_id}/upload` (fallback: cookies file)
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
- Код подтверждения email в MVP печатается в stdout сервера.
- Очистка данных старше 60 дней запускается в фоне в процессе основного сервера.

## Подключение Яндекса
- Ручной ввод JSON cookies в `/tables` удалён.
- Кнопка «Подключить Яндекс» запускает одноразовую сессию подключения (`connect_id`, TTL 10 минут) и открывает popup.
- Popup показывает статусы: ожидание / успех / ошибка.
- Основной сценарий авторизации через headless Playwright может быть ограничен капчей/2FA, поэтому в MVP реализован обязательный fallback: загрузка cookies-файла (`.txt` Netscape или JSON).
- Сессия Яндекса хранится в `APP_DATA_ROOT/users/user_{user_id}/yandex_session.json` и привязана к пользователю сайта.
- Скачивание файлов использует сохранённую пользовательскую сессию; при отсутствии/устаревании сессии возвращается ошибка переподключения.
