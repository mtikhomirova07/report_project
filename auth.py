# auth.py
import streamlit as st

def check_password():
    """Возвращает True, если пользователь ввел правильный пароль."""
    
    def password_entered():
        # Здесь задаем логин и пароль (можно поменять)
        if (
            st.session_state["username"] == "reksoft/admin"
            and st.session_state["password"] == "otchet/reksoft"
        ):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Не храним пароль в памяти
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # Первый запуск: показываем форму ввода
        st.text_input("Логин", key="username")
        st.text_input("Пароль", type="password", key="password")
        st.button("Войти", on_click=password_entered)
        return False
    
    elif not st.session_state["password_correct"]:
        # Неправильный пароль
        st.text_input("Логин", key="username")
        st.text_input("Пароль", type="password", key="password")
        st.button("Войти", on_click=password_entered)
        st.error("😕 Пользователь не найден или пароль неверный")
        return False
    
    else:
        # Пароль верный
        return True