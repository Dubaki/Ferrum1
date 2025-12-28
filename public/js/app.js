const tg = window.Telegram.WebApp;
tg.expand();

// Настройка таблицы
const table = new Tabulator("#grid-table", {
    layout: "fitColumns",
    responsiveLayout: "collapse",
    columns: [
        {title:"Товар", field:"ItemName", editor:"input", widthGrow:2},
        {title:"Кол-во", field:"Quantity", editor:"number", widthGrow:1},
        {title:"Цена", field:"Price", editor:"number", widthGrow:1},
        {title:"Сумма", field:"Total", mutator:(v, d) => d.Quantity * d.Price, widthGrow:1}
    ]
});

// Обработка фото
document.getElementById('file-input').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    document.getElementById('scan-section').querySelector('button').classList.add('hidden');
    document.getElementById('loader').classList.remove('hidden');

    const formData = new FormData();
    formData.append('file', file);

    try {
        // Запрос к нашему API на Vercel
        const response = await fetch('/api/scan', { method: 'POST', body: formData });
        
        if (!response.ok) {
            throw new Error(`Ошибка сервера: ${response.status}`);
        }

        const result = await response.json();
        console.log("API Response:", result); // Лог в консоль браузера

        // Скрываем лоадер сразу после получения ответа
        document.getElementById('loader').classList.add('hidden');

        // Если пришла ошибка с сервера
        if (result.error) {
            alert("Ошибка AI: " + result.error);
            document.getElementById('scan-section').querySelector('button').classList.remove('hidden');
            return;
        }

        if (result.Items && result.Items.length > 0) {
            document.getElementById('result-section').classList.remove('hidden');
            
            // HACK: Нормализуем данные (защита от кривого JSON от AI и регистра ключей)
            const normalizedItems = result.Items.map(item => ({
                ItemName: item.ItemName || item.itemName || item.name || "Товар",
                Quantity: item.Quantity || item.quantity || item.qty || 1,
                Price: item.Price || item.price || 0,
                Total: item.Total || item.total || 0
            }));

            // Заполняем данные
            document.getElementById('inn').value = result.SupplierINN || "";
            document.getElementById('doc_num').value = result.DocNumber || "";
            document.getElementById('doc_date').value = result.DocDate || "";
            
            // HACK: Задержка 100мс, чтобы браузер успел отрисовать div перед рендером таблицы
            setTimeout(() => {
                table.setData(normalizedItems).then(() => table.redraw());
            }, 100);

            // Кнопка отправки в 1С (через бота)
            tg.MainButton.setText("Отправить в 1С");
            tg.MainButton.show();
        } else {
            alert("Товары не найдены. Попробуйте другое фото.");
            document.getElementById('scan-section').querySelector('button').classList.remove('hidden');
        }
    } catch (err) {
        alert("Ошибка: " + err.message);
        document.getElementById('loader').classList.add('hidden');
        document.getElementById('scan-section').querySelector('button').classList.remove('hidden');
    }
});

function sendDataToBot() {
    const data = {
        SupplierINN: document.getElementById('inn').value,
        Items: table.getData()
    };
    tg.sendData(JSON.stringify(data));
}

// Отправка данных боту (через MainButton или обычную кнопку)
tg.MainButton.onClick(sendDataToBot);
document.getElementById('send-btn').addEventListener('click', sendDataToBot);

// Кнопка очистки
document.getElementById('clear-btn').addEventListener('click', () => {
    document.getElementById('result-section').classList.add('hidden');
    document.getElementById('scan-section').querySelector('button').classList.remove('hidden');
    document.getElementById('file-input').value = '';
    document.getElementById('inn').value = '';
    document.getElementById('doc_num').value = '';
    document.getElementById('doc_date').value = '';
    table.clearData();
});