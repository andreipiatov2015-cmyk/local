let currentTableId = null;
let lastVncUrl = null;
let currentMapping = {};
let mappingFields = {};
let currentHeaders = [];
let currentYandexStatus = 'disconnected';
let mappingPanelExpanded = false;

const tableList = document.getElementById('tableList');
const progressEl = document.getElementById('progress');
const tableTitle = document.getElementById('tableTitle');
const yandexStatusEl = document.getElementById('yandexStatus');
const startDownloadBtn = document.getElementById('startDownload');
const openAdminLoginBtn = document.getElementById('openAdminLogin');
const yandexHintEl = document.getElementById('yandexHint');
const mappingAutofillInfoEl = document.getElementById('mappingAutofillInfo');
const tableView = document.getElementById('tableView');
const excelHead = document.getElementById('excelHead');
const excelBody = document.getElementById('excelBody');
const mappingInfo = document.getElementById('mappingInfo');
const mappingCompact = document.getElementById('mappingCompact');
const mappingExpanded = document.getElementById('mappingExpanded');
const mappingPanel = document.getElementById('mappingPanel');
const toggleMappingPanelBtn = document.getElementById('toggleMappingPanel');
const resetMappingBtn = document.getElementById('resetMapping');
const rememberMappingBtn = document.getElementById('rememberMapping');
const mappingDialog = document.getElementById('mappingDialog');
const mappingDialogActions = document.getElementById('mappingDialogActions');
const previewErrorEl = document.getElementById('previewError');

const REQUIRED_FIELDS = ['number_title', 'participant_fio', 'audio_url', 'receipt_url', 'receipt_payer', 'presentation_url'];

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

function setYandexState(status, errText = '', vncUrl = null) {
  currentYandexStatus = status || 'disconnected';
  yandexStatusEl.className = 'status-badge';

  if (currentYandexStatus === 'connected') {
    yandexStatusEl.classList.add('status-badge--ok');
    yandexStatusEl.textContent = 'Яндекс подключен ✅';
    yandexHintEl.textContent = '';
    openAdminLoginBtn.classList.add('hidden');
    return;
  }

  if (currentYandexStatus === 'auth_required') {
    yandexStatusEl.classList.add('status-badge--warn');
    yandexStatusEl.textContent = 'Яндекс: требуется авторизация';
    yandexHintEl.textContent = errText || 'Откройте вход администратора (VNC) и выполните вход в Яндекс.';
    if (vncUrl) lastVncUrl = vncUrl;
    openAdminLoginBtn.classList.remove('hidden');
    return;
  }

  yandexStatusEl.classList.add('status-badge--muted');
  yandexStatusEl.textContent = 'Яндекс: не подключен';
  yandexHintEl.textContent = errText || '';
  openAdminLoginBtn.classList.add('hidden');
}

function showAutofillInfo(text) {
  if (!text) {
    mappingAutofillInfoEl.textContent = '';
    mappingAutofillInfoEl.classList.add('hidden');
    return;
  }
  mappingAutofillInfoEl.textContent = text;
  mappingAutofillInfoEl.classList.remove('hidden');
}

function mappingReverse() {
  const rev = {};
  Object.entries(currentMapping || {}).forEach(([field, col]) => { rev[col] = field; });
  return rev;
}

function renderMappingPanel() {
  const requiredItems = REQUIRED_FIELDS.map((field) => ({
    field,
    title: mappingFields[field] || field,
    assigned: currentMapping[field] !== undefined,
    col: currentMapping[field]
  }));
  const assignedCount = Object.keys(currentMapping).length;
  const totalCount = Object.keys(mappingFields).length;

  mappingCompact.innerHTML = `
    <div class="mapping-progress">Готово: ${assignedCount} / ${totalCount}</div>
    <div class="mapping-required-mini">
      ${requiredItems.map((item) => `<span title="${item.title}">${item.assigned ? '✅' : '⭕'} ${item.title}</span>`).join('')}
    </div>
  `;

  mappingInfo.innerHTML = requiredItems.map((item) => {
    const colName = item.assigned ? (currentHeaders[item.col] || `Колонка ${item.col + 1}`) : 'не назначено';
    return `<div class="mapping-row ${item.assigned ? 'ok' : 'missing'}"><span>${item.assigned ? '✅' : '⭕'} ${item.title}</span><span>${colName}</span></div>`;
  }).join('');

  mappingExpanded.classList.toggle('hidden', !mappingPanelExpanded);
  mappingPanel.classList.toggle('is-collapsed', !mappingPanelExpanded);
  toggleMappingPanelBtn.textContent = mappingPanelExpanded ? 'Свернуть схему' : 'Схема колонок';
}

function showPreviewError(msg) {
  previewErrorEl.textContent = msg;
  previewErrorEl.classList.remove('hidden');
}

