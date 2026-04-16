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

function parseClockToMinutes(value) {
  const text = (value || '').toString().trim();
  if (!text || !text.includes(':')) return null;
  const [hh, mm] = text.split(':');
  const h = Number(hh);
  const m = Number(mm);
  if (!Number.isFinite(h) || !Number.isFinite(m)) return null;
  if (h < 0 || h > 23 || m < 0 || m > 59) return null;
  return h * 60 + m;
}

function formatMinutesToClock(totalMinutes) {
  if (!Number.isFinite(totalMinutes)) return '--:--';
  const normalized = ((Math.floor(totalMinutes) % 1440) + 1440) % 1440;
  const hh = Math.floor(normalized / 60).toString().padStart(2, '0');
  const mm = (normalized % 60).toString().padStart(2, '0');
  return `${hh}:${mm}`;
}

function parseDurationToSeconds(value, fallbackMinutes = 3) {
  const fallback = Math.max(1, Number(fallbackMinutes) || 3) * 60;
  const text = (value || '').toString().trim();
  if (!text) return fallback;

  if (text.includes(':')) {
    const parts = text.split(':').map((v) => Number(v.trim()));
    if (parts.some((v) => !Number.isFinite(v))) return fallback;
    if (parts.length === 2) {
      const [mm, ss] = parts;
      if (mm >= 0 && ss >= 0 && ss < 60) return mm * 60 + ss;
    }
    if (parts.length === 3) {
      const [hh, mm, ss] = parts;
      if (hh >= 0 && mm >= 0 && mm < 60 && ss >= 0 && ss < 60) return hh * 3600 + mm * 60 + ss;
    }
    return fallback;
  }

  const normalized = text.replace(',', '.');
  const asNumber = Number(normalized);
  if (!Number.isFinite(asNumber) || asNumber <= 0) return fallback;
  if (normalized.includes('.')) {
    const [minsRaw, secRaw] = normalized.split('.');
    const mins = Number(minsRaw);
    const seconds = Number((secRaw || '').slice(0, 2));
    if (Number.isFinite(mins) && Number.isFinite(seconds) && seconds >= 0 && seconds < 60) {
      return mins * 60 + seconds;
    }
  }
  return Math.round(asNumber * 60);
}

