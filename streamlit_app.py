# streamlit_app.py
import sys, os
from pathlib import Path

# Asegura que el paquete interno sea visible
BASE_DIR = Path(__file__).resolve().parent / "made4try"
sys.path.append(str(BASE_DIR))

# Importa la app principal
from made4try.app import run

if __name__ == "__main__":
    run()