function clearPreviewError() {
  previewErrorEl.textContent = '';
  previewErrorEl.classList.add('hidden');
}

function renderExcelTable(rows) {
  const rev = mappingReverse();
  excelHead.innerHTML = '';
  excelBody.innerHTML = '';

  if (!currentHeaders.length) {
    showPreviewError('Excel не распознан: не найдены заголовки или пустой файл.');
    renderMappingPanel();
    return;
  }

  const trh = document.createElement('tr');
  currentHeaders.forEach((h, idx) => {
    const th = document.createElement('th');
    const assignedField = rev[idx];
    const title = h || `Колонка ${idx + 1}`;
    th.dataset.col = String(idx);
    th.className = assignedField ? 'mapped' : '';

    const name = document.createElement('span');
    name.className = 'header-title';
    name.textContent = title;
    th.appendChild(name);

    if (assignedField) {
      const badge = document.createElement('span');
      badge.className = 'header-badge';
      badge.textContent = mappingFields[assignedField] || assignedField;
      th.appendChild(badge);
      th.title = `Назначено: ${mappingFields[assignedField] || assignedField}`;
    }

    th.onclick = () => openMappingDialog(idx);
    trh.appendChild(th);
  });
  excelHead.appendChild(trh);

  rows.forEach((row) => {
    const tr = document.createElement('tr');
    currentHeaders.forEach((_, idx) => {
      const td = document.createElement('td');
      td.textContent = row[idx] || '';
      tr.appendChild(td);
    });
    excelBody.appendChild(tr);
  });

  if (!rows.length) {
    showPreviewError('Excel не распознан / пустой файл / не найден лист с данными.');
  } else {
    clearPreviewError();
  }

  renderMappingPanel();
}

async function loadExcelPreview() {
  if (!currentTableId) return;
  const tableId = currentTableId;
  const resp = await fetch(`/api/tables/${tableId}/excel_preview`);
  if (requireAuth(resp)) return;
  const data = await resp.json().catch(() => ({}));
  if (tableId !== currentTableId) return;
  if (!resp.ok) {
    showPreviewError(data.detail || 'Не удалось загрузить предпросмотр Excel.');
    return;
  }

  currentHeaders = data.headers || [];
  mappingFields = data.mapping_fields || mappingFields;
  renderExcelTable(data.rows || []);
}

async function refreshMapping() {
  if (!currentTableId) return;
  const tableId = currentTableId;
  const r = await fetch(`/api/tables/${tableId}/mapping`);
  if (requireAuth(r) || !r.ok) return;
  const data = await r.json();
  if (tableId !== currentTableId) return;
  currentMapping = data.mapping || {};
  mappingFields = data.mapping_fields || mappingFields;
  startDownloadBtn.disabled = !data.can_start;
  startDownloadBtn.title = data.can_start ? '' : data.reason;
  renderMappingPanel();
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
  await loadExcelPreview();
  renderMappingPanel();
}

function openMappingDialog(colIndex) {
  const currentFieldForCol = Object.entries(currentMapping).find(([, c]) => c === colIndex)?.[0];
  mappingDialogActions.innerHTML = '';

  Object.entries(mappingFields).forEach(([field, title]) => {
    const assignedCol = currentMapping[field];
    const assignedToAnother = assignedCol !== undefined && assignedCol !== colIndex;
    const btn = document.createElement('button');
    btn.className = `btn btn-secondary mapping-choice ${assignedToAnother ? 'is-occupied' : ''}`;
    btn.innerHTML = assignedToAnother
      ? `<span>${title}</span><small>уже назначено: ${currentHeaders[assignedCol] || `Колонка ${assignedCol + 1}`}</small>`
      : `<span>${title}</span><small>${assignedCol === colIndex ? 'уже на этой колонке' : 'свободно'}</small>`;

    btn.onclick = async () => {
      if (currentFieldForCol) delete currentMapping[currentFieldForCol];
      if (assignedToAnother) delete currentMapping[field];
      currentMapping[field] = colIndex;
      await saveMapping();
      showAutofillInfo('Схема обновлена вручную. Можно нажать «Запомнить схему».');
      mappingDialog.close();
    };
    mappingDialogActions.appendChild(btn);
  });

  const clearBtn = document.createElement('button');
  clearBtn.className = 'btn btn-secondary';
  clearBtn.textContent = 'Снять назначение';
  clearBtn.onclick = async () => {
    Object.keys(currentMapping).forEach((k) => {
      if (currentMapping[k] === colIndex) delete currentMapping[k];
    });
    await saveMapping();
    showAutofillInfo('Схема обновлена вручную. Можно нажать «Запомнить схему».');
    mappingDialog.close();
  };
  mappingDialogActions.appendChild(clearBtn);
  mappingDialog.showModal();
}

