# Live Server: запуск ретрансляции в VK

## Что реализовано
- Кнопка **"Да"** в модальном окне "Транслировать в" отправляет `POST /vk/start_now` с JSON:
  - `title`
  - `target_ids` (массив выбранных направлений)
- Backend-обработчик `/vk/start_now`:
  - включает `enabled=true`
  - сбрасывает `scheduled_start=null`
  - сохраняет `title` и `target_ids` в `vk_settings.json`
  - удаляет lock `/tmp/start_vk_<stream>.lock` перед запуском
  - запускает `/var/www/live-server/start_vk.py <stream>` в фоне
  - возвращает диагностику (`target`, `stream_name`, `pid`, `command`, `lock_removed`)

## Важные файлы
- Frontend: `static/admin.js`
- Backend: `server.py`
- Ретранслятор: `start_vk.py`
- Nginx RTMP: `../nginx.conf` (`exec_push ... start_vk.py $name`)

## Логи
- `logs/start_vk.log`
- `logs/ffmpeg_live_stream.log`

## Проверка
1. Запустить OBS в `rtmp://<server>/live/stream`.
2. Убедиться, что HLS открывается (`/hls/stream.m3u8`).
3. На сайте: "Настройка трансляции" → "Транслировать в" → выбрать цель → "Да".
4. Проверить `POST /vk/start_now` в DevTools (payload + JSON response).
5. Проверить логи:
   - `tail -f /var/www/live-server/logs/start_vk.log`
   - `tail -f /var/www/live-server/logs/ffmpeg_live_stream.log`

## Переменные окружения
- `RTMP_STREAM_NAME` (по умолчанию `stream`)
- `VK_START_AS_NOBODY=1` — запускать скрипт через `sudo -u nobody`
- `HLS_STREAM_URL` — явный URL HLS-потока для интерфейса (если не задан, сервер сам собирает URL как `{scheme}://{host}/hls/stream.m3u8` из текущего запроса; fallback: `http://127.0.0.1:8082/hls/stream.m3u8`).
- `YANDEX_CHROMIUM_PROFILE` — путь к Chromium-профилю noVNC, из которого сервер читает cookies (по умолчанию `/tmp/chromium-yandex-profile`).



## Подключение Яндекса через noVNC
- Скрипт `restart_astra.sh` запускает Chromium сразу на `https://forms.yandex.ru/admin/` (а не на `passport.yandex.ru`), чтобы после входа гарантированно появлялись cookies для `forms.yandex.ru`.
- Endpoint `POST /api/tables/{id}/yandex/vnc/finish` проверяет доступ через `GET https://forms.yandex.ru/admin/` с cookies из профиля Chromium.
- Если ответ уводит на `passport.yandex.ru` или возвращает `401/403`, подключение считается незавершённым.
- В логи пишется только безопасная диагностика: количество cookies и список доменов (без значений cookies).

## Таблицы заявок
- Раздел `/tables` работает в том же Flask-процессе, что и админка.
- Отдельный запуск `uvicorn`/FastAPI не требуется.
- API таблиц доступно по путям `/api/tables*` на том же домене и порту.
