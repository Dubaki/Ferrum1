const tg = window.Telegram.WebApp;
tg.expand();

// Массив для хранения всех документов
let documents = [];
let currentDocIndex = 0;
let loadingInterval = null;

// Функция валидации ИНН (10 или 12 цифр)
function validateINN(inn) {
    return /^\d{10}$|^\d{12}$/.test(inn.trim());
}

// Fallback функции для старых версий Telegram
function showAlert(message) {
    try {
        if (typeof tg.showAlert === 'function') {
            tg.showAlert(message);
        } else {
            throw new Error('showAlert not supported');
        }
    } catch (e) {
        window.alert(message);
    }
}

function showConfirm(message, callback) {
    try {
        if (typeof tg.showConfirm === 'function') {
            tg.showConfirm(message, callback);
        } else {
            throw new Error('showConfirm not supported');
        }
    } catch (e) {
        const result = window.confirm(message);
        callback(result);
    }
}

function hapticFeedback(type, style) {
    if (tg.HapticFeedback) {
        if (type === 'notification' && typeof tg.HapticFeedback.notificationOccurred === 'function') {
            tg.HapticFeedback.notificationOccurred(style);
        } else if (type === 'impact' && typeof tg.HapticFeedback.impactOccurred === 'function') {
            tg.HapticFeedback.impactOccurred(style);
        }
    }
}

// Настройка таблицы - авто-высота для читаемости
const table = new Tabulator("#grid-table", {
    layout: "fitColumns",
    responsiveLayout: "collapse",
    height: "auto",
    minHeight: 150,
    columns: [
        {title:"Арт.", field:"ItemArticle", editor:"input", widthGrow:1, headerFilter:"input"},
        {title:"Товар", field:"ItemName", editor:"input", widthGrow:3},
        {title:"Кол-во", field:"Quantity", editor:"number", widthGrow:1},
        {title:"Цена", field:"Price", editor:"number", widthGrow:1},
        {title:"Сумма", field:"Total", mutator:(v, d) => (d.Quantity * d.Price).toFixed(2), widthGrow:1}
    ]
});

// BackButton - возврат к сканированию (если поддерживается)
if (tg.BackButton && tg.BackButton.isSupported) {
    tg.BackButton.onClick(() => {
        showConfirm("Вернуться к сканированию? Несохраненные изменения будут потеряны.", (confirmed) => {
            if (confirmed) {
                resetToScan();
            }
        });
    });
}

function resetToScan() {
    documents = [];
    currentDocIndex = 0;
    document.getElementById('result-section').classList.add('hidden');
    document.getElementById('scan-section').querySelector('button').classList.remove('hidden');
    document.getElementById('file-input').value = '';
    document.getElementById('image-preview').classList.add('hidden');
    table.clearData();
    tg.MainButton.hide();
    if (tg.BackButton && tg.BackButton.hide) {
        tg.BackButton.hide();
    }
    updateDocumentsList();
}

