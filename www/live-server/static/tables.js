let currentTableId = null;
let lastVncUrl = null;
let currentMapping = {};
let mappingFields = {};
let currentHeaders = [];
let currentYandexStatus = 'disconnected';
let currentProgramItems = [];
let isProgramMode = false;
let currentVisibleTags = [];
let currentRenderedTagMeta = [];
let draggedProgramItemId = null;

const FORCED_HIDDEN_TAG_PATTERNS = [/номер\s*телефон/i, /телефон/i, /e-?mail/i, /емаил/i, /email/i, /райдер/i, /rider/i];

const tableList = document.getElementById('tableList');
const workspaceEl = document.getElementById('workspace');
const progressEl = document.getElementById('progress');
const tableTitle = document.getElementById('tableTitle');
const yandexStatusEl = document.getElementById('yandexStatus');
const startDownloadBtn = document.getElementById('startDownload');
const finalizeTableBtn = document.getElementById('finalizeTable');
const openAdminLoginBtn = document.getElementById('openAdminLogin');
const yandexHintEl = document.getElementById('yandexHint');
const mappingAutofillInfoEl = document.getElementById('mappingAutofillInfo');
const tableView = document.getElementById('tableView');
const excelHead = document.getElementById('excelHead');
const excelBody = document.getElementById('excelBody');
const mappingInfo = document.getElementById('mappingInfo');
const mappingSummary = document.getElementById('mappingSummary');
const excelColgroup = document.getElementById('excelColgroup');
const resetMappingBtn = document.getElementById('resetMapping');
const rememberMappingBtn = document.getElementById('rememberMapping');
const mappingDialog = document.getElementById('mappingDialog');
const mappingDialogActions = document.getElementById('mappingDialogActions');
const previewErrorEl = document.getElementById('previewError');
const prepareModeEl = document.getElementById('prepareMode');
const programModeEl = document.getElementById('programMode');
const prepareControlsEl = document.getElementById('prepareControls');
const tablesContentEl = document.getElementById('tablesContent');
const programBody = document.getElementById('programBody');
const programSearch = document.getElementById('programSearch');
const filterNoAudio = document.getElementById('filterNoAudio');
const filterNoReceipt = document.getElementById('filterNoReceipt');
const filterNoPresentation = document.getElementById('filterNoPresentation');
const autosaveStatus = document.getElementById('autosaveStatus');
const downloadAllProgramBtn = document.getElementById('downloadAllProgram');
const receiptViewerDialog = document.getElementById('receiptViewerDialog');
const receiptViewerImage = document.getElementById('receiptViewerImage');
const receiptViewerDownload = document.getElementById('receiptViewerDownload');
const programHeadRow = document.getElementById('programHeadRow');
const backToTablesBtn = document.getElementById('backToTables');

const REQUIRED_FIELDS = ['number_title', 'audio_url', 'consent_url', 'presentation_url'];

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

function setAutosave(text) {
  autosaveStatus.textContent = text;
}

function setWorkspaceVisible(visible) {
  workspaceEl?.classList.toggle('hidden', !visible);
}

