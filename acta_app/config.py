"""Constantes compartidas: metadatos del formato, opciones, colores y rutas."""

import functools
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Versión visible al pie de la app. Además se muestra el commit de GitHub desplegado
# (ver version_desplegada), que cambia solo con cada actualización.
APP_VERSION = "0.34.2"

# El servidor (p. ej. Streamlit Cloud) corre en UTC; fechas y horas se toman en hora de Perú.
ZONA_HORARIA = ZoneInfo("America/Lima")

# ---------- Rutas ----------
BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
DATA_DIR = BASE_DIR / "data"
PDF_DIR = DATA_DIR / "pdfs"
LOGO_PATH = ASSETS_DIR / "logo.png"
EXCEL_MAESTRO_PATH = DATA_DIR / "actas_maestro.xlsx"
EQUIPOS_NUEVOS_PATH = DATA_DIR / "equipos_nuevos.xlsx"
PREINSTALACIONES_PATH = DATA_DIR / "preinstalaciones.xlsx"

# Catálogo para el autocompletado (ver acta_app/catalogo.py): equipos, sedes (clientes) y
# departamentos (ubicación). Con SharePoint se leerá de «Equipos.xlsx» en la carpeta Actas.
CATALOGOS_DIR = BASE_DIR / "catalogos"
CATALOGO_EQUIPOS_PATH = CATALOGOS_DIR / "equipos.xlsx"
PROTOCOLOS_PATH = CATALOGOS_DIR / "mantenimientos_preventivos.xlsx"  # solo pruebas locales
REPUESTOS_PATH = CATALOGOS_DIR / "repuestos.xlsx"  # solo pruebas locales
INGENIEROS_PATH = CATALOGOS_DIR / "ingenieros.xlsx"  # solo pruebas locales
ANTECEDENTE_PREVENTIVO = "Mantenimiento Preventivo"

# ---------- SharePoint (se activa con la sección [sharepoint] de los Secrets) ----------
# Destino acordado. Las claves de acceso (tenant, client id, client secret) NO van aquí:
# se cargarán en los «Secrets» de Streamlit Cloud.
AZURE_APP_NOMBRE = "SISA Actas Ingeniería"  # nombre de la app registrada en Entra ID
# Con inicio de sesión activo ([auth] en los Secrets), solo entran correos de este dominio.
DOMINIO_PERMITIDO = "sistemasanaliticos.com"
SHAREPOINT_SITIO = "https://sistemasanaliticospe.sharepoint.com/sites/OperacionesyServicios"
SHAREPOINT_BIBLIOTECA = "Documentos compartidos"
SHAREPOINT_CARPETA = "16. Analisis de Datos/Actas"
SHAREPOINT_CARPETA_PDF = "PDF"  # subcarpeta dentro de SHAREPOINT_CARPETA
SHAREPOINT_EXCEL = "Actas.xlsx"  # lo crea la app la primera vez que guarde un acta
SHAREPOINT_EQUIPOS = "Equipos.xlsx"  # catálogo para el autocompletado
# Equipos con una serie que no está en Equipos.xlsx, para revisarlos y pasarlos a mano.
# Lo crea la app con el primer equipo nuevo.
SHAREPOINT_EQUIPOS_NUEVOS = "Equipos_nuevos.xlsx"
# Reporte de preinstalación (Presite): Excel maestro y PDFs propios, en la misma carpeta.
# Subcarpetas de la carpeta de actas: catálogos (Equipos, Equipos_nuevos, Repuestos y
# Mantenimientos Preventivos) y preinstalaciones (su Excel y su carpeta de PDF). Si un archivo
# aún está suelto en la carpeta de actas (ubicación anterior), se sigue usando ese.
SHAREPOINT_CARPETA_ACTAS = "Actas"  # Actas.xlsx, PDF y Firmas Actas
SHAREPOINT_CARPETA_BASE_DATOS = "Base de Datos"
SHAREPOINT_CARPETA_PREINSTALACIONES = "Preinstalaciones"
SHAREPOINT_PREINSTALACIONES = "Preinstalaciones.xlsx"
SHAREPOINT_CARPETA_FOTOS_PREINSTALACIONES = "Fotos Preinstalaciones"  # <N.°>/Foto 01 - ….jpg
SHAREPOINT_CARPETA_PDF_PREINSTALACIONES = "PDF Preinstalaciones"
# Mantenimientos preventivos de balanzas (acta + pruebas de funcionamiento).
SHAREPOINT_BALANZAS = "Mantenimientos Balanzas.xlsx"
# Protocolos de mantenimiento preventivo: checklist de «Acciones realizadas».
SHAREPOINT_PROTOCOLOS = "Mantenimientos Preventivos.xlsx"
# Repuestos: autocompletado de «Artículos empleados» (código -> descripción).
SHAREPOINT_REPUESTOS = "Repuestos.xlsx"
# Lista de ingenieros (desplegable «Nombre del representante»), dentro de la carpeta de actas
# o junto a ella: el Excel «Nombres Ingenieria.xlsx» o una carpeta «Nombres Ingenieria» (con un
# Excel o una subcarpeta por ingeniero).
SHAREPOINT_NOMBRES_INGENIEROS = "Firmas Ingenieros/Nombres Ingenieria"

# ---------- Metadatos del formato físico ----------
SISTEMA = "SISTEMA INTEGRADO DE GESTIÓN"
CODIGO_FORMATO = "FO-ING-02"
NOMBRE_FORMATO = "Acta de Atención"
EDICION = "Ed. 03"
EMPRESA = "Sistemas Analíticos"
SITIO_WEB = "sistemasanaliticos.com"

# ---------- Opciones exclusivas ----------
TIPO_SERVICIO_PREVENTIVO = "Mant. Preventivo"
TIPO_SERVICIO_PRESITE = "Presite"  # muestra el formato de preinstalación
TIPO_SERVICIO_CORRECTIVO = "Mant. Correctivo"
TIPOS_SERVICIO = [
    TIPO_SERVICIO_PREVENTIVO, TIPO_SERVICIO_CORRECTIVO, TIPO_SERVICIO_PRESITE, "Instalación", "Actualización",
]
# Solo para leer actas anteriores, guardadas como «Otro: <texto>».
TIPO_SERVICIO_OTRO = "Otro"

ESTADOS_FINALES = ["Operativo", "Inoperativo", "En Observación"]

# ---------- Encuesta de satisfacción del cliente ----------
ASPECTOS_ENCUESTA = [
    "Puntualidad del trabajador",
    "Respeto y disposición",
    "Claridad en la explicación técnica",
    "Orden y limpieza al terminar",
    "Eficiencia en el trabajo",
]
ESCALA_ENCUESTA = ["Muy malo", "Malo", "Regular", "Bueno", "Muy bueno"]  # 1 a 5
NOTA_MAXIMA_ENCUESTA = 20  # la suma de los aspectos se lleva a escala vigesimal
# QR de la encuesta: dirección pública de la app (se puede cambiar en los Secrets, sección
# [app]: url_app) y horas que vale cada QR.
URL_APP = "https://sisa-app.streamlit.app"
HORAS_VIGENCIA_ENCUESTA = 24


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
        return f"{APP_VERSION} · actualización {commit} del {fecha:%d/%m/%Y %H:%M}"
    except (OSError, ValueError, subprocess.SubprocessError):
        return APP_VERSION
