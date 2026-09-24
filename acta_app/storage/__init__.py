"""Persistencia de actas: Excel maestro + PDFs.

Hoy se guarda en disco (`RepositorioExcelLocal`). Para SharePoint bastará con otra clase
que cumpla `RepositorioActas` y devolverla aquí; el resto de la app no cambia.
"""

from acta_app.storage.base import (
    COLUMNAS_ACTAS,
    COLUMNAS_ARTICULOS,
    ActaDuplicadaError,
    AlmacenamientoError,
    RepositorioActas,
    ResultadoGuardado,
)
from acta_app.storage.excel_local import RepositorioExcelLocal


def obtener_repositorio() -> RepositorioActas:
    return RepositorioExcelLocal()


__all__ = [
    "COLUMNAS_ACTAS",
    "COLUMNAS_ARTICULOS",
    "ActaDuplicadaError",
    "AlmacenamientoError",
    "RepositorioActas",
    "RepositorioExcelLocal",
    "ResultadoGuardado",
    "obtener_repositorio",
]
