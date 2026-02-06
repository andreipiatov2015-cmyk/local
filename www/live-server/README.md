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
