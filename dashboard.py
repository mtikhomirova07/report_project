import streamlit as st
import pandas as pd
import plotly.express as px
import io
import glob
import re
from datetime import datetime
from pathlib import Path
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

from approvals import (
    set_status, get_status, get_status_label,
    get_last_br_before, DRAFT, PRE_BR, BR,
)
from auth import check_password

st.set_page_config(page_title="Управленческая отчётность", layout="wide")
if not check_password():
    st.stop()

st.cache_data.clear()

def zebra_style(x):
    css = pd.DataFrame('', index=x.index, columns=x.columns)
    for i in range(1, len(x), 2):
        css.iloc[i, :] = 'background-color: #f8f9fa;'
    return css

st.markdown("""
<style>
    [data-testid="stSidebarResizeHandle"] { display: none !important; }
    [data-testid="stSidebarUserContent"] { padding-top: 2rem !important; }
    [data-testid="stSidebar"] h2 { padding-bottom: 0rem !important; margin-bottom: 0.5rem !important; }
    [data-testid="stSidebar"] hr { margin: 10px 0 !important; }
    [data-testid="stSidebar"] .stRadio { margin-bottom: -10px !important; }
</style>
""", unsafe_allow_html=True)

BASE_DIR = Path(__file__).parent
SNAPSHOTS_DIR = BASE_DIR / "data" / "snapshots"

def parse_timestamp(ts):
    try:
        m = re.search(r"(\d{4}-\d{2}-\d{2}_\d{4})", ts)
        return datetime.strptime(m.group(1), "%Y-%m-%d_%H%M") if m else datetime.min
    except Exception:
        return datetime.min

def fmt_num(value, decimals=0, with_sign=False):
    if pd.isna(value) or value is None:
        return "—"
    if abs(value) < 0.5:
        return "0"
    formatted = f"{abs(value):,.{decimals}f}".replace(",", " ")
    if with_sign:
        return f"−{formatted}" if value < 0 else f"+{formatted}" if value > 0 else formatted
    return f"−{formatted}" if value < 0 else formatted

def fmt_pct(value, decimals=1, with_sign=True):
    if pd.isna(value) or value is None:
        return "—"
    if abs(value) < 0.05:
        return f"{abs(value):.{decimals}f}%"
    formatted = f"{abs(value):.{decimals}f}"
    if with_sign:
        return f"−{formatted}%" if value < 0 else f"+{formatted}%" if value > 0 else f"{formatted}%"
    return f"−{formatted}%" if value < 0 else f"{formatted}%"

