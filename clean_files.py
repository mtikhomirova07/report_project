import openpyxl
import glob
from pathlib import Path

# Ищем все файлы в папке snapshots
files = glob.glob("data/snapshots/**/*.xlsx", recursive=True)
print(f"Найдено файлов: {len(files)}")

for f in files:
    try:
        print(f"Очищаю: {f} ...")
        # Загружаем книгу, чтобы прочитать данные и стили
        wb = openpyxl.load_workbook(f)
        
        # Пересохраняем её. По умолчанию openpyxl при сохранении 
        # пересобирает XML-структуру заново, удаляя "битые" куски стилей.
        wb.save(f)
        print(f"  Успешно!")
    except Exception as e:
        print(f"  Ошибка при чтении {f}: {e}")
        print("  Пропускаем этот файл...")

print("Готово!")