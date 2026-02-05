function initAdmin() {
  // Переключение меню
  const sidebar = document.querySelector(".sidebar");
  const collapseSidebarButton = document.getElementById("collapseSidebar");
  const editorLink = document.querySelector('.sidebar-menu a[href="/admin"]');
  const autoAddLink = document.getElementById("autoAddLink");
  const previewSection = document.getElementById("preview");
  const tableSection = document.querySelector("table");
  const autoAddSection = document.getElementById("autoAddSection");

  collapseSidebarButton?.addEventListener("click", () => {
    sidebar?.classList.toggle("collapsed");
  });

  // Переключение секций
  if (!editorLink || !autoAddLink || !previewSection || !tableSection || !autoAddSection) {
    console.warn("Admin UI: missing required section elements.");
  } else {
    editorLink.addEventListener("click", (e) => {
      e.preventDefault();
      document.querySelectorAll(".sidebar-menu .menu-item").forEach((l) => l.classList.remove("active"));
      editorLink.classList.add("active");
      previewSection.style.display = "block";
      tableSection.style.display = "table";
      autoAddSection.style.display = "none";
    });

    autoAddLink.addEventListener("click", (e) => {
      e.preventDefault();
      document.querySelectorAll(".sidebar-menu .menu-item").forEach((l) => l.classList.remove("active"));
      autoAddLink.classList.add("active");
      previewSection.style.display = "none";
      tableSection.style.display = "none";
      autoAddSection.style.display = "block";
    });
  }
  
    // Добавление новой строки
    let rowCount = 1;
    function addNewRow(sendToServer = false) {
        const tableBody = document.getElementById('tableBody');
        const newRow = document.createElement('tr');
        newRow.innerHTML = `
            <td>${++rowCount}</td>
            <td><input type="text" placeholder="Имя"></td>
            <td><input type="text" placeholder="Фамилия"></td>
            <td><input type="text" placeholder="Отчество"></td>
            <td><input type="text" placeholder="Название номера"></td>
            <td><input type="text" placeholder="Название коллектива"></td>
            <td><input type="text" placeholder="Территория"></td>
        `;
        tableBody.appendChild(newRow);
        attachInputListeners(newRow);
        attachRowClickListener(newRow);
        if (sendToServer) {
            saveEntryToServer(newRow);
        }
    }

    // Сохранение записи на сервере
    function saveEntryToServer(row) {
        const cells = row.querySelectorAll('td');
        const firstName = cells[1].querySelector('input').value || '';
        const lastName = cells[2].querySelector('input').value || '';
        const middleName = cells[3].querySelector('input').value || '';
        const entry = {
            id: parseInt(cells[0].textContent),
            name: formatFIO(
                firstName,
                lastName,
                middleName,
                shortName.checked,
                shortSurname.checked,
                shortPatronymic.checked
            ),
            first_name: firstName,
            last_name: lastName,
            patronymic: middleName,
            performance: cells[4].querySelector('input').value || '',
            group: cells[5].querySelector('input').value || '',
            territory: cells[6].querySelector('input').value || ''
        };
        fetch('/add_entry', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(entry)
        }).then(response => response.json())
          .then(data => {
              document.getElementById('importMessage').textContent = data.message;
              loadEntriesFromServer(); // Обновляем таблицу после добавления
          })
          .catch(() => {
              document.getElementById('importMessage').textContent = 'Ошибка сохранения записи.';
          });
    }

    // Обновление существующей записи на сервере
    function updateEntryOnServer(row) {
        const cells = row.querySelectorAll('td');
        const firstName = cells[1].querySelector('input').value || '';
        const lastName = cells[2].querySelector('input').value || '';
        const middleName = cells[3].querySelector('input').value || '';
        const entry = {
            id: parseInt(cells[0].textContent),
            name: formatFIO(
                firstName,
                lastName,
                middleName,
                shortName.checked,
                shortSurname.checked,
                shortPatronymic.checked
            ),
            first_name: firstName,
            last_name: lastName,
            patronymic: middleName,
            performance: cells[4].querySelector('input').value || '',
            group: cells[5].querySelector('input').value || '',
            territory: cells[6].querySelector('input').value || ''
        };
        fetch(`/update_entry/${entry.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(entry)
        }).then(response => response.json())
          .then(data => {
              document.getElementById('importMessage').textContent = data.message;
          })
          .catch(() => {
              document.getElementById('importMessage').textContent = 'Ошибка обновления записи.';
          });
    }

    // Удаление записи
    function deleteEntryFromServer(id) {
        fetch(`/delete_entry/${id}`, {
            method: 'DELETE'
        }).then(response => response.json())
          .then(data => {
              document.getElementById('importMessage').textContent = data.message;
              loadEntriesFromServer(); // Обновляем таблицу после удаления
          })
          .catch(() => {
              document.getElementById('importMessage').textContent = 'Ошибка удаления записи.';
          });
    }

    // Добавление слушателей для инпутов
    function attachInputListeners(row) {
        const inputs = row.querySelectorAll('input');
        inputs.forEach(input => {
            input.addEventListener('input', () => {
                const allRows = document.querySelectorAll('#tableBody tr');
                if (row === allRows[allRows.length - 1]) {
                    addNewRow(true); // Отправляем на сервер новую строку
                } else {
                    updateEntryOnServer(row); // Обновляем существующую строку
                }
            });
        });
        // Удаление по двойному клику
        row.addEventListener('dblclick', () => {
            const id = parseInt(row.querySelector('td').textContent);
            deleteEntryFromServer(id);
            row.remove();
            updateRowNumbers();
        });
    }

    // Обновление номеров строк
    function updateRowNumbers() {
        const rows = document.querySelectorAll('#tableBody tr');
        rows.forEach((row, index) => {
            row.querySelector('td').textContent = index + 1;
        });
        rowCount = rows.length;
    }

    // Удаление пустых строк
    function cleanEmptyRows() {
        const rows = document.querySelectorAll('#tableBody tr');
        rows.forEach(row => {
            const inputs = row.querySelectorAll('input');
            const isEmpty = Array.from(inputs).every(input => !input.value.trim());
            if (isEmpty && row !== rows[0]) { // Не удаляем первую строку
                const id = parseInt(row.querySelector('td').textContent);
                deleteEntryFromServer(id);
                row.remove();
                updateRowNumbers();
            }
        });
        document.getElementById('importMessage').textContent = 'Пустые строки удалены.';
    }

   // Пресеты расположения
const presetSelect = document.getElementById('presetSelect');
const savePresetButton = document.getElementById('savePresetButton');

// Предопределённые пресеты (как fallback, если сервер пустой)
const defaultPresets = [
    { name: 'Вертикальное', layout: { fio: { left: '10px', top: '10px' }, number: { left: '10px', top: '50px' }, act: { left: '10px', top: '90px' }, team: { left: '10px', top: '130px' } } },
    { name: 'Горизонтальное', layout: { fio: { left: '10px', top: '10px' }, number: { left: '200px', top: '10px' }, act: { left: '10px', top: '50px' }, team: { left: '200px', top: '50px' } } },
    { name: 'Компактное', layout: { fio: { left: '10px', top: '10px' }, number: { left: '150px', top: '10px' }, act: { left: '10px', top: '40px' }, team: { left: '10px', top: '70px' } } }
];

// Загрузка пресетов с сервера
function loadPresets() {
    fetch('/presets')
        .then(response => response.json())
        .then(data => {
            presetSelect.innerHTML = '<option value="">Выберите пресет</option>';
            data.forEach(preset => {
                const option = document.createElement('option');
                option.value = JSON.stringify(preset.layout);
                option.textContent = preset.name;
                presetSelect.appendChild(option);
            });
            if (data.length === 0) {
                defaultPresets.forEach(preset => {
                    fetch('/save_preset', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(preset)
                    });
                });
                loadPresets(); // Перезагрузить после добавления
            }
        })
        .catch(() => {
            document.getElementById('importMessage').textContent = 'Ошибка загрузки пресетов.';
        });
}

loadPresets();

// Применение пресета
presetSelect.addEventListener('change', (e) => {
    const layout = e.target.value;
    if (layout) {
        applyPreset(JSON.parse(layout));
    }
});

function applyPreset(layout) {
    const blocks = {
        fio: document.getElementById('fioBlock'),
        number: document.getElementById('numberBlock'),
        act: document.getElementById('actBlock'),
        team: document.getElementById('teamBlock')
    };
    for (const key in layout) {
        const block = blocks[key];
        block.style.left = layout[key].left;
        block.style.top = layout[key].top;
    }
    updateMinSize();
}

// Сохранение нового пресета
savePresetButton.addEventListener('click', () => {
    const name = prompt('Введите название пресета:');
    if (name) {
        const layout = {
            fio: { left: document.getElementById('fioBlock').style.left, top: document.getElementById('fioBlock').style.top },
            number: { left: document.getElementById('numberBlock').style.left, top: document.getElementById('numberBlock').style.top },
            act: { left: document.getElementById('actBlock').style.left, top: document.getElementById('actBlock').style.top },
            team: { left: document.getElementById('teamBlock').style.left, top: document.getElementById('teamBlock').style.top }
        };
        const preset = { name, layout };
        fetch('/save_preset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(preset)
        }).then(response => response.json())
          .then(() => loadPresets())
          .catch(() => {
              document.getElementById('importMessage').textContent = 'Ошибка сохранения пресета.';
          });
    }
});

    // Форматирование ФИО
    let fioFormat = 'FIO';
    const shortName = document.getElementById('shortName');
    const shortSurname = document.getElementById('shortSurname');
    const shortPatronymic = document.getElementById('shortPatronymic');
    function formatFIO(name, surname, patronymic, shortName, shortSurname, shortPatronymic) {
        const formatText = (text, shorten) => {
            if (!text) return '';
            return shorten ? `${text[0]}.` : text;
        };
        const formattedName = formatText(name, shortName);
        const formattedSurname = formatText(surname, shortSurname);
        const formattedPatronymic = formatText(patronymic, shortPatronymic);

        let parts = [];
        if (fioFormat === 'IFO') {
            parts = [formattedName, formattedSurname, formattedPatronymic].filter(Boolean);
        } else {
            parts = [formattedSurname, formattedName, formattedPatronymic].filter(Boolean);
        }
        return parts.join(' ').trim();
    }

    // Обработка клика по строке для предпросмотра
    function attachRowClickListener(row) {
        row.addEventListener('click', () => {
            const cells = row.querySelectorAll('td');
            const id = cells[0].textContent;
            const name = cells[1].querySelector('input').value || '';
            const surname = cells[2].querySelector('input').value || '';
            const patronymic = cells[3].querySelector('input').value || '';
            const act = cells[4].querySelector('input').value || '';
            const team = cells[5].querySelector('input').value || '';
            const territory = cells[6].querySelector('input').value || '';

            const fioText = formatFIO(
                name,
                surname,
                patronymic,
                shortName.checked,
                shortSurname.checked,
                shortPatronymic.checked
            );
            const teamText = [team, territory].filter(Boolean).join(', ');
            document.getElementById('previewFIO').textContent = fioText || '';
            document.getElementById('previewNumber').textContent = id;
            document.getElementById('previewAct').textContent = act || '';
            document.getElementById('previewTeam').textContent = teamText;

            document.querySelectorAll('.label').forEach(label => {
                const parent = label.parentElement;
                const span = parent.querySelector('span:not(.label)');
                label.classList.toggle('hidden', span.textContent !== '');
            });
        });
    }

    // Инициализация слушателей для первой строки
    document.querySelectorAll('#tableBody tr').forEach(row => {
        attachInputListeners(row);
        attachRowClickListener(row);
    });

    // Загрузка данных с сервера при загрузке страницы
    function splitFIO(fioText) {
        const parts = (fioText || '').trim().split(/\s+/).filter(Boolean);
        if (fioFormat === 'IFO') {
            return {
                name: parts[0] || '',
                surname: parts[1] || '',
                patronymic: parts.slice(2).join(' ')
            };
        }
        return {
            surname: parts[0] || '',
            name: parts[1] || '',
            patronymic: parts.slice(2).join(' ')
        };
    }

    function loadEntriesFromServer() {
        fetch('/entries')
            .then(response => response.json())
            .then(data => {
                const tableBody = document.getElementById('tableBody');
                tableBody.innerHTML = '';
                rowCount = 0;
                data.forEach(entry => {
                    addNewRow(false); // Добавляем без отправки на сервер
                    const newRow = tableBody.lastChild;
                    const inputs = newRow.querySelectorAll('input');
                    const fio = entry.first_name || entry.last_name || entry.patronymic
                        ? {
                            name: entry.first_name || '',
                            surname: entry.last_name || '',
                            patronymic: entry.patronymic || ''
                        }
                        : splitFIO(entry.name);
                    inputs[0].value = fio.name || ''; // Имя
                    inputs[1].value = fio.surname || ''; // Фамилия
                    inputs[2].value = fio.patronymic || ''; // Отчество
                    inputs[3].value = entry.performance || '';
                    inputs[4].value = entry.group || '';
                    inputs[5].value = entry.territory || '';
                });
            })
            .catch(error => {
                document.getElementById('importMessage').textContent = `Ошибка загрузки данных с сервера: ${error.message}`;
            });
    }

    loadEntriesFromServer();

    // Обработчик кнопки синхронизации
    const syncButton = document.getElementById('syncButton');
    syncButton.addEventListener('click', () => {
        loadEntriesFromServer();
        document.getElementById('importMessage').textContent = 'Данные синхронизированы.';
    });

    // Обработчик кнопки удаления пустых строк
    const clearEmptyRowsButton = document.getElementById('clearEmptyRowsButton');
    clearEmptyRowsButton.addEventListener('click', () => {
        cleanEmptyRows();
    });

    const clearEntriesButton = document.getElementById("clearEntriesButton");
  clearEntriesButton?.addEventListener("click", async () => {
    if (!confirm("Очистить список выступающих? Это действие нельзя отменить.")) return;

    const resp = await fetch("/entries/clear", { method: "POST" });
    if (resp.ok) {
      loadEntriesFromServer();
      document.getElementById("importMessage").textContent = "Список выступающих очищен.";
    } else {
      document.getElementById("importMessage").textContent = "Не удалось очистить список.";
    }
  });


// Управление областью предпросмотра и сеткой
const previewContent = document.getElementById('previewContent');
const previewWidthInput = document.getElementById('previewWidth');
const previewHeightInput = document.getElementById('previewHeight');
const toggleGridButton = document.getElementById('toggleGrid');
const gridRowsInput = document.getElementById('gridRows');
const gridColsInput = document.getElementById('gridCols');
const resetLayoutButton = document.getElementById('resetLayout');
const toggleFioSettingsButton = document.getElementById('toggleFioSettings');
const fioSettings = document.getElementById('fioSettings');
const capitalizeFIOButton = document.getElementById('capitalizeFIO');
const setFIOButton = document.getElementById('setFIO');
const setIFOButton = document.getElementById('setIFO');
const showFIOBlock = document.getElementById('showFIOBlock');
const showNumberBlock = document.getElementById('showNumberBlock');
const showActBlock = document.getElementById('showActBlock');
const showTeamBlock = document.getElementById('showTeamBlock');
let isGridVisible = false;
let currentDraggable = null;

function updateBlockVisibility() {
    document.getElementById('fioBlock').style.display = showFIOBlock.checked ? 'flex' : 'none';
    document.getElementById('numberBlock').style.display = showNumberBlock.checked ? 'flex' : 'none';
    document.getElementById('actBlock').style.display = showActBlock.checked ? 'flex' : 'none';
    document.getElementById('teamBlock').style.display = showTeamBlock.checked ? 'flex' : 'none';
    updateMinSize();
}

[showFIOBlock, showNumberBlock, showActBlock, showTeamBlock].forEach(checkbox => {
    checkbox.addEventListener('change', updateBlockVisibility);
});

toggleFioSettingsButton.addEventListener('click', () => {
    fioSettings.classList.toggle('hidden');
});

capitalizeFIOButton.addEventListener('click', () => {
    const rows = document.querySelectorAll('#tableBody tr');
    rows.forEach(row => {
        const inputs = row.querySelectorAll('td input');
        inputs[0].value = inputs[0].value ? inputs[0].value.charAt(0).toUpperCase() + inputs[0].value.slice(1) : '';
        inputs[1].value = inputs[1].value ? inputs[1].value.charAt(0).toUpperCase() + inputs[1].value.slice(1) : '';
        inputs[2].value = inputs[2].value ? inputs[2].value.charAt(0).toUpperCase() + inputs[2].value.slice(1) : '';
    });
    const activeRow = document.querySelector('#tableBody tr:hover') || document.querySelector('#tableBody tr:last-child');
    if (activeRow) activeRow.click();
});

setFIOButton.addEventListener('click', () => {
    fioFormat = 'FIO';
    const activeRow = document.querySelector('#tableBody tr:hover') || document.querySelector('#tableBody tr:last-child');
    if (activeRow) activeRow.click();
});

setIFOButton.addEventListener('click', () => {
    fioFormat = 'IFO';
    const activeRow = document.querySelector('#tableBody tr:hover') || document.querySelector('#tableBody tr:last-child');
    if (activeRow) activeRow.click();
});

[shortName, shortSurname, shortPatronymic].forEach(elem => {
    elem.addEventListener('change', () => {
        const activeRow = document.querySelector('#tableBody tr:hover') || document.querySelector('#tableBody tr:last-child');
        if (activeRow) activeRow.click();
    });
});

    function updateMinSize() {
        const draggables = document.querySelectorAll('.draggable');
        let minWidth = 200;
        let minHeight = 200;

        draggables.forEach(draggable => {
            if (draggable.style.display !== 'none') {
                const rect = draggable.getBoundingClientRect();
                const rightEdge = parseFloat(draggable.style.left || 0) + rect.width;
                const bottomEdge = parseFloat(draggable.style.top || 0) + rect.height;
                minWidth = Math.max(minWidth, rightEdge + 10);
                minHeight = Math.max(minHeight, bottomEdge + 10);

                const textElement = draggable.querySelector('span:not(.label)');
                const text = textElement ? textElement.textContent : 'Sample Text';

                const tempSpan = document.createElement('span');
                tempSpan.style.fontSize = draggable.style.fontSize || '16px';
                tempSpan.style.fontFamily = draggable.style.fontFamily || 'Arial';
                tempSpan.style.fontWeight = draggable.style.fontWeight || 'normal';
                tempSpan.style.fontStyle = draggable.style.fontStyle || 'normal';
                tempSpan.style.position = 'absolute';
                tempSpan.style.visibility = 'hidden';
                tempSpan.textContent = text;
                document.body.appendChild(tempSpan);
                const textWidth = tempSpan.offsetWidth + 20;
                const textHeight = tempSpan.offsetHeight + 20;
                document.body.removeChild(tempSpan);

                draggable.style.minWidth = `${textWidth}px`;
                draggable.style.minHeight = `${textHeight}px`;
            }
        });

        previewContent.style.minWidth = `${minWidth}px`;
        previewContent.style.minHeight = `${minHeight}px`;
        previewWidthInput.min = minWidth;
        previewHeightInput.min = minHeight;
    }

    function syncPreviewSize() {
        previewWidthInput.value = Math.round(previewContent.offsetWidth);
        previewHeightInput.value = Math.round(previewContent.offsetHeight);
    }

    function updatePreviewSize() {
        previewContent.style.width = `${previewWidthInput.value}px`;
        previewContent.style.height = `${previewHeightInput.value}px`;
        updateMinSize();
        updateGrid();
    }
    previewWidthInput.addEventListener('input', updatePreviewSize);
    previewHeightInput.addEventListener('input', updatePreviewSize);
    updatePreviewSize();

    // Проверка поддержки ResizeObserver
    if (typeof ResizeObserver === 'undefined') {
        console.warn('ResizeObserver не поддерживается, используем альтернативу.');
        setInterval(syncPreviewSize, 500);
    } else {
        new ResizeObserver(syncPreviewSize).observe(previewContent);
    }

    function updateGrid() {
        const rows = parseInt(gridRowsInput.value) || 10;
        const cols = parseInt(gridColsInput.value) || 10;
        const width = previewContent.offsetWidth;
        const height = previewContent.offsetHeight;
        previewContent.style.setProperty('--grid-size-x', `${width / cols}px`);
        previewContent.style.setProperty('--grid-size-y', `${height / rows}px`);
    }
    gridRowsInput.addEventListener('input', updateGrid);
    gridColsInput.addEventListener('input', updateGrid);
    updateGrid();

    toggleGridButton.addEventListener('click', () => {
        isGridVisible = !isGridVisible;
        previewContent.classList.toggle('grid', isGridVisible);
        toggleGridButton.textContent = isGridVisible ? 'Выкл сетку' : 'Вкл сетку';
    });

    function resetLayout() {
        const draggables = document.querySelectorAll('.draggable');
        let currentY = 10;
        draggables.forEach((draggable) => {
            if (draggable.style.display !== 'none') {
                draggable.style.left = '10px';
                draggable.style.top = `${currentY}px`;
                draggable.style.height = 'auto';
                draggable.style.width = 'auto';
                draggable.style.textAlign = 'center';
                draggable.style.alignItems = 'center';
                currentY += 60;
            }
        });
        updateMinSize();
    }
    resetLayoutButton.addEventListener('click', resetLayout);
    resetLayout();

    const draggables = document.querySelectorAll('.draggable');
    let selectedBlock = null;

    const fontSizeInput = document.getElementById('fontSize');
    const fontFamilySelect = document.getElementById('fontFamily');
    const fontBoldCheckbox = document.getElementById('fontBold');
    const fontItalicCheckbox = document.getElementById('fontItalic');
    const alignLeftButton = document.getElementById('alignLeft');
    const alignCenterButton = document.getElementById('alignCenter');
    const alignRightButton = document.getElementById('alignRight');
    const alignTopButton = document.getElementById('alignTop');
    const alignMiddleButton = document.getElementById('alignMiddle');
    const alignBottomButton = document.getElementById('alignBottom');

    function applyStyles() {
        if (selectedBlock) {
            selectedBlock.style.fontSize = `${fontSizeInput.value}px`;
            selectedBlock.style.fontFamily = fontFamilySelect.value;
            selectedBlock.style.fontWeight = fontBoldCheckbox.checked ? 'bold' : 'normal';
            selectedBlock.style.fontStyle = fontItalicCheckbox.checked ? 'italic' : 'normal';
            updateMinSize();
        }
    }

    alignLeftButton.addEventListener('click', () => {
        if (selectedBlock) {
            selectedBlock.style.textAlign = 'left';
        }
    });

    alignCenterButton.addEventListener('click', () => {
        if (selectedBlock) {
            selectedBlock.style.textAlign = 'center';
        }
    });

    alignRightButton.addEventListener('click', () => {
        if (selectedBlock) {
            selectedBlock.style.textAlign = 'right';
        }
    });

    alignTopButton.addEventListener('click', () => {
        if (selectedBlock) {
            selectedBlock.style.alignItems = 'flex-start';
        }
    });

    alignMiddleButton.addEventListener('click', () => {
        if (selectedBlock) {
            selectedBlock.style.alignItems = 'center';
        }
    });

    alignBottomButton.addEventListener('click', () => {
        if (selectedBlock) {
            selectedBlock.style.alignItems = 'flex-end';
        }
    });

    fontSizeInput.addEventListener('input', applyStyles);
    fontFamilySelect.addEventListener('change', applyStyles);
    fontBoldCheckbox.addEventListener('change', applyStyles);
    fontItalicCheckbox.addEventListener('change', applyStyles);

    draggables.forEach(draggable => {
        draggable.addEventListener('mousedown', () => {
            selectedBlock = draggable;
            applyStyles();
        });

        draggable.addEventListener('dragstart', (event) => {
            currentDraggable = draggable;
            draggable.classList.add('dragging');
            event.dataTransfer.setData('text/plain', draggable.id);
        });

        draggable.addEventListener('dragend', () => {
            currentDraggable = null;
            draggable.classList.remove('dragging');
            updateMinSize();
        });
    });

    previewContent.addEventListener('dragover', (e) => {
        e.preventDefault();
        if (!currentDraggable) return;

        const rect = previewContent.getBoundingClientRect();
        let x = e.clientX - rect.left - currentDraggable.offsetWidth / 2;
        let y = e.clientY - rect.top - currentDraggable.offsetHeight / 2;

        x = Math.max(0, Math.min(x, rect.width - currentDraggable.offsetWidth));
        y = Math.max(0, Math.min(y, rect.height - currentDraggable.offsetHeight));

        if (isGridVisible) {
            const rows = parseInt(gridRowsInput.value) || 10;
            const cols = parseInt(gridColsInput.value) || 10;
            const gridSizeX = rect.width / cols;
            const gridSizeY = rect.height / rows;
            x = Math.round(x / gridSizeX) * gridSizeX;
            y = Math.round(y / gridSizeY) * gridSizeY;
        } else {
            const snapThreshold = 20;
            let closestX = x, closestY = y;
            let minDistance = Infinity;

            draggables.forEach(other => {
                if (other !== currentDraggable && other.style.display !== 'none') {
                    const otherRect = other.getBoundingClientRect();
                    const otherX = otherRect.left - rect.left;
                    const otherY = otherRect.top - rect.top;
                    const otherRight = otherX + otherRect.width;
                    const otherBottom = otherY + otherRect.height;

                    const newX = x, newY = y;
                    const newRight = newX + currentDraggable.offsetWidth;
                    const newBottom = newY + currentDraggable.offsetHeight;

                    if (newX < otherRight && newRight > otherX && newY < otherBottom && newBottom > otherY) {
                        const possiblePositions = [
                            { x: otherX - currentDraggable.offsetWidth, y: newY },
                            { x: otherRight, y: newY },
                            { x: newX, y: otherY - currentDraggable.offsetHeight },
                            { x: newX, y: otherBottom }
                        ];

                        possiblePositions.forEach(pos => {
                            const px = Math.max(0, Math.min(pos.x, rect.width - currentDraggable.offsetWidth));
                            const py = Math.max(0, Math.min(pos.y, rect.height - currentDraggable.offsetHeight));
                            const distance = Math.hypot(px - x, py - y);
                            if (distance < minDistance && !isOverlapping(px, py, currentDraggable)) {
                                minDistance = distance;
                                closestX = px;
                                closestY = py;
                            }
                        });
                    } else {
                        const edges = [
                            { x: otherX, y: newY, distance: Math.abs(otherX - x) },
                            { x: otherRight, y: newY, distance: Math.abs(otherRight - x) },
                            { x: newX, y: otherY, distance: Math.abs(otherY - y) },
                            { x: newX, y: otherBottom, distance: Math.abs(otherBottom - y) }
                        ];

                        edges.forEach(edge => {
                            if (edge.distance < snapThreshold && edge.distance < minDistance) {
                                minDistance = edge.distance;
                                closestX = edge.x;
                                closestY = edge.y;
                            }
                        });
                    }
                }
            });

            x = closestX;
            y = closestY;
        }

        currentDraggable.style.left = `${x}px`;
        currentDraggable.style.top = `${y}px`;
    });

    function isOverlapping(x, y, draggable) {
        const rect = previewContent.getBoundingClientRect();
        const newRight = x + draggable.offsetWidth;
        const newBottom = y + draggable.offsetHeight;
        let overlap = false;
        draggables.forEach(other => {
            if (other !== draggable && other.style.display !== 'none') {
                const otherRect = other.getBoundingClientRect();
                const otherX = otherRect.left - rect.left;
                const otherY = otherRect.top - rect.top;
                const otherRight = otherX + otherRect.width;
                const otherBottom = otherY + otherRect.height;

                if (x < otherRight && newRight > otherX && y < otherBottom && newBottom > otherY) {
                    overlap = true;
                }
            }
        });
        return overlap;
    }

    // Загрузка Excel-файла
    const uploadFile = document.getElementById('uploadFile');
    uploadFile.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (!file) return;

        if (typeof XLSX === 'undefined') {
            document.getElementById('importMessage').textContent = 'Ошибка: Библиотека SheetJS не загружена. Проверьте подключение.';
            return;
        }

        const reader = new FileReader();
        reader.onload = (event) => {
            try {
                const data = event.target.result;
                const workbook = XLSX.read(data, { type: 'binary' });
                const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
                const rows = XLSX.utils.sheet_to_json(firstSheet, { header: 1 });
                displayUploadTable(rows);
            } catch (error) {
                document.getElementById('importMessage').textContent = `Ошибка при чтении файла: ${error.message}`;
            }
        };
        reader.onerror = () => {
            document.getElementById('importMessage').textContent = 'Ошибка при загрузке файла.';
        };
        reader.readAsBinaryString(file);
    });

    // Отображение загруженной таблицы
    function displayUploadTable(rows) {
        const container = document.getElementById('uploadTableContainer');
        container.innerHTML = '';
        if (rows.length === 0) {
            document.getElementById('importMessage').textContent = 'Файл пуст.';
            return;
        }
        const table = document.createElement('table');
        table.classList.add('upload-table');
        const thead = document.createElement('thead');
        const tbody = document.createElement('tbody');
        const headers = rows[0];
        const headerRow = document.createElement('tr');
        headers.forEach((header) => {
            const th = document.createElement('th');
            th.textContent = header;
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);
        for (let i = 1; i < rows.length; i++) {
            const row = document.createElement('tr');
            rows[i].forEach((cell) => {
                const td = document.createElement('td');
                td.textContent = cell || '';
                row.appendChild(td);
            });
            tbody.appendChild(row);
        }
        table.appendChild(thead);
        table.appendChild(tbody);
        container.appendChild(table);
        createMappingSelects(headers);
    }

    // Создание выпадающих списков для маппинга
    const fields = [
        { id: 'mapFio', label: 'ФИО', class: 'mapped-fio' },
        { id: 'mapAct', label: 'Название номера', class: 'mapped-act' },
        { id: 'mapTeam', label: 'Название коллектива', class: 'mapped-team' },
        { id: 'mapTerritory', label: 'Территория', class: 'mapped-territory' }
    ];

  function createMappingSelects(headers) {
    const mappingSection = document.getElementById('mappingSection');
    mappingSection.innerHTML = '';

    fields.forEach(field => {
        const label = document.createElement('label');
        label.textContent = field.label + ': ';

        const select = document.createElement('select');
        select.id = field.id;

        const opt = document.createElement('option');
        opt.value = '';
        opt.textContent = 'Не использовать';
        select.appendChild(opt);

        headers.forEach((header, index) => {
            const option = document.createElement('option');
            option.value = index;
            option.textContent = header;
            select.appendChild(option);
        });

        select.addEventListener('change', updateColumnColors);

        label.appendChild(select);
        mappingSection.appendChild(label);
    });
}


    // Обновление цветов колонок
    function updateColumnColors() {
        const table = document.querySelector('.upload-table');
        if (!table) return;
        table.querySelectorAll('td').forEach(td => {
            fields.forEach(field => td.classList.remove(field.class));
        });
        fields.forEach(field => {
            const select = document.getElementById(field.id);
            const columnIndex = select.value;
            if (columnIndex !== '') {
                const index = parseInt(columnIndex);
                table.querySelectorAll(`tbody tr td:nth-child(${index + 1})`).forEach(td => {
                    td.classList.add(field.class);
                });
            }
        });
    }

    // Импорт данных
    const importButton = document.getElementById('importButton');
    importButton.addEventListener('click', () => {
        const table = document.querySelector('.upload-table');
        if (!table) {
            document.getElementById('importMessage').textContent = 'Сначала загрузите файл.';
            return;
        }
        const rows = table.querySelectorAll('tbody tr');
        if (rows.length === 0) {
            document.getElementById('importMessage').textContent = 'Нет данных для импорта.';
            return;
        }
        const mapping = {};
        fields.forEach(field => {
            const select = document.getElementById(field.id);
            if (select.value !== '') {
                mapping[field.label] = parseInt(select.value);
            }
        });
        let importedCount = 0;
        rows.forEach(row => {
            const cells = row.querySelectorAll('td');
            addNewRow(true); // Отправляем на сервер
            const newRow = document.querySelector('#tableBody tr:last-child');
            const inputs = newRow.querySelectorAll('input');
            if ('ФИО' in mapping) {
                const fio = cells[mapping['ФИО']].textContent.split(' ');
                inputs[0].value = fio[1] || ''; // Имя
                inputs[1].value = fio[0] || ''; // Фамилия
                inputs[2].value = fio[2] || ''; // Отчество
            }
            if ('Название номера' in mapping) inputs[3].value = cells[mapping['Название номера']].textContent;
            if ('Название коллектива' in mapping) inputs[4].value = cells[mapping['Название коллектива']].textContent;
            if ('Территория' in mapping) inputs[5].value = cells[mapping['Территория']].textContent;
            importedCount++;
        });
        document.getElementById('importMessage').textContent = `Импортировано ${importedCount} участников.`;
    });

  // ===== VK modal handlers =====
  const vkStreamButton = document.getElementById("vkStreamButton");
  const vkModal = document.getElementById("vkModal");
  const vkCloseBtn = document.getElementById("vkCloseBtn");
  const vkScheduleBtn = document.getElementById("vkScheduleBtn");
  const vkStopBtn = document.getElementById("vkStopBtn");
  const vkOverlayToggleBtn = document.getElementById("vkOverlayToggle");
  const vkTabs = document.querySelectorAll(".vk-tab");
  const vkTabPanels = document.querySelectorAll(".vk-tab-panel");

  const vkPreviewVideo = document.getElementById("vkPreviewVideo");
  const vkPreviewImage = document.getElementById("vkPreviewImage");
  const vkImageInput = document.getElementById("vkImage");

  const vkTargetsList = document.getElementById("vkTargetsList");
  const vkTargetName = document.getElementById("vkTargetName");
  const vkTargetUrl = document.getElementById("vkTargetUrl");
  const vkAddTargetBtn = document.getElementById("vkAddTargetBtn");
  const vkSaveTargetsBtn = document.getElementById("vkSaveTargetsBtn");
  const vkStartTargetsBtn = document.getElementById("vkStartTargetsBtn");

  let streamUrl = "";
  let vkTargets = [];
  let selectedTargetIds = [];
  let hlsInstance = null;
  let lastVkPreviewUrl = "";
  let showPreviewOnly = false;

  function updateOverlayToggleButton() {
    if (!vkOverlayToggleBtn) return;
    vkOverlayToggleBtn.classList.toggle("active", showPreviewOnly);
    vkOverlayToggleBtn.textContent = showPreviewOnly
      ? "Показать изображение: включено"
      : "Показать изображение: выключено";
  }

  function applyPreviewVisibility() {
    if (showPreviewOnly) {
      showVkPreviewImage(lastVkPreviewUrl);
    } else if (streamUrl) {
      showVkPreviewVideo();
    } else {
      showVkPreviewImage(lastVkPreviewUrl);
    }
    updateOverlayToggleButton();
  }

  function stopVkPreviewPlayer() {
    if (!vkPreviewVideo) return;
    if (hlsInstance) {
      hlsInstance.destroy();
      hlsInstance = null;
    }
    vkPreviewVideo.pause();
    vkPreviewVideo.removeAttribute("src");
    vkPreviewVideo.load();
  }

  function setVkPreviewImage(url) {
    if (!vkPreviewImage) return;
    if (url) {
      lastVkPreviewUrl = url;
      vkPreviewImage.src = url;
      vkPreviewImage.classList.add("visible");
    } else {
      vkPreviewImage.classList.remove("visible");
    }
  }

  function showVkPreviewImage(url) {
    setVkPreviewImage(url || lastVkPreviewUrl);
    vkPreviewVideo?.classList.add("hidden");
  }

  function showVkPreviewVideo() {
    vkPreviewVideo?.classList.remove("hidden");
    vkPreviewImage?.classList.remove("visible");
  }

  function initVkPreviewPlayer(nextStreamUrl) {
    if (!vkPreviewVideo || !nextStreamUrl) {
      stopVkPreviewPlayer();
      showVkPreviewImage(lastVkPreviewUrl);
      return;
    }

    if (hlsInstance) {
      hlsInstance.destroy();
      hlsInstance = null;
    }

    const HlsCtor = globalThis.Hls;
    if (HlsCtor && HlsCtor.isSupported()) {
      hlsInstance = new HlsCtor();
      hlsInstance.loadSource(nextStreamUrl);
      hlsInstance.attachMedia(vkPreviewVideo);
      hlsInstance.on(HlsCtor.Events.ERROR, () => {
        stopVkPreviewPlayer();
        showVkPreviewImage(lastVkPreviewUrl);
      });
    } else if (vkPreviewVideo.canPlayType("application/vnd.apple.mpegurl")) {
      vkPreviewVideo.src = nextStreamUrl;
    }
    showVkPreviewVideo();
  }

  function renderVkTargets() {
    if (!vkTargetsList) return;
    vkTargetsList.innerHTML = "";

    vkTargets.forEach((target) => {
      const wrapper = document.createElement("div");
      wrapper.className = "vk-target";

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = selectedTargetIds.includes(target.id);
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) {
          selectedTargetIds = [...new Set([...selectedTargetIds, target.id])];
        } else {
          selectedTargetIds = selectedTargetIds.filter((id) => id !== target.id);
        }
      });

      const content = document.createElement("div");

      const nameInput = document.createElement("input");
      nameInput.type = "text";
      nameInput.value = target.name || "";
      nameInput.addEventListener("change", () => updateTarget(target.id, { name: nameInput.value }));

      const urlInput = document.createElement("input");
      urlInput.type = "text";
      urlInput.value = target.url || "";
      urlInput.placeholder = "rtmp://...";
      urlInput.addEventListener("change", () => updateTarget(target.id, { url: urlInput.value }));

      content.appendChild(nameInput);
      content.appendChild(urlInput);

      wrapper.appendChild(checkbox);
      wrapper.appendChild(content);
      vkTargetsList.appendChild(wrapper);
    });
  }

  async function updateTarget(targetId, payload) {
    await fetch(`/stream/targets/${targetId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  async function loadVkStatus() {
    const resp = await fetch("/vk/status");
    if (!resp.ok) return;

    const data = await resp.json();
    selectedTargetIds = data.target_ids || [];
    vkTargets = data.targets || [];
    streamUrl = data.stream_url || "";

    const titleInput = document.getElementById("vkTitle");
    if (titleInput) titleInput.value = data.title || "";

    if (data.preview_url) setVkPreviewImage(data.preview_url);
    showPreviewOnly = Boolean(data.show_preview);
    applyPreviewVisibility();
    if (streamUrl && !showPreviewOnly) {
      initVkPreviewPlayer(streamUrl);
    } else if (!streamUrl) {
      stopVkPreviewPlayer();
    }
    renderVkTargets();
  }

  // Tabs switching
  vkTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      vkTabs.forEach((t) => t.classList.remove("active"));
      vkTabPanels.forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      const key = tab.dataset.tab;
      document.querySelector(`.vk-tab-panel[data-panel="${key}"]`)?.classList.add("active");
    });
  });

  vkStreamButton?.addEventListener("click", (e) => {
    e.preventDefault();
    vkModal?.classList.add("visible");
    loadVkStatus();
  });

  vkImageInput?.addEventListener("change", async () => {
    const file = vkImageInput.files?.[0];
    if (!file) return;

    const form = new FormData();
    form.append("image", file);

    const resp = await fetch("/vk/preview", { method: "POST", body: form });
    if (resp.ok) {
      const data = await resp.json();
      if (data.preview_url) {
        setVkPreviewImage(data.preview_url);
        lastVkPreviewUrl = data.preview_url;
        applyPreviewVisibility();
      }
    } else {
      document.getElementById("importMessage").textContent = "Не удалось сохранить превью.";
    }
  });

  vkCloseBtn?.addEventListener("click", () => {
    vkModal?.classList.remove("visible");
  });

  vkOverlayToggleBtn?.addEventListener("click", async () => {
    const nextValue = !showPreviewOnly;
    const resp = await fetch("/vk/preview_visibility", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ show_preview: nextValue }),
    });
    if (resp.ok) {
      const data = await resp.json();
      showPreviewOnly = Boolean(data.show_preview);
      applyPreviewVisibility();
    }
  });

  vkAddTargetBtn?.addEventListener("click", async () => {
    const name = vkTargetName?.value.trim() || "";
    if (!name) return;

    const resp = await fetch("/stream/targets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, url: vkTargetUrl?.value.trim() || "" }),
    });

    if (resp.ok) {
      if (vkTargetName) vkTargetName.value = "";
      if (vkTargetUrl) vkTargetUrl.value = "";
      loadVkStatus();
    }
  });

  vkSaveTargetsBtn?.addEventListener("click", async () => {
    await fetch("/vk/targets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_ids: selectedTargetIds }),
    });
  });

  vkStopBtn?.addEventListener("click", async () => {
    const resp = await fetch("/vk/stop", { method: "POST" });
    if (resp.ok) {
      stopVkPreviewPlayer();
      showVkPreviewImage(lastVkPreviewUrl);
      vkModal?.classList.remove("visible");
    }
    else alert("Ошибка.");
  });

  vkStartTargetsBtn?.addEventListener("click", async () => {
    const title = document.getElementById("vkTitle")?.value || "";
    if (selectedTargetIds.length === 0) {
      alert("Выберите хотя бы одно направление трансляции.");
      return;
    }

    const resp = await fetch("/vk/start_now", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, target_ids: selectedTargetIds }),
    });

    if (resp.ok) {
      showPreviewOnly = false;
      applyPreviewVisibility();
      vkModal?.classList.remove("visible");
    }
    else alert("Ошибка старта.");
  });

  vkScheduleBtn?.addEventListener("click", async () => {
    const title = document.getElementById("vkTitle")?.value || "";
    const date = document.getElementById("vkDate")?.value || "";
    const time = document.getElementById("vkTime")?.value || "";
    const file = document.getElementById("vkImage")?.files?.[0];

    if (!date || !time) {
      alert("Укажите дату и время трансляции.");
      return;
    }

    const form = new FormData();
    form.append("title", title);
    form.append("date", date);
    form.append("time", time);
    selectedTargetIds.forEach((id) => form.append("target_ids", id));
    if (file) form.append("image", file);

    const resp = await fetch("/vk/schedule", { method: "POST", body: form });
    if (resp.ok) vkModal?.classList.remove("visible");
    else alert("Ошибка планирования.");
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initAdmin);
} else {
  initAdmin();
}
