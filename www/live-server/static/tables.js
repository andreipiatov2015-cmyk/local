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

async function apiPostBlob(url, data) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    credentials: 'same-origin',
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `HTTP ${r.status}`);
  return r;
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

function formatDateRuLong(value) {
  const text = (value || '').toString().trim();
  if (!text) return '';
  const match = text.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return text;
  const [, yRaw, mRaw, dRaw] = match;
  const year = Number(yRaw);
  const month = Number(mRaw);
  const day = Number(dRaw);
  const monthNames = [
    'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
    'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
  ];
  if (!Number.isInteger(year) || !Number.isInteger(month) || !Number.isInteger(day) || month < 1 || month > 12 || day < 1 || day > 31) {
    return text;
  }
  return `${day} ${monthNames[month - 1]} ${year} года`;
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
  const docDistributeByNominationEl = document.getElementById('docDistributeByNomination');
  const docNominationAutoDistributeEl = document.getElementById('docNominationAutoDistribute');
  const docNominationAutoRowEl = document.getElementById('docNominationAutoRow');
  const docDistributeByAgeCategoryEl = document.getElementById('docDistributeByAgeCategory');
  const docAgeAutoDistributeEl = document.getElementById('docAgeAutoDistribute');
  const docAgeAutoRowEl = document.getElementById('docAgeAutoRow');
  const docBuildProgramBtn = document.getElementById('docBuildProgram');
  const docProgramStatusEl = document.getElementById('docProgramStatus');
  const programDocCardEl = document.getElementById('programDocCard');
  const programPreviewModalEl = document.getElementById('programPreviewModal');
  const closeProgramPreviewModalEl = document.getElementById('closeProgramPreviewModal');
  const programPreviewModalBodyEl = document.getElementById('programPreviewModalBody');
  const downloadProgramDocxEl = document.getElementById('downloadProgramDocx');

  let headers = [];
  let mappingByHeaderIdx = {};
  let collapsedMappingCards = {};
  let mappingFieldTags = [];
  let mappingFieldTypes = {};
  let previewRowsData = [];
  let sequenceItems = [];
  let participantEditsByRowRef = {};
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

  function isGroupedTag(tagTitle) {
    return mappingFieldTypes?.[tagTitle] === 'grouped_choice';
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

  function getParticipantEdits(rowRef) {
    const safeRowRef = Number(rowRef || 0);
    if (!Number.isInteger(safeRowRef) || safeRowRef < 1) return {};
    const edits = participantEditsByRowRef[safeRowRef];
    return edits && typeof edits === 'object' ? edits : {};
  }

  function buildEffectiveRow(row, item) {
    const nextRow = Array.isArray(row) ? [...row] : [];
    const edits = getParticipantEdits(item?.rowRef);
    if (!edits || typeof edits !== 'object') return nextRow;
    if (edits.tags && typeof edits.tags === 'object') {
      Object.entries(mappingByHeaderIdx).forEach(([idxText, mappedTag]) => {
        const idx = Number(idxText);
        if (!Number.isInteger(idx) || idx < 0 || idx >= headers.length) return;
        const editedValue = typeof edits.tags[mappedTag] === 'string' ? edits.tags[mappedTag].trim() : null;
        if (editedValue === null) return;
        nextRow[idx] = editedValue;
      });
    }
    editableFieldSpecs.forEach((spec) => {
      const editedValue = (typeof edits[spec.key] === 'string') ? edits[spec.key].trim() : null;
      if (editedValue === null) return;
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
        const editedValue = typeof edits.extra[header] === 'string' ? edits.extra[header].trim() : null;
        if (editedValue !== null) nextRow[idx] = editedValue;
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
          isEditing: false,
        });
      }
    }
    sequenceItems = normalized;
  }

  function applyParticipantEdits(items) {
    const next = {};
    (Array.isArray(items) ? items : []).forEach((item) => {
      const rowRef = Number(item?.rowRef || 0);
      if (!Number.isInteger(rowRef) || rowRef < 1) return;
      const edits = item?.editedFields;
      if (!edits || typeof edits !== 'object') return;
      const tags = edits.tags && typeof edits.tags === 'object' ? edits.tags : {};
      const extra = edits.extra && typeof edits.extra === 'object' ? edits.extra : {};
      if (!Object.keys(tags).length && !Object.keys(extra).length) return;
      next[rowRef] = { tags, extra };
    });
    participantEditsByRowRef = next;
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
      card.className = `preview-row-card${isExpanded ? ' is-expanded' : ''}${isEditing ? ' is-editing' : ''}${item.type === 'award_block' ? ' preview-row-card-award' : ''}${item.type === 'break_block' ? ' preview-row-card-break' : ''}`;
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
        const rowEdits = getParticipantEdits(item?.rowRef);
        const editedByTag = rowEdits?.tags && typeof rowEdits.tags[cell.title] === 'string'
          ? rowEdits.tags[cell.title]
          : null;
        const editableValue = editedByTag !== null ? editedByTag : (cell.mergedValue || '');
        const isLongValue = editableValue.length > 80 || editableValue.includes('\n');
        const canEditCell = isParticipant && isEditing && !isGroupedTag(cell.title);
        cellEl.innerHTML = `
          <div class="preview-cell-title">${esc(cell.title)}</div>
          ${
            canEditCell
              ? (
                isLongValue
                  ? `<textarea class="input preview-cell-inline-input" rows="3" data-tag-field="${esc(cell.title)}">${esc(editableValue)}</textarea>`
                  : `<input class="input preview-cell-inline-input" type="text" data-tag-field="${esc(cell.title)}" value="${esc(editableValue)}" />`
              )
              : `<div class="preview-cell-value${isExpanded ? '' : ' preview-cell-clamp'}">${esc(cell.value)}</div>`
          }
          ${cell.hasConflict ? '<div class="preview-conflict-badge">Конфликт значений</div>' : ''}
        `;
        grid.appendChild(cellEl);
      });

      card.appendChild(rowTop);
      card.appendChild(grid);

      if (isExpanded && isParticipant) {
        const extra = document.createElement('div');
        extra.className = 'preview-extra-block';
        const rowEdits = getParticipantEdits(item?.rowRef);
        const remaining = headers
          .map((header, headerIndex) => ({ header, value: (row[headerIndex] ?? '').toString().trim(), headerIndex }))
          .filter((field) => !usedIndexes.has(field.headerIndex));
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
                      ${
                        isEditing
                          ? `<textarea class="input preview-extra-inline-input" rows="2" data-extra-header="${esc(valueItem.header)}">${esc((rowEdits?.extra && typeof rowEdits.extra[valueItem.header] === 'string') ? rowEdits.extra[valueItem.header] : valueItem.value)}</textarea>`
                          : `<span class="preview-conflict-val">${esc(valueItem.value)}</span>`
                      }
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
                  ${
                    isEditing
                      ? (
                        ((rowEdits?.extra && typeof rowEdits.extra[field.header] === 'string'
                          ? rowEdits.extra[field.header]
                          : field.value).length > 80)
                          ? `<textarea class="input preview-extra-inline-input" rows="2" data-extra-header="${esc(field.header)}">${esc((rowEdits?.extra && typeof rowEdits.extra[field.header] === 'string') ? rowEdits.extra[field.header] : field.value)}</textarea>`
                          : `<input class="input preview-extra-inline-input" type="text" data-extra-header="${esc(field.header)}" value="${esc((rowEdits?.extra && typeof rowEdits.extra[field.header] === 'string') ? rowEdits.extra[field.header] : field.value)}" />`
                      )
                      : `<div class="preview-extra-value">${esc(field.value)}</div>`
                  }
                </div>
              `).join('')
              : '<div class="hint">Дополнительных данных нет.</div>'}
          </div>
        `;

        const currentStage = getParticipantStage(item);
        const stageSelectWrap = document.createElement('label');
        stageSelectWrap.className = 'hint';
        stageSelectWrap.innerHTML = isEditing
          ? `
            Статус этапа:
            <select class="input" data-edit-stage="1">
              <option value="" ${currentStage ? '' : 'selected'}>Не распределено</option>
              <option value="onsite" ${currentStage === 'onsite' ? 'selected' : ''}>Очный этап</option>
              <option value="remote" ${currentStage === 'remote' ? 'selected' : ''}>Заочный этап</option>
            </select>
          `
          : `Статус этапа: ${esc(getStageLabel(currentStage))}`;
        extra.prepend(stageSelectWrap);

        if (isEditing) {
          const controls = document.createElement('div');
          controls.className = 'preview-edit-controls';
          controls.innerHTML = `
            <button type="button" class="btn btn-primary btn-small" data-action="save-edit">Сохранить</button>
            <button type="button" class="btn btn-secondary btn-small" data-action="cancel-edit">Отмена</button>
          `;
          controls.querySelector('[data-action="save-edit"]')?.addEventListener('click', async () => {
            const rawRow = previewRowsData[(item.rowRef || 1) - 1] || [];
            const nextTags = {};
            card.querySelectorAll('[data-tag-field]').forEach((inputEl) => {
              const key = inputEl.dataset.tagField;
              if (!key || isGroupedTag(key)) return;
              nextTags[key] = (inputEl.value || '').trim();
            });
            const nextExtra = {};
            card.querySelectorAll('[data-extra-header]').forEach((inputEl) => {
              const key = inputEl.dataset.extraHeader;
              if (!key) return;
              nextExtra[key] = (inputEl.value || '').trim();
            });

            const baseByTag = {};
            normalizeRowByTags(rawRow).cells.forEach((cell) => {
              baseByTag[cell.title] = (cell.mergedValue || '').trim();
            });
            const baseByHeader = {};
            headers.forEach((header, idx) => {
              baseByHeader[header] = (rawRow[idx] ?? '').toString().trim();
            });

            const changedTags = {};
            Object.entries(nextTags).forEach(([tag, value]) => {
              if (value !== (baseByTag[tag] || '')) changedTags[tag] = value;
            });
            const changedExtra = {};
            Object.entries(nextExtra).forEach(([header, value]) => {
              if (value !== (baseByHeader[header] || '')) changedExtra[header] = value;
            });

            const stageSelect = card.querySelector('[data-edit-stage]');
            const nextStage = stageSelect ? (stageSelect.value || null) : getParticipantStage(item);
            const stageChanged = nextStage !== getParticipantStage(item);
            const hasDiff = Object.keys(changedTags).length > 0 || Object.keys(changedExtra).length > 0;
            const rowRef = item.rowRef;

            try {
              if (hasDiff) {
                await apiPostJson(`/api/tables/${tableId}/participant/${rowRef}/edit`, {
                  changed_tags: changedTags,
                  changed_extra: changedExtra,
                });
                participantEditsByRowRef[rowRef] = { tags: changedTags, extra: changedExtra };
              } else if (participantEditsByRowRef[rowRef]) {
                delete participantEditsByRowRef[rowRef];
              }
              sequenceItems[index] = {
                ...item,
                stageStatus: nextStage,
                isEditing: false,
              };
              if (stageChanged) queueSequenceSave();
              renderPreview();
            } catch (e) {
              setStatus(uploadStatusEl, `Не удалось сохранить участника: ${e.message}`, 'warning');
            }
          });
          controls.querySelector('[data-action="cancel-edit"]')?.addEventListener('click', () => setItemEditing(item.id, false));
          extra.appendChild(controls);
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

  function getMappedValueByPreferredTag(row, preferredTags, fallbackMatchers = []) {
    const preferredNorm = (preferredTags || []).map((item) => normalizeHeaderLikeBackend(item));
    for (const [idxText, mappedTag] of Object.entries(mappingByHeaderIdx)) {
      const idx = Number(idxText);
      const tagNorm = normalizeHeaderLikeBackend(mappedTag);
      if (!preferredNorm.includes(tagNorm)) continue;
      return {
        value: (row[idx] ?? '').toString().trim(),
        foundPreferredTag: true,
      };
    }
    return {
      value: getMappedValueByMatchers(row, fallbackMatchers),
      foundPreferredTag: false,
    };
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
      distribute_by_nomination: Boolean(docDistributeByNominationEl?.checked),
      distribute_by_age_category: Boolean(docDistributeByAgeCategoryEl?.checked),
      nomination_auto_distribute: Boolean(docNominationAutoDistributeEl?.checked),
      age_auto_distribute: Boolean(docAgeAutoDistributeEl?.checked),
      age_order: documentationState?.settings?.age_order || [],
      nomination_order: documentationState?.settings?.nomination_order || {},
    };
  }

  function syncDocumentationAdvancedControls() {
    if (docNominationAutoRowEl) {
      docNominationAutoRowEl.classList.toggle('is-hidden', !docDistributeByNominationEl?.checked);
    }
    if (!docDistributeByNominationEl?.checked && docNominationAutoDistributeEl) {
      docNominationAutoDistributeEl.checked = false;
    }
    if (docAgeAutoRowEl) {
      docAgeAutoRowEl.classList.toggle('is-hidden', !docDistributeByAgeCategoryEl?.checked);
    }
    if (!docDistributeByAgeCategoryEl?.checked && docAgeAutoDistributeEl) {
      docAgeAutoDistributeEl.checked = false;
    }
  }

  function applyDocumentationSettingsToForm(settings = {}) {
    if (docEventDateEl) docEventDateEl.value = settings.event_date || '';
    if (docRehearsalStartEl) docRehearsalStartEl.value = settings.rehearsal_start || '09:00';
    if (docCompetitionStartEl) docCompetitionStartEl.value = settings.competition_start || '10:00';
    if (docResultsMinutesEl) docResultsMinutesEl.value = settings.results_minutes ?? 20;
    if (docAwardMinutesEl) docAwardMinutesEl.value = settings.award_minutes ?? 15;
    if (docTechIntervalMinutesEl) docTechIntervalMinutesEl.value = settings.tech_interval_minutes ?? 20;
    if (docDefaultDurationMinutesEl) docDefaultDurationMinutesEl.value = settings.default_duration_minutes ?? 3;
    if (docDistributeByNominationEl) docDistributeByNominationEl.checked = Boolean(settings.distribute_by_nomination);
    if (docDistributeByAgeCategoryEl) docDistributeByAgeCategoryEl.checked = Boolean(settings.distribute_by_age_category);
    if (docNominationAutoDistributeEl) docNominationAutoDistributeEl.checked = Boolean(settings.nomination_auto_distribute);
    if (docAgeAutoDistributeEl) docAgeAutoDistributeEl.checked = Boolean(settings.age_auto_distribute);
    syncDocumentationAdvancedControls();
  }

  function groupParticipantsByKey(items, keyName) {
    const groups = new Map();
    const order = [];
    items.forEach((item) => {
      const key = (item?.[keyName] || '').trim() || 'Без категории';
      if (!groups.has(key)) {
        groups.set(key, []);
        order.push(key);
      }
      groups.get(key).push(item);
    });
    return order.map((key) => ({ key, items: groups.get(key) || [] }));
  }

  function normalizeSpacing(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function normalizeQuotes(value) {
    const cleaned = normalizeSpacing(value).replace(/[«»„“”‟"']/g, '').trim();
    return cleaned ? `«${cleaned}»` : '';
  }

  function toSimpleTitleCase(value) {
    const normalized = normalizeSpacing(value);
    if (!normalized) return '';
    return normalized
      .toLowerCase()
      .replace(/(^|[\s\-–—()])([\p{L}])/gu, (match, prefix, letter) => `${prefix}${letter.toUpperCase()}`);
  }

  function buildParticipantText(order, item) {
    const quotedTitle = normalizeQuotes(item.numberTitle || 'Без названия номера') || '«Без названия номера»';
    const performer = normalizeSpacing(item.performer || 'Участник');
    const institution = toSimpleTitleCase(item.institution || 'Учреждение не указано') || 'Учреждение не указано';
    const municipality = normalizeSpacing(item.municipality || 'Муниципалитет не указан') || 'Муниципалитет не указан';
    return `№${order}. ${quotedTitle} - ${performer}, ${institution}, ${municipality}`;
  }

  function renderParticipantHtml(start, end, text) {
    const timePart = `${esc(formatMinutesToClock(start))}–${esc(formatMinutesToClock(end))}`;
    const match = String(text || '').match(/^\s*(№\s*\d+\.)\s*(«[^»]+»)(.*)$/);
    if (!match) {
      return `${timePart} ${esc(text || '')}`;
    }
    const tail = match[3] || '';
    return `${timePart} <strong>${esc(match[1])}</strong> <strong>${esc(match[2])}</strong>${esc(tail)}`;
  }

  function buildProgramPreviewData(settings) {
    const competitionStart = parseClockToMinutes(settings.competition_start) ?? 600;
    let cursor = competitionStart;
    const participants = [];
    const serviceBlocks = [];
    let onsiteCounter = 0;

    sequenceItems.forEach((item) => {
      if (item.type === 'participant') {
        if (getParticipantStage(item) !== 'onsite') return;
        onsiteCounter += 1;
        const row = buildEffectiveRow(previewRowsData[item.rowRef - 1] || [], item);
        const numberTitle = getMappedValueByMatchers(row, ['название номера', 'навание номреа', 'номер']) || 'Без названия номера';
        const fio = getMappedValueByMatchers(row, ['список участников', 'участник', 'фио']);
        const team = getMappedValueByMatchers(row, ['название коллектива', 'коллектив']);
        const institutionResolved = getMappedValueByPreferredTag(
          row,
          ['полное название учередения', 'полное название учереждения', 'полное название учреждения'],
        );
        const fullInstitution = institutionResolved.value;
        const municipality = getMappedValueByMatchers(row, ['муниципалитет']);
        const nomination = getMappedValueByMatchers(row, ['номинация']) || 'Без номинации';
        const ageCategory = getMappedValueByMatchers(row, ['возрастная категория', 'возрастная кат', 'категория возраста', 'возраст']) || 'Без возрастной категории';
        const rawDuration = getMappedValueByMatchers(row, ['время исполнения', 'продолжительность']);
        const durationSeconds = parseDurationToSeconds(rawDuration, settings.default_duration_minutes);
        const performer = fio || team || 'Участник';
        participants.push({
          type: 'participant',
          start: cursor,
          end: cursor + (durationSeconds / 60),
          numberTitle,
          performer,
          institution: fullInstitution,
          municipality,
          durationSeconds,
          nomination,
          ageCategory,
        });
        cursor += durationSeconds / 60;
        return;
      }
      if (item.type === 'break_block') {
        const block = normalizeBreakBlockSettings(item);
        const rehearsalMinutes = block.add_rehearsal_during_break ? Math.max(0, block.break_duration_minutes - 5) : 0;
        serviceBlocks.push({
          type: 'service',
          start: cursor,
          end: cursor + block.break_duration_minutes,
          text: rehearsalMinutes > 0
            ? `Перерыв — ${block.break_duration_minutes} минут; репетиции — ${rehearsalMinutes} минут`
            : `Перерыв — ${block.break_duration_minutes} минут`,
        });
        cursor += block.break_duration_minutes;
        return;
      }
      if (item.type === 'award_block') {
        const award = normalizeAwardBlockSettings(item, cursor);
        if (award.include_results_time && award.include_rehearsal_time && award.parallel_results_and_rehearsal) {
          const start = Math.max(cursor, Math.min(award.results_start_minutes, award.rehearsal_start_minutes));
          const end = Math.max(award.results_start_minutes + award.results_duration_minutes, award.rehearsal_start_minutes + award.rehearsal_duration_minutes);
          serviceBlocks.push({ type: 'parallel_service', start, end, text: 'Параллельно: подведение итогов и репетиции' });
          cursor = Math.max(cursor, end);
        } else {
          if (award.include_results_time) {
            const start = Math.max(cursor, award.results_start_minutes);
            const end = start + award.results_duration_minutes;
            serviceBlocks.push({ type: 'service', start, end, text: 'Подведение итогов' });
            cursor = Math.max(cursor, end);
          }
          if (award.include_rehearsal_time) {
            const start = Math.max(cursor, award.rehearsal_start_minutes);
            const end = start + award.rehearsal_duration_minutes;
            serviceBlocks.push({ type: 'service', start, end, text: 'Репетиция' });
            cursor = Math.max(cursor, end);
          }
        }
        serviceBlocks.push({ type: 'service', start: cursor, end: cursor + award.award_duration_minutes, text: 'Награждение' });
        cursor += award.award_duration_minutes;
      }
    });

    const byNomination = Boolean(settings.distribute_by_nomination);
    const byAge = Boolean(settings.distribute_by_age_category);
    const byNominationAuto = byNomination && Boolean(settings.nomination_auto_distribute);
    const byAgeAuto = byAge && Boolean(settings.age_auto_distribute);

    let participantGroups = [{ items: participants }];
    if (byAgeAuto) {
      participantGroups = groupParticipantsByKey(participants, 'ageCategory')
        .map((group) => ({ age: group.key, items: group.items }));
    }
    if (byNominationAuto) {
      participantGroups = participantGroups.flatMap((group) => groupParticipantsByKey(group.items, 'nomination')
        .map((nomGroup) => ({ ...group, nomination: nomGroup.key, items: nomGroup.items })));
    }

    const participantBlocks = [];
    let docOrder = 0;
    participantGroups.forEach((group) => {
      const groupItems = group.items || [];
      if (!groupItems.length) return;
      if (byAgeAuto && group.age) {
        participantBlocks.push({
          type: 'age_header',
          start: groupItems[0].start,
          text: `${formatMinutesToClock(groupItems[0].start)} Возрастная категория: ${group.age}`,
        });
      }
      if (byNominationAuto && group.nomination) {
        participantBlocks.push({
          type: 'nomination_header',
          start: groupItems[0].start,
          text: `Номинация: ${normalizeQuotes(group.nomination) || '«Без номинации»'}`,
        });
      }
      groupItems.forEach((item) => {
        if (byAge && !byAgeAuto) {
          participantBlocks.push({
            type: 'age_header',
            start: item.start,
            text: `${formatMinutesToClock(item.start)} Возрастная категория: ${item.ageCategory}`,
          });
        }
        if (byNomination && !byNominationAuto) {
          participantBlocks.push({
            type: 'nomination_header',
            start: item.start,
            text: `Номинация: ${normalizeQuotes(item.nomination) || '«Без номинации»'}`,
          });
        }
        if (byAge && byNomination && byAgeAuto && !byNominationAuto) {
          participantBlocks.push({
            type: 'nomination_header',
            start: item.start,
            text: `Номинация: ${normalizeQuotes(item.nomination) || '«Без номинации»'}`,
          });
        }
        docOrder += 1;
        participantBlocks.push({
          type: 'participant',
          start: item.start,
          end: item.end,
          order: docOrder,
          text: buildParticipantText(docOrder, item),
        });
      });
    });

    const blockPriority = {
      age_header: 1,
      nomination_header: 2,
      service: 3,
      parallel_service: 3,
      participant: 4,
    };
    const blocks = [...serviceBlocks, ...participantBlocks]
      .map((block, idx) => ({ ...block, __idx: idx }))
      .sort((a, b) => {
        const startDiff = (Number(a.start) || 0) - (Number(b.start) || 0);
        if (startDiff !== 0) return startDiff;
        const priorityDiff = (blockPriority[a.type] || 99) - (blockPriority[b.type] || 99);
        if (priorityDiff !== 0) return priorityDiff;
        return a.__idx - b.__idx;
      })
      .map(({ __idx, ...rest }) => rest);

    return {
      title: 'Программа конкурса',
      date: settings.event_date || '',
      rehearsal_start: settings.rehearsal_start || '',
      blocks,
    };
  }

  function renderDocumentationPreview(program, containerEl) {
    if (!containerEl) return;
    if (!program || !Array.isArray(program.blocks) || !program.blocks.length) {
      containerEl.classList.add('is-empty');
      containerEl.innerHTML = '<div>Программа пока не сформирована. Нажмите «Сформировать программу».</div>';
      return;
    }
    containerEl.classList.remove('is-empty');
    const formattedDate = formatDateRuLong(program.date || '');
    const parts = [
      `<div class="doc-preview-title">${esc(program.title || 'Программа конкурса')}</div>`,
      `<div class="doc-preview-date">${esc(formattedDate || 'Дата не указана')}</div>`,
      `<div class="doc-preview-rehearsal">Репетиции: ${esc(program.rehearsal_start || '—')}</div>`,
    ];
    program.blocks.forEach((block) => {
      if (block.type === 'service' || block.type === 'parallel_service') {
        parts.push(`<div class="doc-preview-service">${esc(formatMinutesToClock(block.start))}–${esc(formatMinutesToClock(block.end))} — ${esc(block.text)}</div>`);
        return;
      }
      if (block.type === 'participant') {
        parts.push(`<div class="doc-preview-nomination">${renderParticipantHtml(block.start, block.end, block.text)}</div>`);
        return;
      }
      if (block.type === 'nomination_header') {
        parts.push(`<div class="doc-preview-nomination-header">${esc(block.text)}</div>`);
        return;
      }
      if (block.type === 'age_header') {
        parts.push(`<div class="doc-preview-age-header">${esc(block.text)}</div>`);
      }
    });
    containerEl.innerHTML = parts.join('');
  }

  function openProgramPreviewModal() {
    if (!programPreviewModalEl) return;
    const settings = readDocumentationSettingsFromForm();
    const program = buildProgramPreviewData(settings);
    documentationState = { settings, program };
    renderDocumentationPreview(program, programPreviewModalBodyEl);
    programPreviewModalEl.classList.add('visible');
    programPreviewModalEl.setAttribute('aria-hidden', 'false');
  }

  function closeProgramPreviewModal() {
    if (!programPreviewModalEl) return;
    programPreviewModalEl.classList.remove('visible');
    programPreviewModalEl.setAttribute('aria-hidden', 'true');
  }

  async function downloadProgramDocx() {
    if (!previewRowsData.length) {
      setStatus(docProgramStatusEl, 'Нет данных таблицы для формирования программы.', 'warning');
      return;
    }
    try {
      const settings = readDocumentationSettingsFromForm();
      const program = buildProgramPreviewData(settings);
      const state = { settings, program };
      documentationState = state;
      await saveDocumentationState(state);
      const response = await apiPostBlob(`/api/tables/${tableId}/documentation/program/docx`, state);
      const blob = await response.blob();
      const disposition = response.headers.get('Content-Disposition') || '';
      const match = disposition.match(/filename\*?=(?:UTF-8''|")?([^\";]+)/i);
      const rawName = match ? decodeURIComponent(match[1].replace(/"/g, '').trim()) : 'program.docx';
      const filename = rawName.endsWith('.docx') ? rawName : `${rawName}.docx`;
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      setStatus(docProgramStatusEl, 'DOCX сформирован и скачан.', 'success');
    } catch (e) {
      setStatus(docProgramStatusEl, `Ошибка скачивания DOCX: ${e.message}`, 'error');
    }
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
      distribute_by_nomination: false,
      distribute_by_age_category: false,
      nomination_auto_distribute: false,
      age_auto_distribute: false,
      age_order: [],
      nomination_order: {},
    };
    applyDocumentationSettingsToForm(settings);
    renderDocumentationPreview(documentationState.program, programPreviewModalBodyEl);
  }

  function isAutoDetectedMapping(header, selectedTag) {
    if (!header || !selectedTag) return false;
    const tagNorm = normalizeHeaderLikeBackend(selectedTag);
    const headerNorm = normalizeHeaderLikeBackend(header);
    return Boolean(tagNorm && headerNorm && (tagNorm.includes(headerNorm) || headerNorm.includes(tagNorm)));
  }

  function renderMapping(fieldTags) {
    mappingListEl.innerHTML = '';
    mappingFieldTags = Array.isArray(fieldTags) ? fieldTags : [];
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
      select.innerHTML = '<option value="">не выбрано</option>' + mappingFieldTags.map((fieldTag) => {
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
        renderMapping(mappingFieldTags);
      });

      const toggleBtn = document.createElement('button');
      toggleBtn.type = 'button';
      toggleBtn.className = 'mapping-toggle-btn';
      toggleBtn.title = isCollapsed ? 'Развернуть карточку' : 'Свернуть карточку';
      toggleBtn.textContent = isCollapsed ? '▼' : '▲';
      toggleBtn.addEventListener('click', () => {
        collapsedMappingCards[headerIndex] = !collapsedMappingCards[headerIndex];
        renderMapping(mappingFieldTags);
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
    const [table, preview, mapResp, participantEditsResp] = await Promise.all([
      apiGet(`/api/tables/${tableId}`),
      apiGet(`/api/tables/${tableId}/excel_preview`),
      apiGet(`/api/tables/${tableId}/mapping`),
      apiGet(`/api/tables/${tableId}/participant-edits`),
    ]);
    titleEl.textContent = table.title || `Таблица #${tableId}`;
    headers = preview.headers || [];
    const nextMappingByHeader = {};
    (mapResp.mapping_rows || []).forEach((item) => {
      if (!item || typeof item.excel_column_index !== 'number' || !item.field_tag) return;
      nextMappingByHeader[item.excel_column_index] = item.field_tag;
    });
    mappingByHeaderIdx = nextMappingByHeader;
    mappingFieldTypes = mapResp.field_tag_types || {};
    previewRowsData = preview.rows || [];
    applyParticipantEdits(participantEditsResp?.items || []);
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
    if (event.key === 'Escape') {
      closeContextMenu();
      closeProgramPreviewModal();
    }
  });

  docBuildProgramBtn?.addEventListener('click', async () => {
    try {
      if (!previewRowsData.length) {
        setStatus(docProgramStatusEl, 'Нет данных таблицы для формирования программы.', 'warning');
        renderDocumentationPreview(null, programPreviewModalBodyEl);
        return;
      }
      const settings = readDocumentationSettingsFromForm();
      const program = buildProgramPreviewData(settings);
      const state = { settings, program };
      documentationState = state;
      renderDocumentationPreview(program, programPreviewModalBodyEl);
      await saveDocumentationState(state);
      setStatus(docProgramStatusEl, 'Программа сформирована и сохранена.', 'success');
    } catch (e) {
      setStatus(docProgramStatusEl, `Ошибка формирования: ${e.message}`, 'error');
    }
  });

  [docDistributeByNominationEl, docDistributeByAgeCategoryEl].forEach((el) => {
    el?.addEventListener('change', () => {
      syncDocumentationAdvancedControls();
    });
  });

  programDocCardEl?.addEventListener('click', openProgramPreviewModal);
  closeProgramPreviewModalEl?.addEventListener('click', closeProgramPreviewModal);
  downloadProgramDocxEl?.addEventListener('click', downloadProgramDocx);
  programPreviewModalEl?.addEventListener('click', (event) => {
    if (event.target === programPreviewModalEl) closeProgramPreviewModal();
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
