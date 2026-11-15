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
  auto_number: '#️⃣',
  territory: '🏢',
  team_name: '👥',
  people_count: '🔢',
  supervisor: '🧑‍🏫',
  department: '🏭',
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
          <div class="hint">${d.event_date ? `Дата проведения: ${esc(formatDateRu(d.event_date))}` : 'Дата проведения не указана'}</div>
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

  const openSettingsBtn = document.getElementById('openSettingsBtn');
  const settingsModal = document.getElementById('settingsModal');
  const modalDateInput = document.getElementById('modalEventDateInput');
  const modalSaveBtn = document.getElementById('modalSaveSettingsBtn');
  const modalCloseBtn = document.getElementById('modalCloseSettingsBtn');
  const modalStatus = document.getElementById('modalSettingsStatus');

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
    // "№" — один на форму и не переименовывается (см. REGISTRATION_AUTO_NUMBER_QTYPE
    // на сервере), поэтому его кнопку в панели слева выключаем, как только он уже добавлен.
    const hasAutoNumber = questions.some((q) => q.qtype === AUTO_NUMBER_QTYPE);
    const autoNumberBtn = typeGrid.querySelector(`[data-qtype="${AUTO_NUMBER_QTYPE}"]`);
    if (autoNumberBtn) autoNumberBtn.disabled = hasAutoNumber;

    if (!questions.length) {
      canvas.innerHTML = '<p class="hint">Пока нет вопросов — выберите тип слева, чтобы добавить первый.</p>';
      return;
    }
    canvas.innerHTML = '';
    questions.forEach((q) => {
      const isAutoNumber = q.qtype === AUTO_NUMBER_QTYPE;
      const card = document.createElement('div');
      card.className = 'desk-question-card';
      card.innerHTML = `
        <div class="desk-question-head">
          <span class="desk-type-icon">${QUESTION_TYPE_ICONS[q.qtype] || '❔'}</span>
          <span class="desk-question-type">${esc(QUESTION_TYPES[q.qtype] || q.qtype)}</span>
          <button class="icon-btn desk-question-del" data-id="${q.id}" type="button" title="Удалить вопрос">✕</button>
        </div>
        <input type="text" class="desk-question-label" data-id="${q.id}" value="${esc(q.label)}" ${isAutoNumber ? 'readonly' : ''}>
        ${isAutoNumber ? '<p class="hint">Присваивается автоматически каждой записи, участнику не показывается.</p>' : ''}
      `;
      canvas.appendChild(card);
    });

    canvas.querySelectorAll('.desk-question-del').forEach((btn) => {
      btn.addEventListener('click', async () => {
        if (!confirm('Удалить этот вопрос из формы?')) return;
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

  // Пока дата не указана — настройка всегда на виду (так же, как раньше:
  // "первым делом открывается настройка мероприятия"). Как только дата
  // сохранена один раз, карточка уходит, вместо неё — кнопка ⚙️ рядом с
  // названием (по образцу настроек, вынесенных отдельно — как у Яндекс.Форм),
  // которая открывает ту же настройку в модальном окне.
  function showConfiguredState(show) {
    builderCard.hidden = !show;
    settingsCard.hidden = show;
    openSettingsBtn.hidden = !show;
  }

  function openSettingsModal(currentDate) {
    modalDateInput.value = currentDate || '';
    setStatus(modalStatus, '', 'muted');
    settingsModal.classList.add('visible');
  }

  function closeSettingsModal() {
    settingsModal.classList.remove('visible');
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
      showConfiguredState(true);
      await loadQuestions();
    } catch (e) {
      setStatus(settingsStatus, `Ошибка сохранения: ${e.message}`, 'error');
    } finally {
      saveSettingsBtn.disabled = false;
    }
  });

  openSettingsBtn?.addEventListener('click', () => openSettingsModal(dateInput.value));
  modalCloseBtn?.addEventListener('click', closeSettingsModal);
  settingsModal?.addEventListener('click', (event) => {
    if (event.target === settingsModal) closeSettingsModal();
  });

  modalSaveBtn?.addEventListener('click', async () => {
    const event_date = modalDateInput.value;
    if (!event_date) {
      setStatus(modalStatus, 'Укажите дату проведения.', 'warning');
      return;
    }
    try {
      modalSaveBtn.disabled = true;
      await apiSendJson(`/api/registration-desk/${DESK_ID}/settings`, 'POST', { event_date });
      dateInput.value = event_date;
      setStatus(modalStatus, 'Сохранено.', 'success');
      closeSettingsModal();
    } catch (e) {
      setStatus(modalStatus, `Ошибка сохранения: ${e.message}`, 'error');
    } finally {
      modalSaveBtn.disabled = false;
    }
  });

  // ----------------- Вкладки "Конструктор" / "Ответы" -----------------

  const tabButtons = document.querySelectorAll('.desk-tab');
  const tabPanels = {
    constructor: document.getElementById('constructorPanel'),
    responses: document.getElementById('responsesPanel'),
  };

  tabButtons.forEach((tab) => {
    tab.addEventListener('click', () => {
      tabButtons.forEach((t) => t.classList.toggle('active', t === tab));
      Object.entries(tabPanels).forEach(([key, el]) => {
        if (el) el.hidden = key !== tab.dataset.tab;
      });
      if (tab.dataset.tab === 'responses') loadResponses();
    });
  });

  // ----------------- Публикация формы -----------------

  const publishInfo = document.getElementById('publishInfo');
  const publishBtn = document.getElementById('publishBtn');
  const copyPublishLinkBtn = document.getElementById('copyPublishLinkBtn');
  const republishBtn = document.getElementById('republishBtn');
  const unpublishBtn = document.getElementById('unpublishBtn');
  const publishStatus = document.getElementById('publishStatus');

  function renderPublishInfo(desk) {
    if (desk.publish_url) {
      publishInfo.innerHTML = `Форма опубликована: <a href="${esc(desk.publish_url)}" target="_blank" rel="noopener">${esc(desk.publish_url)}</a>`;
      publishBtn.hidden = true;
      copyPublishLinkBtn.hidden = false;
      republishBtn.hidden = false;
      unpublishBtn.hidden = false;
      copyPublishLinkBtn.dataset.url = desk.publish_url;
    } else {
      publishInfo.textContent = 'Форма не опубликована.';
      publishBtn.hidden = false;
      copyPublishLinkBtn.hidden = true;
      republishBtn.hidden = true;
      unpublishBtn.hidden = true;
    }
  }

  async function refreshPublishInfo() {
    const desk = await apiGet(`/api/registration-desk/${DESK_ID}`);
    renderPublishInfo(desk);
    return desk;
  }

  publishBtn?.addEventListener('click', async () => {
    try {
      publishBtn.disabled = true;
      await apiSendJson(`/api/registration-desk/${DESK_ID}/publish`, 'POST', {});
      await refreshPublishInfo();
      setStatus(publishStatus, 'Форма опубликована.', 'success');
    } catch (e) {
      setStatus(publishStatus, `Ошибка публикации: ${e.message}`, 'error');
    } finally {
      publishBtn.disabled = false;
    }
  });

  unpublishBtn?.addEventListener('click', async () => {
    if (!confirm('Снять форму с публикации? Ссылка перестанет работать.')) return;
    try {
      await apiSendJson(`/api/registration-desk/${DESK_ID}/unpublish`, 'POST', {});
      await refreshPublishInfo();
      setStatus(publishStatus, 'Форма снята с публикации.', 'muted');
    } catch (e) {
      setStatus(publishStatus, `Ошибка: ${e.message}`, 'error');
    }
  });

  republishBtn?.addEventListener('click', async () => {
    if (!confirm('Старая ссылка перестанет работать, появится новая. Продолжить?')) return;
    try {
      await apiSendJson(`/api/registration-desk/${DESK_ID}/republish`, 'POST', {});
      await refreshPublishInfo();
      setStatus(publishStatus, 'Ссылка обновлена.', 'success');
    } catch (e) {
      setStatus(publishStatus, `Ошибка: ${e.message}`, 'error');
    }
  });

  async function copyToClipboard(text) {
    // navigator.clipboard доступен только в "безопасном контексте"
    // (HTTPS или localhost) — админка сайта сейчас на обычном HTTP
    // (:8082), поэтому современный Clipboard API там всегда недоступен
    // (не ошибка сети — браузер сам запрещает). Резервный способ через
    // скрытый textarea + document.execCommand('copy') работает и по HTTP.
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return;
    }
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(textarea);
    if (!ok) throw new Error('execCommand(copy) failed');
  }

  copyPublishLinkBtn?.addEventListener('click', async () => {
    try {
      await copyToClipboard(copyPublishLinkBtn.dataset.url || '');
      setStatus(publishStatus, 'Ссылка скопирована.', 'success');
    } catch {
      setStatus(publishStatus, 'Не удалось скопировать — скопируйте ссылку вручную (выделите текст выше).', 'warning');
    }
  });

  // ----------------- Ответы -----------------

  function formatSubmittedAt(value) {
    return formatDateTimeRu(value);
  }

  let responsesCols = [];
  let responsesRaw = [];
  let responsesSortKey = null;
  let responsesSortDir = 1;
  let responsesFilterText = '';
  let responsesEditingId = null;

  const responsesFilterInput = document.getElementById('responsesFilterInput');
  const exportResponsesBtn = document.getElementById('exportResponsesBtn');
  if (exportResponsesBtn && typeof DESK_ID !== 'undefined') {
    exportResponsesBtn.href = `/api/registration-desk/${DESK_ID}/responses/export.xlsx`;
  }

  function responsesCellText(r, key) {
    if (key === 'submitted_at') return formatSubmittedAt(r.submitted_at);
    return (r.answers[key] ?? '').toString();
  }

  function visibleResponses() {
    let list = responsesRaw;
    const needle = responsesFilterText.trim().toLowerCase();
    if (needle) {
      list = list.filter((r) => responsesCols.some((q) => responsesCellText(r, q.qtype).toLowerCase().includes(needle))
        || responsesCellText(r, 'submitted_at').toLowerCase().includes(needle));
    }
    if (responsesSortKey) {
      list = [...list].sort((a, b) => {
        const av = responsesCellText(a, responsesSortKey);
        const bv = responsesCellText(b, responsesSortKey);
        return av.localeCompare(bv, 'ru') * responsesSortDir;
      });
    }
    return list;
  }

  function renderResponsesHead() {
    const headRow = document.getElementById('responsesHeadRow');
    const sortArrow = (key) => (responsesSortKey === key ? (responsesSortDir === 1 ? ' ▲' : ' ▼') : '');
    headRow.innerHTML = `<th>№</th>${responsesCols.map((q) => (
      `<th class="desk-responses-sortable" data-sort-key="${q.qtype}">${esc(q.label)}${sortArrow(q.qtype)}</th>`
    )).join('')}<th class="desk-responses-sortable" data-sort-key="submitted_at">Время отправки${sortArrow('submitted_at')}</th><th>Действия</th>`;
    headRow.querySelectorAll('[data-sort-key]').forEach((th) => {
      th.style.cursor = 'pointer';
      th.addEventListener('click', () => {
        const key = th.dataset.sortKey;
        responsesSortDir = responsesSortKey === key ? -responsesSortDir : 1;
        responsesSortKey = key;
        renderResponsesHead();
        renderResponsesBody();
      });
    });
  }

  function renderResponsesBody() {
    const body = document.getElementById('responsesBody');
    const list = visibleResponses();
    if (!responsesRaw.length) {
      body.innerHTML = `<tr><td colspan="${responsesCols.length + 3}" class="hint">Ответов пока нет.</td></tr>`;
      return;
    }
    if (!list.length) {
      body.innerHTML = `<tr><td colspan="${responsesCols.length + 3}" class="hint">Ничего не найдено по фильтру.</td></tr>`;
      return;
    }
    body.innerHTML = list.map((r, idx) => {
      if (responsesEditingId === r.id) {
        const cells = responsesCols.map((q) => `<td><input type="text" class="desk-response-edit-input" data-qtype="${q.qtype}" value="${esc(r.answers[q.qtype] ?? '')}"></td>`).join('');
        return `<tr data-id="${r.id}">
          <td>${idx + 1}</td>${cells}<td>${esc(formatSubmittedAt(r.submitted_at))}</td>
          <td class="row" style="gap:4px;">
            <button class="icon-btn desk-response-save" type="button" title="Сохранить">💾</button>
            <button class="icon-btn desk-response-cancel" type="button" title="Отмена">✕</button>
          </td>
        </tr>`;
      }
      const cells = responsesCols.map((q) => `<td>${esc(r.answers[q.qtype] ?? '')}</td>`).join('');
      return `<tr data-id="${r.id}">
        <td>${idx + 1}</td>${cells}<td>${esc(formatSubmittedAt(r.submitted_at))}</td>
        <td class="row" style="gap:4px;">
          <button class="icon-btn desk-response-edit" type="button" title="Править строку">✎</button>
          <button class="icon-btn desk-response-del" type="button" title="Удалить строку">✕</button>
        </td>
      </tr>`;
    }).join('');

    body.querySelectorAll('.desk-response-edit').forEach((btn) => {
      btn.addEventListener('click', () => {
        responsesEditingId = parseInt(btn.closest('tr').dataset.id, 10);
        renderResponsesBody();
      });
    });
    body.querySelectorAll('.desk-response-cancel').forEach((btn) => {
      btn.addEventListener('click', () => {
        responsesEditingId = null;
        renderResponsesBody();
      });
    });
    body.querySelectorAll('.desk-response-save').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const tr = btn.closest('tr');
        const id = parseInt(tr.dataset.id, 10);
        const original = responsesRaw.find((r) => r.id === id);
        const answers = { ...(original ? original.answers : {}) };
        tr.querySelectorAll('.desk-response-edit-input').forEach((input) => {
          answers[input.dataset.qtype] = input.value;
        });
        try {
          await apiSendJson(`/api/registration-desk/${DESK_ID}/responses/${id}`, 'PATCH', { answers });
          responsesEditingId = null;
          await loadResponses();
        } catch (e) {
          setStatus(document.getElementById('responsesStatus'), `Ошибка сохранения: ${e.message}`, 'error');
        }
      });
    });
    body.querySelectorAll('.desk-response-del').forEach((btn) => {
      btn.addEventListener('click', async () => {
        if (!confirm('Удалить этот ответ?')) return;
        const id = parseInt(btn.closest('tr').dataset.id, 10);
        try {
          await apiDelete(`/api/registration-desk/${DESK_ID}/responses/${id}`);
          await loadResponses();
        } catch (e) {
          setStatus(document.getElementById('responsesStatus'), `Ошибка удаления: ${e.message}`, 'error');
        }
      });
    });
  }

  responsesFilterInput?.addEventListener('input', () => {
    responsesFilterText = responsesFilterInput.value;
    renderResponsesBody();
  });

  async function loadResponses() {
    const responsesStatus = document.getElementById('responsesStatus');
    try {
      const [questions, responses] = await Promise.all([
        apiGet(`/api/registration-desk/${DESK_ID}/questions`),
        apiGet(`/api/registration-desk/${DESK_ID}/responses`),
      ]);
      responsesCols = questions.filter((q) => q.qtype !== AUTO_NUMBER_QTYPE);
      responsesRaw = responses;
      renderResponsesHead();
      renderResponsesBody();
      setStatus(responsesStatus, '', 'muted');
    } catch (e) {
      setStatus(responsesStatus, `Ошибка загрузки ответов: ${e.message}`, 'error');
    }
  }

  document.getElementById('refreshResponsesBtn')?.addEventListener('click', loadResponses);

  renderTypeGrid();

  try {
    const desk = await apiGet(`/api/registration-desk/${DESK_ID}`);
    titleEl.textContent = desk.title;
    document.title = `${desk.title} — Стойка регистрации`;
    if (desk.event_date) {
      dateInput.value = desk.event_date;
      showConfiguredState(true);
      await loadQuestions();
      renderPublishInfo(desk);
    }
  } catch (e) {
    setStatus(settingsStatus, `Ошибка загрузки: ${e.message}`, 'error');
  }
}

initDeskListPage();
initDeskDetailPage();
