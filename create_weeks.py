import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).parent
WEEKS_DIR = BASE_DIR / "data" / "weeks"
WEEKS_DIR.mkdir(parents=True, exist_ok=True)

# Список недель (можно менять)
weeks = ["2026-W44", "2026-W45", "2026-W46"]
subdivisions = ["EA", "Corp", "SP", "1C", "DAI"]

# Данные для листа Revenue
revenue_data = {
    "SBU": [], "ID_сделки": [], "Заказчик": [], "Менеджер": [],
    "Тип_сделки": [], "Вероятность": [], "Статус": [],
    "Q1": [], "Q2": [], "Q3": [], "Q4": [],
    "Бюджет": [], "Факт YTD": []
}

# Данные для листа StaffCost
staff_data = {
    "SBU": [], "Статья_затрат": [],
    "Q1": [], "Q2": [], "Q3": [], "Q4": [],
    "Бюджет": [], "Факт YTD": []
}

# Базовые данные (будут меняться в зависимости от недели)
def get_revenue_data(sbu, week_index):
    return [
        {
            "SBU": sbu, "ID_сделки": "D-001", "Заказчик": "Пример заказчика",
            "Менеджер": "Иванов И.И.", "Тип_сделки": "Pipeline",
            "Вероятность": 50, "Статус": "В работе",
            "Q1": 1000000 + week_index * 100000, "Q2": 2000000, "Q3": 0, "Q4": 0,
            "Бюджет": 5000000, "Факт YTD": 1200000 + week_index * 50000
        },
        {
            "SBU": sbu, "ID_сделки": "D-002", "Заказчик": "Пример заказчика 2",
            "Менеджер": "Петров П.П.", "Тип_сделки": "Backlog",
            "Вероятность": 100, "Статус": "Выиграна",
            "Q1": 0, "Q2": 0, "Q3": 3000000, "Q4": 4000000,
            "Бюджет": 7000000, "Факт YTD": 0 + week_index * 300000
        },
    ]

def get_staff_data(sbu, week_index):
    return [
        {
            "SBU": sbu, "Статья_затрат": "ФОТ",
            "Q1": 500000, "Q2": 500000, "Q3": 500000, "Q4": 500000,
            "Бюджет": 2000000, "Факт YTD": 1000000 + week_index * 10000
        },
        {
            "SBU": sbu, "Статья_затрат": "Премии",
            "Q1": 100000, "Q2": 100000, "Q3": 100000, "Q4": 100000,
            "Бюджет": 400000, "Факт YTD": 200000 + week_index * 5000
        },
    ]

for week_idx, week in enumerate(weeks):
    week_dir = WEEKS_DIR / week
    week_dir.mkdir(parents=True, exist_ok=True)
    
    for sbu in subdivisions:
        file_path = week_dir / f"report_{sbu}.xlsx"
        
        rev_rows = get_revenue_data(sbu, week_idx)
        stf_rows = get_staff_data(sbu, week_idx)
        
        rev_df = pd.DataFrame(rev_rows, columns=list(revenue_data.keys()))
        stf_df = pd.DataFrame(stf_rows, columns=list(staff_data.keys()))
        
        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            rev_df.to_excel(writer, sheet_name="Revenue", index=False)
            stf_df.to_excel(writer, sheet_name="StaffCost", index=False)
        
        print(f"Создан файл: {file_path}")

print("\nВсе папки и файлы созданы в data/weeks")