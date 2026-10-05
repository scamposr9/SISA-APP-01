"""Contrato común de los lugares donde se guardan las actas (Excel local, SharePoint...)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import pandas as pd

from acta_app.models import Acta, EncuestaSatisfaccion, EnvioEncuesta
from acta_app.storage.esquema import (
    BLOQUE_ENCUESTA,
    COLUMNAS_ENCUESTA,
    COLUMNAS_ENVIO_ENCUESTA,
    COLUMNAS_RESPUESTA_ENCUESTA,
    envio_desde_registro,
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
        el enlace del correo) verifica que el enlace siga vigente. Lanza ActaNoEncontradaError,
        EncuestaYaRespondidaError o EnlaceEncuestaInvalidoError."""
        ...

    def registrar_envio_encuesta(self, numero: str, envio: EnvioEncuesta) -> None:
        """Guarda a qué correo se envió la encuesta, cuándo vence y el hash del código."""
        ...

    def enviar_correo(self, remitente: str, destino: str, asunto: str, html: str) -> None:
        """Envía un correo desde el buzón `remitente` (Microsoft Graph, permiso Mail.Send)."""
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


def poner_envio(registro: Registro, envio: EnvioEncuesta) -> None:
    """Registra (o reemplaza, si se reenvía) la invitación: el enlace anterior deja de valer."""
    if tiene_encuesta(registro):
        raise EncuestaYaRespondidaError(registro.numero)
    envio_cols = BLOQUE_ENCUESTA.valores(Acta(envio_encuesta=envio))[len(COLUMNAS_RESPUESTA_ENCUESTA):]
    registro.valores.update(zip(COLUMNAS_ENVIO_ENCUESTA, envio_cols))


def validar_codigo(registro: Registro, clave_hash: str | None) -> None:
    """Con `clave_hash`, exige que coincida con la invitación vigente del acta."""
    if clave_hash is None:
        return
    envio = envio_desde_registro(registro)
    if envio is None or envio.clave_hash != clave_hash or not envio.vigente():
        raise EnlaceEncuestaInvalidoError(registro.numero)


def normalizar_numero(numero: str) -> str:
    """'2026-00051 ' y '2026-00051' son la misma acta."""
    return "".join(numero.split()).casefold()
