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
        const result = await response.json();

        if (result.Items) {
            document.getElementById('loader').classList.add('hidden');
            document.getElementById('result-section').classList.remove('hidden');
            
            // Заполняем данные
            document.getElementById('inn').value = result.SupplierINN || "";
            document.getElementById('doc_num').value = result.DocNumber || "";
            document.getElementById('doc_date').value = result.DocDate || "";
            table.replaceData(result.Items);

            // Кнопка отправки в 1С (через бота)
            tg.MainButton.setText("Отправить в 1С");
            tg.MainButton.show();
        }
    } catch (err) {
        tg.showAlert("Ошибка: " + err.message);
        document.getElementById('loader').classList.add('hidden');
        document.getElementById('scan-section').querySelector('button').classList.remove('hidden');
    }
});

// Отправка данных боту
tg.MainButton.onClick(() => {
    const data = {
        SupplierINN: document.getElementById('inn').value,
        Items: table.getData()
    };
    tg.sendData(JSON.stringify(data));
});