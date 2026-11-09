"""
Страница «Сделки» — реестр с фильтрами, кварталами и сравнением с Prev. BR.
"""
import streamlit as st
import pandas as pd

def style_deals(df):
    css = pd.DataFrame('', index=df.index, columns=df.columns)
    
    for i in range(1, len(df), 2):
        css.iloc[i, :] = 'background-color: #f8f9fa;'

    def parse_val(v):
        if pd.isna(v) or str(v).strip() == "—": return 0
        s = str(v).replace(" ", "").replace("+", "").replace("%", "").replace("−", "-")
        try:
            return float(s)
        except:
            return 0

    delta_cols = ["Δ Сумма сделки", "Δ Q1", "Δ Q2", "Δ Q3", "Δ Q4"]
    for col in delta_cols:
        if col in df.columns:
            for idx, val in df[col].items():
                num_val = parse_val(val)
                if num_val != 0:
                    color = '#1a7f37' if num_val > 0 else '#cf222e'
                    css.loc[idx, col] = f'color: {color}; font-weight: 600;'

    return css

def render_deals_page(deals, comparison_deals, selected_by, selected_date, fmt_num, fmt_pct):
    st.title("Сделки")
    st.caption("Фильтры по менеджеру, типу сделки и вероятности.")

    if deals is None:
        st.error("Нет данных по сделкам.")
        return

    deals = deals.copy()

    rename_map = {
        "Backlog_Pipeline": "Тип_сделки",
        "Заказчик": "Клиент",
    }
    deals = deals.rename(columns=rename_map)

    # Заглушка для менеджера
    if "Менеджер" not in deals.columns:
        deals["Менеджер"] = "—"

    if "Тип_сделки" not in deals.columns:
        deals["Тип_сделки"] = "—"

    if "Вероятность" not in deals.columns:
        deals["Вероятность"] = 0.0

    deals["Вероятность"] = pd.to_numeric(deals["Вероятность"], errors="coerce").fillna(0)
    max_prob = deals["Вероятность"].max()
    is_fraction = max_prob <= 1.0 if pd.notna(max_prob) else True

    # Невзвешенная выручка (общая сумма по всем кварталам)
    if "Невзвешенная_Q1" in deals.columns:
        nv_cols = ["Невзвешенная_Q1", "Невзвешенная_Q2", "Невзвешенная_Q3", "Невзвешенная_Q4"]
        for c in nv_cols:
            if c in deals.columns:
                deals[c] = pd.to_numeric(deals[c], errors="coerce").fillna(0)
        deals["Невзвешенная_выручка"] = deals[[c for c in nv_cols if c in deals.columns]].sum(axis=1)
    else:
        deals["Невзвешенная_выручка"] = 0.0

    # Взвешенная выручка (по кварталам + общая)
    if "Взвешенная_Q1" in deals.columns:
        w_cols = ["Взвешенная_Q1", "Взвешенная_Q2", "Взвешенная_Q3", "Взвешенная_Q4"]
        for c in w_cols:
            if c in deals.columns:
                deals[c] = pd.to_numeric(deals[c], errors="coerce").fillna(0)
        deals["Взвешенная_выручка"] = deals[[c for c in w_cols if c in deals.columns]].sum(axis=1)
    else:
        deals["Взвешенная_выручка"] = 0.0
        for q in ["Q1", "Q2", "Q3", "Q4"]:
            deals[f"Взвешенная_{q}"] = 0.0

    # Сумма сделки = Невзвешенная выручка
    deals["Сумма_сделки"] = deals["Невзвешенная_выручка"]

    ctx = (selected_by, selected_date)
    if st.session_state.get("_deals_ctx") != ctx:
        for k in ["deals_manager", "deals_type", "deals_prob_single", "deals_page"]:
            st.session_state.pop(k, None)
        st.session_state["_deals_ctx"] = ctx
        st.session_state["deals_page"] = 1

    st.subheader("Фильтры")

    def reset_filters():
        st.session_state["deals_manager"] = "Все"
        st.session_state["deals_type"] = "Все"
        st.session_state["deals_prob_single"] = "Все"
        st.session_state["deals_page"] = 1

    # Фильтры: Менеджер, Тип сделки, Вероятность (без Статуса)
    col1, col2, col3 = st.columns(3)

    with col1:
        managers = ["Все"] + sorted(deals["Менеджер"].dropna().astype(str).unique().tolist())
        st.selectbox("Менеджер", managers, key="deals_manager")

    with col2:
        valid_types = ["Backlog", "Pipeline", "GAP"]
        deals["Тип_сделки"] = deals["Тип_сделки"].astype(str).str.strip().str.title()
        found_types = [t for t in valid_types if t in deals["Тип_сделки"].unique()]
        types = ["Все"] + found_types
        st.selectbox("Тип сделки", types, key="deals_type")

    with col3:
        prob_options = ["Все", 1, 25, 40, 60, 80, 100]
        st.selectbox("Вероятность сделки", prob_options, key="deals_prob_single")

    st.button("Сбросить фильтры", on_click=reset_filters)

    sel_manager = st.session_state.get("deals_manager", "Все")
    sel_type = st.session_state.get("deals_type", "Все")
    sel_prob = st.session_state.get("deals_prob_single", "Все")

    filtered = deals.copy()

    if sel_manager != "Все":
        filtered = filtered[filtered["Менеджер"].astype(str) == sel_manager]

    if sel_type != "Все":
        filtered = filtered[filtered["Тип_сделки"] == sel_type]

    prob_col = filtered["Вероятность"] * 100 if is_fraction else filtered["Вероятность"]
    if sel_prob != "Все":
        filtered = filtered[prob_col.round(0) == sel_prob]
    else:
        filtered = filtered[prob_col.round(0) > 0]

    # Сравнение с предыдущим BR
    if comparison_deals is not None and not comparison_deals.empty:
        comp = comparison_deals.copy()
        if "Backlog_Pipeline" in comp.columns:
            comp = comp.rename(columns={"Backlog_Pipeline": "Тип_сделки"})
        if "Заказчик" in comp.columns:
            comp = comp.rename(columns={"Заказчик": "Клиент"})
            
        if "Невзвешенная_Q1" in comp.columns:
            cnv = ["Невзвешенная_Q1", "Невзвешенная_Q2", "Невзвешенная_Q3", "Невзвешенная_Q4"]
            for c in cnv:
                if c in comp.columns:
                    comp[c] = pd.to_numeric(comp[c], errors="coerce").fillna(0)
            comp["Сумма_сделки_prev"] = comp[[c for c in cnv if c in comp.columns]].sum(axis=1)
        else:
            comp["Сумма_сделки_prev"] = 0.0

        if "Взвешенная_Q1" in comp.columns:
            cw = ["Взвешенная_Q1", "Взвешенная_Q2", "Взвешенная_Q3", "Взвешенная_Q4"]
            for c in cw:
                if c in comp.columns:
                    comp[c] = pd.to_numeric(comp[c], errors="coerce").fillna(0)
        else:
            for c in ["Взвешенная_Q1", "Взвешенная_Q2", "Взвешенная_Q3", "Взвешенная_Q4"]:
                comp[c] = 0.0

        # Переименовываем кварталы предыдущего BR
        for q in ["Q1", "Q2", "Q3", "Q4"]:
            col = f"Взвешенная_{q}"
            if col in comp.columns:
                comp = comp.rename(columns={col: f"{col}_prev"})

        if "Название" in comp.columns and "Название" in filtered.columns:
            keep_cols = ["Название", "Сумма_сделки_prev"] + \
                        [f"Взвешенная_{q}_prev" for q in ["Q1", "Q2", "Q3", "Q4"] if f"Взвешенная_{q}_prev" in comp.columns]
            cmp_df = comp[keep_cols].copy()
            filtered = filtered.merge(cmp_df, on="Название", how="left")
        else:
            filtered["Сумма_сделки_prev"] = 0.0
            for q in ["Q1", "Q2", "Q3", "Q4"]:
                filtered[f"Взвешенная_{q}_prev"] = 0.0
    else:
        filtered["Сумма_сделки_prev"] = 0.0
        for q in ["Q1", "Q2", "Q3", "Q4"]:
            filtered[f"Взвешенная_{q}_prev"] = 0.0

    # Считаем дельты
    filtered["Δ Сумма сделки"] = filtered["Сумма_сделки"] - filtered["Сумма_сделки_prev"].fillna(0)
    for q in ["Q1", "Q2", "Q3", "Q4"]:
        col_cur = f"Взвешенная_{q}"
        col_prev = f"Взвешенная_{q}_prev"
        if col_cur in filtered.columns:
            filtered[f"Δ {q}"] = filtered[col_cur] - filtered[col_prev].fillna(0)

    st.markdown("---")
    st.subheader("Реестр сделок")

    page_size = 12
    total_rows = len(filtered)
    total_pages = max(1, (total_rows + page_size - 1) // page_size)

    if "deals_page" not in st.session_state:
        st.session_state["deals_page"] = 1

    page = st.session_state["deals_page"]
    page = min(max(1, page), total_pages)

    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total_rows)

    col_pag1, col_pag2, col_pag3 = st.columns([3, 1, 1])
    with col_pag1:
        if total_rows > 0:
            st.caption(f"Показано {start_idx + 1}–{end_idx} из {total_rows} · итого по всей выборке")
        else:
            st.caption("Показано 0 из 0")
    with col_pag2:
        if st.button("← Назад", disabled=(page == 1), width="stretch"):
            st.session_state["deals_page"] = page - 1
            st.rerun()
    with col_pag3:
        if st.button("Вперёд →", disabled=(page == total_pages), width="stretch"):
            st.session_state["deals_page"] = page + 1
            st.rerun()

    page_deals = filtered.iloc[start_idx:end_idx].copy()

    if len(page_deals) > 0:
        display = page_deals.copy()

        if is_fraction:
            display["Вероятность"] = (display["Вероятность"] * 100).round(0)
        else:
            display["Вероятность"] = display["Вероятность"].round(0)
        display["Вероятность"] = display["Вероятность"].fillna(0).astype(int)

        # Порядок колонок
        cols = [
            "Название", "Клиент", "Менеджер", "Тип_сделки",
            "Невзвешенная_выручка", "Вероятность", "Взвешенная_выручка",
            "Взвешенная_Q1", "Δ Q1",
            "Взвешенная_Q2", "Δ Q2",
            "Взвешенная_Q3", "Δ Q3",
            "Взвешенная_Q4", "Δ Q4",
            "Δ Сумма сделки",
        ]
        cols_present = [c for c in cols if c in display.columns]

        numeric_cols = [c for c in display.columns if c.startswith("Взвешенная") or c.startswith("Δ") or c in ["Невзвешенная_выручка"]]
        for c in numeric_cols:
            if c in display.columns:
                display[c] = pd.to_numeric(display[c], errors="coerce").fillna(0)
                display[c] = display[c].apply(lambda v: fmt_num(v, 0))

        df_display = display[cols_present]
        styler = df_display.style.apply(style_deals, axis=None).hide(axis="index")

        st.dataframe(
            styler,
            width="stretch",
            height=400,
            column_config={
                "Вероятность": st.column_config.NumberColumn("Вероятность, %", format="%d%%"),
            },
        )
    else:
        st.info("Нет сделок с выбранными фильтрами")

    st.markdown("---")
    st.subheader("Итого по выборке")

    total_sum = filtered["Сумма_сделки"].sum() if "Сумма_сделки" in filtered.columns else 0
    total_weighted = filtered["Взвешенная_выручка"].sum() if "Взвешенная_выручка" in filtered.columns else 0
    avg_weighted_prob = (total_weighted / total_sum * 100) if total_sum > 0 else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Сумма сделок", f"{fmt_num(total_sum, 0)} тыс. руб.")
    c2.metric("Взвешенная выручка", f"{fmt_num(total_weighted, 0)} тыс. руб.")
    c3.metric("Средневзвешенная вероятность", f"{avg_weighted_prob:.1f}%")

    st.markdown("---")

    def _go_to_pl():
        st.session_state["page_nav"] = "P&L"

    st.button("← Вернуться в P&L", width="content", on_click=_go_to_pl)