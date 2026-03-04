let currentTableId = null;
let lastVncUrl = null;
let stickyNeedLogin = false;
let currentMapping = {};
let mappingFields = {};
let currentHeaders = [];
let selectedColumn = null;

const tableList = document.getElementById('tableList');
const progressEl = document.getElementById('progress');
const tableTitle = document.getElementById('tableTitle');
const yandexStatusEl = document.getElementById('yandexStatus');
const startDownloadBtn = document.getElementById('startDownload');
const openAdminLoginBtn = document.getElementById('openAdminLogin');
const yandexHintEl = document.getElementById('yandexHint');
const tableView = document.getElementById('tableView');
const excelHead = document.getElementById('excelHead');
const excelBody = document.getElementById('excelBody');
const mappingInfo = document.getElementById('mappingInfo');
const mappingDialog = document.getElementById('mappingDialog');
const mappingDialogActions = document.getElementById('mappingDialogActions');

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
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail || JSON.stringify(body));
  return body;
}

function setYandexState(state, vncUrl = null) {
  if (state === 'need_login') {
    stickyNeedLogin = true;
    yandexStatusEl.textContent = 'Требуется авторизация администратора';
    yandexHintEl.textContent = 'Откройте вход администратора (VNC) и выполните вход в Яндекс.';
    openAdminLoginBtn.classList.remove('hidden');
    if (vncUrl) lastVncUrl = vncUrl;
    return;
  }
  if (state === 'ok') {
    stickyNeedLogin = false;
    yandexStatusEl.textContent = '✅ Яндекс подключен';
    yandexHintEl.textContent = '';
    openAdminLoginBtn.classList.add('hidden');
    return;
  }
  if (stickyNeedLogin) {
    yandexStatusEl.textContent = 'Требуется авторизация администратора';
    yandexHintEl.textContent = 'Откройте вход администратора (VNC) и выполните вход в Яндекс.';
    openAdminLoginBtn.classList.remove('hidden');
    return;
  }
  yandexStatusEl.textContent = 'Яндекс: не подключен';
  yandexHintEl.textContent = '';
  openAdminLoginBtn.classList.add('hidden');
}

function mappingReverse() {
  const rev = {};
  Object.entries(currentMapping || {}).forEach(([field, col]) => { rev[col] = field; });
  return rev;
}

function renderMappingInfo() {
  const assigned = Object.entries(currentMapping).map(([f, c]) => `${mappingFields[f] || f}: ${currentHeaders[c] || ('#'+c)}`);
  const missing = Object.keys(mappingFields).filter((f) => !currentMapping[f]).map((f) => mappingFields[f]);
  mappingInfo.innerHTML = `
    <b>Схема колонок</b><br>
    Назначено: ${assigned.length ? assigned.join(' | ') : 'пока нет'}<br>
    Не назначено: ${missing.slice(0, 8).join(', ')}${missing.length > 8 ? ' ...' : ''}
  `;
}

function renderExcelTable(rows) {
  const rev = mappingReverse();
  excelHead.innerHTML = '';
  excelBody.innerHTML = '';

  const trh = document.createElement('tr');
  currentHeaders.forEach((h, idx) => {
    const th = document.createElement('th');
    const assignedField = rev[idx];
    th.textContent = h || `Колонка ${idx + 1}`;
    th.dataset.col = String(idx);
    th.className = assignedField ? 'mapped' : '';
    if (assignedField) th.title = `Назначено: ${mappingFields[assignedField] || assignedField}`;
    th.onclick = () => openMappingDialog(idx);
    trh.appendChild(th);
  });
  excelHead.appendChild(trh);

  rows.forEach((rowObj) => {
    const tr = document.createElement('tr');
    currentHeaders.forEach((_, idx) => {
      const td = document.createElement('td');
      td.textContent = rowObj.row_data?.[String(idx)] || '';
      tr.appendChild(td);
    });
    excelBody.appendChild(tr);
  });

  renderMappingInfo();
}

async function refreshExcelData() {
  if (!currentTableId) return;
  const resp = await fetch(`/api/tables/${currentTableId}/excel-data`);
  if (requireAuth(resp) || !resp.ok) return;
  const data = await resp.json();
  currentHeaders = data.headers || [];
  mappingFields = data.mapping_fields || {};
  renderExcelTable(data.rows || []);
}