function formatProgressText(t) {
  const status = t.status || 'new';
  const progress = t.progress ?? 0;
  const processed = t.processed_count ?? 0;
  const total = t.total_count ?? 0;
  const error = t.status === 'error' && t.last_error ? `, ошибка: ${t.last_error}` : '';
  return `Статус: ${status}, прогресс: ${progress}% (${processed}/${total})${error}`;
}

async function refreshTables() {
  const r = await fetch('/api/tables');
  if (requireAuth(r)) return;
  const tables = await r.json();
  tableList.innerHTML = '';
  tables.forEach((t) => {
    const li = document.createElement('li');
    li.textContent = `#${t.id} ${t.title} [${t.status}] ${t.progress ?? 0}% (${t.processed_count ?? 0}/${t.total_count ?? 0})`;
    li.onclick = () => openTable(t.id, t.title);
    tableList.appendChild(li);
  });

  if (currentTableId) {
    const cur = tables.find((x) => x.id === currentTableId);
    if (cur) {
      progressEl.textContent = formatProgressText(cur);
      setYandexState(cur.yandex_status || 'disconnected', cur.yandex_last_error || '', lastVncUrl);
    }
  }
}



async function refreshYandexSession(tableId, openVncOnFail = false) {
  const resp = await fetch(`/api/tables/${tableId}/yandex/refresh`, { method: 'POST' });
  if (requireAuth(resp)) return { ok: false, needLogin: false };
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    alert(data.detail || 'Не удалось обновить Яндекс-сессию');
    return { ok: false, needLogin: false };
  }

  if (data.status === 'ok') {
    setYandexState('connected', '', data.vnc_url || null);
    await refreshTables();
    return { ok: true, needLogin: false };
  }

  setYandexState('auth_required', 'Требуется вход администратора', data.vnc_url || null);
  await refreshTables();
  if (openVncOnFail && (data.vnc_url || lastVncUrl)) {
    const vncUrl = data.vnc_url || lastVncUrl;
    lastVncUrl = vncUrl;
    window.open(vncUrl, 'yandex_vnc', 'width=520,height=720,menubar=no,toolbar=no,location=no,status=no,resizable=yes,scrollbars=no');
  }
  return { ok: false, needLogin: true };
}

async function openTable(id, title) {
  currentTableId = id;
  tableTitle.textContent = `Таблица: ${title} (#${id})`;
  tableView.classList.remove('hidden');
  showAutofillInfo('');
  await refreshMapping();
  await loadExcelPreview();
  await refreshTables();
}

function initTablesSection() {
  document.getElementById('closeMappingDialog').onclick = () => mappingDialog.close();

  toggleMappingPanelBtn.onclick = () => {
    mappingPanelExpanded = !mappingPanelExpanded;
    renderMappingPanel();
  };

  resetMappingBtn.onclick = async () => {
    currentMapping = {};
    await saveMapping();
    await refreshMapping();
    showAutofillInfo('Схема сброшена. Назначьте колонки и запомните схему заново.');
  };

  rememberMappingBtn.onclick = async () => {
    if (!currentTableId) return alert('Сначала выберите таблицу');
    const resp = await fetch(`/api/tables/${currentTableId}/mapping/remember`, { method: 'POST' });
    if (requireAuth(resp)) return;
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) return alert(data.detail || 'Не удалось запомнить схему');
    showAutofillInfo(`Схема сохранена. Запомнено полей: ${data.saved_fields}.`);
  };

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
    if (!resp.ok) {
      showPreviewError(data.detail || 'Ошибка загрузки Excel');
      return;
    }
    clearPreviewError();
    if (data.mapping_autofilled) {
      const sourceText = data.mapping_autofill_source === 'template' ? 'из сохранённого шаблона' : 'по памяти/эвристикам';
      showAutofillInfo(`Сопоставление автозаполнено ${sourceText}. Проверьте и при необходимости скорректируйте.`);
    } else {
      showAutofillInfo('Автосопоставление не найдено. Назначьте колонки вручную.');
    }
    await loadExcelPreview();
    await refreshMapping();
    await refreshTables();
  };

  document.getElementById('connectYandex').onclick = async () => {
    if (!currentTableId) return alert('Сначала выберите таблицу');
    await refreshYandexSession(currentTableId, true);
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
      setYandexState('auth_required', data.detail || '', data.vnc_url || null);
      return;
    }
    if (requireAuth(resp)) return;
    if (!resp.ok) return alert(data.detail || 'Ошибка запуска');
    await refreshTables();
    alert('Фоновая загрузка запущена');
  };

  renderMappingPanel();
  refreshTables();
  setYandexState('disconnected');
  setInterval(async () => {
    await refreshTables();
    await refreshMapping();
  }, 4000);
}

document.addEventListener('DOMContentLoaded', initTablesSection);
