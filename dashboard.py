import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
import subprocess
import sys
import glob
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
        return datetime.strptime(ts, "%Y-%m-%d_%H%M")
    except ValueError:
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

# --- КНОПКА ОБНОВЛЕНИЯ ---
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

all_snapshots = []
for f in snapshot_files:
    ts = Path(f).stem
    dt = parse_timestamp(ts)
    if dt != datetime.min:
        all_snapshots.append({"timestamp": ts, "datetime": dt, "path": f})
all_snapshots.sort(key=lambda x: x["datetime"], reverse=True)

weeks = {}
for s in all_snapshots:
    week_key = s["datetime"].strftime("%Y-W%W")
    if week_key not in weeks:
        weeks[week_key] = {"label": get_week_label(s["datetime"]), "snapshots": []}
    weeks[week_key]["snapshots"].append(s)
week_keys = sorted(weeks.keys(), reverse=True)

@st.cache_data
def load_snapshot(path):
    return {
        "deals": pd.read_excel(path, sheet_name="Сделки"),
        "revenue": pd.read_excel(path, sheet_name="Выручка"),
        "direct": pd.read_excel(path, sheet_name="Прямые расходы"),
        "sga": pd.read_excel(path, sheet_name="SGA"),
    }

def agg(df, cols):
    return {c: df[c].sum() if c in df.columns else 0 for c in cols}

def build_options(snapshots, is_comp=False):
    options = []
    date_counts = {}
    for s in snapshots:
        d_str = parse_timestamp(s["timestamp"]).strftime('%d.%m.%Y')
        date_counts[d_str] = date_counts.get(d_str, 0) + 1
        
    date_seen = {}
    for s in snapshots:
        dt = parse_timestamp(s["timestamp"])
        d_str = dt.strftime('%d.%m.%Y')
        status_label = get_status_label(s["timestamp"])
        
        if date_counts[d_str] > 1:
            date_seen[d_str] = date_seen.get(d_str, 0) + 1
            label = f"{d_str} ({date_seen[d_str]}) — {status_label}"
        else:
            label = f"{d_str} — {status_label}"
            
        opt = {"label": label, "timestamp": s["timestamp"], "path": s["path"]}
        if not is_comp:
            opt["datetime"] = s["datetime"]
        options.append(opt)
    return options

st.sidebar.markdown("---")

st.sidebar.header("Период (→ PREV-BR)")
week_labels = [weeks[k]["label"] for k in week_keys]
selected_week_label = st.sidebar.selectbox("Неделя", week_labels, index=0, label_visibility="collapsed")
selected_week_key = week_keys[week_labels.index(selected_week_label)]

week_snapshots = weeks[selected_week_key]["snapshots"]
week_snapshots.sort(key=lambda x: x["datetime"], reverse=True)

snapshot_options = build_options(week_snapshots)

def _pick_default_snapshot(snaps):
    pre = [s for s in snaps if get_status(s["timestamp"]) == PRE_BR]
    if pre: return pre[0]
    drafts = [s for s in snaps if get_status(s["timestamp"]) == DRAFT]
    if drafts: return drafts[0]
    return snaps[0]

default_snap = _pick_default_snapshot(week_snapshots)
default_index = next((i for i, opt in enumerate(snapshot_options) if opt["timestamp"] == default_snap["timestamp"]), 0)

selected_snapshot_label = st.sidebar.selectbox("Отчет", [opt["label"] for opt in snapshot_options], index=default_index, label_visibility="collapsed")
selected_snapshot = next(opt for opt in snapshot_options if opt["label"] == selected_snapshot_label)
selected_date = selected_snapshot["timestamp"]

st.sidebar.markdown("---")

st.sidebar.header("Статус версии")
current_status = get_status(selected_date)
current_label = get_status_label(selected_date)

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
        set_status(selected_date, PRE_BR)
        st.rerun()

btn_br_disabled = (current_status != PRE_BR)
with col_s2:
    if st.button("BR", width="stretch", disabled=btn_br_disabled):
        try:
            for s in week_snapshots:
                if s["timestamp"] != selected_date and get_status(s["timestamp"]) == BR:
                    set_status(s["timestamp"], PRE_BR)
            prev_date = get_last_br_before(selected_date)
            if prev_date and prev_date != selected_date:
                set_status(prev_date, PRE_BR)
        except Exception:
            pass
        set_status(selected_date, BR)
        st.rerun()

