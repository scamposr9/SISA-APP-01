"""Actas en SharePoint: Excel maestro (Actas.xlsx), PDFs, firmas y catálogo de equipos.

Estructura en la carpeta configurada (por defecto «16. Analisis de Datos/Actas»):

    Actas.xlsx        Excel maestro (lo crea la app al guardar la primera acta)
    Equipos.xlsx      catálogo para el autocompletado (lo mantiene el equipo)
    PDF/              un PDF por acta y por revisión
    Firmas/<N.°>/     cliente.png y representante.png de cada acta (para corregirla)

`RepositorioSharePoint` solo necesita un `AlmacenArchivos` (leer/escribir archivos con
control de versión). `AlmacenGraph` lo implementa con Microsoft Graph usando la
identidad de la app registrada en Entra ID (permiso de aplicación Sites.Selected).
"""

from __future__ import annotations

import io
import threading
import time
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote, unquote, urlparse

import pandas as pd
from openpyxl import load_workbook

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
from acta_app.storage.excel_formato import HOJA_ACTAS, construir_libro, leer_registros

CARPETA_FIRMAS = "Firmas"
INTENTOS_POR_CONFLICTO = 4


# ---------- Contrato del almacén de archivos ----------
class ConflictoDeVersion(Exception):
    """El archivo cambió desde que se leyó (otro ingeniero guardó al mismo tiempo)."""


@dataclass
class Archivo:
    datos: bytes
    version: str  # eTag de SharePoint
    enlace: str  # URL para abrirlo en el navegador


class AlmacenArchivos(Protocol):
    def leer(self, ruta: str) -> Archivo | None:
        """Contenido y versión del archivo, o None si no existe."""
        ...

    def escribir(self, ruta: str, datos: bytes, version_esperada: str | None = None,
                 solo_si_no_existe: bool = False) -> str:
        """Crea o reemplaza el archivo y devuelve su enlace. Con `version_esperada` (o
        `solo_si_no_existe`) lanza ConflictoDeVersion si alguien lo cambió antes."""
        ...

    def eliminar(self, ruta: str) -> None: ...

    def enlace(self, ruta: str) -> str | None:
        """Enlace para abrir un archivo o carpeta en el navegador (None si no existe)."""
        ...


