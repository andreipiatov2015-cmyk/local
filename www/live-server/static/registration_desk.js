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

async function apiSendJson(url, method, data) {
  const r = await fetch(url, {
    method,
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

// Иконки для панели выбора вопроса — ключи совпадают с REGISTRATION_QUESTION_TYPES на сервере.
const QUESTION_TYPE_ICONS = {
  text: '📝',
  yesno: '✅',
  file: '📎',
  list: '📂',
  text_plain: '💬',
  date: '📅',
  number: '🔢',
  scale: '📊',
  series: '📋',
};

// ======================= Список мероприятий =======================

async function initDeskListPage() {
  const listEl = document.getElementById('deskList');
  if (!listEl) return;
  const createBtn = document.getElementById('createDesk');
  const statusEl = document.getElementById('listStatus');
  let isCreatingDraft = false;

  async function load() {
    const desks = await apiGet('/api/registration-desk');
    if (!desks.length) {
      listEl.innerHTML = '<li class="desk-item"><div class="hint">Пока нет мероприятий.</div></li>';
      return;
    }
    listEl.innerHTML = '';
    desks.forEach((d) => {
      const li = document.createElement('li');
      li.className = 'desk-item';
      li.innerHTML = `
        <a class="desk-main" href="/registration-desk/${d.id}">
          <strong>${esc(d.title)}</strong>
          <div class="hint">${d.event_date ? `Дата проведения: ${esc(d.event_date)}` : 'Дата проведения не указана'}</div>
        </a>
        <div class="row wrap">
          <a class="btn btn-secondary" href="/registration-desk/${d.id}">Открыть</a>
          <button class="btn btn-danger" data-del="${d.id}" type="button">Удалить</button>
        </div>
      `;
      listEl.appendChild(li);
    });

    listEl.querySelectorAll('[data-del]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        if (!confirm('Удалить мероприятие вместе с формой регистрации?')) return;
        try {
          await apiDelete(`/api/registration-desk/${btn.dataset.del}`);
          await load();
        } catch (e) {
          setStatus(statusEl, `Ошибка удаления: ${e.message}`, 'error');
        }
      });
    });
  }

  function removeDraftCard() {
    const draft = listEl.querySelector('.desk-item.is-creating');
    if (draft) draft.remove();
    if (!listEl.children.length) {
      listEl.innerHTML = '<li class="desk-item"><div class="hint">Пока нет мероприятий.</div></li>';
    }
    isCreatingDraft = false;
  }

  async function saveDraftTitle(inputEl, saveBtn) {
    const title = (inputEl?.value || '').trim();
    if (!title) {
      setStatus(statusEl, 'Введите название мероприятия.', 'warning');
      inputEl?.focus();
      return;
    }
    try {
      saveBtn.disabled = true;
      const created = await apiPostForm('/api/registration-desk', { title });
      window.location.href = `/registration-desk/${created.id}`;
    } catch (e) {
      setStatus(statusEl, `Ошибка создания: ${e.message}`, 'error');
      saveBtn.disabled = false;
    }
  }

  function renderCreateDraftCard() {
    if (isCreatingDraft) return;
    isCreatingDraft = true;
    const emptyStub = listEl.querySelector('.desk-item .hint');
    if (emptyStub) listEl.innerHTML = '';

    const li = document.createElement('li');
    li.className = 'desk-item is-creating';
    li.innerHTML = `
      <div class="desk-main">
        <label class="hint" for="newDeskTitleInput">Название мероприятия</label>
        <div class="new-desk-controls">
          <input id="newDeskTitleInput" class="new-desk-input" type="text" placeholder="Введите название мероприятия" maxlength="120" />
          <button id="confirmNewDesk" class="btn btn-primary desk-confirm-btn" type="button" title="Подтвердить (Enter)">✓</button>
        </div>
        <div class="hint">Нажмите Enter или ✓.</div>
      </div>
      <div class="row wrap">
        <button id="cancelNewDesk" class="btn btn-secondary" type="button">Отмена</button>
      </div>
    `;
    listEl.prepend(li);
    const inputEl = li.querySelector('#newDeskTitleInput');
    const confirmBtn = li.querySelector('#confirmNewDesk');
    const cancelBtn = li.querySelector('#cancelNewDesk');

    inputEl?.focus();
    inputEl?.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter') return;
      event.preventDefault();
      saveDraftTitle(inputEl, confirmBtn);
    });
    confirmBtn?.addEventListener('click', () => saveDraftTitle(inputEl, confirmBtn));
    cancelBtn?.addEventListener('click', removeDraftCard);
  }

  createBtn?.addEventListener('click', () => renderCreateDraftCard());

  try {
    await load();
    setStatus(statusEl, '', 'muted');
  } catch (e) {
    setStatus(statusEl, `Ошибка загрузки: ${e.message}`, 'error');
  }
}

// ======================= Страница мероприятия =======================

