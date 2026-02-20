const auth = document.getElementById('auth');
const workspace = document.getElementById('workspace');
const tableView = document.getElementById('tableView');
const tableList = document.getElementById('tableList');
const entriesBody = document.getElementById('entries');
const progressEl = document.getElementById('progress');
const tableTitle = document.getElementById('tableTitle');
let currentTableId = null;

async function postForm(url, data) {
  const fd = new FormData();
  Object.entries(data).forEach(([k, v]) => fd.append(k, v));
  const r = await fetch(url, { method: 'POST', body: fd });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

async function refreshTables() {
  const r = await fetch('/api/tables');
  if (r.status === 401) return;
  const tables = await r.json();
  tableList.innerHTML = '';
  tables.forEach(t => {
    const li = document.createElement('li');
    li.textContent = `#${t.id} ${t.title} [${t.status}] ${t.progress}%`;
    li.onclick = () => openTable(t.id, t.title);
    tableList.appendChild(li);
  });
}

async function openTable(id, title) {
  currentTableId = id;
  tableTitle.textContent = `Таблица: ${title} (#${id})`;
  tableView.classList.remove('hidden');
  await refreshEntries();
}

function fileButtons(entry, type) {
  const local = entry[`${type}_local`];
  if (!local) return '';
  return `<button data-dl="/api/files/${entry.id}/${type}">Скачать ${type}</button>
          <button data-pv="/api/preview/${entry.id}/${type}">Открыть ${type}</button>`;
}

async function refreshEntries() {
  if (!currentTableId) return;
  const t = await (await fetch('/api/tables')).json();
  const cur = t.find(x => x.id === currentTableId);
  if (cur) progressEl.textContent = `Статус: ${cur.status}, прогресс: ${cur.progress}%`;

  const rows = await (await fetch(`/api/tables/${currentTableId}/entries`)).json();
  entriesBody.innerHTML = '';
  rows.forEach(e => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${e.id}</td><td>${e.fio || ''}</td><td>${e.number_title || ''}</td><td>${e.team || ''}</td>
      <td>${fileButtons(e, 'audio')} ${fileButtons(e, 'receipt')} ${fileButtons(e, 'consent')} ${fileButtons(e, 'presentation')}</td>`;
    entriesBody.appendChild(tr);
  });
}

document.body.addEventListener('click', async (e) => {
  const dl = e.target.dataset.dl;
  const pv = e.target.dataset.pv;
  if (dl) window.open(dl, '_blank');
  if (pv) {
    const viewer = document.getElementById('viewer');
    const body = document.getElementById('viewerBody');
    const downloadTop = document.getElementById('downloadTop');
    const ext = pv.split('/').pop();
    downloadTop.onclick = () => window.open(pv.replace('/preview/', '/files/'), '_blank');
    if (ext === 'pdf' || ext === 'consent' || ext === 'receipt' || ext === 'presentation') {
      body.innerHTML = `<iframe src="${pv}"></iframe>`;
    } else {
      body.innerHTML = `<img src="${pv}"/>`;
    }
    viewer.showModal();
  }
});

document.getElementById('closeViewer').onclick = () => document.getElementById('viewer').close();

document.getElementById('sendCode').onclick = async () => {
  await postForm('/api/tables/send_code', { email: document.getElementById('email').value });
  alert('Код отправлен (в MVP выводится в server log).');
};

document.getElementById('verifyCode').onclick = async () => {
  await postForm('/api/tables/verify_code', {
    email: document.getElementById('email').value,
    code: document.getElementById('code').value,
  });
  auth.classList.add('hidden');
  workspace.classList.remove('hidden');
  refreshTables();
};

document.getElementById('createTable').onclick = async () => {
  await postForm('/api/tables', { title: document.getElementById('newTitle').value });
  refreshTables();
};

document.getElementById('uploadExcel').onclick = async () => {
  if (!currentTableId) return alert('Выберите таблицу');
  const f = document.getElementById('excelFile').files[0];
  const fd = new FormData(); fd.append('excel', f);
  await fetch(`/api/tables/${currentTableId}/excel`, { method: 'POST', body: fd });
  alert('Excel загружен');
};

document.getElementById('connectYandex').onclick = async () => {
  if (!currentTableId) return alert('Выберите таблицу');
  await postForm(`/api/tables/${currentTableId}/connect-yandex`, { cookies_json: document.getElementById('yandexCookies').value || '{}' });
  alert('Yandex session сохранена');
};

document.getElementById('startDownload').onclick = async () => {
  if (!currentTableId) return alert('Выберите таблицу');
  await fetch(`/api/tables/${currentTableId}/start-download`, { method: 'POST' });
  alert('Фоновая загрузка запущена');
  setTimeout(refreshEntries, 1500);
};

fetch('/api/tables').then(r => {
  if (r.ok) { auth.classList.add('hidden'); workspace.classList.remove('hidden'); refreshTables(); }
});
setInterval(() => { refreshTables(); refreshEntries(); }, 4000);