function formatDurationLabel(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0));
  const mm = Math.floor(s / 60);
  const ss = s % 60;
  return `${mm}:${ss.toString().padStart(2, '0')}`;
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
  const mappingSectionCardEl = document.getElementById('mappingSectionCard');
  const mappingSectionToggleBtn = document.getElementById('toggleMappingSection');
  const previewMetaEl = document.getElementById('previewMeta');
  const previewCardsEl = document.getElementById('previewCards');
  const docEventDateEl = document.getElementById('docEventDate');
  const docRehearsalStartEl = document.getElementById('docRehearsalStart');
  const docCompetitionStartEl = document.getElementById('docCompetitionStart');
  const docResultsMinutesEl = document.getElementById('docResultsMinutes');
  const docAwardMinutesEl = document.getElementById('docAwardMinutes');
  const docTechIntervalMinutesEl = document.getElementById('docTechIntervalMinutes');
  const docDefaultDurationMinutesEl = document.getElementById('docDefaultDurationMinutes');
  const docBuildProgramBtn = document.getElementById('docBuildProgram');
  const docProgramStatusEl = document.getElementById('docProgramStatus');
  const docProgramPreviewEl = document.getElementById('docProgramPreview');

  let headers = [];
  let mappingByHeaderIdx = {};
  let collapsedMappingCards = {};
  let mappingFieldTags = [];
  let previewRowsData = [];
  let rowOrder = [];
  let isMappingSectionCollapsed = false;
  const expandedRows = {};
  let documentationState = null;

  function syncMappingSectionCollapsedState() {
    if (!mappingSectionCardEl || !mappingSectionToggleBtn) return;
    mappingSectionCardEl.classList.toggle('is-collapsed', isMappingSectionCollapsed);
    mappingSectionToggleBtn.textContent = isMappingSectionCollapsed ? '▼' : '▲';
    mappingSectionToggleBtn.title = isMappingSectionCollapsed ? 'Развернуть блок «Схема колонок»' : 'Свернуть блок «Схема колонок»';
    mappingSectionToggleBtn.setAttribute('aria-expanded', String(!isMappingSectionCollapsed));
  }

  function mappedTagsInOrder() {
    const used = new Set();
    return mappingFieldTags.filter((tag) => {
      const hasAny = Object.values(mappingByHeaderIdx).some((v) => v === tag);
      if (!hasAny || used.has(tag)) return false;
      used.add(tag);
      return true;
    });
  }

  function normalizeRowByTags(row) {
    const tags = mappedTagsInOrder();
    const usedIndexes = new Set();
    const cells = tags.map((tag) => {
      const src = Object.entries(mappingByHeaderIdx)
        .map(([idxText, mappedTag]) => ({ idx: Number(idxText), mappedTag }))
        .filter((item) => item.mappedTag === tag && Number.isInteger(item.idx) && item.idx >= 0 && item.idx < headers.length)
        .sort((a, b) => a.idx - b.idx);

      const sourceValues = src
        .map((item) => {
          usedIndexes.add(item.idx);
          return {
            idx: item.idx,
            header: headers[item.idx] || `Колонка ${item.idx + 1}`,
            value: (row[item.idx] ?? '').toString().trim(),
          };
        })
        .filter((item) => item.value);

      const hasConflict = sourceValues.length > 1;
      const mergedValue = sourceValues.length === 1 ? sourceValues[0].value : '';
      return {
        title: tag,
        value: mergedValue || '—',
        mergedValue,
        sourceValues,
        hasConflict,
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
      const { cells, usedIndexes } = normalizeRowByTags(row);

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
        item.className = `preview-cell${cell.hasConflict ? ' preview-cell-conflict' : ''}`;
        item.innerHTML = `
          <div class="preview-cell-title">${esc(cell.title)}</div>
          <div class="preview-cell-value${isExpanded ? '' : ' preview-cell-clamp'}">${esc(cell.value)}</div>
          ${cell.hasConflict ? '<div class="preview-conflict-badge">Конфликт значений</div>' : ''}
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
        const conflictDetails = cells.filter((cell) => cell.hasConflict);
        extra.innerHTML = `
          ${conflictDetails.length ? `
            <h3 class="preview-extra-title">Конфликты тегов</h3>
            <div class="preview-conflict-list">
              ${conflictDetails.map((cell) => `
                <div class="preview-conflict-item">
                  <div class="preview-conflict-tag">${esc(cell.title)}</div>
                  ${cell.sourceValues.map((item) => `
                    <div class="preview-conflict-source">
                      <span class="preview-conflict-col">${esc(item.header)}</span>
                      <span class="preview-conflict-val">${esc(item.value)}</span>
                    </div>
                  `).join('')}
                </div>
              `).join('')}
            </div>
          ` : ''}
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

  function getMappedValueByMatchers(row, matchers) {
    const matcherList = (matchers || []).map((item) => normalizeHeaderLikeBackend(item));
    for (const [idxText, mappedTag] of Object.entries(mappingByHeaderIdx)) {
      const idx = Number(idxText);
      const tagNorm = normalizeHeaderLikeBackend(mappedTag);
      if (!matcherList.some((m) => tagNorm.includes(m))) continue;
      const value = (row[idx] ?? '').toString().trim();
      if (value) return value;
    }
    return '';
  }

  function readDocumentationSettingsFromForm() {
    return {
      event_date: docEventDateEl?.value || '',
      rehearsal_start: docRehearsalStartEl?.value || '09:00',
      competition_start: docCompetitionStartEl?.value || '10:00',
      results_minutes: Math.max(0, Number(docResultsMinutesEl?.value || 20) || 20),
      award_minutes: Math.max(0, Number(docAwardMinutesEl?.value || 15) || 15),
      tech_interval_minutes: Math.max(0, Number(docTechIntervalMinutesEl?.value || 20) || 20),
      default_duration_minutes: Math.max(1, Number(docDefaultDurationMinutesEl?.value || 3) || 3),
      age_order: documentationState?.settings?.age_order || [],
      nomination_order: documentationState?.settings?.nomination_order || {},
    };
  }

  function applyDocumentationSettingsToForm(settings = {}) {
    if (docEventDateEl) docEventDateEl.value = settings.event_date || '';
    if (docRehearsalStartEl) docRehearsalStartEl.value = settings.rehearsal_start || '09:00';
    if (docCompetitionStartEl) docCompetitionStartEl.value = settings.competition_start || '10:00';
    if (docResultsMinutesEl) docResultsMinutesEl.value = settings.results_minutes ?? 20;
    if (docAwardMinutesEl) docAwardMinutesEl.value = settings.award_minutes ?? 15;
    if (docTechIntervalMinutesEl) docTechIntervalMinutesEl.value = settings.tech_interval_minutes ?? 20;
    if (docDefaultDurationMinutesEl) docDefaultDurationMinutesEl.value = settings.default_duration_minutes ?? 3;
  }

  function buildProgramPreviewData(settings) {
    const rowsInOrder = rowOrder.map((rowRef, index) => {
      const row = previewRowsData[rowRef - 1] || [];
      const ageCategory = getMappedValueByMatchers(row, ['возраст']);
      const nomination = getMappedValueByMatchers(row, ['номинац']);
      const numberTitle = getMappedValueByMatchers(row, ['название номера', 'навание номреа', 'номер']);
      const fio = getMappedValueByMatchers(row, ['участник', 'фио']);
      const team = getMappedValueByMatchers(row, ['коллектив']);
      const institution = getMappedValueByMatchers(row, ['учрежден']);
      const municipality = getMappedValueByMatchers(row, ['территор', 'муницип']);
      const rawDuration = getMappedValueByMatchers(row, ['время исполнения', 'продолжительность']);
      const durationSeconds = parseDurationToSeconds(rawDuration, settings.default_duration_minutes);
      return {
        order: index + 1,
        ageCategory: ageCategory || 'Без возрастной категории',
        nomination: nomination || 'Без номинации',
        numberTitle: numberTitle || 'Без названия номера',
        fio,
        team,
        institution,
        municipality,
        durationSeconds,
      };
    });

    const ageOrder = [];
    const groupedByAge = {};
    rowsInOrder.forEach((item) => {
      if (!groupedByAge[item.ageCategory]) {
        groupedByAge[item.ageCategory] = {};
        ageOrder.push(item.ageCategory);
      }
      if (!groupedByAge[item.ageCategory][item.nomination]) groupedByAge[item.ageCategory][item.nomination] = [];
      groupedByAge[item.ageCategory][item.nomination].push(item);
    });

    const competitionStart = parseClockToMinutes(settings.competition_start) ?? 600;
    const rehearsalStart = parseClockToMinutes(settings.rehearsal_start);
    let cursor = competitionStart;
    const blocks = [];

    if (Number.isFinite(rehearsalStart) && rehearsalStart < competitionStart && ageOrder.length) {
      blocks.push({
        type: 'service',
        text: `Репетиция возрастной категории ${ageOrder[0]}`,
        start: rehearsalStart,
        end: competitionStart,
      });
    }

    ageOrder.forEach((ageCategory, ageIndex) => {
      const nominations = Object.keys(groupedByAge[ageCategory] || {});
      const ageBlock = {
        type: 'age_category',
        ageCategory,
        start: cursor,
        nominations: [],
      };

      nominations.forEach((nomination) => {
        const nominationStart = cursor;
        const items = groupedByAge[ageCategory][nomination];
        const previewItems = items.map((item) => {
          cursor += item.durationSeconds / 60;
          const person = item.fio && item.team ? `${item.fio}, ${item.team}` : (item.fio || item.team || 'Участник');
          const details = [person, item.institution, item.municipality].filter(Boolean).join(', ');
          return {
            order: item.order,
            text: `«${item.numberTitle}» — ${details} (${formatDurationLabel(item.durationSeconds)})`,
          };
        });
        ageBlock.nominations.push({ nomination, start: nominationStart, items: previewItems });
      });
      blocks.push(ageBlock);

      const nextAge = ageOrder[ageIndex + 1];
      if (nextAge) {
        const resultsStart = cursor;
        const resultsEnd = resultsStart + settings.results_minutes;
        blocks.push({ type: 'service', text: `Подведение итогов`, start: resultsStart, end: resultsEnd });
        cursor = resultsEnd;

        const rehearsalEnd = cursor + settings.tech_interval_minutes;
        blocks.push({ type: 'service', text: `Репетиция возрастной категории ${nextAge}`, start: cursor, end: rehearsalEnd });
        cursor = rehearsalEnd;

        const awardEnd = cursor + settings.award_minutes;
        blocks.push({ type: 'service', text: `Награждение возрастной категории ${ageCategory}`, start: cursor, end: awardEnd });
        cursor = awardEnd;
      }
    });

    return { title: 'Программа конкурса', date: settings.event_date || '', blocks };
  }

  function renderDocumentationPreview(program) {
    if (!docProgramPreviewEl) return;
    if (!program || !Array.isArray(program.blocks) || !program.blocks.length) {
      docProgramPreviewEl.classList.add('is-empty');
      docProgramPreviewEl.innerHTML = '<div>После формирования здесь появится предпросмотр программы.</div>';
      return;
    }
    docProgramPreviewEl.classList.remove('is-empty');
    const parts = [
      `<div class="doc-preview-title">${esc(program.title || 'Программа конкурса')}</div>`,
      `<div class="doc-preview-date">Дата: ${esc(program.date || '—')}</div>`,
    ];
    program.blocks.forEach((block) => {
      if (block.type === 'service') {
        parts.push(`<div class="doc-preview-service">${esc(formatMinutesToClock(block.start))}–${esc(formatMinutesToClock(block.end))} — ${esc(block.text)}</div>`);
        return;
      }
      parts.push(`<div class="doc-preview-age">${esc(formatMinutesToClock(block.start))} Возрастная категория: ${esc(block.ageCategory)}</div>`);
      (block.nominations || []).forEach((nom) => {
        parts.push(`<div class="doc-preview-nomination">${esc(formatMinutesToClock(nom.start))} Номинация: ${esc(nom.nomination)}</div>`);
        parts.push(`<ol class="doc-preview-items">${(nom.items || []).map((item) => `<li class="doc-preview-item">${esc(item.text)}</li>`).join('')}</ol>`);
      });
    });
    docProgramPreviewEl.innerHTML = parts.join('');
  }

  async function saveDocumentationState(state) {
    await apiPostJson(`/api/tables/${tableId}/documentation/program`, state);
  }

  async function loadDocumentationState() {
    const resp = await apiGet(`/api/tables/${tableId}/documentation/program`);
    documentationState = resp || {};
    const settings = documentationState.settings || {
      event_date: '',
      rehearsal_start: '09:00',
      competition_start: '10:00',
      results_minutes: 20,
      award_minutes: 15,
      tech_interval_minutes: 20,
      default_duration_minutes: 3,
      age_order: [],
      nomination_order: {},
    };
    applyDocumentationSettingsToForm(settings);
    renderDocumentationPreview(documentationState.program);
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
    const usageByTag = {};
    Object.values(mappingByHeaderIdx).forEach((tag) => {
      if (!tag) return;
      usageByTag[tag] = (usageByTag[tag] || 0) + 1;
    });
    headers.forEach((header, headerIndex) => {
      const tag = mappingByHeaderIdx[headerIndex] || '';
      const card = document.createElement('article');
      const isMapped = Boolean(tag);
      const isCollapsed = Boolean(collapsedMappingCards[headerIndex] && isMapped);
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
        const usedCount = usageByTag[fieldTag] || 0;
        const externalCount = tag === fieldTag ? Math.max(usedCount - 1, 0) : usedCount;
        const usageSuffix = externalCount > 0 ? ` (используется ещё в ${externalCount})` : '';
        const selected = tag === fieldTag ? ' selected' : '';
        return `<option value="${esc(fieldTag)}"${selected}>${esc(fieldTag + usageSuffix)}</option>`;
      }).join('');
      select.addEventListener('change', () => {
        const nextTag = select.value;
        if (nextTag) mappingByHeaderIdx[headerIndex] = nextTag;
        else {
          delete mappingByHeaderIdx[headerIndex];
          collapsedMappingCards[headerIndex] = false;
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
        collapsedMappingCards[headerIndex] = !collapsedMappingCards[headerIndex];
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
    const nextMappingByHeader = {};
    (mapResp.mapping_rows || []).forEach((item) => {
      if (!item || typeof item.excel_column_index !== 'number' || !item.field_tag) return;
      nextMappingByHeader[item.excel_column_index] = item.field_tag;
    });
    mappingByHeaderIdx = nextMappingByHeader;
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
      const mappingRows = Object.entries(mappingByHeaderIdx).map(([idxText, fieldTag]) => ({
        field_tag: fieldTag,
        excel_column_index: Number(idxText),
      }));
      await apiPostJson(`/api/tables/${tableId}/mapping`, { mapping_rows: mappingRows });
      setStatus(mappingStatusEl, 'Mapping сохранён.', 'success');
      await reload();
    } catch (e) {
      setStatus(mappingStatusEl, `Ошибка: ${e.message}`, 'error');
    }
  });

  collapseConfiguredBtn?.addEventListener('click', () => {
    headers.forEach((_, headerIndex) => {
      const tag = mappingByHeaderIdx[headerIndex];
      if (tag) collapsedMappingCards[headerIndex] = true;
    });
    renderMapping(mappingFieldTags);
  });

  mappingSectionToggleBtn?.addEventListener('click', () => {
    isMappingSectionCollapsed = !isMappingSectionCollapsed;
    syncMappingSectionCollapsedState();
  });

  docBuildProgramBtn?.addEventListener('click', async () => {
    try {
      if (!previewRowsData.length) {
        setStatus(docProgramStatusEl, 'Нет данных таблицы для формирования программы.', 'warning');
        renderDocumentationPreview(null);
        return;
      }
      const settings = readDocumentationSettingsFromForm();
      const program = buildProgramPreviewData(settings);
      const state = { settings, program };
      documentationState = state;
      renderDocumentationPreview(program);
      await saveDocumentationState(state);
      setStatus(docProgramStatusEl, 'Программа сформирована и сохранена.', 'success');
    } catch (e) {
      setStatus(docProgramStatusEl, `Ошибка формирования: ${e.message}`, 'error');
    }
  });

  try {
    syncMappingSectionCollapsedState();
    await reload();
    await loadDocumentationState();
  } catch (e) {
    setStatus(uploadStatusEl, `Ошибка загрузки данных: ${e.message}`, 'error');
  }
}

initListPage();
initDetailPage();