btn_draft_disabled = (current_status != PRE_BR)
if current_status != BR:
    if st.sidebar.button("Снять статус (Черновик)", width="stretch", disabled=btn_draft_disabled):
        set_status(selected_date, DRAFT)
        st.rerun()

st.sidebar.markdown("---")

prev_br_date = get_last_br_before(selected_date)
comparison_snapshot = None
comparison_deals = None

if prev_br_date:
    for s in all_snapshots:
        if s["timestamp"] == prev_br_date:
            comparison_snapshot = {"timestamp": s["timestamp"], "path": s["path"]}
            try:
                comp_data = load_snapshot(comparison_snapshot["path"])
                comparison_deals = comp_data["deals"]
            except Exception as e:
                st.sidebar.warning(f"Ошибка загрузки сделок для сравнения: {e}")
            break

st.sidebar.markdown("**Актуальный прогноз**")
if comparison_snapshot:
    comp_dt = parse_timestamp(comparison_snapshot["timestamp"]).strftime('%d.%m.%Y')
    st.sidebar.caption(f"Сравнение с BR от {comp_dt}")
else:
    st.sidebar.caption("Нет предыдущего BR для сравнения")

st.sidebar.markdown("---")

st.sidebar.header("Фильтры")
try:
    data = load_snapshot(selected_snapshot["path"])
except Exception as e:
    st.error(f"Ошибка чтения: {e}")
    st.stop()

deals = data["deals"]
revenue = data["revenue"]
direct = data["direct"]
sga = data["sga"]

by_list = ["Все"] + sorted(revenue["БЮ"].unique().tolist())
selected_by = st.sidebar.selectbox("Бизнес-юнит (БЮ)", by_list)

if selected_by != "Все":
    rev = revenue[revenue["БЮ"] == selected_by]
    dr = direct[direct["БЮ"] == selected_by]
    deals_filtered = deals[deals["БЮ"] == selected_by]
    
    if comparison_deals is not None:
        comparison_deals = comparison_deals[comparison_deals["БЮ"] == selected_by]
else:
    rev = revenue
    dr = direct
    deals_filtered = deals
sg = sga

st.sidebar.markdown("---")

st.sidebar.header("Навигация")
page = st.sidebar.radio("Страница", ["P&L", "Сделки"], key="page_nav", label_visibility="collapsed")

if page == "Сделки":
    from page_deals import render_deals_page
    render_deals_page(
        deals=deals_filtered,
        comparison_deals=comparison_deals,
        selected_by=selected_by,
        selected_date=selected_date,
        fmt_num=fmt_num,
        fmt_pct=fmt_pct,
    )
    st.stop()

# ============================================================
# СТРАНИЦА: P&L
# ============================================================
rev_totals = agg(rev, ["Выручка_бюджет", "Выручка_prev", "Выручка_факт", "Выручка_прогноз",
                       "Выручка_Backlog", "Выручка_Pipeline", "Выручка_Extra_GAP"])
dr_totals = agg(dr, ["StaffCost_бюджет", "StaffCost_prev", "StaffCost_факт", "StaffCost_прогноз",
                     "COGS_бюджет", "COGS_prev", "COGS_факт", "COGS_прогноз"])
sga_totals = agg(sg, ["SGA_бюджет", "SGA_prev", "SGA_факт", "SGA_прогноз"])

if comparison_snapshot:
    try:
        comp_data = load_snapshot(comparison_snapshot["path"])
        c_rev = comp_data["revenue"]
        c_dr = comp_data["direct"]
        c_sga = comp_data["sga"]
        if selected_by != "Все":
            c_rev = c_rev[c_rev["БЮ"] == selected_by]
            c_dr = c_dr[c_dr["БЮ"] == selected_by]
            
        c_rev_totals = agg(c_rev, ["Выручка_прогноз", "Выручка_Backlog", "Выручка_Pipeline", "Выручка_Extra_GAP"])
        c_dr_totals = agg(c_dr, ["StaffCost_прогноз", "COGS_прогноз"])
        c_sga_totals = agg(c_sga, ["SGA_прогноз"])
        
        comp_rev_total = c_rev_totals["Выручка_прогноз"]
        comp_rev_backlog = c_rev_totals["Выручка_Backlog"]
        comp_rev_pipeline = c_rev_totals["Выручка_Pipeline"]
        comp_rev_gap = c_rev_totals["Выручка_Extra_GAP"]
        
        comp_staff = c_dr_totals["StaffCost_прогноз"]
        comp_cogs = c_dr_totals["COGS_прогноз"]
        comp_dr_total = comp_staff + comp_cogs
        
        comp_sga_total = c_sga_totals["SGA_прогноз"]
        
        comp_gp3 = comp_rev_total - comp_dr_total
        comp_ebitda = comp_gp3 - comp_sga_total
        
        comp_total_all = comp_rev_total + comp_dr_total + comp_sga_total
        
    except Exception as e:
        st.warning(f"Не удалось загрузить данные для сравнения: {e}")
        comparison_snapshot = None

