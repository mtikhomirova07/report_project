import pandas as pd
import glob
import os

# Ищем все xlsx файлы
files = glob.glob("data/snapshots/**/*.xlsx", recursive=True)
print(f"Найдено файлов: {len(files)}")

for f in files:
    try:
        # Читаем БЕЗ заголовков (header=None), чтобы не потерять двухуровневую шапку
        # Используем движок openpyxl, чтобы прочитать хоть что-то
        df = pd.read_excel(f, header=None, engine="openpyxl")
        
        # Сохраняем обратно, создавая абсолютно новый файл без стилей
        # (временно сохраняем в новый файл, чтобы не повредить старый, если упадёт)
        temp_file = f + ".tmp.xlsx"
        df.to_excel(temp_file, index=False, header=False)
        
        # Заменяем старый файл новым
        os.replace(temp_file, f)
        print(f"OK: {f}")
    except Exception as e:
        print(f"ОШИБКА в {f}: {e}")

print("Готово! Теперь файлы чистые.")