// Обработка множественной загрузки файлов
document.getElementById('file-input').addEventListener('change', async (e) => {
    const files = Array.from(e.target.files);
    if (files.length === 0) return;

    // Проверка размера файлов
    const MAX_SIZE = 10 * 1024 * 1024;
    for (const file of files) {
        if (file.size > MAX_SIZE) {
            showAlert(`❌ Файл "${file.name}" слишком большой (максимум 10MB)`);
            hapticFeedback('notification','error');
            return;
        }
    }

    // Показываем лоадер
    document.getElementById('scan-section').querySelector('button').classList.add('hidden');
    const loader = document.getElementById('loader');
    loader.classList.remove('hidden');

    // Обрабатываем файлы последовательно
    let processedCount = 0;
    const totalFiles = files.length;

    for (let i = 0; i < files.length; i++) {
        const file = files[i];

        // Обновляем текст загрузки
        const loaderText = loader.querySelector('p');
        loaderText.textContent = `Обрабатываю документ ${i + 1} из ${totalFiles}`;

        // Анимация точек
        let dots = 0;
        loadingInterval = setInterval(() => {
            dots = (dots + 1) % 4;
            loaderText.textContent = `Обрабатываю документ ${i + 1} из ${totalFiles}` + ".".repeat(dots);
        }, 500);

        try {
            // Читаем превью
            const preview = await readFileAsDataURL(file);

            // Отправляем на распознавание
            const formData = new FormData();
            formData.append('file', file);
            const response = await fetch('/api/scan', { method: 'POST', body: formData });
            const result = await response.json();

            // Останавливаем анимацию
            if (loadingInterval) {
                clearInterval(loadingInterval);
                loadingInterval = null;
            }

            if (result.Items && result.Items.length > 0) {
                // Для PDF используем превью из ответа API (первая страница)
                const docPreview = result.preview || preview;

                // Добавляем документ в массив
                documents.push({
                    id: Date.now() + i,
                    fileName: file.name,
                    preview: docPreview,
                    data: result,
                    status: 'ready' // ready, sent, error
                });
                processedCount++;
                hapticFeedback('notification','success');
            } else if (result.error) {
                showAlert(`❌ Ошибка при обработке "${file.name}":\n${result.error}`);
                hapticFeedback('notification','error');
            } else {
                showAlert(`❌ Товары не найдены в "${file.name}"`);
                hapticFeedback('notification','warning');
            }
        } catch (err) {
            if (loadingInterval) {
                clearInterval(loadingInterval);
                loadingInterval = null;
            }
            showAlert(`❌ Ошибка сети при обработке "${file.name}": ${err.message}`);
            hapticFeedback('notification','error');
        }
    }

    // Скрываем лоадер
    loader.classList.add('hidden');

    if (processedCount > 0) {
        // Показываем результаты
        currentDocIndex = 0;
        showDocument(0);
        updateDocumentsList();
        document.getElementById('result-section').classList.remove('hidden');
        if (tg.BackButton && tg.BackButton.show) {
            tg.BackButton.show();
        }
        hapticFeedback('notification','success');

        // Показываем статус только для множественной загрузки
        if (totalFiles > 1) {
            showAlert(`✅ Обработано: ${processedCount} из ${totalFiles}`);
        }
    } else {
        // Если ни один документ не обработан
        resetUI();
    }
});

// Функция для чтения файла как DataURL
function readFileAsDataURL(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target.result);
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

// Показать документ по индексу
function showDocument(index) {
    if (index < 0 || index >= documents.length) return;

    currentDocIndex = index;
    const doc = documents[index];

    // Обновляем превью
    const preview = document.getElementById('image-preview');
    const img = document.getElementById('preview-img');
    img.src = doc.preview;
    preview.classList.remove('hidden');

    // Заполняем поля
    document.getElementById('inn').value = doc.data.SupplierINN || "";
    document.getElementById('doc_num').value = doc.data.DocNumber || "";
    document.getElementById('doc_date').value = doc.data.DocDate || "";
    document.getElementById('total_sum').value = doc.data.TotalSum || 0;

    // Заполняем таблицу
    table.replaceData(doc.data.Items);

    // Обновляем кнопку отправки
    if (doc.status === 'sent') {
        tg.MainButton.setText('✅ Отправлено в 1С');
        tg.MainButton.show();
    } else {
        tg.MainButton.setText('📤 Отправить в 1С');
        tg.MainButton.show();
    }

    // Обновляем список документов
    updateDocumentsList();
}

// Обновление списка документов в UI
function updateDocumentsList() {
    const listContainer = document.getElementById('documents-list');

    if (documents.length === 0) {
        listContainer.classList.add('hidden');
        return;
    }

    listContainer.classList.remove('hidden');
    listContainer.innerHTML = '';

    documents.forEach((doc, index) => {
        const docItem = document.createElement('div');
        docItem.className = 'doc-item' + (index === currentDocIndex ? ' active' : '');

        let statusIcon = '📄';
        if (doc.status === 'sent') statusIcon = '✅';
        else if (doc.status === 'error') statusIcon = '❌';

        docItem.innerHTML = `
            <span class="doc-icon">${statusIcon}</span>
            <span class="doc-name">${doc.fileName || `Документ ${index + 1}`}</span>
            <span class="doc-number">${index + 1}/${documents.length}</span>
        `;

        docItem.onclick = () => {
            showDocument(index);
            hapticFeedback('impact','light');
        };

        listContainer.appendChild(docItem);
    });
}

