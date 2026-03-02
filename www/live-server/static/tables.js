let currentTableId = null;

const workspace = document.getElementById('workspace');
const tableView = document.getElementById('tableView');
const tableList = document.getElementById('tableList');
const entriesBody = document.getElementById('entries');
const progressEl = document.getElementById('progress');
const tableTitle = document.getElementById('tableTitle');

const viewer = document.getElementById('viewer');
const viewerBody = document.getElementById('viewerBody');
const downloadTop = document.getElementById('downloadTop');
const closeViewerBtn = document.getElementById('closeViewer');

function requireAuth(resp) {
  if (resp.status === 401) {
    window.location.href = '/login';
    return true;
  }
  return false;
}

async function postForm(url, data) {
  const fd = new FormData();
  Object.entries(data).forEach(([k, v]) => fd.append(k, v));
  const r = await fetch(url, { method: 'POST', body: fd });
  if (requireAuth(r)) throw new Error('unauthorized');
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

function safeOpen(url) {
  window.open(url, '_blank', 'noopener,noreferrer');
}

async function refreshTables() {
  const r = await fetch('/api/tables');
  if (requireAuth(r)) return;

  const tables = await r.json();
  tableList.innerHTML = '';

  tables.forEach(t => {
    const li = document.createElement('li');
    li.textContent = `#${t.id} ${t.title} [${t.status}] ${t.progress ?? 0}%`;
    li.onclick = () => openTable(t.id, t.title);
    tableList.appendChild(li);
  });
}

async function openTable(id, title) {
  currentTableId = id;
  tableTitle.textContent = `Таблица: ${title} (#${id})`;
  tableView.classList.remove('hidden');
  await refreshEntries();
}

function fileButtons(entry, type) {
  const local = entry[`${type}_local`];
  if (!local) return '';
  return `
    <button data-dl="/api/files/${entry.id}/${type}">Скачать</button>
    <button data-pv="/api/preview/${entry.id}/${type}">Открыть</button>
  `;
}

async function refreshEntries() {
  if (!currentTableId) return;

  const tablesResp = await fetch('/api/tables');
  if (requireAuth(tablesResp)) return;

  const tables = await tablesResp.json();
  const cur = tables.find(x => x.id === currentTableId);
  if (cur) {
    progressEl.textContent = `Статус: ${cur.status}, прогресс: ${cur.progress ?? 0}%`;
  }

  const rowsResp = await fetch(`/api/tables/${currentTableId}/entries`);
  if (requireAuth(rowsResp)) return;

  const rows = await rowsResp.json();
  entriesBody.innerHTML = '';

  rows.forEach(e => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${e.id}</td>
      <td>${e.fio || ''}</td>
      <td>${e.number_title || ''}</td>
      <td>${e.team || ''}</td>
      <td>
        <div style="display:flex;gap:6px;flex-wrap:wrap">
          ${fileButtons(e, 'audio')}
          ${fileButtons(e, 'receipt')}
          ${fileButtons(e, 'consent')}
          ${fileButtons(e, 'presentation')}
        </div>
      </td>
    `;
    entriesBody.appendChild(tr);
  });
}

function openViewer(previewUrl) {
  viewerBody.innerHTML = '';
  downloadTop.onclick = () => safeOpen(previewUrl.replace('/preview/', '/files/'));

  // Мы не знаем реальный тип заранее, поэтому пробуем iframe,
  // а если это картинка — img тоже откроется. (В худшем случае будет пусто.)
  // Лучше потом улучшить: backend пусть отдаёт content-type в JSON.
  const isPdfGuess = previewUrl.includes('/receipt') || previewUrl.includes('/consent') || previewUrl.includes('/presentation');
  if (isPdfGuess) {
    viewerBody.innerHTML = `<iframe src="${previewUrl}" style="width:100%;height:70vh;border:0"></iframe>`;
  } else {
    viewerBody.innerHTML = `<img src="${previewUrl}" style="width:100%;height:70vh;object-fit:contain" />`;
  }

  viewer.showModal();
}

function initTablesSection() {
  // Закрытие viewer
  closeViewerBtn.onclick = () => viewer.close();

  // Создание таблицы
  document.getElementById('createTable').onclick = async () => {
    const title = document.getElementById('newTitle').value.trim();
    if (!title) return alert('Введите название таблицы');
    await postForm('/api/tables', { title });
    await refreshTables();
  };

  // Загрузка Excel
  document.getElementById('uploadExcel').onclick = async () => {
    if (!currentTableId) return alert('Сначала выберите таблицу');
    const f = document.getElementById('excelFile').files[0];
    if (!f) return alert('Выберите файл Excel');
    const fd = new FormData();
    fd.append('excel', f);

    const resp = await fetch(`/api/tables/${currentTableId}/excel`, { method: 'POST', body: fd });
    if (requireAuth(resp)) return;
    if (!resp.ok) return alert(await resp.text());

    alert('Excel загружен');
    await refreshEntries();
  };

  // Подключить Яндекс (cookies json)
  document.getElementById('connectYandex').onclick = async () => {
    if (!currentTableId) return alert('Сначала выберите таблицу');
    const cookiesJson = document.getElementById('yandexCookies').value.trim() || '{}';
    await postForm(`/api/tables/${currentTableId}/connect-yandex`, { cookies_json: cookiesJson });
    alert('Yandex session сохранена');
  };

  // Старт скачивания
  document.getElementById('startDownload').onclick = async () => {
    if (!currentTableId) return alert('Сначала выберите таблицу');
    const resp = await fetch(`/api/tables/${currentTableId}/start-download`, { method: 'POST' });
    if (requireAuth(resp)) return;
    if (!resp.ok) return alert(await resp.text());
    alert('Фоновая загрузка запущена');
    setTimeout(refreshEntries, 1000);
  };

  // Общий обработчик кнопок скачать/открыть
  document.body.addEventListener('click', (e) => {
    const dl = e.target?.dataset?.dl;
    const pv = e.target?.dataset?.pv;
    if (dl) safeOpen(dl);
    if (pv) openViewer(pv);
  });

  // Стартовые данные
  refreshTables();
  setInterval(() => {
    refreshTables();
    refreshEntries();
  }, 4000);
}

document.addEventListener('DOMContentLoaded', initTablesSection);