def sum_direct(prefix):
    return dr_totals[f"StaffCost_{prefix}"] + dr_totals[f"COGS_{prefix}"]

def gp3(prefix):
    return rev_totals[f"Выручка_{prefix}"] - sum_direct(prefix)

def ebitda(prefix):
    return gp3(prefix) - sga_totals[f"SGA_{prefix}"]

def gm_pct(prefix):
    rev_val = rev_totals[f"Выручка_{prefix}"]
    return (gp3(prefix) / rev_val * 100) if rev_val else 0

st.title("Управленческая отчётность")
dt_str = parse_timestamp(selected_date).strftime("%d.%m.%Y %H:%M")
st.caption(f"Отчёт от {dt_str} | БЮ: {selected_by} | Единицы: тыс. руб.")
st.markdown("---")

st.subheader("P&L по статьям")

if comparison_snapshot:
    comp_dt = parse_timestamp(comparison_snapshot["timestamp"]).strftime('%d.%m.%Y')
    st.caption(f"**Режим сравнения:** показатели колонки `Прогноз` сравниваются с отчетом от **{comp_dt}**. Разница отображена в колонке `Δ Prev. BR`.")
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

if comparison_snapshot:
    r_backlog_p = comp_rev_backlog
    r_pipeline_p = comp_rev_pipeline
    r_gap_p = comp_rev_gap
    r_total_p = comp_rev_total
    d_total_p = comp_dr_total
    d_staff_p = comp_staff
    d_cogs_p = comp_cogs
    gp3_p = comp_gp3
    sga_p = comp_sga_total
    ebitda_p = comp_ebitda
else:
    r_backlog_p = rev_totals["Выручка_prev"] * ratio_backlog
    r_pipeline_p = rev_totals["Выручка_prev"] * ratio_pipeline
    r_gap_p = rev_totals["Выручка_prev"] * ratio_gap
    r_total_p = rev_totals["Выручка_prev"]
    d_total_p = sum_direct("prev")
    d_staff_p = dr_totals["StaffCost_prev"]
    d_cogs_p = dr_totals["COGS_prev"]
    gp3_p = gp3("prev")
    sga_p = sga_totals["SGA_prev"]
    ebitda_p = ebitda("prev")

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
    make_row("Прямые расходы", sum_direct("бюджет"), d_total_p,
             sum_direct("факт"), sum_direct("прогноз")),
    make_row("StaffCost", dr_totals["StaffCost_бюджет"], d_staff_p,
             dr_totals["StaffCost_факт"], dr_totals["StaffCost_прогноз"], indent=True),
    make_row("COGS", dr_totals["COGS_бюджет"], d_cogs_p,
             dr_totals["COGS_факт"], dr_totals["COGS_прогноз"], indent=True),
    make_row("GP3", gp3("бюджет"), gp3_p, gp3("факт"), gp3("прогноз")),
    make_row("GM%", gm_pct('бюджет'), gm_pct('prev'), gm_pct('факт'), gm_pct('прогноз')),
    make_row("SGA", sga_totals["SGA_бюджет"], sga_p,
             sga_totals["SGA_факт"], sga_totals["SGA_прогноз"]),
    make_row("EBITDA", ebitda("бюджет"), ebitda_p, ebitda("факт"), ebitda("прогноз")),
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

total_budget = rev_totals["Выручка_бюджет"] + sum_direct("бюджет") + sga_totals["SGA_бюджет"]
total_prev = rev_totals["Выручка_prev"] + sum_direct("prev") + sga_totals["SGA_prev"]
total_fact = rev_totals["Выручка_факт"] + sum_direct("факт") + sga_totals["SGA_факт"]
total_pr_val = rev_totals["Выручка_прогноз"] + sum_direct("прогноз") + sga_totals["SGA_прогноз"]

