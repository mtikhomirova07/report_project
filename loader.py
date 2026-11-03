import streamlit as st
import pandas as pd
import io
import requests
import glob
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
SNAPSHOTS_DIR = BASE_DIR / "data" / "snapshots"
LOGS_DIR = BASE_DIR / "data" / "logs"

SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

YANDEX_TOKEN = "y0__wgBENmAzqeq94ACGKe9TiD99KHQGUiTOezfAC1bXzcTrARWQ753zG3n"

FOLDER_PATH = "/reports"

def download_file_with_retry(url, headers, max_retries=3):
    """Скачивает файл с повторными попытками."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=60)
            if response.status_code == 200:
                return response.content
            time.sleep(2)
        except Exception:
            time.sleep(2)
    return None

def get_all_excel_files():
    """Скачивает все Excel-файлы из папок на Яндекс.Диске."""
    url = "https://cloud-api.yandex.net/v1/disk/resources"
    headers = {"Authorization": f"OAuth {YANDEX_TOKEN}"}
    
    params = {"path": FOLDER_PATH, "limit": 1000}
    
    # Получаем список папок (с повторными попытками)
    response = None
    for attempt in range(3):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            if response.status_code == 200:
                break
        except Exception:
            time.sleep(2)
    
    if not response or response.status_code != 200:
        raise Exception(f"Ошибка доступа к Яндекс.Диску: {response.text if response else 'Нет ответа'}")
    
    items = response.json().get("_embedded", {}).get("items", [])
    folders = [i for i in items if i["type"] == "dir"]
    
    downloaded = []
    now_str = datetime.now().strftime("%Y-%m-%d_%H%M")
    
    if folders:
        for folder in folders:
            folder_name = folder["name"]
            folder_url = "https://cloud-api.yandex.net/v1/disk/resources"
            folder_params = {"path": folder["path"], "limit": 100}
            
            folder_response = requests.get(folder_url, headers=headers, params=folder_params, timeout=30)
            if folder_response.status_code != 200:
                continue
            
            folder_items = folder_response.json().get("_embedded", {}).get("items", [])
            folder_files = [i for i in folder_items if i["name"].endswith(".xlsx") and i["type"] == "file"]
            
            for f in folder_files:
                download_url = f["file"]
                content = download_file_with_retry(download_url, headers)
                
                if content:
                    base_name = Path(f["name"]).stem
                    new_path = SNAPSHOTS_DIR / f"{now_str}_{folder_name}_{base_name}.xlsx"
                    
                    with open(new_path, "wb") as file:
                        file.write(content)
                    
                    downloaded.append(f"{folder_name}/{f['name']}")
                
                # Пауза между файлами, чтобы Яндекс не блокировал
                time.sleep(1)
    else:
        files = [i for i in items if i["name"].endswith(".xlsx") and i["type"] == "file"]
        for f in files:
            download_url = f["file"]
            content = download_file_with_retry(download_url, headers)
            
            if content:
                base_name = Path(f["name"]).stem
                new_path = SNAPSHOTS_DIR / f"{now_str}_{base_name}.xlsx"
                
                with open(new_path, "wb") as file:
                    file.write(content)
                
                downloaded.append(f["name"])
            
            time.sleep(1)
    
    if not downloaded:
        raise Exception("Не удалось скачать ни одного файла")
    
    return downloaded

def update_data():
    try:
        files = get_all_excel_files()
        
        log_file = LOGS_DIR / "last_update.txt"
        log_file.write_text(f"Успешно скачано {len(files)} файлов", encoding="utf-8")
        
        return True, f"Данные обновлены. Скачано файлов: {len(files)}"
    
    except Exception as e:
        error_file = LOGS_DIR / "LAST_ERROR.txt"
        error_file.write_text(str(e), encoding="utf-8")
        return False, str(e)

if __name__ == "__main__":
    success, message = update_data()
    print(message)