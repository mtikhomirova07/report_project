import streamlit as st
import pandas as pd
import io
import requests
import glob
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
SNAPSHOTS_DIR = BASE_DIR / "data" / "snapshots"
LOGS_DIR = BASE_DIR / "data" / "logs"

SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

YANDEX_TOKEN = "y0__wgBENmAzqeq94ACGKe9TiD99KHQGUiTOezfAC1bXzcTrARWQ753zG3n"

FOLDER_PATH = "/reports"

def get_all_excel_files():
    """Скачивает все Excel-файлы из папки на Яндекс.Диске."""
    url = "https://cloud-api.yandex.net/v1/disk/resources"
    headers = {"Authorization": f"OAuth {YANDEX_TOKEN}"}
    
    params = {"path": FOLDER_PATH, "limit": 100}
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code != 200:
        raise Exception(f"Ошибка доступа к Яндекс.Диску: {response.text}")
    
    items = response.json().get("_embedded", {}).get("items", [])
    excel_files = [i for i in items if i["name"].endswith(".xlsx") and i["type"] == "file"]
    
    if not excel_files:
        raise Exception("На Яндекс.Диске нет файлов с расширением .xlsx")
    
    downloaded = []
    now_str = datetime.now().strftime("%Y-%m-%d_%H%M")
    
    for f in excel_files:
        download_url = f["file"]
        file_response = requests.get(download_url, headers=headers)
        
        if file_response.status_code == 200:
            # Сохраняем файл с оригинальным именем + дата
            base_name = Path(f["name"]).stem
            new_path = SNAPSHOTS_DIR / f"{now_str}_{base_name}.xlsx"
            
            with open(new_path, "wb") as file:
                file.write(file_response.content)
            
            downloaded.append(f["name"])
    
    return downloaded

def update_data():
    try:
        print("Начинаю загрузку всех файлов с Яндекс.Диска...")
        files = get_all_excel_files()
        
        log_file = LOGS_DIR / "last_update.txt"
        log_file.write_text(f"Успешно скачано {len(files)} файлов: {', '.join(files)}", encoding="utf-8")
        
        return True, f"Данные обновлены. Скачано файлов: {len(files)}"
    
    except Exception as e:
        error_file = LOGS_DIR / "LAST_ERROR.txt"
        error_file.write_text(str(e), encoding="utf-8")
        return False, str(e)

if __name__ == "__main__":
    success, message = update_data()
    print(message)