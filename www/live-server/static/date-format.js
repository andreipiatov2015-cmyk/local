// Общие хелперы форматирования дат для админки — единое место вместо того,
// чтобы каждая страница сама парсила ISO-строки и могла показать пользователю
// сырые "2026-07-20T12:15:03.482917" или заглушки вроде пустой строки.
// Подключать ПОСЛЕ layout.js и ПЕРЕД скриптом страницы, который эти хелперы
// использует (tables.js, registration_desk.js, инлайн-скрипт editor.html).

function _dateFormatIsPlausible(yRaw, mRaw, dRaw) {
  const year = Number(yRaw);
  const month = Number(mRaw);
  const day = Number(dRaw);
  if (!Number.isInteger(year) || year < 1970 || year > 2200) return false;
  if (!Number.isInteger(month) || month < 1 || month > 12) return false;
  if (!Number.isInteger(day) || day < 1 || day > 31) return false;
  return true;
}

// "2026-07-20" -> "20.07.2026"; пусто/мусор -> "дата не указана".
function formatDateRu(value) {
  const text = (value || '').toString().trim();
  if (!text) return 'дата не указана';
  const match = text.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return text;
  const [, y, m, d] = match;
  if (!_dateFormatIsPlausible(y, m, d)) return 'дата не указана';
  return `${d}.${m}.${y}`;
}

// "2026-07-20T12:15:03.482917" -> "20.07.2026 12:15"; плоская дата без
// времени -> "20.07.2026"; пусто/мусор -> "дата не указана".
function formatDateTimeRu(value) {
  const text = (value || '').toString().trim();
  if (!text) return 'дата не указана';
  const withTime = text.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/);
  if (withTime) {
    const [, y, m, d, hh, mm] = withTime;
    if (!_dateFormatIsPlausible(y, m, d)) return 'дата не указана';
    return `${d}.${m}.${y} ${hh}:${mm}`;
  }
  return formatDateRu(text);
}

// "2026-07-20" -> "20 июля 2026 года" — для текста программ/дипломов,
// где уместна полная форма, а не короткая ДД.MM.ГГГГ.
function formatDateRuLong(value) {
  const text = (value || '').toString().trim();
  if (!text) return '';
  const match = text.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return text;
  const [, yRaw, mRaw, dRaw] = match;
  if (!_dateFormatIsPlausible(yRaw, mRaw, dRaw)) return text;
  const year = Number(yRaw);
  const month = Number(mRaw);
  const day = Number(dRaw);
  const monthNames = [
    'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
    'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
  ];
  return `${day} ${monthNames[month - 1]} ${year} года`;
}
