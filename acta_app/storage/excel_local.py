"""Excel maestro en disco (data/actas_maestro.xlsx) + PDFs en data/pdfs/."""

from __future__ import annotations

import io
import os
import tempfile
import threading
import zipfile
from pathlib import Path

import pandas as pd
from openpyxl import Workbook, load_workbook

from acta_app import config
from acta_app.models import Acta, ahora
from acta_app.storage.base import (
    ActaDuplicadaError,
    AlmacenamientoError,
    ResultadoGuardado,
    normalizar_numero,
)
from acta_app.storage.esquema import Registro, disposicion, registro_desde_acta
from acta_app.storage.excel_formato import (
    HOJA_ACTAS,
    construir_libro,
    es_formato_anterior,
    leer_registros,
)

# Streamlit atiende a varios usuarios en hilos del mismo proceso: una escritura a la vez.
_LOCK = threading.Lock()


class RepositorioExcelLocal:
    def __init__(self, ruta_excel: Path = config.EXCEL_MAESTRO_PATH, dir_pdf: Path = config.PDF_DIR):
        self.ruta_excel = Path(ruta_excel)
        self.dir_pdf = Path(dir_pdf)

    # ---------- Lectura ----------
    def existe(self, numero: str) -> bool:
        buscado = normalizar_numero(numero)
        return any(normalizar_numero(r.numero) == buscado for r in self._registros())

    def leer_actas(self) -> pd.DataFrame:
        registros = self._registros()
        columnas = disposicion(registros)
        return pd.DataFrame(
            [{c.encabezado: c.valor(r) for c in columnas} for r in registros],
            columns=[c.encabezado for c in columnas],
        )

    def excel_bytes(self) -> bytes | None:
        return self.ruta_excel.read_bytes() if self.ruta_excel.exists() else None

    def exportar_zip(self) -> bytes | None:
        """Excel + carpeta pdfs/ en un ZIP: al descomprimirlo, los enlaces del Excel abren
        cada PDF."""
        excel = self.excel_bytes()
        if excel is None:
            return None
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(self.ruta_excel.name, excel)
            for pdf in sorted(self.dir_pdf.glob("*.pdf")):
                zf.write(pdf, f"{self._carpeta_pdf_relativa()}/{pdf.name}")
        return buffer.getvalue()

    # ---------- Escritura ----------
    def guardar(self, acta: Acta, pdf: bytes, nombre_pdf: str) -> ResultadoGuardado:
        acta.fecha_registro = acta.fecha_registro or ahora()
        with _LOCK:
            registros = self._registros()
            buscado = normalizar_numero(acta.numero)
            if any(normalizar_numero(r.numero) == buscado for r in registros):
                raise ActaDuplicadaError(acta.numero)
            try:
                self.dir_pdf.mkdir(parents=True, exist_ok=True)
                ruta_pdf = self.dir_pdf / nombre_pdf
                ruta_pdf.write_bytes(pdf)
                enlace = f"{self._carpeta_pdf_relativa()}/{nombre_pdf}"
                registros.append(registro_desde_acta(acta, nombre_pdf, enlace))
                self._guardar_atomico(construir_libro(registros))
            except PermissionError as exc:
                raise AlmacenamientoError(
                    "No se pudo escribir el Excel maestro. Si está abierto en Excel, ciérralo e "
                    "inténtalo de nuevo."
                ) from exc
            except OSError as exc:
                raise AlmacenamientoError(f"No se pudo guardar el acta: {exc}") from exc
            return ResultadoGuardado(total_actas=len(registros), ubicacion_pdf=str(ruta_pdf))

    # ---------- Internos ----------
    def _registros(self) -> list[Registro]:
        if not self.ruta_excel.exists():
            return []
        ws = load_workbook(self.ruta_excel)[HOJA_ACTAS]
        if es_formato_anterior(ws):
            self._respaldar_formato_anterior()
            return []
        return leer_registros(ws)

    def _respaldar_formato_anterior(self) -> None:
        """El Excel de la versión 0.5 (textos unidos con ' | ') se conserva como respaldo
        y se empieza un Excel maestro nuevo con el formato por columnas."""
        respaldo = self.ruta_excel.with_name(f"actas_maestro_v0.5_respaldo_{ahora():%Y%m%d_%H%M%S}.xlsx")
        os.replace(self.ruta_excel, respaldo)

    def _carpeta_pdf_relativa(self) -> str:
        return Path(os.path.relpath(self.dir_pdf, self.ruta_excel.parent)).as_posix()

    def _guardar_atomico(self, wb: Workbook) -> None:
        """Escribe en un temporal y lo renombra: si algo falla, el Excel anterior queda intacto."""
        self.ruta_excel.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.ruta_excel.parent, suffix=".xlsx")
        os.close(fd)
        try:
            wb.save(tmp)
            os.replace(tmp, self.ruta_excel)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
