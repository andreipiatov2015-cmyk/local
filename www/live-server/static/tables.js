async function apiGet(url) {
  const r = await fetch(url, { credentials: 'same-origin' });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `HTTP ${r.status}`);
  return r.json();
}

async function apiPostForm(url, data) {
  const fd = new FormData();
  Object.entries(data).forEach(([k, v]) => fd.append(k, v));
  const r = await fetch(url, { method: 'POST', body: fd, credentials: 'same-origin' });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `HTTP ${r.status}`);
  return r.json();
}

async function apiPostJson(url, data) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    credentials: 'same-origin',
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `HTTP ${r.status}`);
  return r.json();
}

async function apiDelete(url) {
  const r = await fetch(url, { method: 'DELETE', credentials: 'same-origin' });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `HTTP ${r.status}`);
  return r.json();
}

function setStatus(el, text, kind = 'muted') {
  if (!el) return;
  el.textContent = text;
  el.className = `status status-${kind}`;
}

function esc(v) {
  return (v ?? '').toString().replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
}

function normalizeHeaderLikeBackend(value) {
  return (value || '').toString().trim().toLowerCase().replace(/\s+/g, ' ');
}

async function initListPage() {
  const listEl = document.getElementById('tableList');
  if (!listEl) return;
  const createBtn = document.getElementById('createTable');
  const statusEl = document.getElementById('listStatus');

  async function load() {
    const tables = await apiGet('/api/tables');
    if (!tables.length) {
      listEl.innerHTML = '<li class="table-item"><div class="hint">Пока нет таблиц.</div></li>';
      return;
    }
    listEl.innerHTML = '';
    tables.forEach((t) => {
      const li = document.createElement('li');
      li.className = 'table-item';
      li.innerHTML = `
        <div class="table-main">
          <strong>${esc(t.title)}</strong>
          <div class="hint">Создано: ${esc(t.created_at || '-')} · Изменено: ${esc(t.updated_at || '-')} · Статус: ${esc(t.status || 'new')}</div>
        </div>
        <div class="row wrap">
          <a class="btn btn-secondary" href="/tables/${t.id}">Открыть</a>
          <button class="btn btn-danger" data-del="${t.id}">Удалить</button>
        </div>
      `;
      listEl.appendChild(li);
    });

    listEl.querySelectorAll('[data-del]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        if (!confirm('Удалить таблицу?')) return;
        try {
          await apiDelete(`/api/tables/${btn.dataset.del}`);
          await load();
        } catch (e) {
          setStatus(statusEl, `Ошибка удаления: ${e.message}`, 'error');
        }
      });
    });
  }

  createBtn?.addEventListener('click', async () => {
    const title = prompt('Введите название таблицы', 'Новая таблица');
    if (!title) return;
    try {
      await apiPostForm('/api/tables', { title });
      setStatus(statusEl, 'Таблица создана.', 'success');
      await load();
    } catch (e) {
      setStatus(statusEl, `Ошибка создания: ${e.message}`, 'error');
    }
  });

  try {
    await load();
    setStatus(statusEl, 'Готово.', 'muted');
  } catch (e) {
    setStatus(statusEl, `Ошибка: ${e.message}`, 'error');
  }
}

