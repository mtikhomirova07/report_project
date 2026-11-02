"""
Управление статусами версий отчётов.

Три статуса:
- draft   — черновик (по умолчанию)
- pre_br  — пред-BR (промежуточный)
- br      — Business Review (финальный, согласованный)

Только одна версия может быть в статусе BR одновременно.
"""
import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
STATUSES_FILE = BASE_DIR / "data" / "statuses.json"

# Возможные статусы
DRAFT = "draft"
PRE_BR = "pre_br"
BR = "br"

STATUS_LABELS = {
    DRAFT: "Черновик",
    PRE_BR: "Пред-BR",
    BR: "BR",
}


def _load():
    """Загружает статусы из файла."""
    if not STATUSES_FILE.exists():
        return {"versions": {}}
    try:
        with open(STATUSES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"versions": {}}


def _save(data):
    """Сохраняет статусы."""
    STATUSES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATUSES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def set_status(timestamp, status):
    """
    Устанавливает статус версии.
    Если статус BR — снимает BR со всех остальных.
    """
    if status not in STATUS_LABELS:
        raise ValueError(f"Неизвестный статус: {status}")

    data = _load()

    # Если ставим BR — снимаем BR с других
    if status == BR:
        for ts in list(data["versions"].keys()):
            if ts != timestamp and data["versions"][ts].get("status") == BR:
                data["versions"][ts]["status"] = DRAFT
                data["versions"][ts]["changed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Устанавливаем новый статус
    data["versions"][timestamp] = {
        "status": status,
        "changed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    _save(data)


def get_status(timestamp):
    """Возвращает статус версии (или draft, если нет записи)."""
    data = _load()
    return data["versions"].get(timestamp, {}).get("status", DRAFT)


def get_status_label(timestamp):
    """Возвращает человекочитаемый статус."""
    return STATUS_LABELS.get(get_status(timestamp), "Черновик")


def get_br_version():
    """Возвращает timestamp версии со статусом BR (или None)."""
    data = _load()
    for ts, info in data["versions"].items():
        if info.get("status") == BR:
            return ts
    return None


def get_last_br_before(timestamp):
    """
    Возвращает последнюю BR-версию ДО указанной (не считая её самой).
    Используется для сравнения.
    """
    data = _load()
    candidates = [
        ts for ts, info in data["versions"].items()
        if info.get("status") == BR and ts < timestamp
    ]
    if not candidates:
        return None
    return sorted(candidates, reverse=True)[0]


def list_all_statuses():
    """Возвращает все версии со статусами."""
    return _load()["versions"]


# ---------- Совместимость со старым API ----------
# Если в коде остались вызовы is_approved / approve / unapprove — мапим на новые

def is_approved(timestamp):
    return get_status(timestamp) == BR


def approve(timestamp, comment=""):
    set_status(timestamp, BR)


def unapprove(timestamp):
    set_status(timestamp, DRAFT)


def list_all():
    """Возвращает список BR-версий (для совместимости)."""
    data = _load()
    return [
        {"timestamp": ts, "approved_at": info.get("changed_at", ""), "comment": ""}
        for ts, info in data["versions"].items()
        if info.get("status") == BR
    ]


def get_last_approved_before(timestamp):
    return get_last_br_before(timestamp)