# --- ФАКТ ИЗ DATA (полный, собран из 1С.txt, Corp.txt, DAI.txt, SP.txt, EA) ---
DATA = {
    "1C": {
        "2ba80a6a-1a47-4b2e-b5bb-7ce15fd00ca7": (0, 0),
        "5b35eeb5-6eb9-4f2e-88f5-3b967e998e42": (0, 37627651),
        "612d8d07-433c-4268-b198-18b637050f48": (0, 11567270),
        "e3f183d8-86bc-482d-b183-85c886514e06": (0, 0),
        "baa06374-9824-4480-877b-197ad575c7cd": (0, 0),
        "b4f72574-28ce-4803-b4c5-6476fd7c3e84": (0, 0),
        "01073c55-39cc-444d-af2c-589b7e9fd1be": (0, 0),
        "9a66d047-c85b-437d-9fd7-83f3bdd34a1c": (0, 0),
        "8be615c7-48dd-4ec9-9ed4-bd03801f1c9d": (0, 0),
        "d06403f7-dbbb-4926-9b41-201f419fb59c": (0, 0),
        "c3aa21c2-ef3c-4696-917b-7a25d93ac2a4": (0, 0),
        "d0b6e0d4-b3af-43c8-9baa-1aa1ac09c76e": (0, 0),
        "3fb79b53-029d-46d5-81dc-e5bd4fc749df": (0, 0),
        "34d939c0-f2c9-4d06-a9e9-135cbea579e9": (0, 0),
        "4a68efee-8479-45c9-8261-7ced393b386e": (0, 0),
        "554a8da5-3238-4a45-9533-76c16d464747": (0, 0),
        "fd97e19f-ac42-43b3-a0cf-b3087fb25c42": (0, 0),
        "69dc8682-497c-4647-8a7e-8b25c00be4b5": (0, 0),
        "c008f1ef-e2cd-4490-bbca-e354d483c733": (0, 0),
        "ec7d1f3f-40d5-4010-8a6d-1c13cf81a19e": (0, 0),
        "5f8b5ec8-6dab-4bde-ba38-82f3c76b46a9": (0, 0),
        "6d091cce-fab6-4ab4-bc0d-b679221bc02a": (0, 0),
        "121b663c-fe3e-45ad-a70c-aaa6b69fff0f": (0, 3638300),
        "ffc7f807-cc70-468c-8f69-27b7e4ed4787": (0, 0),
        "bf02c3b3-7952-4f34-bc56-b87122f4356a": (0, 0),
        "7184f083-745f-4ac5-83b1-bf1b8e371747": (0, 0),
        "40286c8a-3246-41ef-a8b0-699d4f57daaf": (0, 0),
        "c179a0a6-37f0-4bab-8066-882112fb32d3": (0, 0),
        "386732e1-d36f-4240-b86d-9388a97ea778": (0, 0),
        "b458e775-4cf2-4ee6-aee2-1a111710bd7a": (0, 0),
        "22dde6c7-fcd1-42c0-9665-e8580eb52f87": (0, 0),
        "1980e664-c210-4b0a-bb5b-f260fe9c502c": (0, 0),
        "3dc7a69b-abe8-4d4d-8a47-9c2e90271ffe": (4941982, 2358161),
        "b521d07f-8656-45b4-8005-0b5c16b308de": (0, 0),
        "d84cca2e-b994-4547-b7d0-efa340c7bc65": (7832378, 4530408),
        "4e8f4f91-586b-4f34-b27d-a077824e5fb0": (0, -77364400),
        "97fbf061-9ba1-4fd0-a168-91312606950b": (726000, 1443600),
        "1034ded5-68c2-418a-b4e7-23e0e0dc3e53": (0, 0),
        "9746693b-21b7-4c67-b2d9-29631f8c7017": (19101128, 16659999),
        "370988c7-6b7a-49fb-92c6-ef3913e1d13b": (196500, 0),
        "cbe63db9-047a-476b-a55a-ed9081633b7a": (1960200, 1581525),
        "cfbc6c81-96d5-4ff1-b13d-877b78257b59": (383250, 667800),
        "65a11198-cbf5-4ed7-9ee1-a65354b89b2a": (0, 2236500),
        "223001ce-80b8-4381-bfb7-a66d58ebf442": (1358669, 64569),
        "35f1fac4-d184-46a7-bfba-2e4a8cd04809": (3244265, 2444888),
        "b99ff2ba-69eb-4ed1-8c03-ae7bd97d873a": (0, 0),
        "a32b903a-99f3-40c9-8dc8-36456de686fe": (0, 0),
        "5dcaef18-e37a-4bec-871e-0b0e1935ff59": (0, 0),
        "0b7df80e-9b81-4580-8718-a12e8e136461": (0, 0),
        "00bd78ae-70a0-4321-879d-ca4060c2a7d8": (0, 0),
        "f251d77b-7a0f-4551-8307-004b50caa71a": (0, 0),
        "f15e73bc-bfd4-402a-9e47-4d8ebeadd3cb": (0, 0),
        "729bb988-4283-4ff0-b158-4d999243f536": (0, 0),
        "513c6f1b-3766-4d38-a52b-e8e41c522afb": (0, 0),
        "6df80f6a-122a-4d60-85cd-3f64963afeb1": (0, 0),
        "a551a63b-22aa-46eb-bb41-6d81e689bbac": (0, 0),
        "6e1403e4-81a5-4041-9dfe-551abd1d21f7": (0, 0),
        "d962b5ed-221c-42a2-bb92-8b75192d4a23": (0, 0),
        "44592b19-f471-4d4a-8794-e2cf11ea865a": (0, 0),
        "4b144729-ade9-46d2-9712-124473c163eb": (0, 0),
        "90ae5ddc-c174-466f-9871-899816fe402a": (0, 0),
        "2607443d-94c9-49fb-87b6-77cd70510742": (0, 0),
        "5723ccb4-301a-4299-a24c-19cc94d90d06": (0, 0),
    },
    "Corp": {
        "77d5a73c-a099-48cc-8283-ed00dcc1ffea": (0, 0),
        "79e258ca-c248-4503-bb94-efa650e0a974": (0, 0),
        "4a836e1b-402f-4b9f-90b6-2a73e53d6b91": (21491000, 20893000),
        "347122f8-f63f-4784-b85f-74cc9c03e241": (0, 0),
    },
    "DAI": {
        "44d63831-6cbd-464e-89bf-29a2a8e25f98": (0, 0),
        "c35dcab1-0ab8-4e5a-8a20-2097fcc39546": (0, 0),
        "0449ab32-e288-4e10-824d-d380af7545bd": (0, 0),
        "a0c3c5f2-836a-4b8e-9fe0-492a10bbc8e0": (6769035, 6769035),
        "50a17e00-26b0-486a-aac3-a93f58b0cbef": (0, 0),
        "73fd8f63-be35-4606-bbc2-c95927b713dc": (0, 0),
        "64f2d64c-fb30-470a-80f6-912bd3d26db4": (0, 0),
        "d435cc25-067a-4615-a7ad-025e259740c1": (0, 0),
        "91f6b311-2b31-44b9-9490-51fb4898f2d3": (3813000, 4032760),
        "fac5087a-74a5-437f-85c4-9d94e20c6984": (0, 0),
        "bd9a2a83-b644-4e37-aa29-b8d238cb9071": (0, 0),
        "6720fb91-27fb-4b00-b282-aa80c1b1410b": (0, 0),
        "2ee559ff-adb2-4a6b-be04-13b0e47bf0ec": (0, 2641048),
        "44f801cf-fb75-42a9-bdd1-8f9362d8e3e4": (0, 0),
        "9781d6b4-d51d-41ea-97f5-64aea9500b82": (0, 0),
        "f626b369-522d-4b13-8102-2d6c6fad26e6": (0, 12018643),
        "401438c4-3e8e-4044-8bc8-02500fb0135d": (0, 0),
        "8cb25d0a-eb54-4c60-b8e4-eb63e2ac1039": (3516379, 3692286),
        "617e099d-6c7b-4d8c-857f-a6d2d1e43ad1": (0, 0),
        "37371b58-56bc-457b-bcbf-6bd2a53f89bc": (0, 0),
        "b549d40a-0716-463f-b471-c0d8108093b8": (0, 0),
        "f4140bbf-41a7-460b-9cea-54ba3f12fc61": (0, 0),
        "7c26d7e5-a334-4fb4-af70-24bdaa2f270a": (0, 0),
        "493ff263-e61e-4063-a956-bcffc44d420f": (0, 0),
        "209c5c28-ba75-4a43-a682-2fe01b21bde6": (0, 0),
        "b59d6667-a5bd-4d0c-8e47-e95c1fb19393": (0, 3285100),
        "8ffa2e17-495b-4346-8fe7-7bdae7d0bbc1": (14842561, 3200000),
        "eb343269-9345-460a-acb0-3ba098e162ed": (0, 0),
    },
    "SP": {
        "44bb74cd-2cdb-447c-9e71-1f073fd4eb79": (0, 0),
        "f4140bbf-41a7-460b-9cea-54ba3f12fc61": (0, 0),
    },
    "EA": {
        "4ab58704-09dd-4dcf-a474-68a09be53c6d": (0, 4884300),
        "4aaf922f-7c73-438c-915c-fef79d078af0": (0, 0),
        "cafe1973-e391-4b00-a288-a997a46c4da1": (0, 0),
        "074a87fb-801c-4a78-822d-897f7f7488e7": (0, 0),
        "6d943155-306a-41d4-8ccc-06f2ed095b4a": (0, 483091),
        "a354e5b8-cad6-4c74-8b4d-9f86e0229afd": (360708, 4801949),
        "2abd8542-f147-4875-88c1-e367dd8744d4": (0, 0),
        "56079b85-dd15-4bf1-a869-43eeb302702a": (0, 0),
        "830bca55-2a20-44b5-a577-2ea19e822764": (500000, 750000),
        "dac95b71-1a02-4a6c-ada5-5e4c487a1204": (0, 0),
        "d6b9b245-e190-4ddc-84b2-765fc0684940": (0, 0),
        "36055de0-083e-47fe-8f98-65907ff01d71": (0, 1212466),
        "4a8cd00d-f9bd-45db-a6ea-e5f680e9f0e7": (0, 0),
        "50560685-2a9f-44ab-88b1-eca75eed744c": (0, 287011),
        "9bf3321e-4e0c-4b1c-81c4-90d103f8a20b": (0, 0),
        "f8693c6e-6d71-46d5-844d-ff03bd6d2528": (513750, 513750),
        "bd41949b-030c-4349-9024-305dc4d2f791": (535437, 1370),
        "275f18de-c233-4592-b76b-97de2ff9a180": (0, 0),
        "bb6eecd7-3290-4f46-a7ab-4f3d076ec114": (0, 675067),
        "34bf4b61-7be2-445c-9990-52f971ed98a8": (1007860, 2885191),
        "2cf3c622-3344-47dc-a693-8ff271f9f31e": (0, 0),
        "bd3a053b-f347-43e8-8104-f07b8372219f": (0, 0),
        "b169197c-a3a8-4da1-b5bf-1d02a985c6a4": (0, 0),
        "05cabe27-dee9-4458-96ac-06fb0fb8e36b": (0, 0),
        "6559be14-ae1e-4bc9-af70-9c0464975ebd": (0, 0),
        "283aa802-a084-43d7-aa69-33d9a2984d02": (0, 0),
        "4e75c93c-bb4f-4c8d-af0c-07b11b4b73c4": (1329615, 0),
        "b2f989fe-75a0-4b8c-a3d3-efe23de294b1": (0, 376600),
        "347122f8-f63f-4784-b85f-74cc9c03e241": (0, 0),
        "7a4b7d60-7b68-4769-bab0-5054c5f5448a": (320000, 0),
        "1d38809d-ebb0-47ac-bf94-166e261cda6b": (0, 60500),
        "5df21dcc-ae07-4a40-8f22-f8e9c46f4b78": (344436, 0),
        "263a27aa-588c-485a-b1b0-0a392a8f6a15": (9878727, 0),
        "b4761dec-cae7-4ca1-a8fe-268da0daded6": (76500, 0),
        "fa20c221-a7d7-43d9-814b-f2580b185366": (1706400, 0),
        "bf207a08-8019-48a5-abe3-e35c289845de": (385662, 168439),
        "5fc12612-671f-4e2f-a2d4-81d2144fbde6": (0, 927001),
        "070c4100-1b09-49fa-9f1e-b89231082da1": (0, 250000),
        "15210516-7122-4b6d-bb1e-08a06b46df27": (0, 1875000),
        "d0784250-caef-41e4-8599-35649cf621a2": (551315, 1610221),
        "16810705-cc1a-46ea-b9f5-231f082a663e": (0, 0),
        "9d9a183f-c0eb-4580-a9d4-934d1fe33a4d": (0, 0),
        "0ca5fb7a-34f5-45f3-8c71-f8703126528a": (0, 0),
        "fa7e3873-72c5-46f9-b1a6-bc24433e2f03": (0, 0),
        "d6cca222-67b2-42b9-abec-62ad7b60401f": (0, 0),
        "0a33e024-c853-41da-b20f-5ce8895d8295": (0, 0),
    },
}

