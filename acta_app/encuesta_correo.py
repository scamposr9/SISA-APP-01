"""Invitación a la encuesta de satisfacción por correo, con un enlace de un solo uso.

El enlace lleva un código aleatorio (imposible de adivinar). En Actas.xlsx solo se guarda su
hash SHA-256, el correo y la fecha de vencimiento: quien vea el Excel no puede armar el
enlace. Un reenvío genera otro código y el anterior deja de valer.
"""

from __future__ import annotations

import hashlib
import html
import re
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from acta_app import config
from acta_app.models import Acta, EnvioEncuesta, ahora, formatear_fecha

_FORMATO_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.IGNORECASE)
# Errores de tipeo frecuentes en dominios de correo.
_DOMINIOS_PARECIDOS = {
    "gmial.com": "gmail.com", "gamil.com": "gmail.com", "gmail.co": "gmail.com", "gmai.com": "gmail.com",
    "gmail.con": "gmail.com", "hotmial.com": "hotmail.com", "hotmail.co": "hotmail.com",
    "hotmal.com": "hotmail.com", "hotmail.con": "hotmail.com", "outlok.com": "outlook.com",
    "outllok.com": "outlook.com", "yaho.com": "yahoo.com", "yahoo.con": "yahoo.com",
}


def normalizar_correo(correo: str) -> str:
    return "".join(correo.split()).lower()


def errores_correo(correo: str, confirmacion: str) -> list[str]:
    """Problemas del correo del cliente (vacío = sin errores). El correo es opcional."""
    correo, confirmacion = normalizar_correo(correo), normalizar_correo(confirmacion)
    if not correo and not confirmacion:
        return []
    if not _FORMATO_CORREO.match(correo):
        return ["Correo del cliente (formato no válido)"]
    if correo != confirmacion:
        return ["Correo del cliente (los dos correos no coinciden)"]
    if correo.endswith("@" + config.DOMINIO_EMPRESA):
        return ["Correo del cliente (no puede ser un correo de Sistemas Analíticos)"]
    return []


def sugerencia_correo(correo: str) -> str | None:
    """'ana@gmial.com' -> 'ana@gmail.com' si el dominio parece mal escrito."""
    usuario, _, dominio = normalizar_correo(correo).partition("@")
    corregido = _DOMINIOS_PARECIDOS.get(dominio)
    return f"{usuario}@{corregido}" if corregido else None


def hash_codigo(codigo: str) -> str:
    return hashlib.sha256(codigo.encode()).hexdigest()


def nuevo_envio(correo: str) -> tuple[EnvioEncuesta, str]:
    """(datos del envío para el Excel, código para el enlace)."""
    codigo = secrets.token_urlsafe(32)
    enviada = ahora()
    envio = EnvioEncuesta(
        correo=normalizar_correo(correo),
        enviada=enviada,
        vence=enviada + timedelta(hours=config.HORAS_VIGENCIA_ENCUESTA),
        clave_hash=hash_codigo(codigo),
    )
    return envio, codigo


def enlace_encuesta(url_app: str, numero: str, codigo: str) -> str:
    return f"{url_app.rstrip('/')}/?{urlencode({'encuesta': numero, 't': codigo})}"


def asunto(acta: Acta) -> str:
    return f"Encuesta de satisfacción del servicio – Acta N.° {acta.numero} – {config.EMPRESA}"


def cuerpo_html(acta: Acta, enlace: str, envio: EnvioEncuesta) -> str:
    """Correo breve: solo lo necesario para que el cliente reconozca el servicio."""
    e = html.escape
    datos = [("N.° de acta", acta.numero), ("Fecha", formatear_fecha(acta.fecha)), ("Equipo", acta.equipo),
             ("Servicio", acta.tipo_servicio_texto)]
    filas = "".join(
        f"<tr><td style='padding:2px 12px 2px 0;color:#555'>{e(k)}</td><td><b>{e(v)}</b></td></tr>"
        for k, v in datos if v
    )
    return f"""\
<div style="font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#1A1A1A;max-width:560px">
  <p>Estimado(a) {e(acta.nombre_cliente or 'cliente')}:</p>
  <p>Gracias por confiar en <b>{e(config.EMPRESA)}</b>. Nos ayudaría mucho conocer su opinión sobre
  el servicio recibido. La encuesta toma menos de un minuto.</p>
  <table style="border-collapse:collapse;margin:8px 0 16px">{filas}</table>
  <p><a href="{e(enlace)}" style="background:{config.NAVY};color:#fff;padding:10px 18px;border-radius:6px;
  text-decoration:none;display:inline-block">Responder la encuesta</a></p>
  <p style="color:#555;font-size:12px">El enlace es personal, se puede usar una sola vez y vence el
  {envio.vence:%d/%m/%Y a las %H:%M} (hora de Perú). Si usted no recibió este servicio, ignore este
  correo.</p>
  <p style="color:#555;font-size:12px">Este es un mensaje automático; por favor no responda a este
  correo.<br>{e(config.EMPRESA)} · {e(config.SITIO_WEB)}</p>
</div>"""


def enviar_invitacion(repo, acta: Acta, correo: str, remitente: str, url_app: str) -> EnvioEncuesta:
    """Registra el envío en Actas.xlsx (el enlace anterior, si había, deja de valer) y envía
    el correo. Lanza los errores del repositorio (AlmacenamientoError, etc.)."""
    envio, codigo = nuevo_envio(correo)
    repo.registrar_envio_encuesta(acta.numero, envio)
    repo.enviar_correo(remitente, envio.correo, asunto(acta),
                       cuerpo_html(acta, enlace_encuesta(url_app, acta.numero, codigo), envio))
    return envio
