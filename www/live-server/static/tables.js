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
  let isCreatingDraft = false;

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

  function removeDraftCard() {
    const draft = listEl.querySelector('.table-item.is-creating');
    if (draft) draft.remove();
    if (!listEl.children.length) {
      listEl.innerHTML = '<li class="table-item"><div class="hint">Пока нет таблиц.</div></li>';
    }
    isCreatingDraft = false;
  }

  async function saveDraftTitle(inputEl, saveBtn) {
    const title = (inputEl?.value || '').trim();
    if (!title) {
      setStatus(statusEl, 'Введите название таблицы.', 'warning');
      inputEl?.focus();
      return;
    }
    try {
      saveBtn.disabled = true;
      await apiPostForm('/api/tables', { title });
      setStatus(statusEl, 'Таблица создана.', 'success');
      removeDraftCard();
      await load();
    } catch (e) {
      setStatus(statusEl, `Ошибка создания: ${e.message}`, 'error');
    } finally {
      saveBtn.disabled = false;
    }
  }

  function renderCreateDraftCard() {
    if (isCreatingDraft) return;
    isCreatingDraft = true;
    const emptyStub = listEl.querySelector('.table-item .hint');
    if (emptyStub) listEl.innerHTML = '';

    const li = document.createElement('li');
    li.className = 'table-item is-creating';
    li.innerHTML = `
      <div class="table-main">
        <label class="hint" for="newTableTitleInput">Название новой таблицы</label>
        <div class="new-table-controls">
          <input id="newTableTitleInput" class="new-table-input" type="text" placeholder="Введите название таблицы" maxlength="120" />
          <button id="saveNewTable" class="btn btn-primary" type="button">Сохранить</button>
        </div>
        <div class="hint">Нажмите Enter или кнопку «Сохранить».</div>
      </div>
      <div class="row wrap">
        <button id="cancelNewTable" class="btn btn-secondary" type="button">Отмена</button>
      </div>
    `;
    listEl.prepend(li);
    const inputEl = li.querySelector('#newTableTitleInput');
    const saveBtn = li.querySelector('#saveNewTable');
    const cancelBtn = li.querySelector('#cancelNewTable');

    inputEl?.focus();
    inputEl?.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter') return;
      event.preventDefault();
      saveDraftTitle(inputEl, saveBtn);
    });
    saveBtn?.addEventListener('click', () => saveDraftTitle(inputEl, saveBtn));
    cancelBtn?.addEventListener('click', removeDraftCard);
  }

  createBtn?.addEventListener('click', () => {
    renderCreateDraftCard();
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
  const previewCardsEl = document.getElementById('previewCards');

  let headers = [];
  let mappingByTag = {};
  let collapsedMappingCards = {};
  let mappingFieldTags = [];
  let previewRowsData = [];
  let rowOrder = [];
  const expandedRows = {};

  const coreColumnDefs = [
    { key: 'territory', title: 'Территория', tags: ['Муниципалитет', 'Территория'], headers: ['Муниципалитет', 'Территория', 'Округ'] },
    { key: 'fio', title: 'ФИО участников', tags: ['ФИО участника', 'Список участников'], headers: ['ФИО участника', 'Список участников', 'ФИО'] },
    { key: 'nomination', title: 'Номинация', tags: ['Номинация'], headers: ['Номинация'] },
    { key: 'numberTitle', title: 'Название номера', tags: ['Название номера'], headers: ['Название номера'] },
    { key: 'phonograms', title: 'Фонограммы', tags: ['Фонограмма'], headers: ['Фонограмма'] },
    { key: 'presentationVideo', title: 'Презентации / видео', tags: ['Презентация', 'Видео', 'Ссылки'], headers: ['Презентация', 'Видео', 'Ссылка', 'Ссылки'] },
    { key: 'consents', title: 'Согласия', tags: ['Согласие / квитки'], headers: ['Согласие', 'Квитки', 'Согласие / квитки'] },
  ];

  function findHeaderIndexByTagOrName(tagCandidates, headerCandidates = []) {
    const normalizedHeaders = headers.map((h) => normalizeHeaderLikeBackend(h));
    for (const tag of tagCandidates || []) {
      const mappedHeader = mappingByTag[tag];
      if (!mappedHeader) continue;
      const idx = headers.findIndex((h) => h === mappedHeader);
      if (idx >= 0) return idx;
    }
    const allCandidates = [...(headerCandidates || []), ...(tagCandidates || [])];
    for (const candidate of allCandidates) {
      const normCandidate = normalizeHeaderLikeBackend(candidate);
      const idx = normalizedHeaders.findIndex((headerNorm) => headerNorm && (headerNorm.includes(normCandidate) || normCandidate.includes(headerNorm)));
      if (idx >= 0) return idx;
    }
    return -1;
  }

  function buildCoreCells(row) {
    const usedIndexes = new Set();
    const cells = coreColumnDefs.map((def) => {
      if (def.key === 'presentationVideo') {
        const presentationIdx = findHeaderIndexByTagOrName(['Презентация'], ['Презентация']);
        const videoIdx = findHeaderIndexByTagOrName(['Видео', 'Ссылки'], ['Видео', 'Ссылка', 'Ссылки']);
        if (presentationIdx >= 0) usedIndexes.add(presentationIdx);
        if (videoIdx >= 0) usedIndexes.add(videoIdx);
        const values = [presentationIdx, videoIdx]
          .filter((idx, index, arr) => idx >= 0 && arr.indexOf(idx) === index)
          .map((idx) => (row[idx] ?? '').toString().trim())
          .filter(Boolean);
        return { title: def.title, value: values.join('\n') || '—' };
      }
      const idx = findHeaderIndexByTagOrName(def.tags, def.headers);
      if (idx >= 0) usedIndexes.add(idx);
      return {
        title: def.title,
        value: idx >= 0 ? ((row[idx] ?? '').toString().trim() || '—') : '—',
      };
    });
    return { cells, usedIndexes };
  }

  function moveRow(fromPos, toPos) {
    if (!rowOrder.length) return;
    const from = Number(fromPos);
    const to = Number(toPos);
    if (!Number.isInteger(from) || !Number.isInteger(to)) return;
    if (from < 1 || to < 1 || from > rowOrder.length || to > rowOrder.length || from === to) return;
    const [moved] = rowOrder.splice(from - 1, 1);
    rowOrder.splice(to - 1, 0, moved);
    renderPreview();
  }

  function renderPreview() {
    previewCardsEl.innerHTML = '';
    if (!headers.length) {
      previewMetaEl.textContent = 'Нет данных для предпросмотра.';
      return;
    }
    if (!previewRowsData.length) {
      previewMetaEl.textContent = 'Нет строк для предпросмотра.';
      return;
    }
    rowOrder.forEach((rowRef, index) => {
      const row = previewRowsData[rowRef - 1] || [];
      const rowNumber = index + 1;
      const isExpanded = Boolean(expandedRows[rowRef]);
      const { cells, usedIndexes } = buildCoreCells(row);

      const card = document.createElement('article');
      card.className = `preview-row-card${isExpanded ? ' is-expanded' : ''}`;

      const rowTop = document.createElement('div');
      rowTop.className = 'preview-row-top';
      rowTop.innerHTML = `
        <button type="button" class="btn btn-secondary btn-small preview-expand-btn">${isExpanded ? 'Свернуть' : 'Развернуть'}</button>
      `;
      const numberCell = document.createElement('div');
      numberCell.className = 'preview-cell preview-cell-order';
      numberCell.innerHTML = `
        <div class="preview-cell-title">Номер</div>
        <div class="preview-order-controls">
          <input class="preview-order-input" type="number" min="1" max="${rowOrder.length}" value="${rowNumber}" />
          <button type="button" class="btn btn-secondary btn-small preview-move-btn" title="Переместить строку">↕</button>
        </div>
      `;
      const numberInput = numberCell.querySelector('.preview-order-input');
      const moveBtn = numberCell.querySelector('.preview-move-btn');
      const commitMove = () => {
        const nextPos = Number(numberInput.value || rowNumber);
        if (!Number.isInteger(nextPos) || nextPos < 1 || nextPos > rowOrder.length) {
          numberInput.value = rowNumber;
          return;
        }
        moveRow(rowNumber, nextPos);
      };
      numberInput?.addEventListener('change', commitMove);
      numberInput?.addEventListener('keydown', (event) => {
        if (event.key !== 'Enter') return;
        event.preventDefault();
        commitMove();
      });
      moveBtn?.addEventListener('click', commitMove);
      rowTop.querySelector('.preview-expand-btn')?.addEventListener('click', () => {
        expandedRows[rowRef] = !expandedRows[rowRef];
        renderPreview();
      });

      const grid = document.createElement('div');
      grid.className = 'preview-row-grid';
      grid.appendChild(numberCell);
      cells.forEach((cell) => {
        const item = document.createElement('div');
        item.className = 'preview-cell';
        item.innerHTML = `
          <div class="preview-cell-title">${esc(cell.title)}</div>
          <div class="preview-cell-value${isExpanded ? '' : ' preview-cell-clamp'}">${esc(cell.value)}</div>
        `;
        grid.appendChild(item);
      });

      card.appendChild(rowTop);
      card.appendChild(grid);

      if (isExpanded) {
        const extra = document.createElement('div');
        extra.className = 'preview-extra-block';
        const remaining = headers
          .map((header, headerIndex) => ({ header, value: (row[headerIndex] ?? '').toString().trim(), headerIndex }))
          .filter((item) => !usedIndexes.has(item.headerIndex) && item.value);
        extra.innerHTML = `
          <h3 class="preview-extra-title">Дополнительные поля</h3>
          <div class="preview-extra-grid">
            ${remaining.length
              ? remaining
                .map((item) => `
                  <div class="preview-extra-row">
                    <div class="preview-extra-key">${esc(item.header)}</div>
                    <div class="preview-extra-value">${esc(item.value)}</div>
                  </div>
                `).join('')
              : '<div class="hint">Дополнительных данных нет.</div>'}
          </div>
        `;
        card.appendChild(extra);
      }

      previewCardsEl.appendChild(card);
    });
  }

  function isAutoDetectedMapping(header, selectedTag) {
    if (!header || !selectedTag) return false;
    const tagNorm = normalizeHeaderLikeBackend(selectedTag);
    const headerNorm = normalizeHeaderLikeBackend(header);
    return Boolean(tagNorm && headerNorm && (tagNorm.includes(headerNorm) || headerNorm.includes(tagNorm)));
  }

  function renderMapping(fieldTags) {
    mappingListEl.innerHTML = '';
    mappingFieldTags = fieldTags;
    headers.forEach((header) => {
      const tag = Object.keys(mappingByTag).find((fieldTag) => mappingByTag[fieldTag] === header) || '';
      const card = document.createElement('article');
      const isMapped = Boolean(tag);
      const isCollapsed = Boolean(collapsedMappingCards[header] && isMapped);
      const isAutoDetected = isAutoDetectedMapping(header, tag);
      card.className = `mapping-card${isMapped ? ' is-mapped' : ''}${isAutoDetected ? ' is-auto' : ''}${isCollapsed ? ' is-collapsed' : ''}`;

      const body = document.createElement('div');
      body.className = 'mapping-card-body';

      const headerEl = document.createElement('span');
      headerEl.className = 'mapping-header';
      headerEl.textContent = header || '(Пустой заголовок)';

      const selectedValueEl = document.createElement('span');
      selectedValueEl.className = 'mapping-selected-value';
      selectedValueEl.textContent = tag || 'не выбрано';

      const select = document.createElement('select');
      select.className = 'mapping-select';
      select.innerHTML = '<option value="">не выбрано</option>' + fieldTags.map((fieldTag) => {
        const selected = tag === fieldTag ? ' selected' : '';
        return `<option value="${esc(fieldTag)}"${selected}>${esc(fieldTag)}</option>`;
      }).join('');
      select.addEventListener('change', () => {
        const nextTag = select.value;
        if (tag) delete mappingByTag[tag];
        if (nextTag) {
          Object.keys(mappingByTag).forEach((key) => {
            if (key !== nextTag && mappingByTag[key] === header) delete mappingByTag[key];
          });
          mappingByTag[nextTag] = header;
        } else {
          collapsedMappingCards[header] = false;
        }
        setStatus(mappingStatusEl, 'Есть несохранённые изменения.', 'warning');
        renderMapping(fieldTags);
      });

      const toggleBtn = document.createElement('button');
      toggleBtn.type = 'button';
      toggleBtn.className = 'mapping-toggle-btn';
      toggleBtn.title = isCollapsed ? 'Развернуть карточку' : 'Свернуть карточку';
      toggleBtn.textContent = isCollapsed ? '▼' : '▲';
      toggleBtn.addEventListener('click', () => {
        collapsedMappingCards[header] = !collapsedMappingCards[header];
        renderMapping(fieldTags);
      });

      if (isCollapsed) {
        body.appendChild(headerEl);
        body.appendChild(selectedValueEl);
      } else {
        body.appendChild(headerEl);
        body.appendChild(select);
      }

      card.appendChild(body);
      if (isMapped) card.appendChild(toggleBtn);
      mappingListEl.appendChild(card);
    });
    renderPreview();
  }

  async function reload() {
    const [table, preview, mapResp] = await Promise.all([
      apiGet(`/api/tables/${tableId}`),
      apiGet(`/api/tables/${tableId}/excel_preview`),
      apiGet(`/api/tables/${tableId}/mapping`),
    ]);
    titleEl.textContent = table.title || `Таблица #${tableId}`;
    headers = preview.headers || [];
    mappingByTag = mapResp.mapping || {};
    previewRowsData = preview.rows || [];
    rowOrder = previewRowsData.map((_, idx) => idx + 1);
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
      await apiPostJson(`/api/tables/${tableId}/mapping`, { mapping: mappingByTag });
      setStatus(mappingStatusEl, 'Mapping сохранён.', 'success');
      await reload();
    } catch (e) {
      setStatus(mappingStatusEl, `Ошибка: ${e.message}`, 'error');
    }
  });

  collapseConfiguredBtn?.addEventListener('click', () => {
    headers.forEach((header) => {
      const tag = Object.keys(mappingByTag).find((fieldTag) => mappingByTag[fieldTag] === header);
      if (tag) collapsedMappingCards[header] = true;
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
