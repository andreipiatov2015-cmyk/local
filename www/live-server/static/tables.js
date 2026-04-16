let currentTableId = null;
let currentHeaders = [];
let currentRows = [];
let mappingFields = {};
let currentMapping = {};

const tableListEl = document.getElementById('tableList');
const newTitleEl = document.getElementById('newTitle');
const createTableBtn = document.getElementById('createTable');
const refreshTablesBtn = document.getElementById('refreshTables');
const currentProjectEl = document.getElementById('currentProject');

const excelFileEl = document.getElementById('excelFile');
const uploadExcelBtn = document.getElementById('uploadExcel');
const uploadStatusEl = document.getElementById('uploadStatus');

const mappingListEl = document.getElementById('mappingList');
const saveMappingBtn = document.getElementById('saveMapping');
const mappingStatusEl = document.getElementById('mappingStatus');

const previewMetaEl = document.getElementById('previewMeta');
const previewHeadEl = document.getElementById('previewHead');
const previewBodyEl = document.getElementById('previewBody');

function requireAuth(resp) {
  if (resp.status === 401) {
    window.location.href = '/login';
    return true;
  }
  return false;
}

async function apiGet(url) {
  const response = await fetch(url);
  if (requireAuth(response)) throw new Error('unauthorized');
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || 'Ошибка запроса');
  return payload;
}

async function apiPostForm(url, data) {
  const formData = new FormData();
  Object.entries(data).forEach(([key, value]) => formData.append(key, value));
  const response = await fetch(url, { method: 'POST', body: formData });
  if (requireAuth(response)) throw new Error('unauthorized');
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || 'Ошибка запроса');
  return payload;
}

async function apiPostJson(url, payload) {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (requireAuth(response)) throw new Error('unauthorized');
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || 'Ошибка запроса');
  return body;
}

function setStatus(element, text, type = 'muted') {
  element.textContent = text;
  element.className = `status status-${type}`;
}

function normalizeMappingValue(value) {
  if (Array.isArray(value)) return Number.isInteger(value[0]) ? value[0] : null;
  return Number.isInteger(value) ? value : null;
}

function renderTablesList(tables) {
  tableListEl.innerHTML = '';
  if (!tables.length) {
    const li = document.createElement('li');
    li.className = 'table-list-empty';
    li.textContent = 'Проектов пока нет. Создайте первый проект импорта.';
    tableListEl.appendChild(li);
    return;
  }

  tables.forEach((table) => {
    const li = document.createElement('li');
    li.className = 'table-list-item';

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'table-open-btn';
    button.textContent = `${table.title} · #${table.id}`;
    button.addEventListener('click', () => openTable(table.id, table.title));

    li.appendChild(button);
    tableListEl.appendChild(li);
  });
}

async function loadTables() {
  const tables = await apiGet('/api/tables');
  renderTablesList(tables);
  if (!currentTableId && tables.length > 0) {
    await openTable(tables[0].id, tables[0].title);
  }
}

function renderPreview(headers, rows, totalRows = 0) {
  previewHeadEl.innerHTML = '';
  previewBodyEl.innerHTML = '';

  if (!headers.length) {
    previewMetaEl.textContent = 'Нет загруженного Excel.';
    return;
  }

  previewMetaEl.textContent = `Колонок: ${headers.length}. Строк всего: ${totalRows}. Показано: ${rows.length}.`;

  const headRow = document.createElement('tr');
  headers.forEach((header, index) => {
    const th = document.createElement('th');
    th.textContent = header || `Колонка ${index + 1}`;
    headRow.appendChild(th);
  });
  previewHeadEl.appendChild(headRow);

  rows.forEach((row) => {
    const tr = document.createElement('tr');
    headers.forEach((_, index) => {
      const td = document.createElement('td');
      td.textContent = row[index] || '';
      tr.appendChild(td);
    });
    previewBodyEl.appendChild(tr);
  });
}

function renderMapping() {
  mappingListEl.innerHTML = '';
  const fields = Object.entries(mappingFields);
  if (!fields.length) {
    mappingListEl.innerHTML = '<p class="hint">Сначала загрузите Excel, чтобы получить схему тегов.</p>';
    saveMappingBtn.disabled = true;
    return;
  }

  fields.forEach(([fieldKey, fieldLabel]) => {
    const row = document.createElement('div');
    row.className = 'mapping-row';

    const name = document.createElement('div');
    name.className = 'mapping-tag';
    name.textContent = fieldLabel;

    const select = document.createElement('select');
    select.className = 'mapping-select';
    select.dataset.field = fieldKey;

    const emptyOption = document.createElement('option');
    emptyOption.value = '';
    emptyOption.textContent = 'не выбрано';
    select.appendChild(emptyOption);

    currentHeaders.forEach((header, index) => {
      const option = document.createElement('option');
      option.value = String(index);
      option.textContent = `${index + 1}. ${header || `Колонка ${index + 1}`}`;
      select.appendChild(option);
    });

    const mappedIndex = normalizeMappingValue(currentMapping[fieldKey]);
    select.value = mappedIndex === null ? '' : String(mappedIndex);

    select.addEventListener('change', () => {
      const value = select.value === '' ? null : Number(select.value);
      if (value === null) {
        delete currentMapping[fieldKey];
      } else {
        currentMapping[fieldKey] = value;
      }
      setStatus(mappingStatusEl, 'Есть несохранённые изменения в mapping.', 'warning');
    });

    row.appendChild(name);
    row.appendChild(select);
    mappingListEl.appendChild(row);
  });

  saveMappingBtn.disabled = !currentTableId || !currentHeaders.length;
}

