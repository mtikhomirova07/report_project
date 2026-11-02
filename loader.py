import streamlit as st
import pandas as pd
import io
import requests
import glob
from datetime import datetime
from pathlib import Path

# Пути к папкам
BASE_DIR = Path(__file__).parent
SNAPSHOTS_DIR = BASE_DIR / "data" / "snapshots"
LOGS_DIR = BASE_DIR / "data" / "logs"

# Создаем папки, если их нет
SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Получаем токен из секретов Streamlit (если он там есть)
try:
    YANDEX_TOKEN = st.secrets["YANDEX_TOKEN"]
except Exception:
    # Если секретов нет (запуск локально), используем токен напрямую
    YANDEX_TOKEN = "y0__wgBENmAzqeq94ACGKe9TiD99KHQGUI7OezfAC1bXzcTrARWQ753zG3n"

# Путь к папке на Яндекс.Диске. 
# Если файл лежит в корне Диска, оставьте "/".
# Если в папке "Отчеты", напишите "/Отчеты".
FOLDER_PATH = "/" 

def get_latest_excel_from_yandex():
    """Ищет самый свежий Excel-файл на Яндекс.Диске и скачивает его."""
    url = "https://cloud-api.yandex.net/v1/disk/resources"
    headers = {"Authorization": f"OAuth {YANDEX_TOKEN}"}
    
    # 1. Получаем список файлов в папке
    params = {"path": FOLDER_PATH, "limit": 100}
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code != 200:
        raise Exception(f"Ошибка доступа к Яндекс.Диску: {response.text}")
    
    items = response.json().get("_embedded", {}).get("items", [])
    
    # Фильтруем только Excel-файлы
    excel_files = [i for i in items if i["name"].endswith(".xlsx") and i["type"] == "file"]
    
    if not excel_files:
        raise Exception("На Яндекс.Диске нет файлов с расширением .xlsx")
    
    # 2. Берем самый свежий по дате модификации
    latest = max(excel_files, key=lambda x: x["modified"])
    
    # 3. Скачиваем его
    download_url = latest["file"]
    file_response = requests.get(download_url, headers=headers)
    
    if file_response.status_code != 200:
        raise Exception(f"Не удалось скачать файл: {latest['name']}")
    
    return file_response.content, latest["name"]

def update_data():
    """Скачивает свежий файл и сохраняет его в папку snapshots."""
    try:
        print("Начинаю загрузку с Яндекс.Диска...")
        content, filename = get_latest_excel_from_yandex()
        
        # Генерируем имя файла с текущей датой и временем
        now = datetime.now().strftime("%Y-%m-%d_%H%M")
        new_path = SNAPSHOTS_DIR / f"{now}.xlsx"
        
        # Сохраняем файл
        with open(new_path, "wb") as f:
            f.write(content)
        
        # Логируем успех
        log_file = LOGS_DIR / "last_update.txt"
        log_file.write_text(f"Успешно обновлено: {filename} в {now}", encoding="utf-8")
        
        print(f"Файл {filename} успешно загружен и сохранен.")
        return True, f"Данные обновлены из файла {filename}"
    
    except Exception as e:
        # Логируем ошибку
        error_file = LOGS_DIR / "LAST_ERROR.txt"
        error_file.write_text(str(e), encoding="utf-8")
        print(f"Ошибка загрузки: {e}")
        return False, str(e)

if __name__ == "__main__":
    # Если скрипт запускается напрямую (не через Streamlit), просто обновляем данные
    success, message = update_data()
    print(message)