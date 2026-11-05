import zipfile
import shutil
import os
import glob
import re

def remove_styles_from_xlsx(file_path):
    """
    Открывает xlsx как zip-архив, удаляет styles.xml и чистит ссылки на него.
    """
    temp_path = file_path + ".tmp"
    
    # Открываем исходный архив
    with zipfile.ZipFile(file_path, 'r') as zin:
        # Создаем новый архив
        with zipfile.ZipFile(temp_path, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                
                # Пропускаем (удаляем) проблемный файл стилей
                if item.filename == 'xl/styles.xml':
                    continue
                
                # В файлах листов и workbook.xml убираем ссылки на стили
                if item.filename.endswith('.xml') and item.filename.startswith('xl/'):
                    try:
                        text = data.decode('utf-8')
                        # Убираем атрибут s="..." (ссылка на стиль)
                        text = re.sub(r'\ss="\d+"', '', text)
                        # Убираем секцию <cellStyles>...</cellStyles> если есть
                        text = re.sub(r'<cellStyles[^>]*>.*?</cellStyles>', '', text, flags=re.DOTALL)
                        data = text.encode('utf-8')
                    except Exception:
                        pass # если не удалось прочитать как текст — оставляем как есть
                
                # Записываем всё, кроме styles.xml
                zout.writestr(item, data)
    
    # Заменяем исходный файл очищенным
    shutil.move(temp_path, file_path)

# Применяем ко всем файлам в snapshots
files = glob.glob("data/snapshots/**/*.xlsx", recursive=True)
print(f"Найдено файлов: {len(files)}")

for f in files:
    try:
        remove_styles_from_xlsx(f)
        print(f"Очищен: {f}")
    except Exception as e:
        print(f"ОШИБКА при очистке {f}: {e}")

print("Готово! Все файлы очищены от стилей.")