# Факт по названию (для сделок без ID в ссылке)
DATA_FACT_BY_NAME = {
    "Проектная команда": (0, 3375000),
    "Внедрение лояльности в АФЛ ТМ Q1-Q2 Оберон Факт": (5400000, 6030000),
    "Сторн АФЛ Оберон": (0, 0),
    "Внедрение лояльности в АФЛ Релиз 4 5 FP": (0, 0),
    "Внедрение лояльности в АФЛ TM Q3/4 Оберон": (0, 0),
    "Внедрение Модус в МКБ": (0, 0),
}

DATA_FACT = {}
for project_data in DATA.values():
    DATA_FACT.update(project_data)

# --- АВТОЗАГРУЗКА / ОБНОВЛЕНИЕ ---
if not glob.glob(str(SNAPSHOTS_DIR / "**" / "*.xlsx"), recursive=True):
    with st.spinner("Первый запуск. Загружаю данные..."):
        from loader import update_data
        ok, msg = update_data()
    if ok:
        st.cache_data.clear(); st.rerun()
    else:
        st.sidebar.error(f"Ошибка: {msg}"); st.stop()

if st.sidebar.button("🔄 Обновить данные", width="stretch"):
    with st.spinner("Загружаю данные..."):
        from loader import update_data
        ok, msg = update_data()
    if ok:
        st.sidebar.success(msg); st.cache_data.clear(); st.rerun()
    else:
        st.sidebar.error(f"Ошибка: {msg}")

