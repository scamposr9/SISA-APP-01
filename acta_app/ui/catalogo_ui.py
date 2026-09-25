"""Carga del catálogo (con caché) para el autocompletado del formulario."""

from __future__ import annotations

import streamlit as st

from acta_app import config
from acta_app.catalogo import Catalogo


def _firma_archivo(ruta) -> float:
    return ruta.stat().st_mtime if ruta.exists() else 0.0


@st.cache_data(show_spinner=False, ttl=600)
def _cargar(firma: float) -> Catalogo:
    # `firma` (fecha de modificación) solo sirve como clave de la caché; no debe llevar
    # "_" delante, porque Streamlit no usa esos parámetros para la clave.
    del firma
    return Catalogo.desde_excel(config.CATALOGO_EQUIPOS_PATH)


def cargar_catalogo() -> Catalogo:
    """Se vuelve a leer cuando cambia el inventario (su fecha de modificación es parte de
    la clave de la caché) o, como máximo, cada 10 minutos."""
    return _cargar(_firma_archivo(config.CATALOGO_EQUIPOS_PATH))
