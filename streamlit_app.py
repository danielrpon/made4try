# streamlit_app.py
import streamlit as st
from made4try.app import run

try:
    run()
except Exception as e:
    st.exception(e)  # si algo revienta, se verá el error en pantalla