# --- ГРУППИРОВКА СНИМКОВ ---
snapshot_files = sorted(glob.glob(str(SNAPSHOTS_DIR / "**" / "*.xlsx"), recursive=True), reverse=True)
if not snapshot_files:
    st.error("Нет снимков."); st.stop()

snapshot_groups = {}
for f in snapshot_files:
    stem = Path(f).stem
    parent_dir = Path(f).parent.name
    m = re.search(r"(2026-W\d+)", stem) or re.search(r"(2026-W\d+)", parent_dir)
    key = m.group(1) if m else stem
    snapshot_groups.setdefault(key, []).append(f)
group_keys = sorted(snapshot_groups.keys(), reverse=True)

# --- ЧТЕНИЕ EXCEL ---
def read_excel_with_header(path, sheet_name):
    try:
        df = pd.read_excel(path, sheet_name=sheet_name, header=None, engine="calamine")
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return pd.DataFrame()

    header_row = None
    for i in range(min(15, len(df))):
        row = [str(x).strip().upper() for x in df.iloc[i].tolist()]
        if "SBU" in row:
            header_row = i
            break
    if header_row is None:
        return pd.DataFrame()

    data = df.iloc[header_row:].copy()
    data = data.dropna(how="all").reset_index(drop=True)

    if "Revenue" in sheet_name or "Rev_" in sheet_name:
        expected_cols = [
            "SBU", "Заказчик", "Название", "Ссылка", "Признак_XT", 
            "Вероятность", "Backlog_Pipeline", 
            "Невзвешенная_Q1", "Невзвешенная_Q2", "Невзвешенная_Q3", "Невзвешенная_Q4",
            "COGS_Q1", "COGS_Q2", "COGS_Q3", "COGS_Q4",
            "Взвешенная_Q1", "Взвешенная_Q2", "Взвешенная_Q3", "Взвешенная_Q4",
            "Взвешенные_COGS_Q1", "Взвешенные_COGS_Q2", "Взвешенные_COGS_Q3", "Взвешенные_COGS_Q4",
            "Rev2027", "Cogs2027", "H2_GM1", "Проект", "ОПП", "GM3",
            "Факт_Q1", "Факт_Q2"
        ]
    else:
        expected_cols = [
            "SBU", "ФИО", "Admin_Проект", "Признак_XT",
            "ФОТ_Q1", "ФОТ_Q2", "ФОТ_Q3", "ФОТ_Q4",
            "Премии_Q1", "Премии_Q2", "Премии_Q3", "Премии_Q4",
            "Доп_Q1", "Доп_Q2", "Доп_Q3", "Доп_Q4",
            "ИТОГО_Q1", "ИТОГО_Q2", "ИТОГО_Q3", "ИТОГО_Q4",
            "Год2027"
        ]

    actual_cols = list(data.columns)
    if len(actual_cols) > len(expected_cols):
        expected_cols += [f"extra_{i}" for i in range(len(actual_cols) - len(expected_cols))]
    elif len(actual_cols) < len(expected_cols):
        expected_cols = expected_cols[:len(actual_cols)]

    data.columns = expected_cols

    if "Вероятность" in data.columns:
        data["Вероятность"] = data["Вероятность"].astype(str).str.replace("%", "").str.replace(",", ".")
        data["Вероятность"] = pd.to_numeric(data["Вероятность"], errors="coerce").fillna(0)

    for col in data.columns:
        if "_Q" in col:
            data[col] = pd.to_numeric(
                data[col].astype(str).str.replace("₽", "").str.replace(" ", "").str.replace(",", "."),
                errors="coerce"
            ).fillna(0)

    return data

@st.cache_data(show_spinner=False)
def load_all_snapshots(paths):
    rev_parts, staff_parts, errors = [], [], []
    for path in paths:
        try:
            xls = pd.ExcelFile(path)
        except Exception as e:
            errors.append(f"{path}: {e}")
            continue
            
        for sh in xls.sheet_names:
            is_rev = sh.startswith("Rev_") or sh == "Revenue"
            is_staff = sh.startswith("Staff_") or sh == "StaffCost"
            
            if is_rev or is_staff:
                d = read_excel_with_header(path, sh)
                if d.empty:
                    continue
                
                if is_rev:
                    rev_parts.append(d)
                else:
                    staff_parts.append(d)
                    
    rev = pd.concat(rev_parts, ignore_index=True) if rev_parts else pd.DataFrame()
    stf = pd.concat(staff_parts, ignore_index=True) if staff_parts else pd.DataFrame()

    # --- МЕРЖ С ФАКТОМ ПО CRM_ID + FALLBACK ПО НАЗВАНИЮ ---
    if not rev.empty:
        try:
            if "Ссылка" in rev.columns:
                rev["crm_id"] = rev["Ссылка"].astype(str).str.extract(r"edit/([a-f0-9-]+)")[0].str.strip().str.lower()
                map_q1 = rev["crm_id"].map(lambda x: DATA_FACT.get(x, (0, 0))[0] if x else 0)
                map_q2 = rev["crm_id"].map(lambda x: DATA_FACT.get(x, (0, 0))[1] if x else 0)
            else:
                map_q1 = pd.Series(0, index=rev.index)
                map_q2 = pd.Series(0, index=rev.index)

            # Факт из файла (если колонки есть)
            file_q1 = pd.to_numeric(rev.get("Факт_Q1", 0), errors="coerce").fillna(0)
            file_q2 = pd.to_numeric(rev.get("Факт_Q2", 0), errors="coerce").fillna(0)

            rev["Факт_Q1"] = file_q1.where(file_q1 != 0, map_q1)
            rev["Факт_Q2"] = file_q2.where(file_q2 != 0, map_q2)

            # Fallback по названию
            if "Название" in rev.columns:
                name_q1 = rev["Название"].astype(str).str.strip().map(lambda x: DATA_FACT_BY_NAME.get(x, (0, 0))[0])
                name_q2 = rev["Название"].astype(str).str.strip().map(lambda x: DATA_FACT_BY_NAME.get(x, (0, 0))[1])
                rev["Факт_Q1"] = rev["Факт_Q1"].where(rev["Факт_Q1"] != 0, name_q1)
                rev["Факт_Q2"] = rev["Факт_Q2"].where(rev["Факт_Q2"] != 0, name_q2)

            if "crm_id" in rev.columns:
                rev = rev.drop(columns=["crm_id"])
        except Exception as e:
            errors.append(f"Ошибка мержа факта: {e}")

    return rev, stf, errors

