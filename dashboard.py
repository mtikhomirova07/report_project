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

def fmt_num(value, decimals=0):
    if pd.isna(value) or value is None:
        return "—"
    formatted = f"{abs(value):,.{decimals}f}".replace(",", " ")
    return f"−{formatted}" if value < 0 else formatted

def fmt_pct(value, decimals=1):
    if pd.isna(value) or value is None:
        return "—"
    formatted = f"{abs(value):.{decimals}f}"
    return f"−{formatted}%" if value < 0 else f"+{formatted}%" if value > 0 else f"{formatted}%"

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

# --- ЧТЕНИЕ EXCEL С ФАКТОМ ---
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
        # Блоки: Невзвешенная (8-11), COGS (12-15), Взвешенная (16-19), Взвешенные COGS (20-23)
        # В каждом блоке: Q1(Факт), Q2(Факт), Q3(Прогноз), Q4(Прогноз)
        expected_cols = [
            "SBU", "Заказчик", "Название", "Ссылка", "Признак_XT", 
            "Вероятность", "Backlog_Pipeline", 
            # Невзвешенная выручка
            "Невзвешенная_Q1_Факт", "Невзвешенная_Q2_Факт", "Невзвешенная_Q3_Прогноз", "Невзвешенная_Q4_Прогноз",
            # COGS
            "COGS_Q1_Факт", "COGS_Q2_Факт", "COGS_Q3_Прогноз", "COGS_Q4_Прогноз",
            # Взвешенная выручка
            "Взвешенная_Q1_Факт", "Взвешенная_Q2_Факт", "Взвешенная_Q3_Прогноз", "Взвешенная_Q4_Прогноз",
            # Взвешенные COGS
            "Взвешенные_COGS_Q1_Факт", "Взвешенные_COGS_Q2_Факт", "Взвешенные_COGS_Q3_Прогноз", "Взвешенные_COGS_Q4_Прогноз",
            # Доп. колонки (как в файле)
            "H2_2026_WAvg", "H2_2026_COGS_WAvg", "H2_GM1_WAvg", "Взвешенная_выручка_доп",
            "Rev2027", "Cogs2027", "Проект", "ОПП", "GM3", "Статус"
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
                data[col].astype(str).str.replace("₽", "").str.replace(" ", "").str.replace(",", ".").replace("-", ""),
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
    return rev, stf, errors

# --- ФУНКЦИИ РАСЧЕТА ---
def get_rev_fact(df):
    """Факт (Q1+Q2) по взвешенной выручке."""
    total = 0.0
    for q in ["Q1", "Q2"]:
        col = f"Взвешенная_{q}_Факт"
        if col in df.columns:
            total += df[col].sum()
    return float(total)

def get_rev_prognoz(df):
    """Прогноз (Q3+Q4) по взвешенной выручке."""
    total = 0.0
    for q in ["Q3", "Q4"]:
        col = f"Взвешенная_{q}_Прогноз"
        if col in df.columns:
            total += df[col].sum()
    return float(total)

def get_cogs_fact(df):
    total = 0.0
    for q in ["Q1", "Q2"]:
        col = f"Взвешенные_COGS_{q}_Факт"
        if col in df.columns:
            total += df[col].sum()
    return float(total)

def get_cogs_prognoz(df):
    total = 0.0
    for q in ["Q3", "Q4"]:
        col = f"Взвешенные_COGS_{q}_Прогноз"
        if col in df.columns:
            total += df[col].sum()
    return float(total)

def get_staff(df):
    if df is None or df.empty:
        return 0.0
    total = 0.0
    for q in ["Q1", "Q2", "Q3", "Q4"]:
        col = f"ИТОГО_{q}"
        if col in df.columns:
            total += df[col].sum()
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
rev_fact = get_rev_fact(rev)
rev_prog = get_rev_prognoz(rev)
rev_total = rev_fact + rev_prog

cogs_fact = get_cogs_fact(rev)
cogs_prog = get_cogs_prognoz(rev)
cogs_total = cogs_fact + cogs_prog

staff_total = get_staff(stf)
direct_total = staff_total + cogs_total
direct_fact = staff_total + cogs_fact  # Условно считаем весь staff фактом

gp3_total = rev_total - direct_total
gp3_fact = rev_fact - direct_fact
ebitda_total = gp3_total
ebitda_fact = gp3_fact
gm_pct_total = (gp3_total / rev_total * 100) if rev_total else 0.0
gm_pct_fact = (gp3_fact / rev_fact * 100) if rev_fact else 0.0

types = split_by_type(rev)
rev_backlog_fact = get_rev_fact(types["Backlog"])
rev_backlog_prog = get_rev_prognoz(types["Backlog"])
rev_backlog_total = rev_backlog_fact + rev_backlog_prog

rev_pipeline_fact = get_rev_fact(types["Pipeline"])
rev_pipeline_prog = get_rev_prognoz(types["Pipeline"])
rev_pipeline_total = rev_pipeline_fact + rev_pipeline_prog

rev_gap_fact = get_rev_fact(types["GAP"])
rev_gap_prog = get_rev_prognoz(types["GAP"])
rev_gap_total = rev_gap_fact + rev_gap_prog

# --- PREV BR ---
if comparison:
    comp_rev = filter_by_sbu(comparison[0], selected_by)
    comp_stf = filter_by_sbu(comparison[1], selected_by)
    
    p_rev = get_rev_fact(comp_rev) + get_rev_prognoz(comp_rev)
    p_cogs = get_cogs_fact(comp_rev) + get_cogs_prognoz(comp_rev)
    p_staff = get_staff(comp_stf)
    p_direct = p_staff + p_cogs
    p_gp3 = p_rev - p_direct
    p_ebitda = p_gp3
    p_gm = (p_gp3 / p_rev * 100) if p_rev else 0.0
else:
    p_rev = p_cogs = p_staff = p_direct = p_gp3 = p_ebitda = p_gm = 0.0

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

# Формируем строки. Для факта передаем рассчитанные значения
rows = [
    make_row("Revenue", p_rev, rev_total, rev_fact),
    make_row("Backlog", 0.0, rev_backlog_total, rev_backlog_fact, indent=True),
    make_row("Pipeline", 0.0, rev_pipeline_total, rev_pipeline_fact, indent=True),
    make_row("Extra GAP", 0.0, rev_gap_total, rev_gap_fact, indent=True),
    make_row("Прямые расходы", p_direct, direct_total, direct_fact),
    make_row("StaffCost", 0.0, staff_total, staff_total, indent=True),
    make_row("COGS", 0.0, cogs_total, cogs_fact, indent=True),
    make_row("GP3", p_gp3, gp3_total, gp3_fact),
    make_row("GM%", p_gm, gm_pct_total, gm_pct_fact),
    make_row("SGA", 0.0, 0.0, 0.0),
    make_row("EBITDA", p_ebitda, ebitda_total, ebitda_fact),
]

table_data = []
for r in rows:
    name, p, pr, f = r["Показатель"], r["Prev. BR"], r["Прогноз"], r["Факт YTD"]
    
    # Бюджет не нужен (мы его удалили или оставили пустым), но если нужно - тут логика
    b = None
    
    if name == "GM%":
        d_abs, d_pct = pr - p, pr - p
    else:
        d_abs = pr - p
        d_pct = (d_abs / p * 100) if p else 0.0

    table_data.append({
        "Показатель": name, "Бюджет": b, "Prev. BR": p,
        "Q1": pr/4, "Q2": pr/4, "Q3": pr/4, "Q4": pr/4,
        "Факт YTD": f,
        "Прогноз": pr,
        "Δ бюджет": None, "Δ бюджет, %": None,
        "Δ Prev. BR": d_abs, "Δ Prev. BR, %": round(d_pct, 1),
    })

total_pr = rev_total + direct_total
total_prev = (p_rev + p_direct) if comparison else None
total_fact = rev_fact + direct_fact

table_data.append({
    "Показатель": "ИТОГО (ключевые)", "Бюджет": None, "Prev. BR": total_prev,
    "Q1": total_pr/4, "Q2": total_pr/4, "Q3": total_pr/4, "Q4": total_pr/4,
    "Факт YTD": total_fact,
    "Прогноз": total_pr,
    "Δ бюджет": None, "Δ бюджет, %": None,
    "Δ Prev. BR": (total_pr - total_prev) if total_prev else None,
    "Δ Prev. BR, %": round(((total_pr - total_prev)/total_prev*100), 1) if total_prev else None,
})
table = pd.DataFrame(table_data)

display_table = table.copy()
def _fmt_cell(row, col):
    v = row[col]
    if pd.isna(v) or v is None:
        return "—"
    if row["Показатель"] == "GM%":
        return fmt_pct(v, 1)
    return fmt_num(v, 0)

for col in ["Бюджет","Prev. BR","Q1","Q2","Q3","Q4","Факт YTD","Прогноз","Δ бюджет","Δ Prev. BR"]:
    display_table[col] = display_table.apply(lambda r, c=col: _fmt_cell(r, c), axis=1)
for col in ["Δ бюджет, %","Δ Prev. BR, %"]:
    display_table[col] = display_table.apply(
        lambda r: "—" if pd.isna(r[col]) or r[col] is None else fmt_pct(r[col], 1), axis=1)

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
    var isExpense = ['Прямые расходы','StaffCost','COGS','SGA','ИТОГО (ключевые)'].indexOf(name) !== -1;
    var good = isExpense ? (v < 0) : (v > 0);
    style.color = good ? '#1a7f37' : '#cf222e';
    style.fontWeight = '600';
    return style;
}
""")

gb = GridOptionsBuilder.from_dataframe(display_table)
gb.configure_default_column(resizable=True, sortable=True, filterable=False)
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

# ... Дальше идут блоки "Детализация по кварталам" и "Динамика по неделям" ...
# Они остаются без изменений, так как логика расчета кварталов не поменялась.
# Для краткости я их не дублирую.