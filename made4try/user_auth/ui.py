# made4try/user_auth/ui.py
import streamlit as st
from .models import init_db
from .auth import create_user, login, get_user_by_email

def _safe_rerun():
    """Rerun compatible con Streamlit nuevo/antiguo."""
    try:
        st.rerun()  # Streamlit >= ~1.27
    except AttributeError:
        st.experimental_rerun()  # Compat versiones antiguas

def render_auth_sidebar():
    """Panel lateral con login/signup y estado de sesión."""
    init_db()  # asegura tablas idempotente
    st.sidebar.header("👤 Cuenta")

    if "user" not in st.session_state:
        st.session_state.user = None

    # Sesión activa
    if st.session_state.user:
        u = st.session_state.user
        nombre = u.get("name") or u.get("email", "usuario")
        rol = u.get("role", "athlete")
        st.sidebar.success(f"Sesión: {nombre} ({rol})")
        if st.sidebar.button("Cerrar sesión", key="btn_logout"):
            st.session_state.user = None
            _safe_rerun()
        return

    # Tabs login / signup
    tab_login, tab_signup = st.sidebar.tabs(["Entrar", "Crear cuenta"])

    # --- Login ---
    with tab_login:
        email = st.text_input("Email", key="auth_email").strip().lower()
        pwd   = st.text_input("Contraseña", type="password", key="auth_pwd")
        if st.button("Iniciar sesión", key="btn_login"):
            if not email or not pwd:
                st.warning("Ingresa email y contraseña.")
            else:
                user = login(email, pwd)
                if user:
                    st.session_state.user = user
                    _safe_rerun()
                else:
                    # Limpia el password si falla
                    st.session_state["auth_pwd"] = ""
                    st.error("Credenciales inválidas. Verifica tu email y contraseña.")

    # --- Signup ---
    with tab_signup:
        name   = st.text_input("Nombre completo", key="su_name").strip()
        email2 = st.text_input("Email", key="su_email").strip().lower()
        pwd2   = st.text_input("Contraseña", type="password", key="su_pwd")

        if st.button("Crear cuenta", key="btn_signup"):
            if not (name and email2 and pwd2):
                st.warning("Completa todos los campos.")
            elif get_user_by_email(email2):
                st.warning("Ese email ya está registrado.")
            else:
                try:
                    create_user(name=name, email=email2, password=pwd2, role="athlete")
                    st.success("Cuenta creada. Ahora inicia sesión en la pestaña 'Entrar'.")
                except Exception as e:
                    st.error(f"No se pudo crear la cuenta: {e}")

def require_login():
    """Bloquea la vista si no hay usuario en sesión."""
    if not st.session_state.get("user"):
        st.info("Inicia sesión para continuar.")
        st.stop()

def is_admin() -> bool:
    u = st.session_state.get("user")
    return bool(u and u.get("role") == "admin")