function setProgramMode(enabled) {
  isProgramMode = !!enabled;
  programModeEl.classList.toggle('hidden', !isProgramMode);
  document.querySelectorAll('.prepare-only').forEach((el) => {
    el.classList.toggle('hidden', isProgramMode);
  });
  if (prepareControlsEl) prepareControlsEl.classList.toggle('hidden', isProgramMode);
  finalizeTableBtn.classList.toggle('hidden', isProgramMode);
  tablesContentEl?.classList.toggle('program-only', isProgramMode);
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

function mappingIndexes(field) {
  const raw = (currentMapping || {})[field];
  if (Array.isArray(raw)) return raw.filter((v) => Number.isInteger(v) && v >= 0);
  if (Number.isInteger(raw) && raw >= 0) return [raw];
  return [];
}

function mappingReverse() {
  const rev = {};
  Object.entries(currentMapping || {}).forEach(([field]) => {
    mappingIndexes(field).forEach((col) => { rev[col] = field; });
  });
  return rev;
}

function getColumnWidthClass(header) {
  const normalized = String(header || '').toLowerCase();
  if (/^id$|№|номер/.test(normalized)) return 'col-id';
  if (/дата|date/.test(normalized)) return 'col-date';
  if (/территор|город|регион/.test(normalized)) return 'col-territory';
  if (/фио|участник|название|коллектив|комментар|описан|примечан/.test(normalized)) return 'col-long';
  return 'col-default';
}

function renderColgroup() {
  excelColgroup.innerHTML = '';
  currentHeaders.forEach((header) => {
    const col = document.createElement('col');
    col.className = getColumnWidthClass(header);
    excelColgroup.appendChild(col);
  });
}

function renderMappingPanel() {
  const requiredItems = REQUIRED_FIELDS.map((field) => {
    const cols = mappingIndexes(field);
    return {
      field,
      title: mappingFields[field] || field,
      assigned: cols.length > 0,
      cols
    };
  });
  const assignedCount = Object.values(currentMapping || {}).reduce((acc, value) => {
    if (Array.isArray(value)) return acc + value.length;
    return Number.isInteger(value) ? acc + 1 : acc;
  }, 0);
  const totalCount = Object.keys(mappingFields).length;

  mappingSummary.textContent = `Схема: ${assignedCount} колонок / ${totalCount} тегов`;

  mappingInfo.innerHTML = requiredItems.map((item) => {
    const colName = item.assigned
      ? item.cols.map((col) => currentHeaders[col] || `Колонка ${col + 1}`).join(', ')
      : 'не назначено';
    return `<div class="mapping-row ${item.assigned ? 'ok' : 'missing'}"><span>${item.assigned ? '✅' : '⭕'} ${item.title}</span><span>${colName}</span></div>`;
  }).join('');
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
  renderColgroup();

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
  if (!currentTableId || isProgramMode) return;
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
  const currentFieldForCol = Object.entries(currentMapping).find(([field]) => mappingIndexes(field).includes(colIndex))?.[0];
  mappingDialogActions.innerHTML = '';

  Object.entries(mappingFields).forEach(([field, title]) => {
    const assignedCols = mappingIndexes(field);
    const assignedToAnother = assignedCols.length > 0 && !assignedCols.includes(colIndex);
    const btn = document.createElement('button');
    btn.className = `btn btn-secondary mapping-choice ${assignedToAnother ? 'is-occupied' : ''}`;
    btn.innerHTML = assignedToAnother
      ? `<span>${title}</span><small>уже назначено: ${assignedCols.map((c) => currentHeaders[c] || `Колонка ${c + 1}`).join(', ')}</small>`
      : `<span>${title}</span><small>${assignedCols.includes(colIndex) ? 'уже на этой колонке' : 'свободно'}</small>`;

    btn.onclick = async () => {
      if (currentFieldForCol && currentFieldForCol !== field) {
        const prev = mappingIndexes(currentFieldForCol).filter((c) => c !== colIndex);
        if (prev.length) currentMapping[currentFieldForCol] = prev;
        else delete currentMapping[currentFieldForCol];
      }
      const updated = [...assignedCols.filter((c) => c !== colIndex), colIndex].sort((a, b) => a - b);
      currentMapping[field] = updated.length === 1 ? updated[0] : updated;
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
      const updated = mappingIndexes(k).filter((c) => c !== colIndex);
      if (updated.length === mappingIndexes(k).length) return;
      if (!updated.length) delete currentMapping[k];
      else currentMapping[k] = updated.length === 1 ? updated[0] : updated;
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
  if ((status === 'auth_required' || status === 'paused' || status === 'downloading_partial') && (t.download_cursor_row_id || 0) > 0) {
    return `Скачивание остановлено на строке ${t.download_cursor_row_id}. Требуется повторное подключение Яндекса.`;
  }
  const error = t.last_error ? `, ошибка: ${t.last_error}` : '';
  return `Статус: ${status}, прогресс: ${progress}% (${processed}/${total})${error}`;
}

async function refreshTables() {
  const r = await fetch('/api/tables');
  if (requireAuth(r)) return;
  const tables = await r.json();
  tableList.innerHTML = '';
  tables.forEach((t) => {
    const li = document.createElement('li');
    li.className = 'table-list-item';

    const openBtn = document.createElement('button');
    openBtn.type = 'button';
    openBtn.className = 'table-open-btn';
    openBtn.textContent = `#${t.id} ${t.title} [${t.status}] ${t.progress ?? 0}% (${t.processed_count ?? 0}/${t.total_count ?? 0})`;
    openBtn.onclick = () => openTable(t.id, t.title);

    const delBtn = document.createElement('button');
    delBtn.type = 'button';
    delBtn.className = 'table-delete-btn';
    delBtn.title = 'Удалить таблицу';
    delBtn.setAttribute('aria-label', `Удалить таблицу ${t.title}`);
    delBtn.textContent = '×';
    delBtn.onclick = async (event) => {
      event.preventDefault();
      event.stopPropagation();
      await deleteTableById(t.id);
    };

    li.appendChild(openBtn);
    li.appendChild(delBtn);
    tableList.appendChild(li);
  });

  if (currentTableId) {
    const cur = tables.find((x) => x.id === currentTableId);
    if (cur) {
      progressEl.textContent = formatProgressText(cur);
      setYandexState(cur.yandex_status || 'disconnected', cur.yandex_last_error || '', lastVncUrl);
      const resumeStatuses = new Set(['auth_required', 'paused', 'downloading_partial']);
      const isResumeReady = resumeStatuses.has(cur.status || '');
      startDownloadBtn.textContent = isResumeReady ? 'Продолжить скачивание' : 'Старт скачивания';
      finalizeTableBtn.classList.toggle('hidden', Number(cur.is_finalized || 0) === 1);
      if (Number(cur.is_finalized || 0) === 1 && !isProgramMode) {
        await loadProgram();
      }
    }
  }
}


async function deleteTableById(tableId) {
  const ok = confirm('Удалить таблицу? Это действие удалит таблицу, программу выступлений и связанные файлы.');
  if (!ok) return;

  const resp = await fetch(`/api/tables/${tableId}`, { method: 'DELETE' });
  if (requireAuth(resp)) return;
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    alert(data.detail || 'Не удалось удалить таблицу');
    return;
  }

  if (currentTableId === tableId) {
    currentTableId = null;
    tableView.classList.add('hidden');
    setProgramMode(false);
    setWorkspaceVisible(true);
  }

  await refreshTables();
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

function filteredProgramItems() {
  const q = (programSearch.value || '').toLowerCase().trim();
  return currentProgramItems.filter((item) => {
    if (item.kind === 'break') return true;
    const audioCell = (item.cells || []).find((c) => c.key === 'audio_url');
    const consentCell = (item.cells || []).find((c) => c.key === 'consent_url');
    const presentationCell = (item.cells || []).find((c) => c.key === 'presentation_url');
    const hasAudio = !!(audioCell && (audioCell.files || []).length);
    const hasConsent = !!(consentCell && ((consentCell.files || []).length || (consentCell.links || []).length));
    const hasPresentation = !!(presentationCell && ((presentationCell.files || []).length || (presentationCell.links || []).length));
    if (filterNoAudio.checked && hasAudio) return false;
    if (filterNoReceipt.checked && hasConsent) return false;
    if (filterNoPresentation.checked && hasPresentation) return false;
    if (!q) return true;
    const hay = `${item.display_number || ''} ${item.number_title || ''} ${item.fio || ''} ${item.team || ''}`.toLowerCase();
    return hay.includes(q);
  });
}

function renderProgramHead() {
  if (!programHeadRow) return;
  programHeadRow.innerHTML = '<th>№</th><th>↕</th><th>Название</th><th>ФИО</th><th>Коллектив</th>';
  (currentRenderedTagMeta || []).forEach(({ tag }) => {
    const th = document.createElement('th');
    th.textContent = tag.label || tag.key;
    programHeadRow.appendChild(th);
  });
}

function isTagForceHidden(tag) {
  const hay = `${tag?.label || ''} ${tag?.key || ''}`.toLowerCase();
  return FORCED_HIDDEN_TAG_PATTERNS.some((rx) => rx.test(hay));
}

function isCellFilled(cell) {
  if (!cell) return false;
  if ((cell.value || '').toString().trim()) return true;
  if ((cell.values || []).some((v) => String(v || '').trim())) return true;
  if ((cell.files || []).length) return true;
  if ((cell.links || []).length) return true;
  if (cell.conflict?.selected) return true;
  return false;
}

function rebuildVisibleProgramTags(items = currentProgramItems, tags = currentVisibleTags) {
  currentRenderedTagMeta = (tags || [])
    .map((tag, index) => ({ tag, index }))
    .filter(({ tag, index }) => {
      if (isTagForceHidden(tag)) return false;
      return (items || []).some((item) => item.kind === 'entry' && isCellFilled((item.cells || [])[index]));
    });
}

function fillTextCell(td, text) {
  const span = document.createElement('span');
  span.className = 'clamp-content';
  span.textContent = text || '';
  td.classList.add('clamp-cell');
  td.appendChild(span);
}

async function resolveGroupedConflict(entryId, field, value) {
  const resp = await fetch(`/api/tables/${currentTableId}/entries/${entryId}/resolve`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ field, value })
  });
  if (!resp.ok) return;
  const data = await resp.json().catch(() => ({}));
  const target = currentProgramItems.find((x) => x.entry_id === entryId);
  if (target) target.resolved_fields = data.resolved_fields || {};
}

function renderTagCell(td, item, cell) {
  if (!cell) return;
  if (cell.type === 'grouped_choice') {
    if (cell.conflict && (cell.conflict.options || []).length) {
      const select = document.createElement('select');
      select.innerHTML = '<option value="">Выбрать</option>' + (cell.conflict.options || []).map((v) => `<option value="${v}">${v}</option>`).join('');
      if (cell.conflict.selected) select.value = cell.conflict.selected;
      select.onchange = async () => {
        await resolveGroupedConflict(item.entry_id, cell.key, select.value);
      };
      td.appendChild(select);
    } else {
      fillTextCell(td, cell.value || '');
    }
    return;
  }

  if (cell.type === 'links') {
    (cell.links || []).forEach((link, i) => {
      const a = document.createElement('a');
      a.href = link.url;
      a.target = '_blank';
      a.rel = 'noopener';
      a.textContent = link.title || `Ссылка ${i + 1}`;
      if (i > 0) td.appendChild(document.createElement('br'));
      td.appendChild(a);
    });
    return;
  }

  if (cell.type === 'files' || cell.type === 'files_or_links') {
    const files = cell.files || [];
    files.forEach((f, i) => {
      if (i > 0) td.appendChild(document.createElement('br'));
      if (f.download_url) {
        const a = document.createElement('a');
        a.className = 'btn btn-secondary';
        a.href = f.download_url;
        a.textContent = cell.key === 'audio_url' ? 'Скачать' : 'Открыть';
        td.appendChild(a);
      } else {
        td.appendChild(document.createTextNode(f.name || 'Файл'));
      }
    });
    if (cell.type === 'files_or_links') {
      (cell.links || []).forEach((link, i) => {
        if (files.length || i > 0) td.appendChild(document.createElement('br'));
        const a = document.createElement('a');
        a.href = link.url;
        a.target = '_blank';
        a.rel = 'noopener';
        a.textContent = link.title || `Ссылка ${i + 1}`;
        td.appendChild(a);
      });
    }
    return;
  }

  fillTextCell(td, cell.value || (cell.values || []).join(', '));
}

function renderProgram() {
  programBody.innerHTML = '';
  const items = filteredProgramItems();
  items.forEach((item, idx) => {
    const tr = document.createElement('tr');
    tr.dataset.itemId = String(item.program_item_id);

    if (item.kind === 'break') {
      tr.className = 'program-break-row';
      tr.innerHTML = `<td></td><td>≡</td><td colspan="${5 + (currentRenderedTagMeta || []).length}"><div class="program-break-cell"><span>${item.label}</span><button class="btn btn-secondary btn-inline">Удалить</button></div></td>`;
      tr.querySelector('button').onclick = () => deleteBreak(item.program_item_id);
    } else {
      tr.className = `program-entry-row ${item.is_problematic ? 'program-problem-row' : ''}`.trim();
      tr.draggable = true;
      tr.ondragstart = () => { draggedProgramItemId = item.program_item_id; };
      tr.ondragover = (e) => e.preventDefault();
      tr.ondrop = async () => {
        if (!draggedProgramItemId || draggedProgramItemId === item.program_item_id) return;
        await reorderByDrop(draggedProgramItemId, item.program_item_id);
      };

      const no = document.createElement('td');
      no.textContent = String(item.display_number || '');
      no.className = 'clickable-number';
      no.onclick = async () => {
        const v = prompt('Введите новую позицию', String(item.display_number || ''));
        if (!v) return;
        setAutosave('Сохраняю…');
        const resp = await fetch(`/api/tables/${currentTableId}/program/item/${item.program_item_id}/move_to_position`, {
          method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ position: Number(v) })
        });
        if (requireAuth(resp)) return;
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) return alert(data.detail || 'Не удалось переместить');
        currentProgramItems = data.items || [];
        renderProgram();
        setAutosave('Изменения сохранены');
      };

      tr.appendChild(no);
      tr.innerHTML += '<td class="drag-handle">≡</td>';
      const titleTd = document.createElement('td');
      const fioTd = document.createElement('td');
      const teamTd = document.createElement('td');
      fillTextCell(titleTd, item.number_title || '');
      fillTextCell(fioTd, item.fio || '');
      fillTextCell(teamTd, item.team || '');
      tr.appendChild(titleTd);
      tr.appendChild(fioTd);
      tr.appendChild(teamTd);

      (currentRenderedTagMeta || []).forEach(({ index }) => {
        const cell = (item.cells || [])[index];
        const td = document.createElement('td');
        renderTagCell(td, item, cell);
        tr.appendChild(td);
      });

      tr.onclick = (event) => {
        if (event.target.closest('a, button, select, input, label')) return;
        tr.classList.toggle('is-expanded');
      };
    }

    programBody.appendChild(tr);
    if (item.kind === 'entry' && idx < items.length - 1) {
      const plusRow = document.createElement('tr');
      plusRow.className = 'program-insert-row';
      plusRow.innerHTML = `<td colspan="${5 + (currentRenderedTagMeta || []).length}"><button class="insert-break-btn">+ добавить перерыв здесь</button></td>`;
      const nextItem = items.slice(idx + 1).find((x) => x.kind === 'entry');
      plusRow.querySelector('button').onclick = () => addBreakAfter(item.program_item_id, nextItem ? nextItem.program_item_id : null);
      programBody.appendChild(plusRow);
    }
  });
}