# --- ФУНКЦИИ РАСЧЕТА ---
def get_rev(df, quarters=("Q1","Q2","Q3","Q4")):
    total = 0.0
    for q in quarters:
        col = f"Взвешенная_{q}"
        if col in df.columns:
            total += df[col].sum()
    return float(total)

def get_cogs(df, quarters=("Q1","Q2","Q3","Q4")):
    total = 0.0
    for q in quarters:
        col = f"Взвешенные_COGS_{q}"
        if col in df.columns:
            total += df[col].sum()
    return float(total)

def get_staff(df, quarters=("Q1","Q2","Q3","Q4")):
    if df is None or df.empty:
        return 0.0
    total = 0.0
    for q in quarters:
        col = f"ИТОГО_{q}"
        if col in df.columns:
            total += df[col].sum()
    return float(total)

def get_fact(df):
    total = 0.0
    for col in ["Факт_Q1", "Факт_Q2"]:
        if col in df.columns:
            total += pd.to_numeric(df[col], errors="coerce").fillna(0).sum()
    return float(total)

def filter_by_sbu(df, sbu):
    if df is None or df.empty or sbu == "Все" or "SBU" not in df.columns:
        return df
    return df[df["SBU"] == sbu]

def split_by_type(df):
    out = {"Backlog": pd.DataFrame(), "Pipeline": pd.DataFrame(), "GAP": pd.DataFrame()}
    if df is None or df.empty or "Backlog_Pipeline" not in df.columns:
        return out
    t = df["Backlog_Pipeline"].astype(str).str.strip().str.title()
    for k in out:
        out[k] = df[t == k.title()]
    return out

# --- САЙДБАР: ПЕРИОД / СТАТУС ---
st.sidebar.markdown("---")
st.sidebar.header("Период (→ PREV-BR)")
selected_key = st.sidebar.selectbox("Неделя", group_keys, index=0, label_visibility="collapsed")
selected_paths = snapshot_groups[selected_key]

st.sidebar.markdown("---")
st.sidebar.header("Статус версии")
cur = get_status(selected_key)
cur_label = get_status_label(selected_key)
if cur == BR:
    st.sidebar.success(f"Статус: {cur_label}")
elif cur == PRE_BR:
    st.sidebar.warning(f"Статус: {cur_label}")
else:
    st.sidebar.info(f"Статус: {cur_label}")

c1, c2 = st.sidebar.columns(2)
with c1:
    if st.button("Пред-BR", width="stretch", disabled=(cur != DRAFT)):
        set_status(selected_key, PRE_BR); st.rerun()
with c2:
    if st.button("BR", width="stretch", disabled=(cur != PRE_BR)):
        try:
            for k in group_keys:
                if k != selected_key and get_status(k) == BR:
                    set_status(k, PRE_BR)
            prev = get_last_br_before(selected_key)
            if prev and prev != selected_key:
                set_status(prev, PRE_BR)
        except Exception:
            pass
        set_status(selected_key, BR); st.rerun()
if cur != BR:
    if st.sidebar.button("Снять статус (Черновик)", width="stretch", disabled=(cur != PRE_BR)):
        set_status(selected_key, DRAFT); st.rerun()

st.sidebar.markdown("---")
prev_br_key = get_last_br_before(selected_key)
comparison = None
if prev_br_key and prev_br_key in snapshot_groups:
    comparison = load_all_snapshots(tuple(snapshot_groups[prev_br_key]))[:2]
st.sidebar.markdown("**Актуальный прогноз**")
st.sidebar.caption(f"Сравнение с BR: {prev_br_key}" if comparison else "Нет предыдущего BR для сравнения")

# --- ЗАГРУЗКА ТЕКУЩИХ ДАННЫХ ---
st.sidebar.markdown("---")
st.sidebar.header("Фильтры")
rev_all, stf_all, errs = load_all_snapshots(tuple(selected_paths))
for e in errs:
    st.sidebar.warning(e)
if rev_all.empty:
    st.error("Не найдены данные по выручке."); st.stop()

by_list = ["Все"]
sbus = rev_all["SBU"].dropna().astype(str).unique().tolist()
for sbu in sorted(sbus):
    if sbu.strip() != "":
        by_list.append(sbu)

