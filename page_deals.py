"""
Страница «Сделки» — реестр с фильтрами и пагинацией.
"""
import streamlit as st
import pandas as pd

def style_deals(df):
    css = pd.DataFrame('', index=df.index, columns=df.columns)
    
    # Зебра
    for i in range(1, len(df), 2):
        css.iloc[i, :] = 'background-color: #f8f9fa;'

    def parse_val(v):
        if pd.isna(v) or str(v).strip() == "—": return 0
        s = str(v).replace(" ", "").replace("+", "").replace("%", "").replace("−", "-")
        try:
            return float(s)
        except:
            return 0

    if 'Δ Сумма сделки' in df.columns:
        for idx, val in df['Δ Сумма сделки'].items():
            num_val = parse_val(val)
            if num_val != 0:
                color = '#1a7f37' if num_val > 0 else '#cf222e'
                css.loc[idx, 'Δ Сумма сделки'] = f'color: {color}; font-weight: 600;'

    if 'Δ Вероятность' in df.columns:
        for idx, val in df['Δ Вероятность'].items():
            num_val = parse_val(val)
            if num_val != 0:
                color = '#1a7f37' if num_val > 0 else '#cf222e'
                css.loc[idx, 'Δ Вероятность'] = f'color: {color}; font-weight: 600;'

    return css