async function reorderByDrop(fromId, toId) {
  setAutosave('Сохраняю…');
  const ids = currentProgramItems.map((x) => x.program_item_id);
  const fromIndex = ids.indexOf(fromId);
  const toIndex = ids.indexOf(toId);
  if (fromIndex < 0 || toIndex < 0) return;
  ids.splice(fromIndex, 1);
  ids.splice(toIndex, 0, fromId);
  const resp = await fetch(`/api/tables/${currentTableId}/program/reorder`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ program_item_ids: ids })
  });
  if (requireAuth(resp)) return;
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) return alert(data.detail || 'Ошибка reorder');
  currentProgramItems = data.items || [];
  renderProgram();
  setAutosave('Изменения сохранены');
}

async function addBreakAfter(afterItemId, beforeItemId = null) {
  const mins = Number(prompt('Перерыв в минутах', '10'));
  if (!mins) return;
  setAutosave('Сохраняю…');
  const resp = await fetch(`/api/tables/${currentTableId}/program/break`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ after_item_id: afterItemId, before_item_id: beforeItemId, break_minutes: mins })
  });
  if (requireAuth(resp)) return;
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) return alert(data.detail || 'Ошибка добавления перерыва');
  currentProgramItems = data.items || [];
  renderProgram();
  setAutosave('Изменения сохранены');
}

