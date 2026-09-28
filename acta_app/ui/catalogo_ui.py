"""Carga del catálogo (con caché) para el autocompletado del formulario."""

from __future__ import annotations

import streamlit as st

from acta_app import config
from acta_app.catalogo import Catalogo
from acta_app.storage import AlmacenamientoError, obtener_repositorio, usa_sharepoint


def _firma_archivo(ruta) -> float:
    return ruta.stat().st_mtime if ruta.exists() else 0.0


@st.cache_data(show_spinner=False, ttl=600)
def _cargar_local(firma: float) -> Catalogo:
    # `firma` (fecha de modificación) solo sirve como clave de la caché; no debe llevar
    # "_" delante, porque Streamlit no usa esos parámetros para la clave.
    del firma
    return Catalogo.desde_excel(config.CATALOGO_EQUIPOS_PATH)


@st.cache_data(show_spinner="Cargando catálogo de equipos desde SharePoint…", ttl=300)
def _cargar_sharepoint() -> Catalogo | None:
    datos = obtener_repositorio().leer_equipos()
    return Catalogo.desde_bytes(datos) if datos else None


def cargar_catalogo() -> Catalogo:
    """Con SharePoint se lee Equipos.xlsx de la carpeta de actas (se refresca cada 5
    minutos). Si no está allí, o no hay SharePoint, se usa el catálogo de la app."""
    if usa_sharepoint():
        try:
            catalogo = _cargar_sharepoint()
        except AlmacenamientoError:
            catalogo = None
        if catalogo is not None:
            return catalogo
    return _cargar_local(_firma_archivo(config.CATALOGO_EQUIPOS_PATH))


def refrescar_catalogo() -> None:
    _cargar_sharepoint.clear()
    _cargar_local.clear()