total_row = {
    "Показатель": "ИТОГО (ключевые)",
    "Бюджет": total_budget,
    "Prev. BR": comp_total_all if comparison_snapshot else total_prev,
    "Q1": total_pr_val / 4,
    "Q2": total_pr_val / 4,
    "Q3": total_pr_val / 4,
    "Q4": total_pr_val / 4,
    "Факт YTD": total_fact,
    "Прогноз": total_pr_val,
    "Δ бюджет": total_pr_val - total_budget,
    "Δ бюджет, %": round(((total_pr_val - total_budget) / total_budget * 100) if total_budget else 0, 1),
    "Δ Prev. BR": total_pr_val - (comp_total_all if comparison_snapshot else total_prev),
    "Δ Prev. BR, %": round(((total_pr_val - (comp_total_all if comparison_snapshot else total_prev)) / (comp_total_all if comparison_snapshot else total_prev) * 100) if (comp_total_all if comparison_snapshot else total_prev) else 0, 1),
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
gb.configure_column("Показатель", width=220, pinned="left", cellStyle={"textAlign": "left"})

num_style = {"textAlign": "right", "fontFamily": "monospace"}
gb.configure_column("Бюджет", width=90, cellStyle=num_style)
gb.configure_column("Prev. BR", width=90, cellStyle={**num_style, "backgroundColor": "#f4f6f8"})
gb.configure_column("Q1", width=70, cellStyle=num_style)
gb.configure_column("Q2", width=70, cellStyle=num_style)
gb.configure_column("Q3", width=70, cellStyle=num_style)
gb.configure_column("Q4", width=70, cellStyle=num_style)
gb.configure_column("Факт YTD", width=90, cellStyle=num_style)
gb.configure_column("Прогноз", width=90, cellStyle=num_style)

for col in ["Δ бюджет", "Δ бюджет, %", "Δ Prev. BR", "Δ Prev. BR, %"]:
    gb.configure_column(col, width=100, cellStyle=_STYLE_JS)

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
    rev.to_excel(writer, sheet_name="Выручка", index=False)
    dr.to_excel(writer, sheet_name="Прямые", index=False)
    sg.to_excel(writer, sheet_name="SGA", index=False)
    deals_filtered.to_excel(writer, sheet_name="Сделки", index=False)

buffer_pdf = io.BytesIO()
pdf_generated = False

try:
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.add_font("DejaVu", fname=str(FONT_REGULAR))
    pdf.add_font("DejaVu", style="B", fname=str(FONT_BOLD))
    font_name = "DejaVu"
    pdf.set_font(font_name, style="B", size=14)
    pdf.cell(0, 10, "Управленческая отчётность", ln=True, align="C")
    pdf.set_font(font_name, size=10)
    pdf.cell(0, 10, f"Отчёт от {dt_str} | БЮ: {selected_by}", ln=True, align="C")
    pdf.ln(5)
    col_widths = [45, 20, 20, 15, 15, 15, 15, 20, 20, 23, 23, 23]
    headers = ["Показатель", "Бюджет", "Prev. BR", "Q1", "Q2", "Q3", "Q4", "Факт YTD", "Прогноз", "Δ Бюджет", "Δ Prev", "Δ Prev %"]
    pdf.set_font(font_name, style="B", size=7)
    pdf.set_fill_color(230, 230, 230)
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 8, h, border=1, align="C", fill=True)
    pdf.ln()
    pdf.set_font(font_name, size=7)
    for _, row in display_table.iterrows():
        name = str(row["Показатель"])[:30]
        pdf.cell(col_widths[0], 6, name, border=1)
        vals = [
            str(row["Бюджет"]), str(row["Prev. BR"]),
            str(row["Q1"]), str(row["Q2"]), str(row["Q3"]), str(row["Q4"]),
            str(row["Факт YTD"]), str(row["Прогноз"]),
            str(row["Δ бюджет"]), str(row["Δ Prev. BR"]), str(row["Δ Prev. BR, %"])
        ]
        for w, v in zip(col_widths[1:], vals):
            pdf.cell(w, 6, v[:12], border=1, align="R")
        pdf.ln()
    pdf.output(buffer_pdf)
    pdf_generated = True