async function deleteBreak(itemId) {
  if (!confirm('Удалить перерыв?')) return;
  setAutosave('Сохраняю…');
  const resp = await fetch(`/api/tables/${currentTableId}/program/item/${itemId}`, { method: 'DELETE' });
  if (requireAuth(resp)) return;
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) return alert(data.detail || 'Ошибка удаления');
  currentProgramItems = data.items || [];
  renderProgram();
  setAutosave('Изменения сохранены');
}

async function loadProgram() {
  if (!currentTableId) return;
  const resp = await fetch(`/api/tables/${currentTableId}/program`);
  if (requireAuth(resp)) return;
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) return;
  if (!data.is_finalized) {
    setProgramMode(false);
    return;
  }
  setProgramMode(true);
  currentProgramItems = data.items || [];
  currentVisibleTags = data.visible_tags || [];
  rebuildVisibleProgramTags(currentProgramItems, currentVisibleTags);
  renderProgramHead();
  renderProgram();
}

async function openTable(id, title) {
  currentTableId = id;
  tableTitle.textContent = `Таблица: ${title} (#${id})`;
  tableView.classList.remove('hidden');
  setWorkspaceVisible(false);
  showAutofillInfo('');
  await refreshTables();
  await loadProgram();
  if (!isProgramMode) {
    await refreshMapping();
    await loadExcelPreview();
  }
}

