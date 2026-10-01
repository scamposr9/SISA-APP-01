"""Carga del catálogo (con caché) para el autocompletado del formulario."""

from __future__ import annotations

import streamlit as st

from acta_app import config
from acta_app.catalogo import Catalogo
from acta_app.protocolos import Protocolos
from acta_app.repuestos import Repuestos
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


@st.cache_data(show_spinner=False, ttl=300)
def _cargar_equipos_nuevos() -> Catalogo | None:
    datos = obtener_repositorio().leer_equipos_nuevos()
    return Catalogo.desde_bytes(datos) if datos else None


def cargar_catalogo() -> Catalogo:
    """Con SharePoint se lee Equipos.xlsx de la carpeta de actas (se refresca cada 5
    minutos). Sin SharePoint, solo si alguien dejó un catalogos/equipos.xlsx local (p. ej.
    para pruebas en su computadora); los datos de la empresa no se guardan en GitHub.
    En ambos casos se suman los equipos anotados en Equipos_nuevos.xlsx."""
    catalogo = None
    if usa_sharepoint():
        try:
            catalogo = _cargar_sharepoint()
        except AlmacenamientoError:
            catalogo = None
    if catalogo is None:
        catalogo = _cargar_local(_firma_archivo(config.CATALOGO_EQUIPOS_PATH))
    try:
        nuevos = _cargar_equipos_nuevos()
    except AlmacenamientoError:
        nuevos = None
    return catalogo.unir(nuevos) if nuevos is not None else catalogo


@st.cache_data(show_spinner=False, ttl=300)
def _cargar_protocolos() -> Protocolos:
    datos = obtener_repositorio().leer_protocolos()
    return Protocolos.desde_bytes(datos) if datos else Protocolos()


def cargar_protocolos() -> Protocolos:
    """Protocolos de Mantenimientos Preventivos.xlsx (se refrescan cada 5 minutos)."""
    try:
        return _cargar_protocolos()
    except Exception:  # sin conexión o Excel ilegible: el formulario sigue sin checklist
        return Protocolos()


@st.cache_data(show_spinner=False, ttl=300)
def _cargar_repuestos() -> Repuestos:
    datos = obtener_repositorio().leer_repuestos()
    return Repuestos.desde_bytes(datos) if datos else Repuestos()


def cargar_repuestos() -> Repuestos:
    """Repuestos.xlsx para «Artículos empleados» (se refresca cada 5 minutos)."""
    try:
        return _cargar_repuestos()
    except Exception:  # sin conexión o Excel ilegible: los artículos se escriben a mano
        return Repuestos()


def refrescar_catalogo() -> None:
    _cargar_repuestos.clear()
    _cargar_protocolos.clear()
    _cargar_sharepoint.clear()
    _cargar_local.clear()
    _cargar_equipos_nuevos.clear()
