import pandas as pd
import glob
import random
import os
from pathlib import Path

BASE_DIR = Path("data/snapshots")

def process_file(filepath):
    print(f"Обработка: {filepath}")
    try:
        # Читаем без шапки (header=None)
        df = pd.read_excel(filepath, sheet_name=None, header=None, engine="openpyxl")
    except Exception as e:
        print(f"  Ошибка чтения: {e}")
        return

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        for sheet_name, data in df.items():
            if not (sheet_name.startswith("Rev_") or sheet_name == "Revenue" or 
                    sheet_name.startswith("Staff_") or sheet_name == "StaffCost"):
                # Пишем лист как есть
                data.to_excel(writer, sheet_name=sheet_name, index=False, header=False)
                continue

            # Ищем строку с SBU
            header_row = None
            for i in range(min(15, len(data))):
                row = [str(x).strip().upper() for x in data.iloc[i].tolist()]
                if "SBU" in row:
                    header_row = i
                    break
            
            if header_row is None:
                data.to_excel(writer, sheet_name=sheet_name, index=False, header=False)
                continue

            # Заполняем пустые SBU (если есть)
            for i in range(header_row + 1, len(data)):
                val = str(data.iloc[i, 0]).strip()
                if val == "nan" or val == "" or val == "None":
                    data.iloc[i, 0] = random.choice(["1C", "CRM", "Corp", "Data & AI"])

            # Добавляем/изменяем колонки с фактом и прогнозом
            # Ищем колонки с "Q1", "Q2", "Q3", "Q4" в шапке
            # Но так как шапка двухуровневая и мы читаем без заголовков, 
            # нам нужно найти индексы колонок, где есть слова "Невзвешенная", "Взвешенная" и т.д.
            # В данном случае, скрипт будет работать с уже переименованными колонками, 
            # которые генерируются в dashboard.py (после сохранения).
            
            # Для упрощения задачи, просто поменяем числовые значения в определенных колонках
            # В вашей структуре (по скрину): 
            # Невзвешенная: H, I, J, K (индексы 7, 8, 9, 10)
            # COGS: M, N, O, P (индексы 12, 13, 14, 15)
            # Взвешенная: R, S, T, U (индексы 17, 18, 19, 20)
            # Взвешенные COGS: W, X, Y, Z (индексы 22, 23, 24, 25)
            
            # Мы не будем добавлять новые колонки, а просто заполним существующие,
            # чтобы данные выглядели как "Факт" и "Прогноз".
            # (Если нужно именно физически добавить колонки, это сложнее и может сломать структуру).
            
            # Заполняем Q1-Q4 случайными числами (для демонстрации)
            start_cols = [7, 12, 17, 22] # Начало блоков Невзвешенная, COGS, Взвешенная, Взвешенные COGS
            
            for start in start_cols:
                for i in range(header_row + 1, len(data)):
                    for col_idx in range(start, start + 4):
                        if col_idx >= len(data.columns):
                            continue
                        # Генерируем случайное число от 100к до 5млн
                        val = random.randint(100_000, 5_000_000)
                        data.iloc[i, col_idx] = val

            # Сохраняем
            data.to_excel(writer, sheet_name=sheet_name, index=False, header=False)
            
    print(f"  Готово: {filepath}")

# Проходим по всем неделям
for week in ["2026-W44", "2026-W45", "2026-W46"]:
    week_path = BASE_DIR / week
    if not week_path.exists():
        continue
    files = glob.glob(str(week_path / "*.xlsx"))
    for f in files:
        process_file(f)

print("Все файлы обновлены!")