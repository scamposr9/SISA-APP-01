"""QR de la encuesta de satisfacción, que el ingeniero muestra al cliente al terminar el acta.

El QR lleva un enlace con un código aleatorio (imposible de adivinar) que abre la encuesta
sin iniciar sesión. En Actas.xlsx solo se guardan su hash SHA-256 y la fecha de vencimiento:
quien vea el Excel no puede armar el enlace. Vale 24 horas y una sola vez (al responder, la
encuesta queda cerrada). Generar otro QR para la misma acta anula el anterior.
"""

from __future__ import annotations

import hashlib
import io
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from PIL import Image, ImageDraw
from reportlab.graphics.barcode.qr import QrCodeWidget

from acta_app import config
from acta_app.models import AccesoEncuesta, ahora


def hash_codigo(codigo: str) -> str:
    return hashlib.sha256(codigo.encode()).hexdigest()


def nuevo_acceso() -> tuple[AccesoEncuesta, str]:
    """(datos del QR para el Excel, código para el enlace)."""
    codigo = secrets.token_urlsafe(32)
    generado = ahora()
    acceso = AccesoEncuesta(
        generado=generado,
        vence=generado + timedelta(hours=config.HORAS_VIGENCIA_ENCUESTA),
        clave_hash=hash_codigo(codigo),
    )
    return acceso, codigo


def enlace_encuesta(url_app: str, numero: str, codigo: str) -> str:
    return f"{url_app.rstrip('/')}/?{urlencode({'encuesta': numero, 't': codigo})}"


def imagen_qr(texto: str, pixeles_por_modulo: int = 10, margen: int = 4) -> bytes:
    """PNG del QR (negro sobre blanco, con el margen que piden los lectores)."""
    widget = QrCodeWidget(texto, barLevel="M")
    widget.draw()  # arma la matriz (elige la versión según el largo del texto)
    qr = widget.qr
    n = qr.getModuleCount()
    lado = (n + 2 * margen) * pixeles_por_modulo
    imagen = Image.new("1", (lado, lado), 1)
    dibujo = ImageDraw.Draw(imagen)
    for fila in range(n):
        for col in range(n):
            if qr.isDark(fila, col):
                x, y = (col + margen) * pixeles_por_modulo, (fila + margen) * pixeles_por_modulo
                dibujo.rectangle([x, y, x + pixeles_por_modulo - 1, y + pixeles_por_modulo - 1], fill=0)
    salida = io.BytesIO()
    imagen.save(salida, format="PNG")
    return salida.getvalue()


def generar_qr(repo, numero: str, url_app: str) -> tuple[AccesoEncuesta, str]:
    """Registra un QR nuevo para el acta en Actas.xlsx (el anterior, si había, deja de valer)
    y devuelve (datos del QR, enlace que lleva). Lanza los errores del repositorio
    (EncuestaYaRespondidaError, AlmacenamientoError, ActaNoEncontradaError)."""
    acceso, codigo = nuevo_acceso()
    repo.registrar_acceso_encuesta(numero, acceso)
    return acceso, enlace_encuesta(url_app, numero, codigo)
