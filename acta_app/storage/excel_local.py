"""Excel maestro en disco (data/actas_maestro.xlsx) + PDFs en data/pdfs/."""

from __future__ import annotations

import os
import tempfile
import threading
from pathlib import Path

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.worksheet.worksheet import Worksheet

from acta_app import config
from acta_app.models import Acta, ahora
from acta_app.storage.base import (
    COLUMNAS_ACTAS,
    COLUMNAS_ARTICULOS,
    HOJA_ACTAS,
    HOJA_ARTICULOS,
    TABLA_ACTAS,
    TABLA_ARTICULOS,
    ActaDuplicadaError,
    AlmacenamientoError,
    ResultadoGuardado,
    normalizar_numero,
)

# Streamlit atiende a varios usuarios en hilos del mismo proceso: una escritura a la vez.
_LOCK = threading.Lock()

FORMATO_FECHA = "dd/mm/yyyy"
FORMATO_FECHA_HORA = "dd/mm/yyyy hh:mm:ss AM/PM"

# Ancho (en caracteres) de las columnas; el resto usa ANCHO_POR_DEFECTO.
ANCHOS = {
    "N° de Acta": 14, "Fecha": 12, "Cliente": 30, "Ubicación": 22, "Equipo": 22,
    "Tipo de Servicio": 20, "Antecedentes Iniciales": 45, "Acciones Realizadas": 45,
    "Detalle del Diagnóstico": 45, "Artículos Empleados": 40, "Observaciones": 45,
    "Nombre Representante Sistemas Analíticos": 28, "Fecha de registro": 22,
    "Archivo PDF": 24, "Descripción": 45,
}
ANCHO_POR_DEFECTO = 16
COLUMNAS_TEXTO_LARGO = {
    "Antecedentes Iniciales", "Acciones Realizadas", "Detalle del Diagnóstico",
    "Artículos Empleados", "Observaciones", "Descripción",
}


class RepositorioExcelLocal:
    def __init__(self, ruta_excel: Path = config.EXCEL_MAESTRO_PATH, dir_pdf: Path = config.PDF_DIR):
        self.ruta_excel = Path(ruta_excel)
        self.dir_pdf = Path(dir_pdf)

    # ---------- Lectura ----------
    def existe(self, numero: str) -> bool:
        if not self.ruta_excel.exists():
            return False
        ws = load_workbook(self.ruta_excel, read_only=True)[HOJA_ACTAS]
        buscado = normalizar_numero(numero)
        return any(
            fila[0] is not None and normalizar_numero(str(fila[0])) == buscado
            for fila in ws.iter_rows(min_row=2, max_col=1, values_only=True)
        )

    def leer_actas(self) -> pd.DataFrame:
        if not self.ruta_excel.exists():
            return pd.DataFrame(columns=COLUMNAS_ACTAS)
        return pd.read_excel(self.ruta_excel, sheet_name=HOJA_ACTAS, dtype={"N° de Acta": str})

    def excel_bytes(self) -> bytes | None:
        return self.ruta_excel.read_bytes() if self.ruta_excel.exists() else None

    # ---------- Escritura ----------
    def guardar(self, acta: Acta, pdf: bytes, nombre_pdf: str) -> ResultadoGuardado:
        acta.fecha_registro = acta.fecha_registro or ahora()
        with _LOCK:
            if self.existe(acta.numero):
                raise ActaDuplicadaError(acta.numero)
            try:
                self.dir_pdf.mkdir(parents=True, exist_ok=True)
                ruta_pdf = self.dir_pdf / nombre_pdf
                ruta_pdf.write_bytes(pdf)

                wb = self._abrir_o_crear()
                ws_actas, ws_articulos = wb[HOJA_ACTAS], wb[HOJA_ARTICULOS]
                _agregar_fila(ws_actas, TABLA_ACTAS, COLUMNAS_ACTAS, _fila_acta(acta, nombre_pdf))
                for fila in _filas_articulos(acta):
                    _agregar_fila(ws_articulos, TABLA_ARTICULOS, COLUMNAS_ARTICULOS, fila)
                self._guardar_atomico(wb)
            except PermissionError as exc:
                raise AlmacenamientoError(
                    "No se pudo escribir el Excel maestro. Si está abierto en Excel, ciérralo e "
                    "inténtalo de nuevo."
                ) from exc
            except OSError as exc:
                raise AlmacenamientoError(f"No se pudo guardar el acta: {exc}") from exc
            return ResultadoGuardado(total_actas=ws_actas.max_row - 1, ubicacion_pdf=str(ruta_pdf))

    def _abrir_o_crear(self) -> Workbook:
        if self.ruta_excel.exists():
            return load_workbook(self.ruta_excel)
        wb = Workbook()
        wb.active.title = HOJA_ACTAS
        wb.create_sheet(HOJA_ARTICULOS)
        _preparar_hoja(wb[HOJA_ACTAS], COLUMNAS_ACTAS)
        _preparar_hoja(wb[HOJA_ARTICULOS], COLUMNAS_ARTICULOS)
        return wb

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