async function loadPreviewAndMapping(tableId) {
  try {
    const [preview, mappingResp] = await Promise.all([
      apiGet(`/api/tables/${tableId}/excel_preview`),
      apiGet(`/api/tables/${tableId}/mapping`),
    ]);

    currentHeaders = Array.isArray(preview.headers) ? preview.headers : [];
    currentRows = Array.isArray(preview.rows) ? preview.rows : [];
    mappingFields = (mappingResp && mappingResp.mapping_fields) || preview.mapping_fields || {};
    currentMapping = (mappingResp && mappingResp.mapping) || {};

    renderPreview(currentHeaders, currentRows, preview.total_rows || 0);
    renderMapping();

    if (currentHeaders.length) {
      setStatus(uploadStatusEl, 'Excel уже загружен. Можно обновить файл.', 'success');
    } else {
      setStatus(uploadStatusEl, 'Excel ещё не загружен.', 'muted');
    }
    setStatus(mappingStatusEl, 'Mapping загружен.', 'muted');
  } catch (error) {
    renderPreview([], []);
    mappingFields = {};
    currentMapping = {};
    renderMapping();
    setStatus(uploadStatusEl, `Ошибка загрузки данных: ${error.message}`, 'error');
  }
}

async function openTable(tableId, title) {
  currentTableId = tableId;
  currentProjectEl.textContent = `Текущий проект: ${title} (#${tableId})`;
  uploadExcelBtn.disabled = false;
  await loadPreviewAndMapping(tableId);
}

createTableBtn.addEventListener('click', async () => {
  const title = newTitleEl.value.trim();
  if (!title) {
    setStatus(uploadStatusEl, 'Введите название проекта перед созданием.', 'warning');
    return;
  }

  try {
    await apiPostForm('/api/tables', { title });
    newTitleEl.value = '';
    await loadTables();
    setStatus(uploadStatusEl, 'Проект создан.', 'success');
  } catch (error) {
    setStatus(uploadStatusEl, `Не удалось создать проект: ${error.message}`, 'error');
  }
});

refreshTablesBtn.addEventListener('click', async () => {
  try {
    await loadTables();
  } catch (error) {
    setStatus(uploadStatusEl, `Не удалось обновить список: ${error.message}`, 'error');
  }
});

uploadExcelBtn.addEventListener('click', async () => {
  if (!currentTableId) {
    setStatus(uploadStatusEl, 'Сначала выберите проект импорта.', 'warning');
    return;
  }

  const file = excelFileEl.files && excelFileEl.files[0];
  if (!file) {
    setStatus(uploadStatusEl, 'Выберите Excel-файл (.xlsx или .xls).', 'warning');
    return;
  }

  const isExcel = /\.(xlsx|xls)$/i.test(file.name || '');
  if (!isExcel) {
    setStatus(uploadStatusEl, 'Поддерживаются только файлы .xlsx или .xls.', 'warning');
    return;
  }

  try {
    setStatus(uploadStatusEl, 'Загрузка и чтение Excel...', 'muted');
    const payload = await apiPostForm(`/api/tables/${currentTableId}/excel`, { excel: file });

    currentHeaders = Array.isArray(payload.headers) ? payload.headers : [];
    currentRows = Array.isArray(payload.rows) ? payload.rows : [];
    currentMapping = payload.mapping || {};

    if (!Object.keys(mappingFields).length && payload.mapping_fields) {
      mappingFields = payload.mapping_fields;
    }

    renderPreview(currentHeaders, currentRows, payload.total_rows || 0);
    renderMapping();

    const autoLabel = payload.mapping_autofilled ? ' Mapping автоопределён, проверьте вручную.' : '';
    setStatus(uploadStatusEl, `Excel загружен успешно.${autoLabel}`, 'success');
    setStatus(mappingStatusEl, 'Проверьте и сохраните mapping.', 'warning');
  } catch (error) {
    setStatus(uploadStatusEl, `Ошибка загрузки Excel: ${error.message}`, 'error');
  }
});

saveMappingBtn.addEventListener('click', async () => {
  if (!currentTableId) {
    setStatus(mappingStatusEl, 'Сначала выберите проект.', 'warning');
    return;
  }

  try {
    const response = await apiPostJson(`/api/tables/${currentTableId}/mapping`, { mapping: currentMapping });
    currentMapping = response.mapping || currentMapping;
    renderMapping();
    setStatus(mappingStatusEl, 'Mapping сохранён. Нормализация данных выполнена в backend.', 'success');
  } catch (error) {
    setStatus(mappingStatusEl, `Не удалось сохранить mapping: ${error.message}`, 'error');
  }
});

(async function init() {
  try {
    await loadTables();
  } catch (error) {
    setStatus(uploadStatusEl, `Ошибка инициализации: ${error.message}`, 'error');
  }
})();
