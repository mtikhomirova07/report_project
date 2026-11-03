import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
import subprocess
import sys
import glob
import re
from datetime import datetime
from pathlib import Path
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode
from fpdf import FPDF

from approvals import (
    set_status, get_status, get_status_label,
    get_last_br_before, list_all_statuses,
    is_approved, unapprove, approve,
    DRAFT, PRE_BR, BR,
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

st.markdown(
    """
    <style>
        [data-testid="stSidebarResizeHandle"] { display: none !important; }
        [data-testid="stSidebarUserContent"] { padding-top: 2rem !important; }
        [data-testid="stSidebar"] h2 { padding-bottom: 0rem !important; margin-bottom: 0.5rem !important; }
        [data-testid="stSidebar"] hr { margin: 10px 0 !important; }
        [data-testid="stSidebar"] .stRadio { margin-bottom: -10px !important; }
    </style>
    """,
    unsafe_allow_html=True
)

BASE_DIR = Path(__file__).parent
SNAPSHOTS_DIR = BASE_DIR / "data" / "snapshots"
LOGS_DIR = BASE_DIR / "data" / "logs"
LAST_ERROR_FILE = LOGS_DIR / "LAST_ERROR.txt"

FONT_DIR = BASE_DIR / "dejavu-sans"
FONT_REGULAR = FONT_DIR / "DejaVuSans.ttf"
FONT_BOLD = FONT_DIR / "DejaVuSans-Bold.ttf"

def parse_timestamp(ts):
    try:
        match = re.search(r"(\d{4}-\d{2}-\d{2}_\d{4})", ts)
        if match:
            return datetime.strptime(match.group(1), "%Y-%m-%d_%H%M")
        return datetime.min
    except Exception:
        return datetime.min

def get_week_label(dt):
    iso = dt.isocalendar()
    monday = dt - pd.Timedelta(days=dt.weekday())
    sunday = monday + pd.Timedelta(days=6)
    return f"Неделя {iso[1]} ({monday.strftime('%d.%m')} – {sunday.strftime('%d.%m.%y')})"

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

# --- АВТОЗАГРУЗКА ПРИ ПЕРВОМ ВХОДЕ ---
snapshot_files_check = glob.glob(str(SNAPSHOTS_DIR / "*.xlsx"))

if not snapshot_files_check:
    with st.spinner("Первый запуск. Загружаю данные с Яндекс.Диска..."):
        from loader import update_data
        success, message = update_data()
    if success:
        st.sidebar.success(message)
        st.cache_data.clear()
        st.rerun()
    else:
        st.sidebar.error(f"Ошибка: {message}")
        st.stop()

# --- КНОПКА ОБНОВЛЕНИЯ (ручная) ---
if st.sidebar.button("🔄 Обновить данные", width="stretch"):
    with st.spinner("Загружаю данные с Яндекс.Диска..."):
        from loader import update_data
        success, message = update_data()
    if success:
        st.sidebar.success(message)
        st.cache_data.clear()
        st.rerun()
    else:
        st.sidebar.error(f"Ошибка: {message}")
# ------------------------

snapshot_files = sorted(glob.glob(str(SNAPSHOTS_DIR / "*.xlsx")), reverse=True)
if not snapshot_files:
    st.error("Нет снимков. Нажмите «Обновить данные».")
    st.stop()

# Группируем файлы по неделям (папкам)
snapshot_groups = {}
for f in snapshot_files:
    stem = Path(f).stem
    week_match = re.search(r"(2026-W\d+)", stem)
    date_match = re.search(r"(\d{4}-\d{2}-\d{2}_\d{4})", stem)
    
    if week_match:
        key = week_match.group(1)
    elif date_match:
        key = date_match.group(1)
    else:
        key = stem
    
    if key not in snapshot_groups:
        snapshot_groups[key] = []
    snapshot_groups[key].append(f)

group_keys = sorted(snapshot_groups.keys(), reverse=True)

@st.cache_data
def load_all_snapshots(paths):
    all_revenue = []
    all_staff = []

    for path in paths:
        try:
            xls = pd.ExcelFile(path)
            sheet_names = xls.sheet_names
            
            if "Revenue" in sheet_names:
                df = pd.read_excel(path, sheet_name="Revenue")
                all_revenue.append(df)
                
            if "StaffCost" in sheet_names:
                df = pd.read_excel(path, sheet_name="StaffCost")
                all_staff.append(df)
                    
        except Exception as e:
            st.warning(f"Ошибка чтения файла {path}: {e}")

    return {
        "revenue": pd.concat(all_revenue, ignore_index=True) if all_revenue else pd.DataFrame(),
        "staff": pd.concat(all_staff, ignore_index=True) if all_staff else pd.DataFrame(),
    }

def build_group_options(groups):
    options = []
    for key in sorted(groups.keys(), reverse=True):
        if key.startswith("2026-W"):
            label = key
        else:
            dt = parse_timestamp(key)
            if dt != datetime.min:
                label = f"{dt.strftime('%d.%m.%Y %H:%M')}"
            else:
                label = key
        options.append({"label": label, "key": key, "paths": groups[key]})
    return options

st.sidebar.markdown("---")

st.sidebar.header("Период (→ PREV-BR)")
group_options = build_group_options(snapshot_groups)
group_labels = [o["label"] for o in group_options]

selected_group_label = st.sidebar.selectbox("Неделя", group_labels, index=0, label_visibility="collapsed")
selected_group = next(o for o in group_options if o["label"] == selected_group_label)

st.sidebar.markdown("---")

st.sidebar.header("Статус версии")
current_status = get_status(selected_group["key"])
current_label = get_status_label(selected_group["key"])

if current_status == BR:
    st.sidebar.success(f"Статус: {current_label}")
elif current_status == PRE_BR:
    st.sidebar.warning(f"Статус: {current_label}")
else:
    st.sidebar.info(f"Статус: {current_label}")

col_s1, col_s2 = st.sidebar.columns(2)

btn_pre_br_disabled = (current_status != DRAFT)
with col_s1:
    if st.button("Пред-BR", width="stretch", disabled=btn_pre_br_disabled):
        set_status(selected_group["key"], PRE_BR)
        st.rerun()

btn_br_disabled = (current_status != PRE_BR)
with col_s2:
    if st.button("BR", width="stretch", disabled=btn_br_disabled):
        try:
            for o in group_options:
                if o["key"] != selected_group["key"] and get_status(o["key"]) == BR:
                    set_status(o["key"], PRE_BR)
            prev_date = get_last_br_before(selected_group["key"])
            if prev_date and prev_date != selected_group["key"]:
                st.set_status(prev_date, PRE_BR)
        except Exception:
            pass
        set_status(selected_group["key"], BR)
        st.rerun()

btn_draft_disabled = (current_status != PRE_BR)
if current_status != BR:
    if st.sidebar.button("Снять статус (Черновик)", width="stretch", disabled=btn_draft_disabled):
        set_status(selected_group["key"], DRAFT)
        st.rerun()

st.sidebar.markdown("---")

prev_br_date = get_last_br_before(selected_group["key"])
comparison_data = None

if prev_br_date:
    for o in group_options:
        if o["key"] == prev_br_date:
            try:
                comparison_data = load_all_snapshots(tuple(o["paths"]))
            except Exception as e:
                st.sidebar.warning(f"Ошибка загрузки данных для сравнения: {e}")
            break

st.sidebar.markdown("**Актуальный прогноз**")
if comparison_data:
    st.sidebar.caption(f"Сравнение с BR: {prev_br_date}")
else:
    st.sidebar.caption("Нет предыдущего BR для сравнения")

st.sidebar.markdown("---")

st.sidebar.header("Фильтры")
try:
    data = load_all_snapshots(tuple(selected_group["paths"]))
except Exception as e:
    st.error(f"Ошибка чтения: {e}")
    st.stop()

revenue = data["revenue"]
staff = data["staff"]

if revenue.empty:
    st.error("В загруженных файлах не найдены данные по выручке (лист Revenue). Проверьте структуру файлов.")
    st.stop()

by_list = ["Все"] + sorted(revenue["SBU"].dropna().unique().tolist())
selected_by = st.sidebar.selectbox("Бизнес-юнит (БЮ)", by_list)

if selected_by != "Все":
    rev = revenue[revenue["SBU"] == selected_by]
    stf = staff[staff["SBU"] == selected_by]
else:
    rev = revenue
    stf = staff

st.sidebar.markdown("---")

st.sidebar.header("Навигация")
page = st.sidebar.radio("Страница", ["P&L", "Сделки"], key="page_nav", label_visibility="collapsed")

if page == "Сделки":
    from page_deals import render_deals_page
    render_deals_page(
        deals=rev,
        comparison_deals=comparison_data["revenue"] if comparison_data else None,
        selected_by=selected_by,
        selected_date=selected_group["key"],
        fmt_num=fmt_num,
        fmt_pct=fmt_pct,
    )
    st.stop()

# ============================================================
# СТРАНИЦА: P&L
# ============================================================
rev_totals = {
    "Выручка_бюджет": 0, "Выручка_prev": 0, "Выручка_факт": 0, "Выручка_прогноз": 0,
    "Выручка_Backlog": 0, "Выручка_Pipeline": 0, "Выручка_Extra_GAP": 0,
}

for _, row in rev.iterrows():
    qty = row.get("Вероятность", 0) / 100.0
    total = row.get("Q1", 0) + row.get("Q2", 0) + row.get("Q3", 0) + row.get("Q4", 0)
    
    rev_totals["Выручка_бюджет"] += row.get("Бюджет", 0)
    rev_totals["Выручка_прогноз"] += total * qty
    rev_totals["Выручка_факт"] += row.get("Факт YTD", 0)
    rev_totals["Выручка_prev"] += 0

    deal_type = str(row.get("Тип_сделки", "")).strip()
    if deal_type == "Backlog":
        rev_totals["Выручка_Backlog"] += total * qty
    elif deal_type == "Pipeline":
        rev_totals["Выручка_Pipeline"] += total * qty
    elif deal_type == "GAP":
        rev_totals["Выручка_Extra_GAP"] += total * qty

staff_totals = {
    "StaffCost_бюджет": 0, "StaffCost_prev": 0, "StaffCost_факт": 0, "StaffCost_прогноз": 0,
    "COGS_бюджет": 0, "COGS_prev": 0, "COGS_факт": 0, "COGS_прогноз": 0,
}

for _, row in stf.iterrows():
    total = row.get("Q1", 0) + row.get("Q2", 0) + row.get("Q3", 0) + row.get("Q4", 0)
    article = str(row.get("Статья_затрат", "")).strip()

    if "ФОТ" in article or "Премии" in article:
        staff_totals["StaffCost_бюджет"] += row.get("Бюджет", 0)
        staff_totals["StaffCost_прогноз"] += total
        staff_totals["StaffCost_факт"] += row.get("Факт YTD", 0)
        staff_totals["StaffCost_prev"] += 0
    else:
        staff_totals["COGS_бюджет"] += row.get("Бюджет", 0)
        staff_totals["COGS_прогноз"] += total
        staff_totals["COGS_факт"] += row.get("Факт YTD", 0)
        staff_totals["COGS_prev"] += 0

sga_totals = {
    "SGA_бюджет": 0, "SGA_prev": 0, "SGA_факт": 0, "SGA_прогноз": 0,
}

# --- СЧИТАЕМ ДАННЫЕ ДЛЯ ПРЕДЫДУЩЕГО BR ---
if comparison_data:
    comp_rev = comparison_data["revenue"]
    comp_staff = comparison_data["staff"]
    if selected_by != "Все":
        comp_rev = comp_rev[comp_rev["SBU"] == selected_by]
        comp_staff = comp_staff[comp_staff["SBU"] == selected_by]

    comp_rev_total = 0
    comp_rev_backlog = 0
    comp_rev_pipeline = 0
    comp_rev_gap = 0
    for _, row in comp_rev.iterrows():
        qty = row.get("Вероятность", 0) / 100.0
        total = row.get("Q1", 0) + row.get("Q2", 0) + row.get("Q3", 0) + row.get("Q4", 0)
        val = total * qty
        comp_rev_total += val
        deal_type = str(row.get("Тип_сделки", "")).strip()
        if deal_type == "Backlog":
            comp_rev_backlog += val
        elif deal_type == "Pipeline":
            comp_rev_pipeline += val
        elif deal_type == "GAP":
            comp_rev_gap += val

    comp_staff_total = 0
    comp_cogs_total = 0
    for _, row in comp_staff.iterrows():
        total = row.get("Q1", 0) + row.get("Q2", 0) + row.get("Q3", 0) + row.get("Q4", 0)
        article = str(row.get("Статья_затрат", "")).strip()
        if "ФОТ" in article or "Премии" in article:
            comp_staff_total += total
        else:
            comp_cogs_total += total

    rev_totals["Выручка_prev"] = comp_rev_total
    staff_totals["StaffCost_prev"] = comp_staff_total
    staff_totals["COGS_prev"] = comp_cogs_total

def sum_direct(prefix):
    return staff_totals[f"StaffCost_{prefix}"] + staff_totals[f"COGS_{prefix}"]

def gp3(prefix):
    return rev_totals[f"Выручка_{prefix}"] - sum_direct(prefix)

def ebitda(prefix):
    return gp3(prefix) - sga_totals[f"SGA_{prefix}"]

def gm_pct(prefix):
    rev_val = rev_totals[f"Выручка_{prefix}"]
    return (gp3(prefix) / rev_val * 100) if rev_val else 0

st.title("Управленческая отчётность")
dt_str = selected_group["key"]
st.caption(f"Отчёт от {dt_str} | БЮ: {selected_by} | Единицы: тыс. руб.")
st.markdown("---")

st.subheader("P&L по статьям")

if comparison_data:
    st.caption(f"**Режим сравнения:** показатели колонки `Прогноз` сравниваются с отчетом **{prev_br_date}**. Разница отображена в колонке `Δ Prev. BR`.")
else:
    st.caption("Кликните на строку Backlog / Pipeline / Extra GAP, чтобы открыть детализацию по сделкам. Сравнение не выбрано, данные в колонке `Prev. BR` — базовые (из файла).")

def delta_pct(a, b):
    return (a - b) / b * 100 if b else 0

total_pr = rev_totals["Выручка_прогноз"] if rev_totals["Выручка_прогноз"] else 1
ratio_backlog = rev_totals["Выручка_Backlog"] / total_pr
ratio_pipeline = rev_totals["Выручка_Pipeline"] / total_pr
ratio_gap = rev_totals["Выручка_Extra_GAP"] / total_pr

def make_row(name, b, p, f, pr, indent=False):
    return {
        "Показатель": ("    — " + name) if indent else name,
        "Бюджет": b,
        "Prev. BR": p,
        "Q1": pr / 4,
        "Q2": pr / 4,
        "Q3": pr / 4,
        "Q4": pr / 4,
        "Факт YTD": f,
        "Прогноз": pr,
    }

if comparison_data:
    r_backlog_p = comp_rev_backlog
    r_pipeline_p = comp_rev_pipeline
    r_gap_p = comp_rev_gap
    r_total_p = comp_rev_total
    d_staff_p = comp_staff_total
    d_cogs_p = comp_cogs_total
    d_total_p = comp_staff_total + comp_cogs_total
    gp3_p = comp_rev_total - d_total_p
    sga_p = 0
    ebitda_p = gp3_p - sga_p
else:
    r_backlog_p = 0
    r_pipeline_p = 0
    r_gap_p = 0
    r_total_p = 0
    d_total_p = 0
    d_staff_p = 0
    d_cogs_p = 0
    gp3_p = 0
    sga_p = 0
    ebitda_p = 0

rows = [
    make_row("Revenue", rev_totals["Выручка_бюджет"], r_total_p,
             rev_totals["Выручка_факт"], rev_totals["Выручка_прогноз"]),
    make_row("Backlog",
             rev_totals["Выручка_бюджет"] * ratio_backlog,
             r_backlog_p,
             rev_totals["Выручка_факт"] * ratio_backlog,
             rev_totals["Выручка_Backlog"], indent=True),
    make_row("Pipeline",
             rev_totals["Выручка_бюджет"] * ratio_pipeline,
             r_pipeline_p,
             rev_totals["Выручка_факт"] * ratio_pipeline,
             rev_totals["Выручка_Pipeline"], indent=True),
    make_row("Extra GAP",
             rev_totals["Выручка_бюджет"] * ratio_gap,
             r_gap_p,
             rev_totals["Выручка_факт"] * ratio_gap,
             rev_totals["Выручка_Extra_GAP"], indent=True),
    make_row("Прямые расходы", staff_totals["StaffCost_бюджет"] + staff_totals["COGS_бюджет"], d_total_p,
             staff_totals["StaffCost_факт"] + staff_totals["COGS_факт"], sum_direct("прогноз")),
    make_row("StaffCost", staff_totals["StaffCost_бюджет"], d_staff_p,
             staff_totals["StaffCost_факт"], staff_totals["StaffCost_прогноз"], indent=True),
    make_row("COGS", staff_totals["COGS_бюджет"], d_cogs_p,
             staff_totals["COGS_факт"], staff_totals["COGS_прогноз"], indent=True),
    make_row("GP3", 0, gp3_p, 0, gp3("прогноз")),
    make_row("GM%", 0, gm_pct('prev'), 0, gm_pct('прогноз')),
    make_row("SGA", 0, sga_p, 0, sga_totals["SGA_прогноз"]),
    make_row("EBITDA", 0, ebitda_p, 0, ebitda("прогноз")),
]

table_data = []
for row_dict in rows:
    name = row_dict["Показатель"]
    b = row_dict["Бюджет"]
    p = row_dict["Prev. BR"]
    f = row_dict["Факт YTD"]
    pr = row_dict["Прогноз"]

    if name == "GM%":
        delta_b = pr - b if b else 0
        delta_b_pct = pr - b if b else 0
        delta_p = pr - p if p else 0
        delta_p_pct = pr - p if p else 0
    else:
        delta_b = pr - b if b else 0
        delta_b_pct = delta_pct(pr, b)
        delta_p = pr - p if p else 0
        delta_p_pct = delta_pct(pr, p)

    table_data.append({
        "Показатель": name,
        "Бюджет": b,
        "Prev. BR": p,
        "Q1": row_dict["Q1"],
        "Q2": row_dict["Q2"],
        "Q3": row_dict["Q3"],
        "Q4": row_dict["Q4"],
        "Факт YTD": f,
        "Прогноз": pr,
        "Δ бюджет": delta_b,
        "Δ бюджет, %": round(delta_b_pct, 1),
        "Δ Prev. BR": delta_p,
        "Δ Prev. BR, %": round(delta_p_pct, 1),
    })

total_budget = rev_totals["Выручка_бюджет"] + staff_totals["StaffCost_бюджет"] + staff_totals["COGS_бюджет"] + sga_totals["SGA_бюджет"]
total_prev = rev_totals["Выручка_prev"] + staff_totals["StaffCost_prev"] + staff_totals["COGS_prev"] + sga_totals["SGA_prev"] if comparison_data else 0
total_fact = rev_totals["Выручка_факт"] + staff_totals["StaffCost_факт"] + staff_totals["COGS_факт"] + sga_totals["SGA_факт"]
total_pr_val = rev_totals["Выручка_прогноз"] + staff_totals["StaffCost_прогноз"] + staff_totals["COGS_прогноз"] + sga_totals["SGA_прогноз"]

total_row = {
    "Показатель": "ИТОГО (ключевые)",
    "Бюджет": total_budget,
    "Prev. BR": total_prev,
    "Q1": total_pr_val / 4,
    "Q2": total_pr_val / 4,
    "Q3": total_pr_val / 4,
    "Q4": total_pr_val / 4,
    "Факт YTD": total_fact,
    "Прогноз": total_pr_val,
    "Δ бюджет": total_pr_val - total_budget,
    "Δ бюджет, %": round(((total_pr_val - total_budget) / total_budget * 100) if total_budget else 0, 1),
    "Δ Prev. BR": total_pr_val - total_prev,
    "Δ Prev. BR, %": round(((total_pr_val - total_prev) / total_prev * 100) if total_prev else 0, 1),
}

table_data.append(total_row)
table = pd.DataFrame(table_data)

display_table = table.copy()
for col in ["Бюджет", "Prev. BR", "Q1", "Q2", "Q3", "Q4", "Факт YTD", "Прогноз"]:
    display_table[col] = display_table.apply(
        lambda row: fmt_pct(row[col], 1) if row["Показатель"] == "GM%" else fmt_num(row[col], 0),
        axis=1
    )

for col in ["Δ бюджет", "Δ Prev. BR"]:
    display_table[col] = display_table.apply(
        lambda row: (fmt_pct(row[col], 1) if row["Показатель"] == "GM%" else fmt_num(row[col], 0)),
        axis=1
    )

for col in ["Δ бюджет, %", "Δ Prev. BR, %"]:
    display_table[col] = display_table.apply(
        lambda row: fmt_pct(row[col], 1),
        axis=1
    )

_STYLE_JS = JsCode("""
function(params) {
    var style = { textAlign: 'right', fontFamily: 'monospace' };
    if (params.value === null || params.value === undefined) return style;
    var s = String(params.value).replace(/\\s/g, '').replace(/,/g, '.').replace(/%/g, '');
    var neg = s.indexOf('−') === 0 || s.indexOf('-') === 0;
    s = s.replace('−', '').replace('-', '');
    var v = parseFloat(s);
    if (isNaN(v) || v === 0) return style;
    if (neg) v = -v;
    var name = (params.data && params.data['Показатель']) ? String(params.data['Показатель']) : '';
    name = name.replace(/^\\s*—\\s*/, '').trim();
    var isExpense = ['Прямые расходы', 'StaffCost', 'COGS', 'SGA', 'ИТОГО (ключевые)'].indexOf(name) !== -1;
    var good;
    if (isExpense) { good = v < 0; } else { good = v > 0; }
    style.color = good ? '#1a7f37' : '#cf222e';
    style.fontWeight = '600';
    return style;
}
""")

gb = GridOptionsBuilder.from_dataframe(display_table)
gb.configure_default_column(resizable=True, sortable=True, filterable=False)
gb.configure_column("Показатель", width=200, pinned="left", cellStyle={"textAlign": "left"})

num_style = {"textAlign": "right", "fontFamily": "monospace"}
gb.configure_column("Бюджет", width=110, cellStyle=num_style)
gb.configure_column("Prev. BR", width=110, cellStyle={**num_style, "backgroundColor": "#f4f6f8"})
gb.configure_column("Q1", width=90, cellStyle=num_style)
gb.configure_column("Q2", width=90, cellStyle=num_style)
gb.configure_column("Q3", width=90, cellStyle=num_style)
gb.configure_column("Q4", width=90, cellStyle=num_style)
gb.configure_column("Факт YTD", width=110, cellStyle=num_style)
gb.configure_column("Прогноз", width=110, cellStyle=num_style)

for col in ["Δ бюджет", "Δ бюджет, %", "Δ Prev. BR", "Δ Prev. BR, %"]:
    gb.configure_column(col, width=120, cellStyle=_STYLE_JS)

gb.configure_selection(selection_mode="single", use_checkbox=False)
grid_options = gb.build()

grid_options["getRowStyle"] = JsCode("""
function(params) {
    if (params.node.rowIndex % 2 === 1) {
        return { background: '#f8f9fa' };
    }
    return { background: '#ffffff' };
}
""")

custom_css = {
    ".ag-row-hover": {"background-color": "#e8f0fe !important", "color": "#000 !important"},
    ".ag-row-selected": {"background-color": "#d2e3fc !important", "color": "#000 !important"},
    ".ag-row-selected:hover": {"background-color": "#d2e3fc !important"},
    ".ag-cell": {"background-color": "transparent !important"}
}

grid_response = AgGrid(
    display_table,
    gridOptions=grid_options,
    update_mode=GridUpdateMode.SELECTION_CHANGED,
    fit_columns_on_grid_load=False,
    height=500,
    theme="streamlit",
    allow_unsafe_jscode=True,
    custom_css=custom_css,
)

buffer_excel = io.BytesIO()
with pd.ExcelWriter(buffer_excel, engine="openpyxl") as writer:
    table.to_excel(writer, sheet_name="P&L", index=False)
    rev.to_excel(writer, sheet_name="Revenue", index=False)
    stf.to_excel(writer, sheet_name="StaffCost", index=False)

col_dl1, col_dl2 = st.columns(2)
with col_dl1:
    st.download_button("Скачать отчёт в Excel", data=buffer_excel.getvalue(), file_name=f"report_{selected_group['key']}.xlsx", width="stretch")
with col_dl2:
    st.button("PDF недоступен", disabled=True, width="stretch")

st.markdown("---")

st.subheader("Детализация по кварталам")
st.caption("Кварталы раскрываются по клику. Внутри — 3 месяца + итого за квартал.")
months_by_quarter = {"Q1": ["Январь", "Февраль", "Март"], "Q2": ["Апрель", "Май", "Июнь"], "Q3": ["Июль", "Август", "Сентябрь"], "Q4": ["Октябрь", "Ноябрь", "Декабрь"]}

for q_label, months in months_by_quarter.items():
    with st.expander(f"{q_label} ({months[0]} — {months[-1]})", expanded=False):
        month_rows = []
        for row_dict in rows:
            name = row_dict["Показатель"]
            q_val = row_dict[q_label]
            month_val = q_val / 3
            
            if name == "GM%":
                month_rows.append({
                    "Показатель": name,
                    months[0]: fmt_pct(q_val, 1),
                    months[1]: fmt_pct(q_val, 1),
                    months[2]: fmt_pct(q_val, 1),
                    f"Итого {q_label}": fmt_pct(q_val, 1),
                })
            else:
                month_rows.append({
                    "Показатель": name,
                    months[0]: fmt_num(month_val, 0),
                    months[1]: fmt_num(month_val, 0),
                    months[2]: fmt_num(month_val, 0),
                    f"Итого {q_label}": fmt_num(q_val, 0),
                })
                
        df_month = pd.DataFrame(month_rows)
        styler = df_month.style.apply(zebra_style, axis=None).hide(axis="index")
        st.dataframe(styler, width="stretch", height=350)

st.markdown("---")

st.subheader("Тренд: отклонение от плана по неделям")
all_weeks_data = []
seen_weeks = set()

for key in group_keys:
    if key in seen_weeks:
        continue
    seen_weeks.add(key)
    
    try:
        w_data = load_all_snapshots(tuple(snapshot_groups[key]))
        w_rev_df = w_data["revenue"]
        if selected_by != "Все":
            w_rev_df = w_rev_df[w_rev_df["SBU"] == selected_by]
        w_rev_pr = 0
        w_rev_b = 0
        for _, row in w_rev_df.iterrows():
            qty = row.get("Вероятность", 0) / 100.0
            total = row.get("Q1", 0) + row.get("Q2", 0) + row.get("Q3", 0) + row.get("Q4", 0)
            w_rev_pr += total * qty
            w_rev_b += row.get("Бюджет", 0)
        
        w_stf_df = w_data["staff"]
        if selected_by != "Все":
            w_stf_df = w_stf_df[w_stf_df["SBU"] == selected_by]
        
        w_staff_pr = 0
        w_staff_b = 0
        w_cogs_pr = 0
        w_cogs_b = 0
        for _, row in w_stf_df.iterrows():
            total = row.get("Q1", 0) + row.get("Q2", 0) + row.get("Q3", 0) + row.get("Q4", 0)
            article = str(row.get("Статья_затрат", "")).strip()
            if "ФОТ" in article or "Премии" in article:
                w_staff_pr += total
                w_staff_b += row.get("Бюджет", 0)
            else:
                w_cogs_pr += total
                w_cogs_b += row.get("Бюджет", 0)

        w_gp3_pr = w_rev_pr - (w_staff_pr + w_cogs_pr)
        w_gp3_b = w_rev_b - (w_staff_b + w_cogs_b)
        w_sga_pr = 0
        w_sga_b = 0
        w_ebitda_pr = w_gp3_pr - w_sga_pr
        w_ebitda_b = w_gp3_b - w_sga_b

        all_weeks_data.append({
            "Неделя": key,
            "Revenue": w_rev_pr - w_rev_b,
            "StaffCost": w_staff_pr - w_staff_b,
            "COGS": w_cogs_pr - w_cogs_b,
            "Прямые расходы": (w_staff_pr + w_cogs_pr) - (w_staff_b + w_cogs_b),
            "SGA": w_sga_pr - w_sga_b,
            "GP3": w_gp3_pr - w_gp3_b,
            "EBITDA": w_ebitda_pr - w_ebitda_b,
        })
    except Exception:
        continue

if all_weeks_data:
    trend_df = pd.DataFrame(all_weeks_data).sort_values("Неделя")
    metric = st.radio(
        "Показатель",
        ["Revenue", "Прямые расходы", "StaffCost", "COGS", "SGA", "GP3", "EBITDA"],
        horizontal=True,
        key="trend_metric",
    )
    
    fig_trend = px.line(trend_df, x="Неделя", y=metric, markers=True, title=f"Отклонение прогноза {metric} от плана")
    fig_trend.update_layout(
        xaxis=dict(
            tickformat="%d.%m",
            tickmode="array",
            tickvals=trend_df["Неделя"],
            ticktext=trend_df["Неделя"]
        ),
        height=400,
    )
    fig_trend.add_hline(y=0, line_dash="dash", line_color="gray")
    st.plotly_chart(fig_trend, width="stretch")

st.markdown("---")

st.subheader("Динамика по неделям")
dyn_metric = st.radio(
    "Что показывать на графике", 
    ["Revenue (общая)", "Revenue (по типам)", "Прямые расходы", "SGA", "GP3", "EBITDA"], 
    horizontal=True, 
    key="dyn_metric"
)

week_dyn = []
seen_weeks_dyn = set()

for key in group_keys:
    if key in seen_weeks_dyn:
        continue
    seen_weeks_dyn.add(key)
    
    try:
        w_data = load_all_snapshots(tuple(snapshot_groups[key]))
        w_rev = w_data["revenue"]
        w_dr = w_data["staff"]
        
        if selected_by != "Все":
            w_rev = w_rev[w_rev["SBU"] == selected_by]
            w_dr = w_dr[w_dr["SBU"] == selected_by]

        w_rev_total = 0
        w_rev_backlog = 0
        w_rev_pipeline = 0
        w_rev_gap = 0
        for _, row in w_rev.iterrows():
            qty = row.get("Вероятность", 0) / 100.0
            total = row.get("Q1", 0) + row.get("Q2", 0) + row.get("Q3", 0) + row.get("Q4", 0)
            val = total * qty
            w_rev_total += val
            deal_type = str(row.get("Тип_сделки", "")).strip()
            if deal_type == "Backlog":
                w_rev_backlog += val
            elif deal_type == "Pipeline":
                w_rev_pipeline += val
            elif deal_type == "GAP":
                w_rev_gap += val

        w_staff = 0
        w_cogs = 0
        for _, row in w_dr.iterrows():
            total = row.get("Q1", 0) + row.get("Q2", 0) + row.get("Q3", 0) + row.get("Q4", 0)
            article = str(row.get("Статья_затрат", "")).strip()
            if "ФОТ" in article or "Премии" in article:
                w_staff += total
            else:
                w_cogs += total
        
        w_direct = w_staff + w_cogs
        w_sga = 0
        w_gp3 = w_rev_total - w_direct
        w_ebitda = w_gp3 - w_sga

        week_dyn.append({
            "Неделя": key, 
            "Revenue": w_rev_total, 
            "Revenue_Backlog": w_rev_backlog,
            "Revenue_Pipeline": w_rev_pipeline, 
            "Revenue_Extra_GAP": w_rev_gap,
            "StaffCost": w_staff, 
            "COGS": w_cogs, 
            "Прямые расходы": w_direct,
            "SGA": w_sga, 
            "GP3": w_gp3, 
            "EBITDA": w_ebitda,
        })
    except Exception:
        continue

if week_dyn:
    dyn_df = pd.DataFrame(week_dyn).sort_values("Неделя")

    if dyn_metric == "Revenue (общая)":
        y_cols = ["Revenue"]
        title = "Revenue по неделям"
    elif dyn_metric == "Revenue (по типам)":
        y_cols = ["Revenue_Backlog", "Revenue_Pipeline", "Revenue_Extra_GAP"]
        title = "Revenue по типам (Backlog / Pipeline / Extra GAP)"
    elif dyn_metric == "Прямые расходы":
        y_cols = ["StaffCost", "COGS"]
        title = "Прямые расходы: StaffCost vs COGS"
    elif dyn_metric == "SGA":
        y_cols = ["SGA"]
        title = "SGA по неделям"
    elif dyn_metric == "GP3":
        y_cols = ["GP3"]
        title = "GP3 по неделям"
    elif dyn_metric == "EBITDA":
        y_cols = ["EBITDA"]
        title = "EBITDA по неделям"
    else:
        y_cols = ["Revenue", "Прямые расходы", "SGA", "GP3", "EBITDA"]
        title = "Все ключевые показатели по неделям"

    fig_dyn = px.line(dyn_df, x="Неделя", y=y_cols, markers=True, title=title)
    fig_dyn.update_layout(
        height=450, 
        xaxis=dict(
            tickformat="%d.%m", 
            tickmode="array", 
            tickvals=dyn_df["Неделя"], 
            ticktext=dyn_df["Неделя"]
        )
    )
    st.plotly_chart(fig_dyn, width="stretch")

    with st.expander("Показать данные по неделям"):
        display_df = dyn_df.copy()
        styler = display_df.style.apply(zebra_style, axis=None).hide(axis="index")
        st.dataframe(styler, width="stretch", height=350)