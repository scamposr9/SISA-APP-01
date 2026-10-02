"""Persistencia de actas: Excel maestro + PDFs.

- Si los Secrets de Streamlit tienen la sección [sharepoint] completa, todo se guarda en
  SharePoint (`RepositorioSharePoint`).
- Si no, en el disco del servidor (`RepositorioExcelLocal`), que en Streamlit Cloud es
  temporal.
"""

from __future__ import annotations

import functools

from acta_app import config
from acta_app.storage.base import (
    ActaDuplicadaError,
    ActaNoEncontradaError,
    AlmacenamientoError,
    EncuestaYaRespondidaError,
    RepositorioActas,
    ResultadoGuardado,
)
from acta_app.storage.esquema import fila_plana, formatear_valor, registro_desde_acta
from acta_app.storage.excel_local import RepositorioExcelLocal
from acta_app.storage.sharepoint import RepositorioSharePoint

CLAVES_SHAREPOINT = ("tenant_id", "client_id", "client_secret")


def configuracion_sharepoint() -> dict[str, str] | None:
    """Sección [sharepoint] de los Secrets de Streamlit, o None si falta algo."""
    try:
        import streamlit as st

        seccion = dict(st.secrets.get("sharepoint", {}))
    except Exception:  # sin archivo de secrets o fuera de Streamlit
        return None
    if not all(str(seccion.get(c, "")).strip() for c in CLAVES_SHAREPOINT):
        return None
    return {k: str(v).strip() for k, v in seccion.items()}


def usa_sharepoint() -> bool:
    return configuracion_sharepoint() is not None


def obtener_repositorio() -> RepositorioActas:
    cfg = configuracion_sharepoint()
    if cfg is None:
        return RepositorioExcelLocal()
    return _repositorio_sharepoint(tuple(sorted(cfg.items())))


@functools.cache
def _repositorio_sharepoint(cfg_items: tuple[tuple[str, str], ...]) -> RepositorioSharePoint:
    """Una instancia por configuración: reutiliza la sesión y el token de Microsoft."""
    from acta_app.storage.sharepoint import AlmacenGraph

    cfg = dict(cfg_items)
    almacen = AlmacenGraph(
        tenant_id=cfg["tenant_id"],
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        sitio_url=cfg.get("sitio", config.SHAREPOINT_SITIO),
        biblioteca=cfg.get("biblioteca", config.SHAREPOINT_BIBLIOTECA),
    )
    return RepositorioSharePoint(
        almacen,
        carpeta=cfg.get("carpeta", config.SHAREPOINT_CARPETA),
        excel=cfg.get("excel", config.SHAREPOINT_EXCEL),
        carpeta_pdf=cfg.get("carpeta_pdf", config.SHAREPOINT_CARPETA_PDF),
        equipos=cfg.get("equipos", config.SHAREPOINT_EQUIPOS),
        equipos_nuevos=cfg.get("equipos_nuevos", config.SHAREPOINT_EQUIPOS_NUEVOS),
        protocolos=cfg.get("protocolos", config.SHAREPOINT_PROTOCOLOS),
        repuestos=cfg.get("repuestos", config.SHAREPOINT_REPUESTOS),
        nombres_ingenieros=cfg.get("nombres_ingenieros", config.SHAREPOINT_NOMBRES_INGENIEROS),
    )


__all__ = [
    "ActaDuplicadaError",
    "ActaNoEncontradaError",
    "AlmacenamientoError",
    "EncuestaYaRespondidaError",
    "RepositorioActas",
    "RepositorioExcelLocal",
    "RepositorioSharePoint",
    "ResultadoGuardado",
    "configuracion_sharepoint",
    "fila_plana",
    "formatear_valor",
    "obtener_repositorio",
    "registro_desde_acta",
    "usa_sharepoint",
]