selected_by = st.sidebar.selectbox("Бизнес-юнит (БЮ)", by_list)

rev = filter_by_sbu(rev_all, selected_by)
stf = filter_by_sbu(stf_all, selected_by)

# --- НАВИГАЦИЯ ---
st.sidebar.markdown("---")
st.sidebar.header("Навигация")
page = st.sidebar.radio("Страница", ["P&L", "Сделки"], key="page_nav", label_visibility="collapsed")

if page == "Сделки":
    from page_deals import render_deals_page
    render_deals_page(
        deals=rev,
        comparison_deals=comparison[0] if comparison else None,
        selected_by=selected_by,
        selected_date=selected_key,
        fmt_num=fmt_num,
        fmt_pct=fmt_pct,
    )
    st.stop()

# --- ТЕКУЩИЕ ИТОГИ ---
rev_total = get_rev(rev)
cogs_total = get_cogs(rev)
staff_total = get_staff(stf)
direct_total = staff_total + cogs_total
gp3_total = rev_total - direct_total
sga_total = 0.0
ebitda_total = gp3_total - sga_total
gm_pct_total = (gp3_total / rev_total * 100) if rev_total else 0.0

# Бюджет (фейковый: -5% от прогноза)
budget_rev = rev_total * 0.95 if rev_total else 0.0
budget_staff = staff_total * 0.95 if staff_total else 0.0
budget_cogs = cogs_total * 0.95 if cogs_total else 0.0
budget_direct = budget_staff + budget_cogs
budget_gp3 = budget_rev - budget_direct
budget_ebitda = budget_gp3 - sga_total

types = split_by_type(rev)
rev_backlog = get_rev(types["Backlog"])
rev_pipeline = get_rev(types["Pipeline"])
rev_gap = get_rev(types["GAP"])

# ФАКТ
rev_fact = get_fact(rev)
cogs_fact = get_fact(rev)
staff_fact = get_fact(stf) if not stf.empty else 0.0
direct_fact = staff_fact + cogs_fact
gp3_fact = rev_fact - direct_fact
ebitda_fact = gp3_fact - sga_total

# --- PREV BR ---
if comparison:
    comp_rev = filter_by_sbu(comparison[0], selected_by)
    comp_stf = filter_by_sbu(comparison[1], selected_by)
    p_rev = get_rev(comp_rev)
    p_cogs = get_cogs(comp_rev)
    p_staff = get_staff(comp_stf)
    p_direct = p_staff + p_cogs
    p_gp3 = p_rev - p_direct
    p_sga = 0.0
    p_ebitda = p_gp3 - p_sga
    p_gm = (p_gp3 / p_rev * 100) if p_rev else 0.0
    ct = split_by_type(comp_rev)
    p_backlog, p_pipeline, p_gap = get_rev(ct["Backlog"]), get_rev(ct["Pipeline"]), get_rev(ct["GAP"])
else:
    p_rev = p_cogs = p_staff = p_direct = p_gp3 = p_sga = p_ebitda = p_gm = 0.0
    p_backlog = p_pipeline = p_gap = 0.0

st.title("Управленческая отчётность")
st.caption(f"Отчёт от {selected_key} | БЮ: {selected_by} | Единицы: руб. (без НДС)")
st.markdown("---")
st.subheader("P&L по статьям")

def make_row(name, prev, pr, fact=None, indent=False):
    return {
        "Показатель": ("    — " + name) if indent else name,
        "Prev. BR": prev,
        "Q1": pr / 4, "Q2": pr / 4, "Q3": pr / 4, "Q4": pr / 4,
        "Факт YTD": fact,
        "Прогноз": pr,
    }

rows = [
    make_row("Revenue", p_rev, rev_total, rev_fact),
    make_row("Backlog", p_backlog, rev_backlog, None, indent=True),
    make_row("Pipeline", p_pipeline, rev_pipeline, None, indent=True),
    make_row("Extra GAP", p_gap, rev_gap, None, indent=True),
    make_row("Прямые расходы", p_direct, direct_total, direct_fact),
    make_row("StaffCost", p_staff, staff_total, staff_fact, indent=True),
    make_row("COGS", p_cogs, cogs_total, cogs_fact, indent=True),
    make_row("GP3", p_gp3, gp3_total, gp3_fact),
    make_row("GM%", p_gm, gm_pct_total, None),
    make_row("SGA", p_sga, sga_total, None),
    make_row("EBITDA", p_ebitda, ebitda_total, ebitda_fact),
]

table_data = []
for r in rows:
    name, p, pr, f = r["Показатель"], r["Prev. BR"], r["Прогноз"], r["Факт YTD"]
    
    if name == "GM%":
        b = None
    elif name == "Revenue":
        b = budget_rev
    elif name == "Прямые расходы":
        b = budget_direct
    elif name == "StaffCost":
        b = budget_staff
    elif name == "COGS":
        b = budget_cogs
    elif name == "GP3":
        b = budget_gp3
    elif name == "EBITDA":
        b = budget_ebitda
    else:
        b = pr * 0.95 if pr else 0.0

    if name == "GM%":
        d_abs, d_pct = pr - p, pr - p
    else:
        d_abs = pr - p
        d_pct = (d_abs / p * 100) if p else 0.0
        
    db_abs = (pr - b) if (b is not None and pr is not None) else None
    db_pct = (db_abs / b * 100) if (b not in (None, 0) and db_abs is not None) else None
    
    table_data.append({
        "Показатель": name, "Бюджет": b, "Prev. BR": p,
        "Q1": pr/4, "Q2": pr/4, "Q3": pr/4, "Q4": pr/4,
        "Факт YTD": f,
        "Прогноз": pr,
        "Δ бюджет": db_abs, "Δ бюджет, %": round(db_pct, 1) if db_pct is not None else None,
        "Δ Prev. BR": d_abs, "Δ Prev. BR, %": round(d_pct, 1),
    })

