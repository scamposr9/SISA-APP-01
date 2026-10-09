"""Contrato común de los lugares donde se guardan las actas (Excel local, SharePoint...)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import pandas as pd

from acta_app.preinstalacion import Preinstalacion
from acta_app.models import Acta, AccesoEncuesta, EncuestaSatisfaccion
from acta_app.storage.esquema import (
    BLOQUE_ENCUESTA,
    COLUMNAS_ENCUESTA,
    COLUMNAS_ACCESO_ENCUESTA,
    COLUMNAS_RESPUESTA_ENCUESTA,
    acceso_desde_registro,
    tiene_encuesta,
)

if TYPE_CHECKING:
    from acta_app.storage.esquema import Registro


class ActaDuplicadaError(Exception):
    """Ya existe un acta registrada con el mismo número."""


class ActaNoEncontradaError(Exception):
    """No hay ningún acta registrada con ese número."""


class EncuestaYaRespondidaError(Exception):
    """El acta ya tiene una encuesta de satisfacción registrada."""


class EnlaceEncuestaInvalidoError(Exception):
    """El enlace de la encuesta no es válido, ya venció o fue reemplazado por otro envío."""


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

    def corregir(self, acta: Acta, pdf: bytes, nombre_pdf: str) -> ResultadoGuardado:
        """Actualiza la fila del acta (acta.revision = revisión anterior + 1) y enlaza el
        nuevo PDF, conservando el original."""
        ...

    def numeros(self) -> list[str]: ...

    def obtener(self, numero: str) -> Acta:
        """Acta guardada, con sus firmas. Lanza ActaNoEncontradaError."""
        ...

    def leer_actas(self) -> pd.DataFrame: ...

    def guardar_encuesta(self, numero: str, encuesta: EncuestaSatisfaccion,
                         clave_hash: str | None = None) -> None:
        """Escribe la encuesta en la fila del acta. Con `clave_hash` (encuesta abierta desde
        el QR) verifica que el QR siga vigente. Lanza ActaNoEncontradaError,
        EncuestaYaRespondidaError o EnlaceEncuestaInvalidoError."""
        ...

    def registrar_acceso_encuesta(self, numero: str, acceso: AccesoEncuesta) -> None:
        """Guarda cuándo se generó el QR de la encuesta, cuándo vence y el hash del código.
        Lanza EncuestaYaRespondidaError si la encuesta ya se respondió."""
        ...

    def excel_bytes(self) -> bytes | None:
        """Contenido actual del Excel maestro, para descargarlo desde la app."""
        ...

    def exportar_zip(self) -> bytes | None:
        """Excel maestro + PDFs en un ZIP (con los enlaces del Excel funcionando).
        None si no aplica (en SharePoint los archivos ya están en la carpeta)."""
        ...

    def enlace_carpeta(self) -> str | None:
        """Enlace para abrir la carpeta de actas en el navegador (SharePoint)."""
        ...

    def leer_equipos(self) -> bytes | None:
        """Catálogo de equipos guardado junto a las actas, si existe."""
        ...

    def leer_protocolos(self) -> bytes | None:
        """Mantenimientos Preventivos.xlsx (protocolos por marca/modelo), si existe."""
        ...

    def leer_repuestos(self) -> bytes | None:
        """Repuestos.xlsx (código y descripción de los artículos), si existe."""
        ...

    def leer_nombres_ingenieros(self) -> tuple[list[str], str] | None:
        """Nombres de los ingenieros para el desplegable del representante y de dónde se
        leyeron; None si no hay lista."""
        ...

    def leer_equipos_nuevos(self) -> bytes | None:
        """Equipos_nuevos.xlsx (equipos fuera del catálogo, por revisar), si existe."""
        ...

    def existe_preinstalacion(self, numero: str) -> bool: ...

    def guardar_preinstalacion(self, p: Preinstalacion, pdf: bytes, nombre_pdf: str) -> ResultadoGuardado:
        """Agrega el reporte de preinstalación a su Excel maestro y sube su PDF. Lanza
        ActaDuplicadaError si el N.° ya existe."""
        ...

    def preinstalaciones_bytes(self) -> bytes | None:
        """Contenido del Excel de preinstalaciones, para descargarlo desde la app."""
        ...

    def registrar_balanza(self, acta: Acta, nombre_pdf: str, enlace_pdf: str) -> int:
        """Copia el acta de una balanza (con sus pruebas) a Mantenimientos Balanzas.xlsx; una
        corrección reemplaza su fila. Devuelve el total de actas de balanzas."""
        ...

    def leer_pruebas_balanza(self, numero: str):
        """Pruebas de funcionamiento guardadas de esa acta (para corregirla), o None."""
        ...

    def registrar_equipo_nuevo(self, acta: Acta, registrado_por: str) -> bool:
        """Anota el equipo del acta en Equipos_nuevos.xlsx (lo crea si no existe).
        False si su serie ya estaba anotada."""
        ...


def copiar_encuesta(anterior: Registro, nuevo: Registro) -> None:
    """Una corrección del acta conserva la encuesta ya respondida por el cliente."""
    for columna in COLUMNAS_ENCUESTA:
        if columna in anterior.valores:
            nuevo.valores[columna] = anterior.valores[columna]


def poner_encuesta(registro: Registro, encuesta: EncuestaSatisfaccion) -> None:
    if tiene_encuesta(registro):
        raise EncuestaYaRespondidaError(registro.numero)
    respuesta = BLOQUE_ENCUESTA.valores(Acta(encuesta=encuesta))[: len(COLUMNAS_RESPUESTA_ENCUESTA)]
    registro.valores.update(zip(COLUMNAS_RESPUESTA_ENCUESTA, respuesta))


def poner_acceso(registro: Registro, acceso: AccesoEncuesta) -> None:
    """Registra (o reemplaza, si se genera otro) el QR: el QR anterior deja de valer."""
    if tiene_encuesta(registro):
        raise EncuestaYaRespondidaError(registro.numero)
    columnas = BLOQUE_ENCUESTA.valores(Acta(acceso_encuesta=acceso))[len(COLUMNAS_RESPUESTA_ENCUESTA):]
    registro.valores.update(zip(COLUMNAS_ACCESO_ENCUESTA, columnas))


def validar_codigo(registro: Registro, clave_hash: str | None) -> None:
    """Con `clave_hash`, exige que coincida con el QR vigente del acta."""
    if clave_hash is None:
        return
    acceso = acceso_desde_registro(registro)
    if acceso is None or acceso.clave_hash != clave_hash or not acceso.vigente():
        raise EnlaceEncuestaInvalidoError(registro.numero)


def normalizar_numero(numero: str) -> str:
    """'2026-00051 ' y '2026-00051' son la misma acta."""
    return "".join(numero.split()).casefold()


def fila_balanza(acta: Acta, nombre_pdf: str, enlace_pdf: str) -> dict[str, object]:
    """Fila de Mantenimientos Balanzas.xlsx: las columnas del acta, sus pruebas y el PDF."""
    from acta_app import balanzas
    from acta_app.storage.esquema import COLUMNAS_PDF, fila_plana, registro_desde_acta
    from acta_app.storage.excel_formato import formula_hipervinculo

    fila = {c: v for c, v in fila_plana(registro_desde_acta(acta)).items() if c not in COLUMNAS_PDF}
    fila.update(balanzas.fila_pruebas(acta.pruebas_balanza))
    enlace = formula_hipervinculo(enlace_pdf, nombre_pdf) if enlace_pdf.startswith("http") else None
    fila[balanzas.COLUMNA_PDF] = enlace or nombre_pdf
    return fila