async function initDetailPage() {
  const tableId = Number(document.body.dataset.tableId || 0);
  if (!tableId) return;

  const titleEl = document.getElementById('tableTitle');
  const uploadBtn = document.getElementById('uploadExcel');
  const fileEl = document.getElementById('excelFile');
  const uploadStatusEl = document.getElementById('uploadStatus');
  const mappingListEl = document.getElementById('mappingList');
  const mappingStatusEl = document.getElementById('mappingStatus');
  const saveMappingBtn = document.getElementById('saveMapping');
  const collapseConfiguredBtn = document.getElementById('collapseConfigured');
  const previewMetaEl = document.getElementById('previewMeta');
  const previewHeadEl = document.getElementById('previewHead');
  const previewBodyEl = document.getElementById('previewBody');

  let headers = [];
  let mapping = {};
  let collapsedMappingCards = {};
  let mappingFieldTags = [];

  function renderPreview(rows) {
    previewHeadEl.innerHTML = '';
    previewBodyEl.innerHTML = '';
    if (!headers.length) {
      previewMetaEl.textContent = 'Нет данных для предпросмотра.';
      return;
    }
    previewHeadEl.innerHTML = `<tr>${headers.map((h) => `<th>${esc(h)}</th>`).join('')}</tr>`;
    rows.forEach((row) => {
      const tr = document.createElement('tr');
      tr.innerHTML = headers.map((_, i) => `<td>${esc(row[i])}</td>`).join('');
      previewBodyEl.appendChild(tr);
    });
  }

  function isAutoDetectedMapping(tag, selectedHeader) {
    if (!selectedHeader || !headers.length) return false;
    const tagNorm = normalizeHeaderLikeBackend(tag);
    const normalizedHeaders = headers.map((h) => normalizeHeaderLikeBackend(h));
    const firstMatchedIndex = normalizedHeaders.findIndex((headerNorm) => {
      return tagNorm && (tagNorm.includes(headerNorm) || headerNorm.includes(tagNorm));
    });
    return firstMatchedIndex >= 0 && headers[firstMatchedIndex] === selectedHeader;
  }

  function renderMapping(fieldTags) {
    mappingListEl.innerHTML = '';
    mappingFieldTags = fieldTags;
    fieldTags.forEach((tag) => {
      const card = document.createElement('article');
      const current = mapping[tag] || '';
      const isMapped = Boolean(current);
      const isCollapsed = Boolean(collapsedMappingCards[tag] && isMapped);
      const isAutoDetected = isAutoDetectedMapping(tag, current);
      card.className = `mapping-card${isMapped ? ' is-mapped' : ''}${isAutoDetected ? ' is-auto' : ''}${isCollapsed ? ' is-collapsed' : ''}`;

      const body = document.createElement('div');
      body.className = 'mapping-card-body';

      const tagEl = document.createElement('span');
      tagEl.className = 'mapping-tag';
      tagEl.textContent = tag;

      const selectedValueEl = document.createElement('span');
      selectedValueEl.className = 'mapping-selected-value';
      selectedValueEl.textContent = current || 'не выбрано';

      const select = document.createElement('select');
      select.className = 'mapping-select';
      select.innerHTML = '<option value="">не выбрано</option>' + headers.map((h, i) => {
        const selected = current === h ? ' selected' : '';
        return `<option value="${esc(h)}"${selected}>${esc(h)} (колонка ${i + 1})</option>`;
      }).join('');
      select.addEventListener('change', () => {
        if (!select.value) delete mapping[tag];
        else mapping[tag] = select.value;
        if (!select.value) collapsedMappingCards[tag] = false;
        setStatus(mappingStatusEl, 'Есть несохранённые изменения.', 'warning');
        renderMapping(fieldTags);
      });

      const toggleBtn = document.createElement('button');
      toggleBtn.type = 'button';
      toggleBtn.className = 'mapping-toggle-btn';
      toggleBtn.title = isCollapsed ? 'Развернуть карточку' : 'Свернуть карточку';
      toggleBtn.textContent = isCollapsed ? '▼' : '▲';
      toggleBtn.addEventListener('click', () => {
        collapsedMappingCards[tag] = !collapsedMappingCards[tag];
        renderMapping(fieldTags);
      });

      if (isCollapsed) {
        body.appendChild(tagEl);
        body.appendChild(selectedValueEl);
      } else {
        body.appendChild(select);
        body.appendChild(tagEl);
      }

      card.appendChild(body);
      if (isMapped) card.appendChild(toggleBtn);
      mappingListEl.appendChild(card);
    });
  }

  async function reload() {
    const [table, preview, mapResp] = await Promise.all([
      apiGet(`/api/tables/${tableId}`),
      apiGet(`/api/tables/${tableId}/excel_preview`),
      apiGet(`/api/tables/${tableId}/mapping`),
    ]);
    titleEl.textContent = table.title || `Таблица #${tableId}`;
    headers = preview.headers || [];
    mapping = mapResp.mapping || {};
    renderPreview(preview.rows || []);
    renderMapping(mapResp.field_tags || []);
    previewMetaEl.textContent = `Показано ${preview.rows?.length || 0} из ${preview.total_rows || 0} строк`;
  }

  uploadBtn.addEventListener('click', async () => {
    const file = fileEl.files?.[0];
    if (!file) {
      setStatus(uploadStatusEl, 'Выберите файл Excel.', 'warning');
      return;
    }
    try {
      setStatus(uploadStatusEl, 'Загрузка...', 'muted');
      await apiPostForm(`/api/tables/${tableId}/excel`, { excel: file });
      setStatus(uploadStatusEl, 'Excel загружен.', 'success');
      await reload();
    } catch (e) {
      setStatus(uploadStatusEl, `Ошибка: ${e.message}`, 'error');
    }
  });

  saveMappingBtn.addEventListener('click', async () => {
    try {
      await apiPostJson(`/api/tables/${tableId}/mapping`, { mapping });
      setStatus(mappingStatusEl, 'Mapping сохранён.', 'success');
      await reload();
    } catch (e) {
      setStatus(mappingStatusEl, `Ошибка: ${e.message}`, 'error');
    }
  });

  collapseConfiguredBtn?.addEventListener('click', () => {
    mappingFieldTags.forEach((tag) => {
      if (mapping[tag]) collapsedMappingCards[tag] = true;
    });
    renderMapping(mappingFieldTags);
  });

  try {
    await reload();
  } catch (e) {
    setStatus(uploadStatusEl, `Ошибка загрузки данных: ${e.message}`, 'error');
  }
}

initListPage();
initDetailPage();