# ---------- Filas ----------
def _fila_acta(acta: Acta, nombre_pdf: str) -> dict:
    fila: dict = acta.a_fila()
    # Fechas como fechas reales de Excel (se pueden filtrar y ordenar).
    fila["Fecha"] = acta.fecha
    fila["Fecha de registro"] = acta.fecha_registro
    fila["Archivo PDF"] = nombre_pdf
    return fila


def _filas_articulos(acta: Acta) -> list[dict]:
    return [
        {
            "N° de Acta": acta.numero,
            "Fecha": acta.fecha,
            "Cliente": acta.cliente,
            "Código": art.codigo,
            "Descripción": art.descripcion,
            "Cantidad": art.cantidad,
        }
        for art in acta.articulos_usados
    ]


# ---------- Formato ----------
_ENCABEZADO_FILL = PatternFill("solid", start_color=config.NAVY.lstrip("#"))
_ENCABEZADO_FONT = Font(bold=True, color="FFFFFF")


def _preparar_hoja(ws: Worksheet, columnas: list[str]) -> None:
    ws.append(columnas)
    for i, nombre in enumerate(columnas, start=1):
        celda = ws.cell(row=1, column=i)
        celda.fill, celda.font = _ENCABEZADO_FILL, _ENCABEZADO_FONT
        celda.alignment = Alignment(vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = ANCHOS.get(nombre, ANCHO_POR_DEFECTO)
    ws.freeze_panes = "B2"


def _agregar_fila(ws: Worksheet, nombre_tabla: str, columnas: list[str], fila: dict) -> None:
    ws.append([fila.get(c) for c in columnas])
    n = ws.max_row
    for i, nombre in enumerate(columnas, start=1):
        celda = ws.cell(row=n, column=i)
        celda.alignment = Alignment(vertical="top", wrap_text=nombre in COLUMNAS_TEXTO_LARGO)
        if nombre == "Fecha":
            celda.number_format = FORMATO_FECHA
        elif nombre == "Fecha de registro":
            celda.number_format = FORMATO_FECHA_HORA

    # Tabla de Excel (filtros, estilo y base para la API de Excel de SharePoint).
    rango = f"A1:{get_column_letter(len(columnas))}{n}"
    if nombre_tabla in ws.tables:
        tabla = ws.tables[nombre_tabla]
        tabla.ref = rango
        if tabla.autoFilter is not None:  # una tabla recién creada lo genera al guardar
            tabla.autoFilter.ref = rango
    else:
        tabla = Table(displayName=nombre_tabla, ref=rango)
        tabla.tableStyleInfo = TableStyleInfo(name="TableStyleLight9", showRowStripes=True)
        ws.add_table(tabla)
