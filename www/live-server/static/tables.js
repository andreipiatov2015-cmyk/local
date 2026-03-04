let currentTableId = null;
let yandexConnected = false;
let lastVncUrl = null;

const workspace = document.getElementById('workspace');
const tableView = document.getElementById('tableView');
const tableList = document.getElementById('tableList');
const entriesBody = document.getElementById('entries');
const progressEl = document.getElementById('progress');
const tableTitle = document.getElementById('tableTitle');
const yandexStatusEl = document.getElementById('yandexStatus');
const startDownloadBtn = document.getElementById('startDownload');
const openAdminLoginBtn = document.getElementById('openAdminLogin');
const yandexHintEl = document.getElementById('yandexHint');

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

function setYandexStatus(status, vncUrl = null) {
  if (status === 'success') {
    yandexStatusEl.textContent = '✅ Яндекс подключен (используется сессия организатора)';
    yandexConnected = true;
    startDownloadBtn.disabled = false;
    yandexHintEl.textContent = '';
    lastVncUrl = null;
    openAdminLoginBtn.classList.add('hidden');
    return;
  }

  if (status === 'need_login') {
    yandexStatusEl.textContent = '❌ Нужен вход администратора';
    yandexConnected = false;
    startDownloadBtn.disabled = true;
    yandexHintEl.textContent = 'Сессия организатора не активна. Откройте окно входа администратора и выполните вход в Яндекс.';
    lastVncUrl = vncUrl;
    openAdminLoginBtn.classList.remove('hidden');
    return;
  }

  yandexStatusEl.textContent = 'Яндекс: не подключен';
  yandexConnected = false;
  startDownloadBtn.disabled = true;
  yandexHintEl.textContent = '';
  lastVncUrl = null;
  openAdminLoginBtn.classList.add('hidden');
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
    setYandexStatus(cur.yandex_connected ? 'success' : 'idle');
    if (cur.status === 'need_login') {
      setYandexStatus('need_login', lastVncUrl);
    }
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

  const isPdfGuess = previewUrl.includes('/receipt') || previewUrl.includes('/consent') || previewUrl.includes('/presentation');
  if (isPdfGuess) {
    viewerBody.innerHTML = `<iframe src="${previewUrl}" style="width:100%;height:70vh;border:0"></iframe>`;
  } else {
    viewerBody.innerHTML = `<img src="${previewUrl}" style="width:100%;height:70vh;object-fit:contain" />`;
  }

  viewer.showModal();
}

function initTablesSection() {
  closeViewerBtn.onclick = () => viewer.close();

  document.getElementById('createTable').onclick = async () => {
    const title = document.getElementById('newTitle').value.trim();
    if (!title) return alert('Введите название таблицы');
    await postForm('/api/tables', { title });
    await refreshTables();
  };

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

  document.getElementById('connectYandex').onclick = async () => {
    const resp = await fetch('/api/yandex/connect', { method: 'POST' });
    if (requireAuth(resp)) return;
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) return alert(data.detail || 'Не удалось проверить сессию Яндекса');

    if (data.status === 'ok') {
      setYandexStatus('success');
      await refreshTables();
      return;
    }

    if (data.status === 'need_login') {
      setYandexStatus('need_login', data.vnc_url || null);
      return;
    }

    setYandexStatus('idle');
  };

  openAdminLoginBtn.onclick = async () => {
    if (!currentTableId) return alert('Сначала выберите таблицу');
    let vncUrl = lastVncUrl;
    if (!vncUrl) {
      const resp = await fetch(`/api/tables/${currentTableId}/yandex/vnc/start`, { method: 'POST' });
      if (requireAuth(resp)) return;
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) return alert(data.detail || 'Не удалось получить ссылку VNC');
      vncUrl = data.vnc_url;
    }
    const popup = window.open(vncUrl, 'yandex_vnc', 'width=520,height=720,menubar=no,toolbar=no,location=no,status=no,resizable=yes,scrollbars=no');
    if (!popup) alert('Не удалось открыть окно noVNC (проверьте блокировщик pop-up)');
  };

  document.getElementById('startDownload').onclick = async () => {
    if (!currentTableId) return alert('Сначала выберите таблицу');
    if (!yandexConnected) return alert('Сначала подключите Яндекс');
    const resp = await fetch(`/api/tables/${currentTableId}/start-download`, { method: 'POST' });
    if (requireAuth(resp)) return;
    if (!resp.ok) return alert(await resp.text());
    alert('Фоновая загрузка запущена');
    setTimeout(refreshEntries, 1000);
  };

  document.body.addEventListener('click', (e) => {
    const dl = e.target?.dataset?.dl;
    const pv = e.target?.dataset?.pv;
    if (dl) safeOpen(dl);
    if (pv) openViewer(pv);
  });


  refreshTables();
  setInterval(() => {
    refreshTables();
    refreshEntries();
  }, 4000);
}

document.addEventListener('DOMContentLoaded', initTablesSection);
