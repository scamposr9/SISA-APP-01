"""Constantes compartidas: metadatos del formato, opciones, colores y rutas."""

from pathlib import Path

# ---------- Rutas ----------
BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
DATA_DIR = BASE_DIR / "data"
PDF_DIR = DATA_DIR / "pdfs"
LOGO_PATH = ASSETS_DIR / "logo.png"
EXCEL_MAESTRO_PATH = DATA_DIR / "actas_maestro.xlsx"

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