table = pd.DataFrame(table_data)

display_table = table.copy()
def _fmt_cell(row, col):
    v = row[col]
    if pd.isna(v) or v is None:
        return "—"
    if row["Показатель"] == "GM%":
        return fmt_pct(v, 1, with_sign=False)
    if col in ["Δ бюджет", "Δ Prev. BR"]:
        return fmt_num(v, 0, with_sign=False)
    return fmt_num(v, 0)

for col in ["Бюджет","Prev. BR","Q1","Q2","Q3","Q4","Факт YTD","Прогноз","Δ бюджет","Δ Prev. BR"]:
    display_table[col] = display_table.apply(lambda r, c=col: _fmt_cell(r, c), axis=1)
for col in ["Δ бюджет, %","Δ Prev. BR, %"]:
    display_table[col] = display_table.apply(
        lambda r: "—" if pd.isna(r[col]) or r[col] is None else (
            fmt_pct(r[col], 1, with_sign=False) if r["Показатель"] == "GM%" else fmt_pct(r[col], 1)
        ), axis=1)

_STYLE_JS = JsCode("""
function(params) {
    var style = { textAlign: 'right', fontFamily: 'monospace' };
    if (params.value === null || params.value === undefined) return style;
    var s = String(params.value).replace(/\\s/g,'').replace(/,/g,'.').replace(/%/g,'');
    var neg = s.indexOf('−') === 0 || s.indexOf('-') === 0;
    s = s.replace('−','').replace('-','');
    var v = parseFloat(s); if (isNaN(v) || v === 0) return style;
    if (neg) v = -v;
    var name = (params.data && params.data['Показатель']) ? String(params.data['Показатель']) : '';
    name = name.replace(/^\\s*—\\s*/,'').trim();
    var isExpense = ['Прямые расходы','StaffCost','COGS','SGA'].indexOf(name) !== -1;
    var good = isExpense ? (v < 0) : (v > 0);
    style.color = good ? '#1a7f37' : '#cf222e';
    style.fontWeight = '600';
    return style;
}
""")

gb = GridOptionsBuilder.from_dataframe(display_table)
gb.configure_default_column(resizable=True, sortable=True, filterable=False, minWidth=100, flex=1)
gb.configure_column("Показатель", width=200, pinned="left", cellStyle={"textAlign":"left"})
num_style = {"textAlign":"right","fontFamily":"monospace"}
for c, w in [("Бюджет",110),("Prev. BR",110),("Q1",130),("Q2",130),("Q3",130),("Q4",130),
             ("Факт YTD",130),("Прогноз",140)]:
    gb.configure_column(c, width=w, cellStyle=num_style)
for c in ["Δ бюджет","Δ бюджет, %","Δ Prev. BR","Δ Prev. BR, %"]:
    gb.configure_column(c, width=120, cellStyle=_STYLE_JS)
gb.configure_selection(selection_mode="single", use_checkbox=False)
grid_options = gb.build()
grid_options["getRowStyle"] = JsCode("""
function(p){ return p.node.rowIndex % 2 === 1 ? {background:'#f8f9fa'} : {background:'#ffffff'}; }
""")

AgGrid(display_table, gridOptions=grid_options,
       update_mode=GridUpdateMode.SELECTION_CHANGED,
       fit_columns_on_grid_load=False, height=500, theme="streamlit",
       allow_unsafe_jscode=True,
       custom_css={
           ".ag-row-hover":{"background-color":"#e8f0fe !important","color":"#000 !important"},
           ".ag-row-selected":{"background-color":"#d2e3fc !important","color":"#000 !important"},
           ".ag-cell":{"background-color":"transparent !important"},
       })

# --- EXCEL ---
buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as w:
    table.to_excel(w, sheet_name="P&L", index=False)
    rev.to_excel(w, sheet_name="Revenue", index=False)
    if not stf.empty:
        stf.to_excel(w, sheet_name="StaffCost", index=False)
st.download_button("Скачать отчёт в Excel", data=buf.getvalue(),
                   file_name=f"report_{selected_key}.xlsx", width="stretch")

st.markdown("---")
st.subheader("Детализация по кварталам")
months_by_quarter = {"Q1":["Январь","Февраль","Март"],"Q2":["Апрель","Май","Июнь"],
                     "Q3":["Июль","Август","Сентябрь"],"Q4":["Октябрь","Ноябрь","Декабрь"]}