async function refreshMapping() {
  if (!currentTableId) return;
  const r = await fetch(`/api/tables/${currentTableId}/mapping`);
  if (requireAuth(r) || !r.ok) return;
  const data = await r.json();
  currentMapping = data.mapping || {};
  mappingFields = data.mapping_fields || mappingFields;
  startDownloadBtn.disabled = !data.can_start;
  startDownloadBtn.title = data.can_start ? '' : data.reason;
  renderMappingInfo();
}

async function saveMapping() {
  const r = await fetch(`/api/tables/${currentTableId}/mapping`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mapping: currentMapping })
  });
  if (requireAuth(r)) return;
  const data = await r.json().catch(() => ({}));
  if (!r.ok) return alert(data.detail || 'Ошибка сохранения mapping');
  startDownloadBtn.disabled = !data.can_start;
  startDownloadBtn.title = data.can_start ? '' : data.reason;
  await refreshExcelData();
}

function openMappingDialog(colIndex) {
  selectedColumn = colIndex;
  mappingDialogActions.innerHTML = '';
  Object.entries(mappingFields).forEach(([field, title]) => {
    const btn = document.createElement('button');
    btn.textContent = `Назначить как: ${title}`;
    btn.onclick = async () => {
      Object.keys(currentMapping).forEach((k) => {
        if (currentMapping[k] === colIndex || k === field) delete currentMapping[k];
      });
      currentMapping[field] = colIndex;
      await saveMapping();
      mappingDialog.close();
    };
    mappingDialogActions.appendChild(btn);
  });
  const clearBtn = document.createElement('button');
  clearBtn.textContent = 'Снять назначение';
  clearBtn.onclick = async () => {
    Object.keys(currentMapping).forEach((k) => {
      if (currentMapping[k] === colIndex) delete currentMapping[k];
    });
    await saveMapping();
    mappingDialog.close();
  };
  mappingDialogActions.appendChild(clearBtn);
  mappingDialog.showModal();
}

async function refreshTables() {
  const r = await fetch('/api/tables');
  if (requireAuth(r)) return;
  const tables = await r.json();
  tableList.innerHTML = '';
  tables.forEach((t) => {
    const li = document.createElement('li');
    li.textContent = `#${t.id} ${t.title} [${t.status}] ${t.progress ?? 0}%`;
    li.onclick = () => openTable(t.id, t.title);
    tableList.appendChild(li);
  });

  if (currentTableId) {
    const cur = tables.find((x) => x.id === currentTableId);
    if (cur) {
      progressEl.textContent = `Статус: ${cur.status}, прогресс: ${cur.progress ?? 0}%`;
      if (cur.status === 'need_login') setYandexState('need_login', lastVncUrl);
      else if (cur.yandex_connected) setYandexState('ok');
      else setYandexState('idle');
    }
  }
}

async function openTable(id, title) {
  currentTableId = id;
  tableTitle.textContent = `Таблица: ${title} (#${id})`;
  tableView.classList.remove('hidden');
  await refreshMapping();
  await refreshExcelData();
}

function initTablesSection() {
  document.getElementById('closeMappingDialog').onclick = () => mappingDialog.close();

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
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) return alert(data.detail || 'Ошибка загрузки');
    await refreshMapping();
    await refreshExcelData();
  };

  document.getElementById('connectYandex').onclick = async () => {
    const resp = await fetch('/api/yandex/connect', { method: 'POST' });
    if (requireAuth(resp)) return;
    const data = await resp.json().catch(() => ({}));
    if (data.status === 'ok') setYandexState('ok');
    else if (data.status === 'need_login') setYandexState('need_login', data.vnc_url || null);
    else setYandexState('idle');
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
    lastVncUrl = vncUrl;
    window.open(vncUrl, 'yandex_vnc', 'width=520,height=720,menubar=no,toolbar=no,location=no,status=no,resizable=yes,scrollbars=no');
  };

  startDownloadBtn.onclick = async () => {
    if (!currentTableId) return alert('Сначала выберите таблицу');
    const resp = await fetch(`/api/tables/${currentTableId}/start-download`, { method: 'POST' });
    const data = await resp.json().catch(() => ({}));
    if (resp.status === 400 && data.status === 'need_login') {
      setYandexState('need_login', data.vnc_url || null);
      return;
    }
    if (requireAuth(resp)) return;
    if (!resp.ok) return alert(data.detail || 'Ошибка запуска');
    alert('Фоновая загрузка запущена');
  };

  refreshTables();
  setInterval(async () => {
    await refreshTables();
    await refreshMapping();
    await refreshExcelData();
  }, 4000);
}

document.addEventListener('DOMContentLoaded', initTablesSection);
