const tg = window.Telegram.WebApp;
tg.expand();

// Настройка таблицы
const table = new Tabulator("#grid-table", {
    layout: "fitColumns",
    responsiveLayout: "collapse",
    columns: [
        {title:"Арт.", field:"ItemArticle", editor:"input", widthGrow:1, headerFilter:"input"},
        {title:"Товар", field:"ItemName", editor:"input", widthGrow:3},
        {title:"Кол-во", field:"Quantity", editor:"number", widthGrow:1},
        {title:"Цена", field:"Price", editor:"number", widthGrow:1},
        {title:"Сумма", field:"Total", mutator:(v, d) => (d.Quantity * d.Price).toFixed(2), widthGrow:1}
    ]
});

// Обработка фото
document.getElementById('file-input').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // UI переключение
    document.getElementById('scan-section').querySelector('button').classList.add('hidden');
    document.getElementById('loader').classList.remove('hidden');

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/scan', { method: 'POST', body: formData });
        const result = await response.json();

        if (result.Items) {
            document.getElementById('loader').classList.add('hidden');
            document.getElementById('result-section').classList.remove('hidden');
            
            // Заполняем поля шапки
            document.getElementById('inn').value = result.SupplierINN || "";
            document.getElementById('doc_num').value = result.DocNumber || "";
            document.getElementById('doc_date').value = result.DocDate || "";
            document.getElementById('total_sum').value = result.TotalSum || 0;

            // Заполняем таблицу
            table.replaceData(result.Items);

            // Показываем кнопку отправки
            tg.MainButton.setText("✅ Отправить в 1С");
            tg.MainButton.show();
        } else if (result.error) {
            tg.showAlert("Ошибка: " + result.error);
            resetUI();
        }
    } catch (err) {
        tg.showAlert("Ошибка сети: " + err.message);
        resetUI();
    }
});

function resetUI() {
    document.getElementById('loader').classList.add('hidden');
    document.getElementById('scan-section').querySelector('button').classList.remove('hidden');
}

// Отправка данных боту
tg.MainButton.onClick(() => {
    const data = {
        SupplierINN: document.getElementById('inn').value,
        DocNumber: document.getElementById('doc_num').value,
        DocDate: document.getElementById('doc_date').value,
        TotalSum: document.getElementById('total_sum').value,
        Items: table.getData()
    };
    tg.sendData(JSON.stringify(data));
});