for q_label, months in months_by_quarter.items():
    with st.expander(f"{q_label} ({months[0]} — {months[-1]})", expanded=False):
        mrows = []
        for r in rows:
            name, q_val = r["Показатель"], r[q_label]
            mv = q_val / 3
            matched = next((t for t in table_data if t["Показатель"] == name), None)
            
            if name == "GM%":
                row_data = {
                    "Показатель": name,
                    months[0]: fmt_pct(q_val, 1, with_sign=False),
                    months[1]: fmt_pct(q_val, 1, with_sign=False),
                    months[2]: fmt_pct(q_val, 1, with_sign=False),
                    f"Итого {q_label}": fmt_pct(q_val, 1, with_sign=False),
                }
                if matched:
                    row_data["Δ бюджет"] = fmt_num(matched.get("Δ бюджет", 0), 0, with_sign=False) if matched.get("Δ бюджет") is not None else "—"
                    row_data["Δ бюджет, %"] = fmt_pct(matched.get("Δ бюджет, %", 0), 1, with_sign=False) if matched.get("Δ бюджет, %") is not None else "—"
                    row_data["Δ Prev. BR"] = fmt_num(matched.get("Δ Prev. BR", 0), 0, with_sign=False) if matched.get("Δ Prev. BR") is not None else "—"
                    row_data["Δ Prev. BR, %"] = fmt_pct(matched.get("Δ Prev. BR, %", 0), 1, with_sign=False) if matched.get("Δ Prev. BR, %") is not None else "—"
            else:
                row_data = {
                    "Показатель": name,
                    months[0]: fmt_num(mv, 0),
                    months[1]: fmt_num(mv, 0),
                    months[2]: fmt_num(mv, 0),
                    f"Итого {q_label}": fmt_num(q_val, 0),
                }
                if matched:
                    row_data["Δ бюджет"] = fmt_num(matched.get("Δ бюджет", 0), 0, with_sign=False) if matched.get("Δ бюджет") is not None else "—"
                    row_data["Δ бюджет, %"] = fmt_pct(matched.get("Δ бюджет, %", 0), 1) if matched.get("Δ бюджет, %") is not None else "—"
                    row_data["Δ Prev. BR"] = fmt_num(matched.get("Δ Prev. BR", 0), 0, with_sign=False) if matched.get("Δ Prev. BR") is not None else "—"
                    row_data["Δ Prev. BR, %"] = fmt_pct(matched.get("Δ Prev. BR, %", 0), 1) if matched.get("Δ Prev. BR, %") is not None else "—"
            
            mrows.append(row_data)
        
        df_q = pd.DataFrame(mrows)
        
        def style_detail(df):
            css = pd.DataFrame('', index=df.index, columns=df.columns)
            for i in range(1, len(df), 2):
                css.iloc[i, :] = 'background-color: #f8f9fa;'
            delta_cols = ["Δ бюджет", "Δ бюджет, %", "Δ Prev. BR", "Δ Prev. BR, %"]
            for idx, row in df.iterrows():
                name = str(row.get("Показатель", "")).replace("—", "").strip()
                is_expense = name in ["Прямые расходы", "StaffCost", "COGS", "SGA"]
                for col in delta_cols:
                    if col not in df.columns:
                        continue
                    val = row[col]
                    if pd.isna(val) or str(val).strip() in ["—", ""]:
                        continue
                    s = str(val).replace(" ", "").replace("+", "").replace("%", "").replace("−", "-").replace(",", ".")
                    try:
                        v = float(s)
                    except:
                        continue
                    if v == 0:
                        continue
                    good = (v < 0) if is_expense else (v > 0)
                    color = '#1a7f37' if good else '#cf222e'
                    css.loc[idx, col] = f'color: {color}; font-weight: 600;'
            return css
        
        styler = df_q.style.apply(style_detail, axis=None).hide(axis="index")
        st.dataframe(styler, width="stretch", height=350)

st.markdown("---")
st.subheader("Динамика по неделям")
dyn_metric = st.radio("Что показывать",
    ["Revenue (общая)","Revenue (по типам)","Прямые расходы","SGA","GP3","EBITDA"],
    horizontal=True, key="dyn_metric")

week_dyn = []
for key in group_keys:
    try:
        w_rev, w_stf, _ = load_all_snapshots(tuple(snapshot_groups[key]))
    except Exception:
        continue
    w_rev = filter_by_sbu(w_rev, selected_by)
    w_stf = filter_by_sbu(w_stf, selected_by)
    wr = get_rev(w_rev)
    wc = get_cogs(w_rev)
    ws = get_staff(w_stf)
    wd = ws + wc
    wg = wr - wd
    wt = split_by_type(w_rev)
    week_dyn.append({
        "Неделя": key, "Revenue": wr,
        "Revenue_Backlog": get_rev(wt["Backlog"]),
        "Revenue_Pipeline": get_rev(wt["Pipeline"]),
        "Revenue_Extra_GAP": get_rev(wt["GAP"]),
        "StaffCost": ws, "COGS": wc, "Прямые расходы": wd,
        "SGA": 0.0, "GP3": wg, "EBITDA": wg,
    })

if week_dyn:
    dyn_df = pd.DataFrame(week_dyn).sort_values("Неделя")
    if dyn_metric == "Revenue (общая)":
        y, title = ["Revenue"], "Revenue по неделям"
    elif dyn_metric == "Revenue (по типам)":
        y, title = ["Revenue_Backlog","Revenue_Pipeline","Revenue_Extra_GAP"], "Revenue по типам"
    elif dyn_metric == "Прямые расходы":
        y, title = ["StaffCost","COGS"], "Прямые расходы: StaffCost vs COGS"
    elif dyn_metric == "SGA":
        y, title = ["SGA"], "SGA по неделям (в источнике отсутствует)"
    elif dyn_metric == "GP3":
        y, title = ["GP3"], "GP3 по неделям"
    else:
        y, title = ["EBITDA"], "EBITDA по неделям"

    fig = px.line(dyn_df, x="Неделя", y=y, markers=True, title=title)
    fig.update_layout(height=450,
        xaxis=dict(tickformat="%d.%m", tickmode="array",
                   tickvals=dyn_df["Неделя"], ticktext=dyn_df["Неделя"]),
        yaxis=dict(tickformat="~s"))
    st.plotly_chart(fig, width="stretch")

    with st.expander("Показать данные по неделям"):
        dd = dyn_df.copy()
        for c in dd.columns:
            if c != "Неделя":
                dd[c] = dd[c].apply(lambda v: fmt_num(v, 0))
        st.dataframe(dd.style.apply(zebra_style, axis=None).hide(axis="index"),
                     width="stretch", height=350)