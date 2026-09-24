"""Constantes compartidas: metadatos del formato, opciones, colores y rutas."""

import functools
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Versión visible al pie de la app. Además se muestra el commit de GitHub desplegado
# (ver version_desplegada), que cambia solo con cada actualización.
APP_VERSION = "0.7"

# El servidor (p. ej. Streamlit Cloud) corre en UTC; fechas y horas se toman en hora de Perú.
ZONA_HORARIA = ZoneInfo("America/Lima")

# ---------- Rutas ----------
BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
DATA_DIR = BASE_DIR / "data"
PDF_DIR = DATA_DIR / "pdfs"
LOGO_PATH = ASSETS_DIR / "logo.png"
EXCEL_MAESTRO_PATH = DATA_DIR / "actas_maestro.xlsx"

# Catálogos para el autocompletado (ver acta_app/catalogo.py).
CATALOGOS_DIR = BASE_DIR / "catalogos"
CATALOGO_EQUIPOS_PATH = CATALOGOS_DIR / "equipos.xlsx"
CATALOGO_CLIENTES_PATH = CATALOGOS_DIR / "clientes.xlsx"

# ---------- Metadatos del formato físico ----------
SISTEMA = "SISTEMA INTEGRADO DE GESTIÓN"
CODIGO_FORMATO = "FO-ING-02"
NOMBRE_FORMATO = "Acta de Atención"
EDICION = "Ed. 03"
EMPRESA = "Sistemas Analíticos"
SITIO_WEB = "sistemasanaliticos.com"

# ---------- Opciones exclusivas ----------
TIPO_SERVICIO_PREVENTIVO = "Mant. Preventivo"
TIPO_SERVICIO_CORRECTIVO = "Mant. Correctivo"
TIPO_SERVICIO_OTRO = "Otro"
TIPOS_SERVICIO = [TIPO_SERVICIO_PREVENTIVO, TIPO_SERVICIO_CORRECTIVO, TIPO_SERVICIO_OTRO]

ESTADOS_FINALES = ["Operativo", "Inoperativo", "En Observación"]

# Filas vacías con las que arranca la tabla de artículos (igual que el formato físico)
FILAS_ARTICULOS_INICIALES = 4

# ---------- Paleta (idéntica al prototipo HTML) ----------
NAVY = "#16305C"
NAVY_DARK = "#0F2244"
ORANGE = "#F7941D"
RED = "#C0392B"
INK = "#1A1A1A"
GREY_LINE = "#C7CDD6"
GREY_BG = "#F4F6F9"


@functools.cache
def version_desplegada() -> str:
    """'0.7 · actualización fe08408 del 24/09/2026 05:44 PM', tomada del último commit.

    Tras un Reboot en Streamlit Cloud, el código corto debe coincidir con el último
    commit de la rama en GitHub. Si no hay información de git, solo se muestra APP_VERSION.
    """
    try:
        salida = subprocess.run(
            ["git", "log", "-1", "--format=%h|%cI"],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=5, check=True,
        ).stdout.strip()
        commit, fecha_iso = salida.split("|")
        fecha = datetime.fromisoformat(fecha_iso).astimezone(ZONA_HORARIA)
        return f"{APP_VERSION} · actualización {commit} del {fecha:%d/%m/%Y %I:%M %p}"
    except (OSError, ValueError, subprocess.SubprocessError):
        return APP_VERSION
