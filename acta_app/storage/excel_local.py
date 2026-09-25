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
    ActaNoEncontradaError,
    AlmacenamientoError,
    ResultadoGuardado,
    normalizar_numero,
)
from acta_app.storage.esquema import (
    COLUMNA_PDF_CORREGIDO,
    COLUMNA_PDF_ORIGINAL,
    Registro,
    acta_desde_registro,
    disposicion,
    registro_desde_acta,
)
from acta_app.storage.excel_formato import (
    HOJA_ACTAS,
    construir_libro,
    es_formato_anterior,
    leer_registros,
)

# Streamlit atiende a varios usuarios en hilos del mismo proceso: una escritura a la vez.
_LOCK = threading.Lock()


class RepositorioExcelLocal:
    def __init__(
        self,
        ruta_excel: Path = config.EXCEL_MAESTRO_PATH,
        dir_pdf: Path = config.PDF_DIR,
        dir_firmas: Path | None = None,
    ):
        self.ruta_excel = Path(ruta_excel)
        self.dir_pdf = Path(dir_pdf)
        # Firmas en PNG, para reutilizarlas al corregir un acta.
        self.dir_firmas = Path(dir_firmas) if dir_firmas else self.ruta_excel.parent / "firmas"

    # ---------- Lectura ----------
    def existe(self, numero: str) -> bool:
        buscado = normalizar_numero(numero)
        return any(normalizar_numero(r.numero) == buscado for r in self._registros())

    def numeros(self) -> list[str]:
        """Números de acta registrados, del más reciente al más antiguo."""
        return [r.numero for r in reversed(self._registros())]

    def obtener(self, numero: str) -> Acta:
        """Acta guardada (con sus firmas), para cargarla en el formulario de corrección."""
        registro = self._buscar(self._registros(), numero)
        acta = acta_desde_registro(registro)
        acta.firma_cliente_png = self._leer_firma(acta.numero, "cliente")
        acta.firma_representante_png = self._leer_firma(acta.numero, "representante")
        return acta

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
                registro = registro_desde_acta(acta)
                registro.poner_pdf(COLUMNA_PDF_ORIGINAL, nombre_pdf, self._enlace(nombre_pdf))
                registros.append(registro)
                self._guardar_firmas(acta)
                self._guardar_atomico(construir_libro(registros))
            except PermissionError as exc:
                raise AlmacenamientoError(
                    "No se pudo escribir el Excel maestro. Si está abierto en Excel, ciérralo e "
                    "inténtalo de nuevo."
                ) from exc
            except OSError as exc:
                raise AlmacenamientoError(f"No se pudo guardar el acta: {exc}") from exc
            return ResultadoGuardado(total_actas=len(registros), ubicacion_pdf=str(ruta_pdf))

    def corregir(self, acta: Acta, pdf: bytes, nombre_pdf: str) -> ResultadoGuardado:
        """Reemplaza la fila del acta con los datos corregidos. El PDF original se conserva
        y el nuevo (Rev1, Rev2, ...) queda enlazado en «PDF corregido»."""
        with _LOCK:
            registros = self._registros()
            anterior = self._buscar(registros, acta.numero)
            revision_anterior = int(anterior.valores.get("Revisión") or 0)
            if acta.revision != revision_anterior + 1:
                raise AlmacenamientoError(
                    f"El acta N.° {acta.numero} fue corregida por otra persona mientras la "
                    "editabas. Vuelve a cargarla e inténtalo de nuevo."
                )
            try:
                self.dir_pdf.mkdir(parents=True, exist_ok=True)
                ruta_pdf = self.dir_pdf / nombre_pdf
                ruta_pdf.write_bytes(pdf)
                nuevo = registro_desde_acta(acta)
                # Se mantienen el registro original y su PDF.
                nuevo.valores["Fecha de registro"] = anterior.valores.get("Fecha de registro")
                nuevo.poner_pdf(
                    COLUMNA_PDF_ORIGINAL,
                    anterior.valores.get(COLUMNA_PDF_ORIGINAL),
                    anterior.enlaces.get(COLUMNA_PDF_ORIGINAL),
                )
                nuevo.poner_pdf(COLUMNA_PDF_CORREGIDO, nombre_pdf, self._enlace(nombre_pdf))
                registros[registros.index(anterior)] = nuevo
                self._guardar_firmas(acta)
                self._guardar_atomico(construir_libro(registros))
            except PermissionError as exc:
                raise AlmacenamientoError(
                    "No se pudo escribir el Excel maestro. Si está abierto en Excel, ciérralo e "
                    "inténtalo de nuevo."
                ) from exc
            except OSError as exc:
                raise AlmacenamientoError(f"No se pudo guardar la corrección: {exc}") from exc
            return ResultadoGuardado(total_actas=len(registros), ubicacion_pdf=str(ruta_pdf))

    # ---------- Internos ----------
    @staticmethod
    def _buscar(registros: list[Registro], numero: str) -> Registro:
        buscado = normalizar_numero(numero)
        for registro in registros:
            if normalizar_numero(registro.numero) == buscado:
                return registro
        raise ActaNoEncontradaError(numero)

    def _enlace(self, nombre_pdf: str) -> str:
        return f"{self._carpeta_pdf_relativa()}/{nombre_pdf}"

    def _ruta_firma(self, numero: str, quien: str) -> Path:
        seguro = "".join(ch if ch.isalnum() or ch == "-" else "_" for ch in numero)
        return self.dir_firmas / f"{seguro}_{quien}.png"

    def _leer_firma(self, numero: str, quien: str) -> bytes | None:
        ruta = self._ruta_firma(numero, quien)
        return ruta.read_bytes() if ruta.exists() else None

    def _guardar_firmas(self, acta: Acta) -> None:
        self.dir_firmas.mkdir(parents=True, exist_ok=True)
        for quien, png in (("cliente", acta.firma_cliente_png), ("representante", acta.firma_representante_png)):
            if png:
                self._ruta_firma(acta.numero, quien).write_bytes(png)

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
