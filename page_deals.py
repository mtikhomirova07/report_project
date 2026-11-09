"""
Страница «Сделки» — реестр с фильтрами и пагинацией.
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
    # CSS-хак, чтобы убрать кнопку "Select all" в выпадающих списках
    st.markdown("""
        <style>
            [data-testid="stMultiSelect"] span[data-baseweb="tag"] + div + div button {
                display: none !important;
            }
            /* Более надежный вариант: скрываем кнопку по aria-label */
            button[aria-label="Select all"] {
                display: none !important;
            }
        </style>
    """, unsafe_allow_html=True)

    st.title("Сделки")
    st.caption("Фильтр по статусу — выберите нужный в фильтрах ниже.")

    if deals is None:
        st.error("Нет данных по сделкам.")
        return

    deals = deals.copy()

    # Подменяем имена колонок, если они отличаются
    rename_map = {
        "Backlog_Pipeline": "Тип_сделки",
        "Заказчик": "Клиент",
    }
    deals = deals.rename(columns=rename_map)

    required_cols = ["Тип_сделки", "Вероятность"]
    for col in required_cols:
        if col not in deals.columns:
            deals[col] = "—"

    if "Вероятность" not in deals.columns:
        deals["Вероятность"] = 0.0

    # Безопасный подсчет суммы сделки
    if "Взвешенная_Q1" in deals.columns:
        q_cols = ["Взвешенная_Q1", "Взвешенная_Q2", "Взвешенная_Q3", "Взвешенная_Q4"]
        for c in q_cols:
            if c in deals.columns:
                deals[c] = pd.to_numeric(deals[c], errors="coerce").fillna(0)
        deals["Сумма_сделки"] = deals[[c for c in q_cols if c in deals.columns]].sum(axis=1)
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
        st.session_state["deals_type"] = "Все"
        st.session_state["deals_probs"] = []
        st.session_state["deals_page"] = 1

    col1, col2, col3 = st.columns(3)

    with col1:
        # Оставляем только Pipeline, Backlog, GAP
        valid_types = ["Backlog", "Pipeline", "GAP"]
        deals["Тип_сделки"] = deals["Тип_сделки"].astype(str).str.strip().str.title()
        found_types = [t for t in valid_types if t in deals["Тип_сделки"].unique()]
        
        types = ["Все"] + found_types
        st.selectbox("Тип сделки", types, key="deals_type")

    with col2:
        prob_options = [1, 25, 40, 60, 80, 100]
        # Параметр select_all не поддерживается нативно, поэтому работает CSS выше
        st.multiselect(
            "Вероятность сделки", 
            options=prob_options, 
            key="deals_probs", 
            placeholder="Все вероятности",
        )
        
    with col3:
        # Фильтр "Статус" скрыт (в данных нет колонки статуса)
        st.selectbox("Статус", ["Все"], key="deals_status", disabled=True)

    st.button("Сбросить фильтры", on_click=reset_filters)

    sel_type = st.session_state.get("deals_type", "Все")
    sel_probs = st.session_state.get("deals_probs", [])

    filtered_deals = deals.copy()
    filtered_deals['Вероятность'] = pd.to_numeric(filtered_deals['Вероятность'], errors='coerce').fillna(0)
    
    max_prob = filtered_deals["Вероятность"].max()
    is_fraction = max_prob <= 1.0 if pd.notna(max_prob) else True

    if sel_type != "Все":
        filtered_deals = filtered_deals[filtered_deals["Тип_сделки"] == sel_type]

    if sel_probs:
        prob_col = filtered_deals["Вероятность"] * 100 if is_fraction else filtered_deals["Вероятность"]
        filtered_deals = filtered_deals[prob_col.round(0).isin(sel_probs)]
    else:
        prob_col = filtered_deals["Вероятность"] * 100 if is_fraction else filtered_deals["Вероятность"]
        filtered_deals = filtered_deals[prob_col.round(0) > 0]

    # Сравнение с предыдущим BR
    if comparison_deals is not None and not comparison_deals.empty:
        comparison_deals = comparison_deals.copy()
        
        if "Взвешенная_Q1" in comparison_deals.columns:
            comp_q_cols = ["Взвешенная_Q1", "Взвешенная_Q2", "Взвешенная_Q3", "Взвешенная_Q4"]
            for c in comp_q_cols:
                if c in comparison_deals.columns:
                    comparison_deals[c] = pd.to_numeric(comparison_deals[c], errors="coerce").fillna(0)
            comparison_deals["Сумма_сделки"] = comparison_deals[[c for c in comp_q_cols if c in comparison_deals.columns]].sum(axis=1)
        else:
            comparison_deals["Сумма_сделки"] = 0
            
        if 'Вероятность' in comparison_deals.columns:
            comparison_deals['Вероятность'] = pd.to_numeric(comparison_deals['Вероятность'], errors='coerce').fillna(0)

        if 'Название' in comparison_deals.columns and 'Название' in filtered_deals.columns:
            comp_df = comparison_deals[['Название', 'Сумма_сделки', 'Вероятность']].copy()
            comp_df = comp_df.rename(columns={
                'Сумма_сделки': 'Сумма_сделки_prev',
                'Вероятность': 'Вероятность_prev',
            })
            
            filtered_deals = filtered_deals.merge(comp_df, on='Название', how='left')
            
            filtered_deals['Δ Сумма сделки'] = filtered_deals['Сумма_сделки'] - filtered_deals['Сумма_сделки_prev'].fillna(0)
            
            if is_fraction:
                filtered_deals['Δ Вероятность'] = (filtered_deals['Вероятность'] - filtered_deals['Вероятность_prev'].fillna(0)) * 100
            else:
                filtered_deals['Δ Вероятность'] = filtered_deals['Вероятность'] - filtered_deals['Вероятность_prev'].fillna(0)
        else:
            filtered_deals['Δ Сумма сделки'] = 0
            filtered_deals['Δ Вероятность'] = 0
    else:
        filtered_deals['Δ Сумма сделки'] = 0
        filtered_deals['Δ Вероятность'] = 0

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
            "Название", "SBU", "Клиент", 
            "Тип_сделки", "Сумма_сделки", "Δ Сумма сделки", 
            "Вероятность", "Δ Вероятность",
        ]

        cols_present = [c for c in all_concept_cols if c in display.columns]

        for col in ["Сумма_сделки", "Δ Сумма сделки"]:
            if col in display.columns:
                display[col] = display[col].apply(lambda v: fmt_num(v, 0))

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