# ---------- Repositorio ----------
class RepositorioSharePoint:
    def __init__(
        self,
        almacen: AlmacenArchivos,
        carpeta: str = config.SHAREPOINT_CARPETA,
        excel: str = config.SHAREPOINT_EXCEL,
        carpeta_pdf: str = config.SHAREPOINT_CARPETA_PDF,
        equipos: str = config.SHAREPOINT_EQUIPOS,
        segundos_cache: float = 30,
    ):
        self.almacen = almacen
        self.carpeta = carpeta.strip("/")
        self.ruta_excel = f"{self.carpeta}/{excel}"
        self.ruta_pdf = f"{self.carpeta}/{carpeta_pdf}"
        self.ruta_firmas = f"{self.carpeta}/{CARPETA_FIRMAS}"
        self.ruta_equipos = f"{self.carpeta}/{equipos}"
        # La app vuelve a dibujarse con cada cambio en el formulario: se evita descargar
        # el Excel en cada una. Al guardar siempre se lee la versión más reciente.
        self._segundos_cache = segundos_cache
        self._cache: tuple[float, Archivo | None] | None = None
        self._lock = threading.Lock()

    # ---------- Lectura ----------
    def existe(self, numero: str) -> bool:
        buscado = normalizar_numero(numero)
        return any(normalizar_numero(r.numero) == buscado for r in self._registros())

    def numeros(self) -> list[str]:
        return [r.numero for r in reversed(self._registros())]

    def obtener(self, numero: str) -> Acta:
        registro = _buscar(self._registros(fresco=True), numero)
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
        archivo = self._excel()
        return archivo.datos if archivo else None

    def exportar_zip(self) -> bytes | None:
        return None  # los PDF ya están en SharePoint: se abren desde el enlace de la carpeta

    def enlace_carpeta(self) -> str | None:
        return self.almacen.enlace(self.carpeta)

    def enlace_excel(self) -> str | None:
        archivo = self._excel()
        return archivo.enlace if archivo else None

    def leer_equipos(self) -> bytes | None:
        """Catálogo Equipos.xlsx para el autocompletado (None si aún no está en la carpeta)."""
        archivo = self.almacen.leer(self.ruta_equipos)
        return archivo.datos if archivo else None

    # ---------- Escritura ----------
    def guardar(self, acta: Acta, pdf: bytes, nombre_pdf: str) -> ResultadoGuardado:
        acta.fecha_registro = acta.fecha_registro or ahora()
        with self._lock:
            archivos_subidos = False
            enlace_pdf = ""
            for _ in range(INTENTOS_POR_CONFLICTO):
                excel = self._excel(fresco=True)
                registros = self._leer(excel)
                buscado = normalizar_numero(acta.numero)
                if any(normalizar_numero(r.numero) == buscado for r in registros):
                    raise ActaDuplicadaError(acta.numero)
                if not archivos_subidos:
                    enlace_pdf = self._subir(f"{self.ruta_pdf}/{nombre_pdf}", pdf)
                    self._subir_firmas(acta)
                    archivos_subidos = True
                registro = registro_desde_acta(acta)
                registro.poner_pdf(COLUMNA_PDF_ORIGINAL, nombre_pdf, enlace_pdf)
                registros.append(registro)
                if self._escribir_excel(registros, excel):
                    return ResultadoGuardado(total_actas=len(registros), ubicacion_pdf=enlace_pdf)
            raise AlmacenamientoError(_MENSAJE_CONFLICTO)

    def corregir(self, acta: Acta, pdf: bytes, nombre_pdf: str) -> ResultadoGuardado:
        with self._lock:
            archivos_subidos = False
            enlace_pdf = ""
            for _ in range(INTENTOS_POR_CONFLICTO):
                excel = self._excel(fresco=True)
                registros = self._leer(excel)
                anterior = _buscar(registros, acta.numero)
                if acta.revision != int(anterior.valores.get("Revisión") or 0) + 1:
                    raise AlmacenamientoError(
                        f"El acta N.° {acta.numero} fue corregida por otra persona mientras la "
                        "editabas. Vuelve a cargarla e inténtalo de nuevo."
                    )
                if not archivos_subidos:
                    enlace_pdf = self._subir(f"{self.ruta_pdf}/{nombre_pdf}", pdf)
                    self._subir_firmas(acta)
                    archivos_subidos = True
                nuevo = registro_desde_acta(acta)
                nuevo.valores["Fecha de registro"] = anterior.valores.get("Fecha de registro")
                nuevo.poner_pdf(
                    COLUMNA_PDF_ORIGINAL,
                    anterior.valores.get(COLUMNA_PDF_ORIGINAL),
                    anterior.enlaces.get(COLUMNA_PDF_ORIGINAL),
                )
                nuevo.poner_pdf(COLUMNA_PDF_CORREGIDO, nombre_pdf, enlace_pdf)
                registros[registros.index(anterior)] = nuevo
                if self._escribir_excel(registros, excel):
                    return ResultadoGuardado(total_actas=len(registros), ubicacion_pdf=enlace_pdf)
            raise AlmacenamientoError(_MENSAJE_CONFLICTO)

    # ---------- Diagnóstico ----------
    def probar_conexion(self) -> list[tuple[bool, str]]:
        """Pasos de verificación (ok, mensaje) para mostrarlos en la app."""
        pasos: list[tuple[bool, str]] = []
        try:
            enlace = self.almacen.enlace(self.carpeta)
        except AlmacenamientoError as exc:
            return [(False, str(exc))]
        if not enlace:
            return [(False, f"No se encontró la carpeta «{self.carpeta}» en la biblioteca.")]
        pasos.append((True, f"Carpeta encontrada: {self.carpeta}"))
        pasos.append((
            bool(self.almacen.enlace(self.ruta_pdf)),
            f"Subcarpeta «{self.ruta_pdf.rsplit('/', 1)[-1]}»"
            + (" encontrada" if self.almacen.enlace(self.ruta_pdf) else " no existe (se creará al guardar)"),
        ))
        prueba = f"{self.carpeta}/_prueba_conexion_app.txt"
        try:
            self.almacen.escribir(prueba, f"Prueba de escritura {ahora():%d/%m/%Y %H:%M}".encode())
            self.almacen.eliminar(prueba)
            pasos.append((True, "La app puede escribir en la carpeta."))
        except AlmacenamientoError as exc:
            pasos.append((False, f"La app NO puede escribir: {exc}"))
        excel = self.almacen.leer(self.ruta_excel)
        pasos.append((True, "Actas.xlsx encontrado." if excel else "Actas.xlsx aún no existe (se creará al guardar la primera acta)."))
        pasos.append((
            bool(self.almacen.enlace(self.ruta_equipos)),
            "Equipos.xlsx encontrado (autocompletado desde SharePoint)."
            if self.almacen.enlace(self.ruta_equipos)
            else "Equipos.xlsx no está en la carpeta: el autocompletado de equipos queda vacío.",
        ))
        return pasos

    # ---------- Internos ----------
    def _excel(self, fresco: bool = False) -> Archivo | None:
        ahora_s = time.monotonic()
        if not fresco and self._cache and ahora_s - self._cache[0] < self._segundos_cache:
            return self._cache[1]
        archivo = self.almacen.leer(self.ruta_excel)
        self._cache = (ahora_s, archivo)
        return archivo

    def _registros(self, fresco: bool = False) -> list[Registro]:
        return self._leer(self._excel(fresco))

    @staticmethod
    def _leer(archivo: Archivo | None) -> list[Registro]:
        if archivo is None:
            return []
        return leer_registros(load_workbook(io.BytesIO(archivo.datos))[HOJA_ACTAS])

    def _escribir_excel(self, registros: list[Registro], anterior: Archivo | None) -> bool:
        """Sube el Excel solo si nadie lo cambió desde que se leyó. False = reintentar."""
        buffer = io.BytesIO()
        construir_libro(registros).save(buffer)
        try:
            self.almacen.escribir(
                self.ruta_excel,
                buffer.getvalue(),
                version_esperada=anterior.version if anterior else None,
                solo_si_no_existe=anterior is None,
            )
        except ConflictoDeVersion:
            self._cache = None
            return False
        self._cache = None
        return True

    def _subir(self, ruta: str, datos: bytes) -> str:
        return self.almacen.escribir(ruta, datos) or self.almacen.enlace(ruta) or ""

    def _ruta_firma(self, numero: str, quien: str) -> str:
        """Firmas/<N.°>/cliente.png: una subcarpeta por acta."""
        return f"{self.ruta_firmas}/{_nombre_seguro(numero)}/{quien}.png"

    def _ruta_firma_anterior(self, numero: str, quien: str) -> str:
        """Formato hasta la versión 0.15: todas sueltas en Firmas/ (<N.°>_cliente.png)."""
        return f"{self.ruta_firmas}/{_nombre_seguro(numero)}_{quien}.png"

    def _leer_firma(self, numero: str, quien: str) -> bytes | None:
        archivo = self.almacen.leer(self._ruta_firma(numero, quien))
        if archivo:
            return archivo.datos
        return self._mover_firma_anterior(numero, quien)

    def _mover_firma_anterior(self, numero: str, quien: str) -> bytes | None:
        """Si la firma está en el formato anterior, la pasa a la subcarpeta del acta."""
        anterior = self._ruta_firma_anterior(numero, quien)
        archivo = self.almacen.leer(anterior)
        if archivo is None:
            return None
        self._subir(self._ruta_firma(numero, quien), archivo.datos)
        self.almacen.eliminar(anterior)
        return archivo.datos

    def ordenar_firmas(self) -> int:
        """Pasa las firmas sueltas de las actas registradas a Firmas/<N.°>/. Devuelve
        cuántos archivos movió."""
        movidas = 0
        with self._lock:
            for numero in self.numeros():
                for quien in ("cliente", "representante"):
                    if self.almacen.leer(self._ruta_firma(numero, quien)) is None:
                        movidas += self._mover_firma_anterior(numero, quien) is not None
        return movidas

    def _subir_firmas(self, acta: Acta) -> None:
        for quien, png in (("cliente", acta.firma_cliente_png), ("representante", acta.firma_representante_png)):
            if png:
                self._subir(self._ruta_firma(acta.numero, quien), png)


