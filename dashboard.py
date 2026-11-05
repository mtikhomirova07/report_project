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

# --- ЧТЕНИЕ EXCEL С ЖЕСТКИМИ КОЛОНКАМИ ---
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
        # ИСПРАВЛЕНО: вернули ссылку на место (4-я колонка), Менеджера нет в файле
        expected_cols = [
            "SBU", "Заказчик", "Название", "Ссылка", "Признак_XT", 
            "Вероятность", "Backlog_Pipeline", 
            "Невзвешенная_Q1", "Невзвешенная_Q2", "Невзвешенная_Q3", "Невзвешенная_Q4",
            "COGS_Q1", "COGS_Q2", "COGS_Q3", "COGS_Q4",
            "Взвешенная_Q1", "Взвешенная_Q2", "Взвешенная_Q3", "Взвешенная_Q4",
            "Взвешенные_COGS_Q1", "Взвешенные_COGS_Q2", "Взвешенные_COGS_Q3", "Взвешенные_COGS_Q4",
            "Rev2027", "Cogs2027", "H2_GM1", "Проект", "ОПП", "GM3",
            "Статус"
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

types = split_by_type(rev)
rev_backlog = get_rev(types["Backlog"])
rev_pipeline = get_rev(types["Pipeline"])
rev_gap = get_rev(types["GAP"])

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

def make_row(name, prev, pr, indent=False):
    return {
        "Показатель": ("    — " + name) if indent else name,
        "Prev. BR": prev,
        "Q1": pr / 4, "Q2": pr / 4, "Q3": pr / 4, "Q4": pr / 4,
        "Прогноз": pr,
    }

rows = [
    make_row("Revenue", p_rev, rev_total),
    make_row("Backlog", p_backlog, rev_backlog, indent=True),
    make_row("Pipeline", p_pipeline, rev_pipeline, indent=True),
    make_row("Extra GAP", p_gap, rev_gap, indent=True),
    make_row("Прямые расходы", p_direct, direct_total),
    make_row("StaffCost", p_staff, staff_total, indent=True),
    make_row("COGS", p_cogs, cogs_total, indent=True),
    make_row("GP3", p_gp3, gp3_total),
    make_row("GM%", p_gm, gm_pct_total),
    make_row("SGA", p_sga, sga_total),
    make_row("EBITDA", p_ebitda, ebitda_total),
]

table_data = []
for r in rows:
    name, p, pr = r["Показатель"], r["Prev. BR"], r["Прогноз"]
    if name == "GM%":
        d_abs, d_pct = pr - p, pr - p
    else:
        d_abs = pr - p
        d_pct = (d_abs / p * 100) if p else 0.0
    table_data.append({
        "Показатель": name, "Бюджет": None, "Prev. BR": p,
        "Q1": pr/4, "Q2": pr/4, "Q3": pr/4, "Q4": pr/4,
        "Факт YTD": None, "Прогноз": pr,
        "Δ бюджет": None, "Δ бюджет, %": None,
        "Δ Prev. BR": d_abs, "Δ Prev. BR, %": round(d_pct, 1),
    })

total_pr = rev_total + direct_total + sga_total
total_prev = (p_rev + p_direct + p_sga) if comparison else None
table_data.append({
    "Показатель": "ИТОГО (ключевые)", "Бюджет": None, "Prev. BR": total_prev,
    "Q1": total_pr/4, "Q2": total_pr/4, "Q3": total_pr/4, "Q4": total_pr/4,
    "Факт YTD": None, "Прогноз": total_pr,
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
            if name == "GM%":
                mrows.append({"Показатель": name,
                              months[0]: fmt_pct(q_val,1), months[1]: fmt_pct(q_val,1),
                              months[2]: fmt_pct(q_val,1), f"Итого {q_label}": fmt_pct(q_val,1)})
            else:
                mrows.append({"Показатель": name,
                              months[0]: fmt_num(mv,0), months[1]: fmt_num(mv,0),
                              months[2]: fmt_num(mv,0), f"Итого {q_label}": fmt_num(q_val,0)})
        st.dataframe(pd.DataFrame(mrows).style.apply(zebra_style, axis=None).hide(axis="index"),
                     width="stretch", height=350)

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