except Exception as e:
    st.toast(f"Не удалось сгенерировать PDF: {e}", icon="⚠️")

col_dl1, col_dl2 = st.columns(2)
with col_dl1:
    st.download_button("Скачать отчёт в Excel", data=buffer_excel.getvalue(), file_name=f"report_{selected_date}.xlsx", width="stretch")
with col_dl2:
    if pdf_generated:
        st.download_button("Скачать отчёт в PDF", data=buffer_pdf.getvalue(), file_name=f"report_{selected_date}.pdf", width="stretch", mime="application/pdf")
    else:
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

for s in all_snapshots:
    week_key = s["datetime"].strftime("%Y-W%W")
    if week_key in seen_weeks:
        continue
    seen_weeks.add(week_key)
    
    try:
        w_data = load_snapshot(s["path"])
        w_rev_df = w_data["revenue"]
        if selected_by != "Все":
            w_rev_df = w_rev_df[w_rev_df["БЮ"] == selected_by]
        w_rev_b = w_rev_df["Выручка_бюджет"].sum()
        w_rev_pr = w_rev_df["Выручка_прогноз"].sum()
        
        w_dr_df = w_data["direct"]
        if selected_by != "Все":
            w_dr_df = w_dr_df[w_dr_df["БЮ"] == selected_by]
        w_staff_b = w_dr_df["StaffCost_бюджет"].sum()
        w_staff_pr = w_dr_df["StaffCost_прогноз"].sum()
        w_cogs_b = w_dr_df["COGS_бюджет"].sum()
        w_cogs_pr = w_dr_df["COGS_прогноз"].sum()
        
        w_sga_df = w_data["sga"]
        w_sga_b = w_sga_df["SGA_бюджет"].sum()
        w_sga_pr = w_sga_df["SGA_прогноз"].sum()

        w_gp3_b = w_rev_b - (w_staff_b + w_cogs_b)
        w_gp3_pr = w_rev_pr - (w_staff_pr + w_cogs_pr)
        w_ebitda_b = w_gp3_b - w_sga_b
        w_ebitda_pr = w_gp3_pr - w_sga_pr

        monday = s["datetime"] - pd.Timedelta(days=s["datetime"].weekday())
        all_weeks_data.append({
            "Неделя": monday,
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
            ticktext=[d.strftime("%d.%m") for d in trend_df["Неделя"]]
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

for s in all_snapshots:
    week_key = s["datetime"].strftime("%Y-W%W")
    if week_key in seen_weeks_dyn:
        continue
    seen_weeks_dyn.add(week_key)
    
    try:
        w_data = load_snapshot(s["path"])
        w_rev, w_dr, w_sg = w_data["revenue"], w_data["direct"], w_data["sga"]
        if selected_by != "Все":
            w_rev = w_rev[w_rev["БЮ"] == selected_by]
            w_dr = w_dr[w_dr["БЮ"] == selected_by]

        w_rev_total = w_rev["Выручка_факт"].sum()
        w_rev_backlog = w_rev["Выручка_Backlog"].sum() if "Выручка_Backlog" in w_rev.columns else 0
        w_rev_pipeline = w_rev["Выручка_Pipeline"].sum() if "Выручка_Pipeline" in w_rev.columns else 0
        w_rev_gap = w_rev["Выручка_Extra_GAP"].sum() if "Выручка_Extra_GAP" in w_rev.columns else 0

        w_staff, w_cogs = w_dr["StaffCost_факт"].sum(), w_dr["COGS_факт"].sum()
        w_direct = w_staff + w_cogs
        w_sga = w_sg["SGA_факт"].sum()
        w_gp3 = w_rev_total - w_direct
        w_ebitda = w_gp3 - w_sga

        monday = s["datetime"] - pd.Timedelta(days=s["datetime"].weekday())
        week_dyn.append({
            "Неделя": monday, 
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
            ticktext=[d.strftime("%d.%m") for d in dyn_df["Неделя"]]
        )
    )
    st.plotly_chart(fig_dyn, width="stretch")

    with st.expander("Показать данные по неделям"):
        display_df = dyn_df.copy()
        display_df["Неделя"] = display_df["Неделя"].dt.strftime("%d.%m.%Y")
        styler = display_df.style.apply(zebra_style, axis=None).hide(axis="index")
        st.dataframe(styler, width="stretch", height=350)