def render_deals_page(deals, comparison_deals, selected_by, selected_date, fmt_num, fmt_pct):
    st.title("Сделки")
    st.caption("Фильтр по статусу — выберите нужный в фильтрах ниже.")

    if deals is None:
        st.error("Нет данных по сделкам.")
        return

    deals = deals.copy()

    # Переименовываем колонки, если они называются иначе (из-за вырезанных стилей)
    rename_map = {
        "Менеджер проекта": "Менеджер",
        "Вероятность сделки": "Вероятность",
        "Тип предложения": "Тип_сделки",
        "Backlog_Pipeline": "Тип_сделки",
        "Заказчик": "Клиент",
    }
    deals = deals.rename(columns=rename_map)

    # Безопасное создание обязательных колонок
    required_cols = ["Менеджер", "Тип_сделки", "Статус", "Вероятность"]
    for col in required_cols:
        if col not in deals.columns:
            deals[col] = "—"

    if "Статус" not in deals.columns:
        deals["Статус"] = "В работе"

    if "Вероятность" not in deals.columns:
        deals["Вероятность"] = 0.0

    # --- FIX: Безопасный подсчет суммы сделки ---
    q_cols = [c for c in ["Q1", "Q2", "Q3", "Q4"] if c in deals.columns]
    if q_cols:
        for c in q_cols:
            deals[c] = pd.to_numeric(deals[c].astype(str).str.replace(" ", "").str.replace(",", "."), errors="coerce").fillna(0)
        deals["Сумма_сделки"] = deals[q_cols].sum(axis=1)
    else:
        deals["Сумма_сделки"] = 0

    ctx = (selected_by, selected_date)
    if st.session_state.get("_deals_ctx") != ctx:
        for k in ["deals_manager", "deals_type", "deals_status", "deals_probs", "deals_by"]:
            st.session_state.pop(k, None)
        st.session_state["_deals_ctx"] = ctx
        st.session_state["deals_page"] = 1

    st.subheader("Фильтры")

    def reset_filters():
        st.session_state["deals_manager"] = "Все"
        st.session_state["deals_type"] = "Все"
        st.session_state["deals_status"] = "Все"
        st.session_state["deals_probs"] = []
        st.session_state["deals_page"] = 1

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        managers = ["Все"] + sorted(deals["Менеджер"].dropna().unique().tolist())
        st.selectbox("Менеджер", managers, key="deals_manager")

    with col2:
        types = ["Все"] + sorted(deals["Тип_сделки"].dropna().unique().tolist())
        st.selectbox("Тип сделки", types, key="deals_type")

    with col3:
        statuses = ["Все"] + sorted(deals["Статус"].dropna().unique().tolist())
        st.selectbox("Статус", statuses, key="deals_status")
        
    with col4:
        prob_options = [1, 25, 40, 60, 80, 100]
        st.multiselect(
            "Вероятность сделки", 
            options=prob_options, 
            key="deals_probs", 
            placeholder="Все вероятности",
        )

    st.button("Сбросить фильтры", on_click=reset_filters)

    sel_manager = st.session_state.get("deals_manager", "Все")
    sel_type = st.session_state.get("deals_type", "Все")
    sel_status = st.session_state.get("deals_status", "Все")
    sel_probs = st.session_state.get("deals_probs", [])

    filtered_deals = deals.copy()

    # Приводим вероятность к числам
    filtered_deals['Вероятность'] = pd.to_numeric(filtered_deals['Вероятность'], errors='coerce').fillna(0)
    
    # Если вероятности пришли как 0.3, 0.5 — переводим в 30, 50
    max_prob = filtered_deals["Вероятность"].max()
    is_fraction = max_prob <= 1.0 if pd.notna(max_prob) else True

    if sel_manager != "Все":
        filtered_deals = filtered_deals[filtered_deals["Менеджер"] == sel_manager]

    if sel_type != "Все":
        filtered_deals = filtered_deals[filtered_deals["Тип_сделки"] == sel_type]

    if sel_status != "Все":
        filtered_deals = filtered_deals[filtered_deals["Статус"] == sel_status]

    if sel_probs:
        prob_col = filtered_deals["Вероятность"] * 100 if is_fraction else filtered_deals["Вероятность"]
        filtered_deals = filtered_deals[prob_col.round(0).isin(sel_probs)]
    else:
        prob_col = filtered_deals["Вероятность"] * 100 if is_fraction else filtered_deals["Вероятность"]
        filtered_deals = filtered_deals[prob_col.round(0) > 0]

    # Сравнение с предыдущим BR (если передано)
    if comparison_deals is not None and not comparison_deals.empty:
        comparison_deals = comparison_deals.copy()
        comp_q_cols = [c for c in ["Q1", "Q2", "Q3", "Q4"] if c in comparison_deals.columns]
        if comp_q_cols:
            for c in comp_q_cols:
                comparison_deals[c] = pd.to_numeric(comparison_deals[c].astype(str).str.replace(" ", "").str.replace(",", "."), errors="coerce").fillna(0)
            comparison_deals["Сумма_сделки"] = comparison_deals[comp_q_cols].sum(axis=1)
        
        if 'Вероятность' in comparison_deals.columns:
            comparison_deals['Вероятность'] = pd.to_numeric(comparison_deals['Вероятность'], errors='coerce').fillna(0)

        if 'Название' in comparison_deals.columns and 'Название' in filtered_deals.columns:
            # Вместо ID используем Название проекта как ключ
            comp_df = comparison_deals[['Название', 'Сумма_сделки', 'Вероятность', 'Статус']].copy()
            comp_df = comp_df.rename(columns={
                'Сумма_сделки': 'Сумма_сделки_prev',
                'Вероятность': 'Вероятность_prev',
                'Статус': 'Статус_prev'
            })
            
            filtered_deals = filtered_deals.merge(comp_df, on='Название', how='left')
            
            filtered_deals['Δ Сумма сделки'] = filtered_deals['Сумма_сделки'] - filtered_deals['Сумма_сделки_prev'].fillna(0)
            
            max_prob_cur = filtered_deals["Вероятность"].max()
            is_frac_cur = max_prob_cur <= 1.0 if pd.notna(max_prob_cur) else True
            
            if is_frac_cur:
                filtered_deals['Δ Вероятность'] = (filtered_deals['Вероятность'] - filtered_deals['Вероятность_prev'].fillna(0)) * 100
            else:
                filtered_deals['Δ Вероятность'] = filtered_deals['Вероятность'] - filtered_deals['Вероятность_prev'].fillna(0)
        else:
            filtered_deals['Δ Сумма сделки'] = 0
            filtered_deals['Δ Вероятность'] = 0
            filtered_deals['Статус_prev'] = "—"
    else:
        filtered_deals['Δ Сумма сделки'] = 0
        filtered_deals['Δ Вероятность'] = 0
        filtered_deals['Статус_prev'] = "—"

    st.markdown("---")
    st.subheader("Реестр сделок")

    page_size = 12
    total_rows = len(filtered_deals)
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

    page_deals = filtered_deals.iloc[start_idx:end_idx].copy()

    if len(page_deals) > 0:
        display = page_deals.copy()
        
        if is_fraction:
            display["Вероятность"] = (display["Вероятность"] * 100).round(0)
        else:
            display["Вероятность"] = display["Вероятность"].round(0)
            
        display["Вероятность"] = display["Вероятность"].fillna(0).astype(int)
        
        display["Δ Вероятность"] = display["Δ Вероятность"].fillna(0).round(0).astype(int)
        display["Δ Вероятность"] = display["Δ Вероятность"].apply(lambda x: f"+{x}%" if x > 0 else f"{x}%" if x < 0 else "0%")

        all_concept_cols = [
            "Название", "SBU", "Менеджер", "Клиент", 
            "Тип_сделки", "Сумма_сделки", "Δ Сумма сделки", 
            "Статус", "Статус_prev",
            "Вероятность", "Δ Вероятность",
        ]

        cols_present = [c for c in all_concept_cols if c in display.columns]

        for col in ["Сумма_сделки", "Δ Сумма сделки"]:
            if col in display.columns:
                display[col] = display[col].apply(lambda v: fmt_num(v, 0))

        df_display = display[cols_present].rename(columns={"Статус_prev": "Статус (Prev. BR)"})
        
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

    total_sum = filtered_deals["Сумма_сделки"].sum() if "Сумма_сделки" in filtered_deals.columns else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Всего сделок", len(filtered_deals))
    c2.metric("Сумма сделок", f"{fmt_num(total_sum, 0)} тыс. руб.")
    
    if len(filtered_deals) > 0 and "Вероятность" in filtered_deals.columns:
        avg_prob = filtered_deals['Вероятность'].mean()
        if is_fraction:
            avg_prob *= 100
        c3.metric("Средняя вероятность", f"{avg_prob:.0f}%")
    else:
        c3.metric("Средняя вероятность", "—")

    st.markdown("---")

    def _go_to_pl():
        st.session_state["page_nav"] = "P&L"

    st.button("← Вернуться в P&L", width="content", on_click=_go_to_pl)