function initTablesSection() {
  document.getElementById('closeMappingDialog').onclick = () => mappingDialog.close();
  document.getElementById('closeReceiptViewer').onclick = () => receiptViewerDialog.close();
  if (backToTablesBtn) {
    backToTablesBtn.onclick = () => {
      currentTableId = null;
      tableView.classList.add('hidden');
      setProgramMode(false);
      setWorkspaceVisible(true);
      refreshTables();
    };
  }

  [programSearch, filterNoAudio, filterNoReceipt, filterNoPresentation].forEach((el) => {
    el.addEventListener('input', renderProgram);
    el.addEventListener('change', renderProgram);
  });

  downloadAllProgramBtn.onclick = () => {
    if (!currentTableId) return;
    window.location.href = `/api/tables/${currentTableId}/program/download_all`;
  };

  finalizeTableBtn.onclick = async () => {
    if (!currentTableId) return alert('Сначала выберите таблицу');
    setAutosave('Сохраняю…');
    const resp = await fetch(`/api/tables/${currentTableId}/finalize`, { method: 'POST' });
    if (requireAuth(resp)) return;
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) return alert(data.detail || 'Не удалось сформировать программу');
    await loadProgram();
    setAutosave('Изменения сохранены');
    await refreshTables();
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
    alert(data.mode === 'resume' ? 'Продолжение скачивания запущено' : 'Фоновая загрузка запущена');
  };

  renderMappingPanel();
  setWorkspaceVisible(true);
  refreshTables();
  setYandexState('disconnected');
  setInterval(async () => {
    await refreshTables();
    await refreshMapping();
    if (isProgramMode) await loadProgram();
  }, 6000);
}

document.addEventListener('DOMContentLoaded', initTablesSection);
