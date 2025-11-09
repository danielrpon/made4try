# made4try/user_auth/ui.py
import re
import streamlit as st

from .models import init_db, reset_password, get_user_by_email
from .auth import create_user, login

def _safe_rerun():
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()

def render_auth_sidebar():
    init_db()
    st.sidebar.header("👤 Cuenta")

    if "user" not in st.session_state:
        st.session_state.user = None

    # Sesión activa
    if st.session_state.user:
        u = st.session_state.user
        st.sidebar.success(f"Sesión: {u['name']} ({u['role']})")
        if st.sidebar.button("Cerrar sesión"):
            st.session_state.user = None
            _safe_rerun()
        return

    tab_login, tab_signup, tab_reset = st.sidebar.tabs(["Entrar", "Crear cuenta", "Recuperar clave"])

    # --- Login ---
    with tab_login:
        email = st.text_input("Email", key="auth_email")
        pwd   = st.text_input("Contraseña", type="password", key="auth_pwd")
        if st.button("Iniciar sesión", key="btn_login"):
            email_norm = email.strip().lower()
            if not (email_norm and pwd):
                st.warning("Completa email y contraseña.")
            else:
                user = login(email_norm, pwd)
                if user:
                    st.session_state.user = user
                    _safe_rerun()
                else:
                    st.error("Credenciales inválidas.")

    # --- Registro ---
    with tab_signup:
        name   = st.text_input("Nombre completo", key="su_name")
        email2 = st.text_input("Email", key="su_email")
        pwd2   = st.text_input("Contraseña", type="password", key="su_pwd")
        if st.button("Crear cuenta", key="btn_signup"):
            email2_norm = email2.strip().lower()
            import re
            if not (name and email2_norm and pwd2):
                st.warning("Completa todos los campos.")
            elif not re.match(r"[^@]+@[^@]+\.[^@]+", email2_norm):
                st.warning("Email no parece válido.")
            elif get_user_by_email(email2_norm):
                st.warning("Ese email ya está registrado.")
            else:
                try:
                    create_user(name=name, email=email2_norm, password=pwd2, role="athlete")
                    st.success("Cuenta creada. Ahora inicia sesión.")
                except Exception as e:
                    st.error(f"No se pudo crear la cuenta: {e}")

    # --- Recuperar contraseña (con código de admin) ---
    with tab_reset:
        st.caption("Para resetear la contraseña sin estar logueado, ingresa tu email, una nueva contraseña y el código de administrador.")
        email_r = st.text_input("Email de la cuenta", key="reset_email_input")
        new_pw  = st.text_input("Nueva contraseña", type="password", key="reset_new_pw_input")
        code    = st.text_input("Código de administrador", type="password", key="reset_code_input")

        if st.button("Resetear contraseña", key="btn_reset_pw"):
            email_r_norm = email_r.strip().lower()
            admin_code = st.secrets.get("ADMIN_RESET_CODE")
            if not admin_code:
                st.error("Falta configurar ADMIN_RESET_CODE (en local puedes definirlo en .streamlit/secrets.toml).")
                return
            elif not (email_r_norm and new_pw and code):
                st.warning("Completa todos los campos.")
            elif code != admin_code:
                st.error("Código de administrador incorrecto.")
            elif not get_user_by_email(email_r_norm):
                st.error("No existe un usuario con ese email.")
            else:
                n = reset_password(email_r_norm, new_pw)
                if n == 1:
                    st.success("Contraseña actualizada. Ya puedes iniciar sesión.")
                    st.info("Ve a la pestaña **Entrar** y usa tu nueva contraseña.")
                else:
                    st.error("No fue posible actualizar la contraseña.")

def require_login():
    if not st.session_state.get("user"):
        st.info("Inicia sesión para continuar.")
        st.stop()

def is_admin() -> bool:
    u = st.session_state.get("user")
    return bool(u and u.get("role") == "admin")