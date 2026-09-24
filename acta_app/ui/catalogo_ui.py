"""Carga del catálogo (con caché) para el autocompletado del formulario."""

from __future__ import annotations

import streamlit as st

from acta_app import config
from acta_app.catalogo import Catalogo
from acta_app.storage import obtener_repositorio


def _firma_archivo(ruta) -> float:
    return ruta.stat().st_mtime if ruta.exists() else 0.0


@st.cache_data(show_spinner=False, ttl=600)
def _cargar(firma: tuple[float, float, float]) -> Catalogo:
    # `firma` (fechas de modificación) solo sirve como clave de la caché; no debe llevar
    # "_" delante, porque Streamlit no usa esos parámetros para la clave.
    del firma
    return Catalogo.desde_fuentes(
        config.CATALOGO_EQUIPOS_PATH,
        config.CATALOGO_CLIENTES_PATH,
        obtener_repositorio().leer_actas(),
    )


def cargar_catalogo() -> Catalogo:
    """Se vuelve a leer cuando cambia el inventario, la lista de clientes o se guarda un
    acta (la fecha de modificación de los archivos es parte de la clave de la caché)."""
    firma = (
        _firma_archivo(config.CATALOGO_EQUIPOS_PATH),
        _firma_archivo(config.CATALOGO_CLIENTES_PATH),
        _firma_archivo(config.EXCEL_MAESTRO_PATH),
    )
    return _cargar(firma)
