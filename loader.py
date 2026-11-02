import yadisk
import pandas as pd
from datetime import datetime
from pathlib import Path
import logging
import sys
from notifier import send_error_email

# ---------- НАСТРОЙКИ ----------
TOKEN = "y0__wgBENmAzqeq94ACGNuWAyCN_rSmGV7XnACBcxC1jJgTe34-wzwi8bFd"
SOURCE_PATH = "/test_v2.xlsx"
TODAY = datetime.now().strftime("%Y-%m-%d")

# Папки проекта
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LIVE_DIR = DATA_DIR / "live"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
LOGS_DIR = DATA_DIR / "logs"

# Создаём папки, если их нет
for d in [LIVE_DIR, SNAPSHOTS_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ---------- ЛОГИРОВАНИЕ ----------
logging.basicConfig(
    filename=LOGS_DIR / "loading.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8",
)

error_logger = logging.getLogger("errors")
error_logger.setLevel(logging.ERROR)
error_handler = logging.FileHandler(LOGS_DIR / "errors.log", encoding="utf-8")
error_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
error_logger.addHandler(error_handler)

# ---------- ТРЕБОВАНИЯ К ДАННЫМ ----------
REQUIRED_SHEETS = ["Сделки", "Выручка", "Прямые расходы", "SGA"]

REQUIRED_COLUMNS = {
    "Сделки": ["ID_сделки", "БЮ", "Сумма_сделки", "Вероятность", "Статус"],
    "Выручка": ["БЮ", "Квартал", "Выручка_бюджет", "Выручка_факт"],
    "Прямые расходы": ["БЮ", "Квартал", "StaffCost_факт", "COGS_факт"],
    "SGA": ["Квартал", "SGA_факт"],
}


# ---------- ВАЛИДАЦИЯ ----------
def validate(df_dict):
    """Проверяет, что данные корректные. Возвращает список ошибок."""
    errors = []

    # 1. Проверка листов
    for sheet in REQUIRED_SHEETS:
        if sheet not in df_dict:
            errors.append(f"Отсутствует лист '{sheet}'")
            continue

        df = df_dict[sheet]

        # 2. Проверка колонок
        for col in REQUIRED_COLUMNS[sheet]:
            if col not in df.columns:
                errors.append(f"Лист '{sheet}': нет колонки '{col}'")

        # 3. Проверка на пустоту
        if df.empty:
            errors.append(f"Лист '{sheet}' пустой")
            continue

        # 4. Проверка ключевых полей на пустые значения
        key_cols = REQUIRED_COLUMNS[sheet][:2]
        for col in key_cols:
            if col in df.columns and df[col].isna().any():
                errors.append(f"Лист '{sheet}': колонка '{col}' содержит пустые значения")

    return errors


# ---------- ЗАГРУЗКА ----------
def load_and_save():
    """Скачивает данные с Диска, валидирует и сохраняет снимок."""
    logging.info("=" * 60)
    logging.info(f"Начало загрузки за {TODAY}")

    try:
        # 1. Скачиваем с Яндекс.Диска
        logging.info(f"Скачиваю {SOURCE_PATH} с Яндекс.Диска")
        client = yadisk.Client(token=TOKEN)
        with client:
            if not client.check_token():
                raise Exception("Токен Яндекс.Диска недействителен")

            local_path = LIVE_DIR / "current.xlsx"
            client.download(SOURCE_PATH, str(local_path), overwrite=True)
        logging.info(f"Файл скачан: {local_path}")

        # 2. Читаем все листы
        df_dict = {}
        for sheet in REQUIRED_SHEETS:
            df_dict[sheet] = pd.read_excel(local_path, sheet_name=sheet)
        logging.info(f"Прочитано {len(df_dict)} листов")

        # 3. Валидация
        errors = validate(df_dict)

        if errors:
            # Есть ошибки — снимок НЕ сохраняем
            error_msg = " | ".join(errors)
            error_logger.error(f"Ошибки валидации за {TODAY}: {error_msg}")
            logging.error(f"Загрузка прервана: {error_msg}")

            # Отправляем email с уведомлением
            send_error_email(errors, snapshot_date=TODAY)

            return {
                "success": False,
                "errors": errors,
                "date": TODAY,
            }

        # 4. Сохраняем снимок
        snapshot_path = SNAPSHOTS_DIR / f"{TODAY}.xlsx"
        with pd.ExcelWriter(snapshot_path, engine="openpyxl") as writer:
            for sheet, df in df_dict.items():
                df.to_excel(writer, sheet_name=sheet, index=False)

        logging.info(f"Снимок сохранён: {snapshot_path}")
        logging.info(f"Строк в листах: " + ", ".join(
            f"{s}={len(df)}" for s, df in df_dict.items()
        ))

        return {
            "success": True,
            "errors": [],
            "date": TODAY,
            "path": str(snapshot_path),
        }

    except Exception as e:
        error_logger.error(f"Критическая ошибка за {TODAY}: {e}")
        logging.error(f"Критическая ошибка: {e}")

        # Отправляем email с уведомлением о критической ошибке
        send_error_email([f"Критическая ошибка: {e}"], snapshot_date=TODAY)

        return {
            "success": False,
            "errors": [str(e)],
            "date": TODAY,
        }


# ---------- ЗАПУСК ----------
if __name__ == "__main__":
    result = load_and_save()

    if result["success"]:
        print(f"✅ Загрузка успешна: {result['date']}")
        print(f"   Файл: {result['path']}")
        sys.exit(0)
    else:
        print(f"❌ Ошибка загрузки за {result['date']}:")
        for err in result["errors"]:
            print(f"   - {err}")
        sys.exit(1)