async function initDeskDetailPage() {
  const builderCard = document.getElementById('builderCard');
  const settingsCard = document.getElementById('settingsCard');
  if (!settingsCard || typeof DESK_ID === 'undefined') return;

  const titleEl = document.getElementById('deskTitle');
  const dateInput = document.getElementById('eventDateInput');
  const saveSettingsBtn = document.getElementById('saveSettingsBtn');
  const settingsStatus = document.getElementById('settingsStatus');
  const typeGrid = document.getElementById('questionTypeGrid');
  const canvas = document.getElementById('questionCanvas');

  function renderTypeGrid() {
    typeGrid.innerHTML = '';
    Object.entries(QUESTION_TYPES).forEach(([qtype, label]) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'desk-type-btn';
      btn.dataset.qtype = qtype;
      btn.innerHTML = `<span class="desk-type-icon">${QUESTION_TYPE_ICONS[qtype] || '❔'}</span><span>${esc(label)}</span>`;
      btn.addEventListener('click', () => addQuestion(qtype));
      typeGrid.appendChild(btn);
    });
  }

  function renderQuestions(questions) {
    if (!questions.length) {
      canvas.innerHTML = '<p class="hint">Пока нет вопросов — выберите тип слева, чтобы добавить первый.</p>';
      return;
    }
    canvas.innerHTML = '';
    questions.forEach((q) => {
      const card = document.createElement('div');
      card.className = 'desk-question-card';
      card.innerHTML = `
        <div class="desk-question-head">
          <span class="desk-type-icon">${QUESTION_TYPE_ICONS[q.qtype] || '❔'}</span>
          <span class="desk-question-type">${esc(QUESTION_TYPES[q.qtype] || q.qtype)}</span>
          <button class="icon-btn desk-question-del" data-id="${q.id}" type="button" title="Удалить вопрос">✕</button>
        </div>
        <input type="text" class="desk-question-label" data-id="${q.id}" value="${esc(q.label)}">
      `;
      canvas.appendChild(card);
    });

    canvas.querySelectorAll('.desk-question-del').forEach((btn) => {
      btn.addEventListener('click', async () => {
        try {
          await apiDelete(`/api/registration-desk/${DESK_ID}/questions/${btn.dataset.id}`);
          await loadQuestions();
        } catch (e) {
          setStatus(settingsStatus, `Ошибка удаления вопроса: ${e.message}`, 'error');
        }
      });
    });

    canvas.querySelectorAll('.desk-question-label').forEach((input) => {
      let lastSaved = input.value;
      const save = async () => {
        const label = input.value.trim();
        if (!label || label === lastSaved) {
          input.value = label || lastSaved;
          return;
        }
        try {
          await apiSendJson(`/api/registration-desk/${DESK_ID}/questions/${input.dataset.id}`, 'PUT', { label });
          lastSaved = label;
        } catch (e) {
          input.value = lastSaved;
          setStatus(settingsStatus, `Ошибка сохранения вопроса: ${e.message}`, 'error');
        }
      };
      input.addEventListener('blur', save);
      input.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
          event.preventDefault();
          input.blur();
        }
      });
    });
  }

  async function loadQuestions() {
    const questions = await apiGet(`/api/registration-desk/${DESK_ID}/questions`);
    renderQuestions(questions);
  }

  async function addQuestion(qtype) {
    try {
      await apiSendJson(`/api/registration-desk/${DESK_ID}/questions`, 'POST', { qtype });
      await loadQuestions();
    } catch (e) {
      setStatus(settingsStatus, `Ошибка добавления вопроса: ${e.message}`, 'error');
    }
  }

  function showBuilder(show) {
    builderCard.hidden = !show;
  }

  saveSettingsBtn?.addEventListener('click', async () => {
    const event_date = dateInput.value;
    if (!event_date) {
      setStatus(settingsStatus, 'Укажите дату проведения.', 'warning');
      return;
    }
    try {
      saveSettingsBtn.disabled = true;
      await apiSendJson(`/api/registration-desk/${DESK_ID}/settings`, 'POST', { event_date });
      setStatus(settingsStatus, 'Сохранено.', 'success');
      showBuilder(true);
      await loadQuestions();
    } catch (e) {
      setStatus(settingsStatus, `Ошибка сохранения: ${e.message}`, 'error');
    } finally {
      saveSettingsBtn.disabled = false;
    }
  });

  renderTypeGrid();

  try {
    const desk = await apiGet(`/api/registration-desk/${DESK_ID}`);
    titleEl.textContent = desk.title;
    document.title = `${desk.title} — Стойка регистрации`;
    if (desk.event_date) {
      dateInput.value = desk.event_date;
      showBuilder(true);
      await loadQuestions();
    }
  } catch (e) {
    setStatus(settingsStatus, `Ошибка загрузки: ${e.message}`, 'error');
  }
}

initDeskListPage();
initDeskDetailPage();
