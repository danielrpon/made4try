# made4try/user_auth/ui.py
import streamlit as st
from .models import init_db
from .auth import create_user, login, get_user_by_email

def _safe_rerun():
    """Rerun compatible con Streamlit nuevo/antiguo."""
    try:
        # Streamlit >= 1.27 aprox.
        st.rerun()
    except AttributeError:
        # Compat: versiones antiguas
        st.experimental_rerun()

def render_auth_sidebar():
    """Panel lateral con login/signup y estado de sesión."""
    init_db()  # asegura tablas
    st.sidebar.header("👤 Cuenta")

    if "user" not in st.session_state:
        st.session_state.user = None

    if st.session_state.user:
        u = st.session_state.user
        st.sidebar.success(f"Sesión: {u['name']} ({u['role']})")
        if st.sidebar.button("Cerrar sesión"):
            st.session_state.user = None
            _safe_rerun()
        return

    tab_login, tab_signup = st.sidebar.tabs(["Entrar", "Crear cuenta"])

    with tab_login:
        email = st.text_input("Email", key="auth_email")
        pwd = st.text_input("Contraseña", type="password", key="auth_pwd")
        if st.button("Iniciar sesión"):
            user = login(email, pwd)
            if user:
                st.session_state.user = user
                _safe_rerun()
            else:
                st.error("Credenciales inválidas.")

    with tab_signup:
        name = st.text_input("Nombre completo", key="su_name")
        email2 = st.text_input("Email", key="su_email")
        pwd2 = st.text_input("Contraseña", type="password", key="su_pwd")
        if st.button("Crear cuenta"):
            if get_user_by_email(email2):
                st.warning("Ese email ya está registrado.")
            elif not (name and email2 and pwd2):
                st.warning("Completa todos los campos.")
            else:
                try:
                    create_user(name=name, email=email2, password=pwd2, role="athlete")
                    st.success("Cuenta creada. Ahora inicia sesión.")
                except Exception as e:
                    st.error(f"No se pudo crear la cuenta: {e}")

def require_login():
    """Usa esto para proteger vistas."""
    if not st.session_state.get("user"):
        st.info("Inicia sesión para continuar.")
        st.stop()

def is_admin() -> bool:
    u = st.session_state.get("user")
    return bool(u and u.get("role") == "admin")