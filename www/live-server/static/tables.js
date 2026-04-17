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
  let sequenceItems = [];
  let isMappingSectionCollapsed = false;
  const expandedRows = {};
  let documentationState = null;
  let contextMenuEl = null;
  let contextMenuTargetId = '';

  function syncMappingSectionCollapsedState() {
    if (!mappingSectionCardEl || !mappingSectionToggleBtn) return;
    const bodyEl = document.getElementById('mappingSectionBody');
    mappingSectionCardEl.classList.toggle('is-collapsed', isMappingSectionCollapsed);
    if (bodyEl) {
      if (isMappingSectionCollapsed) {
        const currentHeight = bodyEl.scrollHeight;
        bodyEl.style.maxHeight = `${currentHeight}px`;
        window.requestAnimationFrame(() => {
          bodyEl.style.maxHeight = '0px';
        });
      } else {
        bodyEl.style.maxHeight = `${bodyEl.scrollHeight}px`;
        window.setTimeout(() => {
          if (!isMappingSectionCollapsed) bodyEl.style.maxHeight = 'none';
        }, 300);
      }
      bodyEl.style.opacity = isMappingSectionCollapsed ? '0' : '1';
      bodyEl.style.marginTop = isMappingSectionCollapsed ? '0px' : '10px';
    }
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

  function getParticipantOrderByIndex(index) {
    if (!Number.isInteger(index) || index < 0) return 0;
    let order = 0;
    for (let i = 0; i <= index && i < sequenceItems.length; i += 1) {
      if (sequenceItems[i]?.type === 'participant') order += 1;
    }
    return order;
  }

  function getIndexByParticipantOrder(order) {
    const target = Number(order);
    if (!Number.isInteger(target) || target < 1) return -1;
    let current = 0;
    for (let i = 0; i < sequenceItems.length; i += 1) {
      if (sequenceItems[i]?.type !== 'participant') continue;
      current += 1;
      if (current === target) return i;
    }
    return -1;
  }

  function moveParticipant(fromOrder, toOrder) {
    const totalParticipants = sequenceItems.filter((item) => item.type === 'participant').length;
    const from = Number(fromOrder);
    const to = Number(toOrder);
    if (!Number.isInteger(from) || !Number.isInteger(to)) return;
    if (from < 1 || to < 1 || from > totalParticipants || to > totalParticipants || from === to) return;
    const fromIndex = getIndexByParticipantOrder(from);
    let toIndex = getIndexByParticipantOrder(to);
    if (fromIndex < 0 || toIndex < 0) return;
    const [moved] = sequenceItems.splice(fromIndex, 1);
    if (fromIndex < toIndex) toIndex -= 1;
    sequenceItems.splice(toIndex, 0, moved);
    queueSequenceSave();
    renderPreview();
  }

  function getParticipantStage(item) {
    if (item?.stageStatus === 'onsite' || item?.stageStatus === 'remote') return item.stageStatus;
    if (item?.isOnsite === true) return 'onsite';
    if (item?.isOnsite === false) return 'remote';
    return null;
  }

  function getStageLabel(stageStatus) {
    if (stageStatus === 'onsite') return 'Очный этап';
    if (stageStatus === 'remote') return 'Заочный этап';
    return 'Не распределено';
  }

  const editableFieldSpecs = [
    { key: 'territory', label: 'Территория', matchers: ['территория'] },
    { key: 'participant_fio', label: 'ФИО участника/участников', matchers: ['участник', 'фио'] },
    { key: 'nomination', label: 'Номинация', matchers: ['номинация'] },
    { key: 'number_title', label: 'Название номера', matchers: ['название номера', 'номер'] },
    { key: 'audio', label: 'Фонограммы', matchers: ['фонограмм', 'audio'] },
    { key: 'presentation_video', label: 'Презентации / видео', matchers: ['презентац', 'видео'] },
    { key: 'consents', label: 'Согласия', matchers: ['соглас'] },
  ];

  function buildEffectiveRow(row, item) {
    const nextRow = Array.isArray(row) ? [...row] : [];
    const edits = item?.editedFields;
    if (!edits || typeof edits !== 'object') return nextRow;
    editableFieldSpecs.forEach((spec) => {
      const editedValue = (typeof edits[spec.key] === 'string') ? edits[spec.key].trim() : '';
      if (!editedValue) return;
      Object.entries(mappingByHeaderIdx).forEach(([idxText, mappedTag]) => {
        const idx = Number(idxText);
        if (!Number.isInteger(idx) || idx < 0 || idx >= headers.length) return;
        const tagNorm = normalizeHeaderLikeBackend(mappedTag);
        if (spec.matchers.some((matcher) => tagNorm.includes(normalizeHeaderLikeBackend(matcher)))) {
          nextRow[idx] = editedValue;
        }
      });
    });
    if (edits.extra && typeof edits.extra === 'object') {
      headers.forEach((header, idx) => {
        const editedValue = typeof edits.extra[header] === 'string' ? edits.extra[header].trim() : '';
        if (editedValue) nextRow[idx] = editedValue;
      });
    }
    return nextRow;
  }

  function setItemEditing(itemId, isEditing) {
    sequenceItems = sequenceItems.map((item) => (item.id === itemId ? { ...item, isEditing: Boolean(isEditing) } : item));
    expandedRows[itemId] = true;
    queueSequenceSave();
    renderPreview();
  }

  function moveItem(fromPos, toPos) {
    if (!sequenceItems.length) return;
    const from = Number(fromPos);
    const to = Number(toPos);
    if (!Number.isInteger(from) || !Number.isInteger(to)) return;
    if (from < 1 || to < 1 || from > sequenceItems.length || to > sequenceItems.length || from === to) return;
    const [moved] = sequenceItems.splice(from - 1, 1);
    sequenceItems.splice(to - 1, 0, moved);
    queueSequenceSave();
    renderPreview();
  }

  function createSequenceId(prefix) {
    return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  }

  function getSequenceItemById(itemId) {
    return sequenceItems.find((item) => item.id === itemId) || null;
  }

  function normalizeAwardBlockSettings(item = {}, minStartMinutes = 0) {
    const safeMin = Math.max(0, Math.floor(minStartMinutes || 0));
    const awardDurationMinutes = Math.max(1, Number(item.award_duration_minutes || 15) || 15);
    const includeResults = Boolean(item.include_results_time);
    const includeRehearsal = Boolean(item.include_rehearsal_time);
    const resultsStart = Math.max(safeMin, Number(item.results_start_minutes ?? safeMin) || safeMin);
    const rehearsalStart = Math.max(safeMin, Number(item.rehearsal_start_minutes ?? safeMin) || safeMin);
    return {
      ...item,
      block_type: 'award_block',
      award_duration_minutes: awardDurationMinutes,
      include_results_time: includeResults,
      include_rehearsal_time: includeRehearsal,
      parallel_results_and_rehearsal: Boolean(item.parallel_results_and_rehearsal),
      results_start_minutes: resultsStart,
      results_duration_minutes: Math.max(1, Number(item.results_duration_minutes || 20) || 20),
      rehearsal_start_minutes: rehearsalStart,
      rehearsal_duration_minutes: Math.max(1, Number(item.rehearsal_duration_minutes || 20) || 20),
    };
  }

  function normalizeBreakBlockSettings(item = {}) {
    return {
      ...item,
      block_type: 'break_block',
      break_duration_minutes: Math.max(1, Number(item.break_duration_minutes || 15) || 15),
      add_rehearsal_during_break: Boolean(item.add_rehearsal_during_break),
    };
  }

  function ensureSequenceFromRows(serializedItems) {
    const existsByRowRef = new Map();
    const parsed = Array.isArray(serializedItems) ? serializedItems : [];
    const normalized = [];

    parsed.forEach((item) => {
      if (!item || typeof item !== 'object') return;
      if (item.type === 'participant') {
        const rowRef = Number(item.rowRef || 0);
        if (!Number.isInteger(rowRef) || rowRef < 1 || rowRef > previewRowsData.length || existsByRowRef.has(rowRef)) return;
        existsByRowRef.set(rowRef, true);
        normalized.push({
          id: item.id || createSequenceId('participant'),
          type: 'participant',
          rowRef,
          stageStatus: getParticipantStage(item),
          editedFields: item.editedFields && typeof item.editedFields === 'object' ? item.editedFields : {},
          isEditing: false,
        });
        return;
      }
      if (item.type === 'award_block') {
        normalized.push(normalizeAwardBlockSettings({ id: item.id || createSequenceId('award'), type: 'award_block', ...item }));
        return;
      }
      if (item.type === 'break_block') {
        normalized.push(normalizeBreakBlockSettings({ id: item.id || createSequenceId('break'), type: 'break_block', ...item }));
      }
    });

    for (let rowRef = 1; rowRef <= previewRowsData.length; rowRef += 1) {
      if (!existsByRowRef.has(rowRef)) {
        normalized.push({
          id: createSequenceId('participant'),
          type: 'participant',
          rowRef,
          stageStatus: null,
          editedFields: {},
          isEditing: false,
        });
      }
    }
    sequenceItems = normalized;
  }

  async function saveSequenceState() {
    await apiPostJson(`/api/tables/${tableId}/card-sequence`, { items: sequenceItems });
  }

  let queueTimer = null;
  function queueSequenceSave() {
    if (queueTimer) window.clearTimeout(queueTimer);
    queueTimer = window.setTimeout(async () => {
      try {
        await saveSequenceState();
      } catch (e) {
        setStatus(uploadStatusEl, `Не удалось сохранить порядок карточек: ${e.message}`, 'warning');
      }
    }, 250);
  }

  async function loadSequenceState() {
    const resp = await apiGet(`/api/tables/${tableId}/card-sequence`);
    ensureSequenceFromRows(resp?.items || []);
  }

  function closeContextMenu() {
    if (contextMenuEl) contextMenuEl.remove();
    contextMenuEl = null;
    contextMenuTargetId = '';
  }

  function getParticipantLabel(item) {
    const row = previewRowsData[(item?.rowRef || 1) - 1] || [];
    const title = getMappedValueByMatchers(row, ['название номера', 'номер']) || 'Без названия номера';
    const fio = getMappedValueByMatchers(row, ['участник', 'фио']);
    return fio ? `${title} — ${fio}` : title;
  }

  function getLastEndMinutesBeforeIndex(index, settings) {
    let cursor = parseClockToMinutes(settings.competition_start) ?? 600;
    for (let i = 0; i < index; i += 1) {
      const item = sequenceItems[i];
      if (!item) continue;
      if (item.type === 'participant') {
        if (getParticipantStage(item) === 'onsite') {
          const row = buildEffectiveRow(previewRowsData[item.rowRef - 1] || [], item);
          const rawDuration = getMappedValueByMatchers(row, ['время исполнения', 'продолжительность']);
          const durationSeconds = parseDurationToSeconds(rawDuration, settings.default_duration_minutes);
          cursor += durationSeconds / 60;
        }
        continue;
      }
      if (item.type === 'break_block') {
        cursor += Math.max(0, Number(item.break_duration_minutes || 0));
        continue;
      }
      if (item.type === 'award_block') {
        const award = normalizeAwardBlockSettings(item, cursor);
        let serviceEnd = cursor;
        if (award.include_results_time && award.include_rehearsal_time && award.parallel_results_and_rehearsal) {
          const resultsEnd = award.results_start_minutes + award.results_duration_minutes;
          const rehearsalEnd = award.rehearsal_start_minutes + award.rehearsal_duration_minutes;
          serviceEnd = Math.max(serviceEnd, resultsEnd, rehearsalEnd);
        } else {
          if (award.include_results_time) serviceEnd = Math.max(serviceEnd, award.results_start_minutes + award.results_duration_minutes);
          if (award.include_rehearsal_time) serviceEnd = Math.max(serviceEnd, award.rehearsal_start_minutes + award.rehearsal_duration_minutes);
        }
        cursor = Math.max(cursor, serviceEnd) + award.award_duration_minutes;
      }
    }
    return cursor;
  }

  function renderPreview() {
    previewCardsEl.innerHTML = '';
    if (!headers.length) {
      previewMetaEl.textContent = 'Нет данных для предпросмотра.';
      return;
    }
    if (!previewRowsData.length || !sequenceItems.length) {
      previewMetaEl.textContent = 'Нет строк для предпросмотра.';
      return;
    }
    previewMetaEl.textContent = `Карточек: ${sequenceItems.length}, участников: ${sequenceItems.filter((item) => item.type === 'participant').length}`;

    sequenceItems.forEach((item, index) => {
      const isParticipant = item.type === 'participant';
      const rowRef = isParticipant ? item.rowRef : 0;
      const rawRow = isParticipant ? (previewRowsData[rowRef - 1] || []) : [];
      const row = isParticipant ? buildEffectiveRow(rawRow, item) : [];
      const participantNumber = isParticipant ? getParticipantOrderByIndex(index) : null;
      const isExpanded = Boolean(expandedRows[item.id]);
      const isEditing = Boolean(item.isEditing);
      const { cells, usedIndexes } = normalizeRowByTags(row);

      const card = document.createElement('article');
      card.className = `preview-row-card${isExpanded ? ' is-expanded' : ''}${item.type === 'award_block' ? ' preview-row-card-award' : ''}${item.type === 'break_block' ? ' preview-row-card-break' : ''}`;
      card.dataset.itemId = item.id;
      card.dataset.itemType = item.type;

      const rowTop = document.createElement('div');
      rowTop.className = 'preview-row-top';
      rowTop.innerHTML = `<button type="button" class="btn btn-secondary btn-small preview-expand-btn">${isExpanded ? 'Свернуть' : 'Развернуть'}</button>`;
      rowTop.querySelector('.preview-expand-btn')?.addEventListener('click', () => {
        expandedRows[item.id] = !expandedRows[item.id];
        renderPreview();
      });

      const grid = document.createElement('div');
      grid.className = 'preview-row-grid';

      if (isParticipant) {
        const totalParticipants = sequenceItems.filter((entry) => entry.type === 'participant').length;
        const numberCell = document.createElement('div');
        numberCell.className = 'preview-cell preview-cell-order';
        numberCell.dataset.noContext = '1';
        numberCell.innerHTML = `
          <div class="preview-cell-title">Номер</div>
          <div class="preview-order-controls">
            <input class="preview-order-input" type="number" min="1" max="${totalParticipants}" value="${participantNumber}" />
            <button type="button" class="btn btn-secondary btn-small preview-move-btn" title="Переместить участника">↕</button>
          </div>
        `;
        const numberInput = numberCell.querySelector('.preview-order-input');
        const moveBtn = numberCell.querySelector('.preview-move-btn');
        const commitMove = () => {
          const nextPos = Number(numberInput.value || participantNumber);
          if (!Number.isInteger(nextPos) || nextPos < 1 || nextPos > totalParticipants) {
            numberInput.value = participantNumber;
            return;
          }
          moveParticipant(participantNumber, nextPos);
        };
        numberInput?.addEventListener('change', commitMove);
        numberInput?.addEventListener('keydown', (event) => {
          if (event.key !== 'Enter') return;
          event.preventDefault();
          commitMove();
        });
        moveBtn?.addEventListener('click', commitMove);
        grid.appendChild(numberCell);
      }

      const cardCells = [];
      if (isParticipant) {
        cardCells.push({ title: 'Статус этапа', value: getStageLabel(getParticipantStage(item)) });
        cardCells.push(...cells);
      } else if (item.type === 'award_block') {
        const award = normalizeAwardBlockSettings(item);
        const serviceFlags = [
          award.include_results_time ? 'есть подведение итогов' : 'без подведения итогов',
          award.include_rehearsal_time ? 'есть репетиции' : 'без репетиций',
          award.parallel_results_and_rehearsal ? 'параллельно' : 'последовательно',
        ].join(', ');
        cardCells.push(
          { title: 'Тип блока', value: 'Награждение' },
          { title: 'Длительность награждения', value: `${award.award_duration_minutes} мин.` },
          { title: 'Дополнительно', value: serviceFlags },
        );
      } else if (item.type === 'break_block') {
        const block = normalizeBreakBlockSettings(item);
        const rehearsalMinutes = block.add_rehearsal_during_break ? Math.max(0, block.break_duration_minutes - 5) : 0;
        cardCells.push(
          { title: 'Тип блока', value: 'Перерыв' },
          { title: 'Длительность', value: `${block.break_duration_minutes} мин.` },
          { title: 'Репетиция во время перерыва', value: block.add_rehearsal_during_break ? `${rehearsalMinutes} мин.` : 'нет' },
        );
      }
      cardCells.forEach((cell) => {
        const cellEl = document.createElement('div');
        cellEl.className = `preview-cell${cell.hasConflict ? ' preview-cell-conflict' : ''}`;
        cellEl.innerHTML = `
          <div class="preview-cell-title">${esc(cell.title)}</div>
          <div class="preview-cell-value${isExpanded ? '' : ' preview-cell-clamp'}">${esc(cell.value)}</div>
          ${cell.hasConflict ? '<div class="preview-conflict-badge">Конфликт значений</div>' : ''}
        `;
        grid.appendChild(cellEl);
      });

      card.appendChild(rowTop);
      card.appendChild(grid);

      if (isExpanded && isParticipant) {
        const extra = document.createElement('div');
        extra.className = 'preview-extra-block';
        const remaining = headers
          .map((header, headerIndex) => ({ header, value: (row[headerIndex] ?? '').toString().trim(), headerIndex }))
          .filter((field) => !usedIndexes.has(field.headerIndex) && field.value);
        const conflictDetails = cells.filter((cell) => cell.hasConflict);
        extra.innerHTML = `
          ${conflictDetails.length ? `
            <h3 class="preview-extra-title">Конфликты тегов</h3>
            <div class="preview-conflict-list">
              ${conflictDetails.map((cell) => `
                <div class="preview-conflict-item">
                  <div class="preview-conflict-tag">${esc(cell.title)}</div>
                  ${cell.sourceValues.map((valueItem) => `
                    <div class="preview-conflict-source">
                      <span class="preview-conflict-col">${esc(valueItem.header)}</span>
                      <span class="preview-conflict-val">${esc(valueItem.value)}</span>
                    </div>
                  `).join('')}
                </div>
              `).join('')}
            </div>
          ` : ''}
          <h3 class="preview-extra-title">Дополнительные поля</h3>
          <div class="preview-extra-grid">
            ${remaining.length
              ? remaining.map((field) => `
                <div class="preview-extra-row">
                  <div class="preview-extra-key">${esc(field.header)}</div>
                  <div class="preview-extra-value">${esc(field.value)}</div>
                </div>
              `).join('')
              : '<div class="hint">Дополнительных данных нет.</div>'}
          </div>
        `;

        const currentStage = getParticipantStage(item);
        const stageSelectWrap = document.createElement('label');
        stageSelectWrap.className = 'hint';
        stageSelectWrap.innerHTML = `
          Статус этапа:
          <select class="input" data-stage-select="1">
            <option value="" ${currentStage ? '' : 'selected'}>Не распределено</option>
            <option value="onsite" ${currentStage === 'onsite' ? 'selected' : ''}>Очный этап</option>
            <option value="remote" ${currentStage === 'remote' ? 'selected' : ''}>Заочный этап</option>
          </select>
        `;
        stageSelectWrap.querySelector('select')?.addEventListener('change', (event) => {
          sequenceItems[index] = { ...item, stageStatus: event.target.value || null };
          queueSequenceSave();
          renderPreview();
        });
        extra.prepend(stageSelectWrap);

        if (isEditing) {
          const edits = item.editedFields && typeof item.editedFields === 'object' ? item.editedFields : {};
          const editForm = document.createElement('div');
          editForm.className = 'preview-block-form-grid';
          const mainRows = editableFieldSpecs.map((spec) => {
            const value = (typeof edits[spec.key] === 'string' ? edits[spec.key] : getMappedValueByMatchers(row, spec.matchers)) || '';
            return `<label>${esc(spec.label)}<input type="text" class="input" data-edit-field="${esc(spec.key)}" value="${esc(value)}"/></label>`;
          }).join('');
          const extraRows = headers
            .map((header, headerIndex) => ({ header, value: (row[headerIndex] ?? '').toString().trim(), headerIndex }))
            .filter((field) => !usedIndexes.has(field.headerIndex))
            .map((field) => {
              const v = edits.extra && typeof edits.extra[field.header] === 'string' ? edits.extra[field.header] : field.value;
              return `<label>${esc(field.header)}<input type="text" class="input" data-extra-header="${esc(field.header)}" value="${esc(v || '')}"/></label>`;
            }).join('');
          editForm.innerHTML = `
            <h3 class="preview-extra-title">Редактирование участника</h3>
            ${mainRows}
            ${extraRows}
            <div>
              <button type="button" class="btn btn-primary btn-small" data-action="save-edit">Сохранить</button>
              <button type="button" class="btn btn-secondary btn-small" data-action="cancel-edit">Отмена</button>
            </div>
          `;
          editForm.querySelector('[data-action="save-edit"]')?.addEventListener('click', () => {
            const nextEdits = { ...edits, extra: { ...(edits.extra || {}) } };
            editForm.querySelectorAll('[data-edit-field]').forEach((inputEl) => {
              nextEdits[inputEl.dataset.editField] = (inputEl.value || '').trim();
            });
            editForm.querySelectorAll('[data-extra-header]').forEach((inputEl) => {
              nextEdits.extra[inputEl.dataset.extraHeader] = (inputEl.value || '').trim();
            });
            sequenceItems[index] = { ...item, editedFields: nextEdits, isEditing: false };
            queueSequenceSave();
            renderPreview();
          });
          editForm.querySelector('[data-action="cancel-edit"]')?.addEventListener('click', () => setItemEditing(item.id, false));
          extra.prepend(editForm);
        }

        card.appendChild(extra);
      }

      if (isExpanded && item.type === 'award_block') {
        const settings = readDocumentationSettingsFromForm();
        const minStart = getLastEndMinutesBeforeIndex(index, settings);
        const award = normalizeAwardBlockSettings(item, minStart);
        const showParallelToggle = award.include_results_time && award.include_rehearsal_time;
        const resultsStart = Math.max(minStart, award.results_start_minutes);
        const rehearsalStart = Math.max(minStart, award.rehearsal_start_minutes);
        const resultsFieldsClass = award.include_results_time ? '' : ' is-hidden';
        const rehearsalFieldsClass = award.include_rehearsal_time ? '' : ' is-hidden';
        const parallelFieldClass = showParallelToggle ? '' : ' is-hidden';
        const extra = document.createElement('div');
        extra.className = 'preview-extra-block';
        extra.innerHTML = `
          <div class="preview-block-form-grid">
            <label><input type="checkbox" data-award-checkbox="include_results_time" ${award.include_results_time ? 'checked' : ''}/> Добавить время для подведения итогов</label>
            <label><input type="checkbox" data-award-checkbox="include_rehearsal_time" ${award.include_rehearsal_time ? 'checked' : ''}/> Добавить время для репетиций</label>
            <label class="preview-conditional-row${parallelFieldClass}"><input type="checkbox" data-award-checkbox="parallel_results_and_rehearsal" ${award.parallel_results_and_rehearsal ? 'checked' : ''}/> Подведение итогов и репетиции идут параллельно</label>
            <label>Награждение, мин. <input type="number" min="1" step="1" data-award-input="award_duration_minutes" value="${award.award_duration_minutes}"/></label>
            <label class="preview-conditional-row${resultsFieldsClass}">Старт подведения итогов <input type="time" data-award-time="results_start_minutes" value="${formatMinutesToClock(resultsStart)}"/></label>
            <label class="preview-conditional-row${resultsFieldsClass}">Длительность подведения итогов, мин. <input type="number" min="1" step="1" data-award-input="results_duration_minutes" value="${award.results_duration_minutes}"/></label>
            <label class="preview-conditional-row${rehearsalFieldsClass}">Старт репетиций <input type="time" data-award-time="rehearsal_start_minutes" value="${formatMinutesToClock(rehearsalStart)}"/></label>
            <label class="preview-conditional-row${rehearsalFieldsClass}">Длительность репетиций, мин. <input type="number" min="1" step="1" data-award-input="rehearsal_duration_minutes" value="${award.rehearsal_duration_minutes}"/></label>
          </div>
          <div class="hint">Ранний старт недоступен: не раньше ${formatMinutesToClock(minStart)} (окончание предыдущего номера).</div>
        `;
        extra.querySelectorAll('input').forEach((inputEl) => {
          inputEl.addEventListener('change', () => {
            if (inputEl.dataset.awardCheckbox) award[inputEl.dataset.awardCheckbox] = inputEl.checked;
            if (inputEl.dataset.awardInput) award[inputEl.dataset.awardInput] = Math.max(1, Number(inputEl.value || 1) || 1);
            if (inputEl.dataset.awardTime) {
              const nextMinutes = parseClockToMinutes(inputEl.value);
              award[inputEl.dataset.awardTime] = Math.max(minStart, Number.isFinite(nextMinutes) ? nextMinutes : minStart);
              inputEl.value = formatMinutesToClock(award[inputEl.dataset.awardTime]);
            }
            if (!(award.include_results_time && award.include_rehearsal_time)) {
              award.parallel_results_and_rehearsal = false;
            }
            sequenceItems[index] = normalizeAwardBlockSettings(award, minStart);
            queueSequenceSave();
            renderPreview();
          });
        });
        card.appendChild(extra);
      }

      if (isExpanded && item.type === 'break_block') {
        const block = normalizeBreakBlockSettings(item);
        const rehearsalMinutes = block.add_rehearsal_during_break ? Math.max(0, block.break_duration_minutes - 5) : 0;
        const extra = document.createElement('div');
        extra.className = 'preview-extra-block';
        extra.innerHTML = `
          <div class="preview-block-form-grid">
            <label>Длительность перерыва, мин. <input type="number" min="1" step="1" data-break-input="break_duration_minutes" value="${block.break_duration_minutes}"/></label>
            <label><input type="checkbox" data-break-checkbox="add_rehearsal_during_break" ${block.add_rehearsal_during_break ? 'checked' : ''}/> Добавить репетицию на время перерыва</label>
            <div class="hint">Репетиция во время перерыва: ${rehearsalMinutes} мин. (последние 5 минут — резерв).</div>
          </div>
        `;
        extra.querySelectorAll('input').forEach((inputEl) => {
          inputEl.addEventListener('change', () => {
            if (inputEl.dataset.breakCheckbox) block[inputEl.dataset.breakCheckbox] = inputEl.checked;
            if (inputEl.dataset.breakInput) block[inputEl.dataset.breakInput] = Math.max(1, Number(inputEl.value || 1) || 1);
            sequenceItems[index] = normalizeBreakBlockSettings(block);
            queueSequenceSave();
            renderPreview();
          });
        });
        card.appendChild(extra);
      }

      if (isParticipant) {
        card.addEventListener('contextmenu', (event) => {
          const inNumberArea = event.target?.closest?.('[data-no-context="1"]');
          if (inNumberArea) return;
          event.preventDefault();
          openContextMenu(event.clientX, event.clientY, item.id);
        });
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
    const competitionStart = parseClockToMinutes(settings.competition_start) ?? 600;
    let cursor = competitionStart;
    const blocks = [];
    let onsiteCounter = 0;

    sequenceItems.forEach((item) => {
      if (item.type === 'participant') {
        if (getParticipantStage(item) !== 'onsite') return;
        onsiteCounter += 1;
        const row = buildEffectiveRow(previewRowsData[item.rowRef - 1] || [], item);
        const numberTitle = getMappedValueByMatchers(row, ['название номера', 'навание номреа', 'номер']) || 'Без названия номера';
        const fio = getMappedValueByMatchers(row, ['участник', 'фио']);
        const team = getMappedValueByMatchers(row, ['коллектив']);
        const rawDuration = getMappedValueByMatchers(row, ['время исполнения', 'продолжительность']);
        const durationSeconds = parseDurationToSeconds(rawDuration, settings.default_duration_minutes);
        const person = fio && team ? `${fio}, ${team}` : (fio || team || 'Участник');
        blocks.push({
          type: 'participant',
          start: cursor,
          end: cursor + (durationSeconds / 60),
          order: onsiteCounter,
          text: `№${onsiteCounter}. «${numberTitle}» — ${person} (${formatDurationLabel(durationSeconds)})`,
        });
        cursor += durationSeconds / 60;
        return;
      }
      if (item.type === 'break_block') {
        const block = normalizeBreakBlockSettings(item);
        const rehearsalMinutes = block.add_rehearsal_during_break ? Math.max(0, block.break_duration_minutes - 5) : 0;
        blocks.push({
          type: 'service',
          start: cursor,
          end: cursor + block.break_duration_minutes,
          text: rehearsalMinutes > 0
            ? `Перерыв (${block.break_duration_minutes} мин), репетиция ${rehearsalMinutes} мин`
            : `Перерыв (${block.break_duration_minutes} мин)`,
        });
        cursor += block.break_duration_minutes;
        return;
      }
      if (item.type === 'award_block') {
        const award = normalizeAwardBlockSettings(item, cursor);
        if (award.include_results_time && award.include_rehearsal_time && award.parallel_results_and_rehearsal) {
          const start = Math.max(cursor, Math.min(award.results_start_minutes, award.rehearsal_start_minutes));
          const end = Math.max(award.results_start_minutes + award.results_duration_minutes, award.rehearsal_start_minutes + award.rehearsal_duration_minutes);
          blocks.push({ type: 'parallel_service', start, end, text: 'Параллельно: подведение итогов и репетиции' });
          cursor = Math.max(cursor, end);
        } else {
          if (award.include_results_time) {
            const start = Math.max(cursor, award.results_start_minutes);
            const end = start + award.results_duration_minutes;
            blocks.push({ type: 'service', start, end, text: 'Подведение итогов' });
            cursor = Math.max(cursor, end);
          }
          if (award.include_rehearsal_time) {
            const start = Math.max(cursor, award.rehearsal_start_minutes);
            const end = start + award.rehearsal_duration_minutes;
            blocks.push({ type: 'service', start, end, text: 'Репетиции' });
            cursor = Math.max(cursor, end);
          }
        }
        blocks.push({ type: 'service', start: cursor, end: cursor + award.award_duration_minutes, text: 'Награждение' });
        cursor += award.award_duration_minutes;
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
      if (block.type === 'service' || block.type === 'parallel_service') {
        parts.push(`<div class="doc-preview-service">${esc(formatMinutesToClock(block.start))}–${esc(formatMinutesToClock(block.end))} — ${esc(block.text)}</div>`);
        return;
      }
      if (block.type === 'participant') {
        parts.push(`<div class="doc-preview-nomination">${esc(formatMinutesToClock(block.start))}–${esc(formatMinutesToClock(block.end))} ${esc(block.text)}</div>`);
      }
    });
    docProgramPreviewEl.innerHTML = parts.join('');
  }

  function openContextMenu(x, y, targetId) {
    closeContextMenu();
    contextMenuTargetId = targetId;
    const item = getSequenceItemById(targetId);
    if (!item || item.type !== 'participant') return;
    const menu = document.createElement('div');
    menu.className = 'preview-context-menu';
    const stage = getParticipantStage(item);
    menu.innerHTML = `
      <button data-action="delete">Удалить участника</button>
      <button data-action="edit">Редактировать участника</button>
      <button data-action="mark_onsite" ${stage === 'onsite' ? 'disabled' : ''}>Отметить участника, очного этапа</button>
      <button data-action="mark_remote" ${stage === 'remote' ? 'disabled' : ''}>Отметить участника, заочного этапа</button>
      <button data-action="mark_unset" ${!stage ? 'disabled' : ''}>Снять назначение этапа</button>
      <button data-action="add_award_after">Добавить блок награждения после выбранного участника</button>
      <button data-action="add_award_before">Добавить блок награждения до выбранного участника</button>
      <button data-action="add_break_before">Добавить блок перерыва до выбранного участника</button>
      <button data-action="add_break_after">Добавить блок перерыва после выбранного участника</button>
    `;
    menu.querySelectorAll('button').forEach((btn) => {
      btn.addEventListener('click', () => handleContextAction(btn.dataset.action));
    });
    document.body.appendChild(menu);
    contextMenuEl = menu;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const mw = menu.offsetWidth;
    const mh = menu.offsetHeight;
    menu.style.left = `${Math.min(x, vw - mw - 8)}px`;
    menu.style.top = `${Math.min(y, vh - mh - 8)}px`;
  }

  function insertServiceBlockNear(targetId, type, place) {
    const index = sequenceItems.findIndex((item) => item.id === targetId);
    if (index < 0) return;
    const insertIndex = place === 'before' ? index : index + 1;
    const settings = readDocumentationSettingsFromForm();
    const minStart = getLastEndMinutesBeforeIndex(insertIndex, settings);
    const nextItem = type === 'award_block'
      ? normalizeAwardBlockSettings({ id: createSequenceId('award'), type }, minStart)
      : normalizeBreakBlockSettings({ id: createSequenceId('break'), type });
    sequenceItems.splice(insertIndex, 0, nextItem);
    queueSequenceSave();
    renderPreview();
  }

  function handleContextAction(action) {
    const item = getSequenceItemById(contextMenuTargetId);
    if (!item) {
      closeContextMenu();
      return;
    }
    const index = sequenceItems.findIndex((entry) => entry.id === item.id);
    if (index < 0) {
      closeContextMenu();
      return;
    }
    if (action === 'edit') {
      setItemEditing(item.id, true);
    } else if (action === 'delete') {
      sequenceItems.splice(index, 1);
      queueSequenceSave();
      renderPreview();
    } else if (action === 'mark_onsite') {
      sequenceItems[index] = { ...item, stageStatus: 'onsite' };
      queueSequenceSave();
      renderPreview();
    } else if (action === 'mark_remote') {
      sequenceItems[index] = { ...item, stageStatus: 'remote' };
      queueSequenceSave();
      renderPreview();
    } else if (action === 'mark_unset') {
      sequenceItems[index] = { ...item, stageStatus: null };
      queueSequenceSave();
      renderPreview();
    } else if (action === 'add_award_after') {
      insertServiceBlockNear(item.id, 'award_block', 'after');
    } else if (action === 'add_award_before') {
      insertServiceBlockNear(item.id, 'award_block', 'before');
    } else if (action === 'add_break_after') {
      insertServiceBlockNear(item.id, 'break_block', 'after');
    } else if (action === 'add_break_before') {
      insertServiceBlockNear(item.id, 'break_block', 'before');
    }
    closeContextMenu();
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
    await loadSequenceState();
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

  previewCardsEl?.addEventListener('contextmenu', (event) => {
    if (!event.target.closest('.preview-row-card')) return;
    if (event.target.closest('[data-no-context="1"]')) return;
    event.preventDefault();
  });
  document.addEventListener('click', (event) => {
    if (!contextMenuEl) return;
    if (event.target.closest('.preview-context-menu')) return;
    closeContextMenu();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeContextMenu();
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