_MENSAJE_CONFLICTO = (
    "No se pudo actualizar Actas.xlsx porque está cambiando constantemente (otra persona "
    "guardando o editándolo). Espera unos segundos e inténtalo de nuevo."
)


def _buscar(registros: list[Registro], numero: str) -> Registro:
    buscado = normalizar_numero(numero)
    for registro in registros:
        if normalizar_numero(registro.numero) == buscado:
            return registro
    raise ActaNoEncontradaError(numero)


# ---------- Microsoft Graph ----------
GRAPH = "https://graph.microsoft.com/v1.0"


class AlmacenGraph:
    """Archivos de una biblioteca de SharePoint vía Microsoft Graph (identidad de la app)."""

    def __init__(self, tenant_id: str, client_id: str, client_secret: str,
                 sitio_url: str = config.SHAREPOINT_SITIO,
                 biblioteca: str = config.SHAREPOINT_BIBLIOTECA,
                 sesion=None):
        import requests

        self._credenciales = (tenant_id, client_id, client_secret)
        self._msal = None  # se crea al pedir el primer token (msal consulta a Microsoft)
        self._http = sesion or requests.Session()
        self.sitio_url = sitio_url
        self.biblioteca = biblioteca
        self._drive_id: str | None = None

    # ---------- Contrato ----------
    def leer(self, ruta: str) -> Archivo | None:
        item = self._item(ruta)
        if item is None:
            return None
        respuesta = self._pedir("GET", f"{self._raiz()}/items/{item['id']}/content")
        return Archivo(datos=respuesta.content, version=item.get("eTag", ""), enlace=item.get("webUrl", ""))

    def escribir(self, ruta: str, datos: bytes, version_esperada: str | None = None,
                 solo_si_no_existe: bool = False) -> str:
        cabeceras = {"Content-Type": "application/octet-stream"}
        if version_esperada:
            cabeceras["If-Match"] = version_esperada
        parametros = {"@microsoft.graph.conflictBehavior": "fail"} if solo_si_no_existe else None
        respuesta = self._pedir(
            "PUT", f"{self._raiz()}/root:/{_ruta_url(ruta)}:/content",
            data=datos, headers=cabeceras, params=parametros,
            conflictos=(409, 412),
        )
        return respuesta.json().get("webUrl", "")

    def eliminar(self, ruta: str) -> None:
        item = self._item(ruta)
        if item is not None:
            self._pedir("DELETE", f"{self._raiz()}/items/{item['id']}")

    def enlace(self, ruta: str) -> str | None:
        item = self._item(ruta)
        return item.get("webUrl") if item else None

    # ---------- Internos ----------
    def _token(self) -> str:
        tenant_id, client_id, client_secret = self._credenciales
        try:
            if self._msal is None:
                import msal

                self._msal = msal.ConfidentialClientApplication(
                    client_id,
                    authority=f"https://login.microsoftonline.com/{tenant_id}",
                    client_credential=client_secret,
                )
            resultado = self._msal.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        except Exception as exc:  # tenant inválido, sin conexión con Microsoft, etc.
            raise AlmacenamientoError(
                f"No se pudo conectar con Microsoft para iniciar sesión: {exc}. "
                "Revisa el tenant_id en los Secrets de Streamlit."
            ) from exc
        if "access_token" not in resultado:
            detalle = (resultado.get("error_description") or resultado.get("error") or "").splitlines()
            raise AlmacenamientoError(
                "No se pudo iniciar sesión en Microsoft con las claves de la app"
                f"{f' ({detalle[0]})' if detalle else ''}. "
                "Revisa tenant_id, client_id y client_secret en los Secrets de Streamlit."
            )
        return resultado["access_token"]

    def _pedir(self, metodo: str, url: str, conflictos: tuple[int, ...] = (), **kwargs):
        cabeceras = {"Authorization": f"Bearer {self._token()}", **kwargs.pop("headers", {})}
        for intento in range(4):
            try:
                respuesta = self._http.request(metodo, url, headers=cabeceras, timeout=60, **kwargs)
            except Exception as exc:  # sin conexión, DNS, timeout...
                raise AlmacenamientoError(f"No se pudo conectar con SharePoint: {exc}") from exc
            if respuesta.status_code in (429, 503, 504) and intento < 3:
                time.sleep(min(float(respuesta.headers.get("Retry-After", 2 ** intento)), 10))
                continue
            break
        if respuesta.status_code in conflictos:
            raise ConflictoDeVersion(url)
        if respuesta.status_code == 404:
            raise _NoEncontrado(url)
        if respuesta.status_code == 423:
            raise AlmacenamientoError(
                "SharePoint tiene el archivo bloqueado (alguien lo está editando en Excel). "
                "Espera unos segundos e inténtalo de nuevo."
            )
        if respuesta.status_code in (401, 403):
            raise AlmacenamientoError(
                "SharePoint rechazó el acceso de la app (HTTP "
                f"{respuesta.status_code}). Verifica que TI haya dado a «{config.AZURE_APP_NOMBRE}» "
                "permiso de escritura sobre el sitio (Sites.Selected → asignación del sitio)."
            )
        if respuesta.status_code >= 400:
            raise AlmacenamientoError(
                f"Error de SharePoint (HTTP {respuesta.status_code}): {respuesta.text[:300]}"
            )
        return respuesta

    def _raiz(self) -> str:
        return f"{GRAPH}/drives/{self._drive()}"

    def _drive(self) -> str:
        if self._drive_id:
            return self._drive_id
        partes = urlparse(self.sitio_url)
        sitio = self._pedir("GET", f"{GRAPH}/sites/{partes.hostname}:{partes.path.rstrip('/')}").json()
        drives = self._pedir("GET", f"{GRAPH}/sites/{sitio['id']}/drives").json().get("value", [])
        buscada = self.biblioteca.casefold()
        for drive in drives:
            ruta_web = unquote(urlparse(drive.get("webUrl", "")).path).rstrip("/").casefold()
            if drive.get("name", "").casefold() == buscada or ruta_web.endswith("/" + buscada):
                self._drive_id = drive["id"]
                return self._drive_id
        nombres = ", ".join(d.get("name", "?") for d in drives) or "ninguna"
        raise AlmacenamientoError(
            f"No se encontró la biblioteca «{self.biblioteca}» en el sitio (disponibles: {nombres})."
        )

    def _item(self, ruta: str) -> dict | None:
        try:
            return self._pedir("GET", f"{self._raiz()}/root:/{_ruta_url(ruta)}").json()
        except _NoEncontrado:
            return None


class _NoEncontrado(AlmacenamientoError):
    pass


def _nombre_seguro(numero: str) -> str:
    """N.° de acta apto para nombre de archivo o carpeta."""
    return "".join(ch if ch.isalnum() or ch == "-" else "_" for ch in numero)


def _ruta_url(ruta: str) -> str:
    return quote(ruta.strip("/"), safe="/")