function resetUI() {
    document.getElementById('loader').classList.add('hidden');
    document.getElementById('scan-section').querySelector('button').classList.remove('hidden');
    document.getElementById('image-preview').classList.add('hidden');
    if (loadingInterval) {
        clearInterval(loadingInterval);
        loadingInterval = null;
    }
}

// Сохранение изменений текущего документа
function saveCurrentDocument() {
    if (currentDocIndex < 0 || currentDocIndex >= documents.length) return;

    const doc = documents[currentDocIndex];
    doc.data.SupplierINN = document.getElementById('inn').value;
    doc.data.DocNumber = document.getElementById('doc_num').value;
    doc.data.DocDate = document.getElementById('doc_date').value;
    doc.data.TotalSum = document.getElementById('total_sum').value;
    doc.data.Items = table.getData();
}

// Отправка текущего документа
function sendCurrentDocument() {
    if (currentDocIndex < 0 || currentDocIndex >= documents.length) return;

    // Сохраняем изменения перед отправкой
    saveCurrentDocument();

    const doc = documents[currentDocIndex];
    const inn = doc.data.SupplierINN.trim();
    const items = doc.data.Items;

    // Валидация ИНН
    if (!inn) {
        showAlert("❌ Укажите ИНН поставщика");
        hapticFeedback('notification','error');
        return;
    }
    if (!validateINN(inn)) {
        showAlert("❌ Некорректный ИНН\n\nИНН должен содержать 10 или 12 цифр");
        hapticFeedback('notification','error');
        return;
    }

    // Валидация товаров
    if (items.length === 0) {
        showAlert("❌ Нет товаров для отправки");
        hapticFeedback('notification','error');
        return;
    }

    // Проверка на пустые товары
    const hasEmptyItems = items.some(item => !item.ItemName || item.ItemName.trim() === '');
    if (hasEmptyItems) {
        showAlert("❌ Есть товары без названия");
        hapticFeedback('notification','error');
        return;
    }

    const data = {
        SupplierINN: inn,
        DocNumber: doc.data.DocNumber,
        DocDate: doc.data.DocDate,
        TotalSum: doc.data.TotalSum,
        Items: items,
        documentIndex: currentDocIndex,
        totalDocuments: documents.length
    };

    // Отмечаем документ как отправленный
    doc.status = 'sent';
    updateDocumentsList();

    hapticFeedback('impact','medium');
    tg.sendData(JSON.stringify(data));
}

tg.MainButton.onClick(sendCurrentDocument);

// Кнопка добавления товара
document.getElementById('add-item-btn').addEventListener('click', () => {
    table.addRow({ItemArticle: "", ItemName: "", Quantity: 1, Price: 0, Total: 0}, true);
    hapticFeedback('impact','light');
});

// Кнопка очистки текущего документа
document.getElementById('clear-btn').addEventListener('click', () => {
    showConfirm("Удалить текущий документ из списка?", (confirmed) => {
        if (confirmed) {
            documents.splice(currentDocIndex, 1);

            if (documents.length === 0) {
                resetToScan();
            } else {
                // Показываем предыдущий или первый документ
                const newIndex = Math.min(currentDocIndex, documents.length - 1);
                showDocument(newIndex);
            }

            hapticFeedback('notification','success');
        }
    });
});

// Автосохранение при переключении документов
table.on("cellEdited", () => {
    saveCurrentDocument();
});

// Функции для modal просмотра фото
function openImageModal() {
    const previewImg = document.getElementById('preview-img');
    const modal = document.getElementById('image-modal');
    const modalImg = document.getElementById('modal-img');

    modalImg.src = previewImg.src;
    modal.classList.remove('hidden');
}

function closeImageModal() {
    document.getElementById('image-modal').classList.add('hidden');
}
