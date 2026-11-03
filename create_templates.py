import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "data" / "templates"
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

subdivisions = ["EA", "Corp", "SP", "1C", "DAI"]

# Структура для листа Revenue
revenue_columns = [
    "SBU", "ID_сделки", "Заказчик", "Менеджер", 
    "Тип_сделки", "Вероятность", "Статус", 
    "Q1", "Q2", "Q3", "Q4",
    "Бюджет", "Факт YTD"  # <--- Добавили
]

# Структура для листа StaffCost
staff_columns = [
    "SBU", "Статья_затрат", "Q1", "Q2", "Q3", "Q4",
    "Бюджет", "Факт YTD"  # <--- Добавили
]

# Пример заполнения (2 строки)
example_revenue = [
    {
        "ID_сделки": "D-001", "Заказчик": "Пример заказчика", 
        "Менеджер": "Иванов И.И.", "Тип_сделки": "Pipeline", 
        "Вероятность": 50, "Статус": "В работе",
        "Q1": 1000000, "Q2": 2000000, "Q3": 0, "Q4": 0,
        "Бюджет": 5000000, "Факт YTD": 1200000
    },
    {
        "ID_сделки": "D-002", "Заказчик": "Пример заказчика 2", 
        "Менеджер": "Петров П.П.", "Тип_сделки": "Backlog", 
        "Вероятность": 100, "Статус": "Выиграна",
        "Q1": 0, "Q2": 0, "Q3": 3000000, "Q4": 4000000,
        "Бюджет": 7000000, "Факт YTD": 0
    },
]

example_staff = [
    {
        "Статья_затрат": "ФОТ",
        "Q1": 500000, "Q2": 500000, "Q3": 500000, "Q4": 500000,
        "Бюджет": 2000000, "Факт YTD": 1000000
    },
    {
        "Статья_затрат": "Премии",
        "Q1": 100000, "Q2": 100000, "Q3": 100000, "Q4": 100000,
        "Бюджет": 400000, "Факт YTD": 200000
    },
]

for sbu in subdivisions:
    file_path = TEMPLATES_DIR / f"report_{sbu}.xlsx"
    
    revenue_df = pd.DataFrame([
        {**row, "SBU": sbu} for row in example_revenue
    ], columns=revenue_columns)
    
    staff_df = pd.DataFrame([
        {**row, "SBU": sbu} for row in example_staff
    ], columns=staff_columns)
    
    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        revenue_df.to_excel(writer, sheet_name="Revenue", index=False)
        staff_df.to_excel(writer, sheet_name="StaffCost", index=False)
    
    print(f"Создан шаблон: {file_path}")

print("\nВсе шаблоны созданы в папке data/templates")