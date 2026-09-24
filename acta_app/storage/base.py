"""Contrato común de los lugares donde se guardan las actas (Excel local, SharePoint...)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pandas as pd

from acta_app.models import Acta


class ActaDuplicadaError(Exception):
    """Ya existe un acta registrada con el mismo número."""


class AlmacenamientoError(Exception):
    """No se pudo escribir en el almacenamiento (archivo bloqueado, sin conexión, etc.)."""


@dataclass
class ResultadoGuardado:
    total_actas: int
    ubicacion_pdf: str


class RepositorioActas(Protocol):
    def existe(self, numero: str) -> bool: ...

    def guardar(self, acta: Acta, pdf: bytes, nombre_pdf: str) -> ResultadoGuardado:
        """Guarda el PDF y agrega el acta como fila nueva. Lanza ActaDuplicadaError o
        AlmacenamientoError si no se pudo."""
        ...

    def leer_actas(self) -> pd.DataFrame: ...

    def excel_bytes(self) -> bytes | None:
        """Contenido actual del Excel maestro, para descargarlo desde la app."""
        ...

    def exportar_zip(self) -> bytes | None:
        """Excel maestro + PDFs en un ZIP (con los enlaces del Excel funcionando)."""
        ...


def normalizar_numero(numero: str) -> str:
    """'2026-00051 ' y '2026-00051' son la misma acta."""
    return "".join(numero.split()).casefold()
