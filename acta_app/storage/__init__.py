"""Persistencia de actas: Excel maestro + PDFs.

Hoy se guarda en disco (`RepositorioExcelLocal`). Para SharePoint bastará con otra clase
que cumpla `RepositorioActas` y devolverla aquí; el resto de la app no cambia.
"""

from acta_app.storage.base import (
    ActaDuplicadaError,
    ActaNoEncontradaError,
    AlmacenamientoError,
    RepositorioActas,
    ResultadoGuardado,
)
from acta_app.storage.esquema import fila_plana, formatear_valor, registro_desde_acta
from acta_app.storage.excel_local import RepositorioExcelLocal


def obtener_repositorio() -> RepositorioActas:
    return RepositorioExcelLocal()


__all__ = [
    "ActaDuplicadaError",
    "ActaNoEncontradaError",
    "AlmacenamientoError",
    "RepositorioActas",
    "RepositorioExcelLocal",
    "ResultadoGuardado",
    "fila_plana",
    "formatear_valor",
    "obtener_repositorio",
    "registro_desde_acta",
]
