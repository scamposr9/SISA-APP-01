"""Borrador del acta que se está llenando, guardado automáticamente para no perderlo si se
cae la conexión, se bloquea el celular o la app se reinicia.

Hay un borrador por usuario (su cuenta de Microsoft), en JSON. Las firmas NO se guardan:
al recuperar un borrador, el cliente y el representante firman de nuevo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, time

from acta_app import preinstalacion as pre
from acta_app.models import Acta, ActividadChecklist, Articulo, ahora
from acta_app.preinstalacion import Preinstalacion

VERSION = 1


@dataclass
class Borrador:
    acta: Acta
    guardado: datetime
    # Actividades del checklist que el ingeniero quitó con × (protocolos repetidos).
    quitadas: list[str] = field(default_factory=list)
    preinstalacion: Preinstalacion | None = None  # apartados de Presite, si se eligió

    @property
    def tiene_datos(self) -> bool:
        return tiene_datos(self.acta)


def tiene_datos(acta: Acta) -> bool:
    """¿Se escribió algo además de la fecha (que ya viene puesta)?"""
    a = acta
    return any((
        a.numero, a.cliente, a.ubicacion, a.equipo, a.marca, a.modelo, a.numero_serie, a.tipo_servicio,
        a.antecedentes, a.hora_inicio_trabajo, a.hora_fin_trabajo, a.acciones, a.estado_final,
        a.articulos_usados, a.observaciones, a.nombre_cliente, a.nombre_representante,
        any(c.hecha for c in a.checklist),
    ))


def _hora(valor: time | None) -> str | None:
    return valor.strftime("%H:%M") if valor else None


def huella(acta: Acta, quitadas: list[str] | None = None) -> str:
    """Resumen del contenido (sin la hora): si no cambia, no hace falta volver a subirlo."""
    return json.dumps(_datos(acta, quitadas), ensure_ascii=False, sort_keys=True)


def a_json(acta: Acta, quitadas: list[str] | None = None) -> bytes:
    """Datos del formulario (sin firmas) en JSON."""
    datos = {"version": VERSION, "guardado": ahora().isoformat(), **_datos(acta, quitadas)}
    return json.dumps(datos, ensure_ascii=False).encode()


def _datos(acta: Acta, quitadas: list[str] | None) -> dict:
    return {
        "numero": acta.numero,
        "fecha": acta.fecha.isoformat() if acta.fecha else None,
        "ubicacion": acta.ubicacion,
        "cliente": acta.cliente,
        "equipo": acta.equipo,
        "marca": acta.marca,
        "modelo": acta.modelo,
        "numero_serie": acta.numero_serie,
        "tipo_servicio": acta.tipo_servicio,
        "antecedentes": acta.antecedentes,
        "hora_inicio_trabajo": _hora(acta.hora_inicio_trabajo),
        "hora_fin_trabajo": _hora(acta.hora_fin_trabajo),
        "checklist": [[c.texto, c.hecha] for c in acta.checklist],
        "acciones": acta.acciones,
        "estado_final": acta.estado_final,
        "articulos": [[a.codigo, a.descripcion, a.cantidad] for a in acta.articulos if not a.esta_vacio],
        "observaciones": acta.observaciones,
        "nombre_cliente": acta.nombre_cliente,
        "nombre_representante": acta.nombre_representante,
        "quitadas": list(quitadas or []),
        "preinstalacion": pre.a_dict(acta.preinstalacion) if acta.preinstalacion is not None else None,
    }


def desde_json(contenido: bytes) -> Borrador | None:
    """Borrador guardado, o None si el archivo no se puede leer."""
    try:
        d = json.loads(contenido)

        def hora(valor: str | None) -> time | None:
            return time.fromisoformat(valor) if valor else None

        acta = Acta(
            numero=d.get("numero") or "",
            fecha=date.fromisoformat(d["fecha"]) if d.get("fecha") else None,
            ubicacion=d.get("ubicacion") or "",
            cliente=d.get("cliente") or "",
            equipo=d.get("equipo") or "",
            marca=d.get("marca") or "",
            modelo=d.get("modelo") or "",
            numero_serie=d.get("numero_serie") or "",
            tipo_servicio=d.get("tipo_servicio"),
            antecedentes=list(d.get("antecedentes") or []),
            hora_inicio_trabajo=hora(d.get("hora_inicio_trabajo")),
            hora_fin_trabajo=hora(d.get("hora_fin_trabajo")),
            checklist=[ActividadChecklist(t, bool(h)) for t, h in d.get("checklist") or []],
            acciones=list(d.get("acciones") or []),
            estado_final=d.get("estado_final"),
            articulos=[Articulo(c or "", s or "", q) for c, s, q in d.get("articulos") or []],
            observaciones=list(d.get("observaciones") or []),
            nombre_cliente=d.get("nombre_cliente") or "",
            nombre_representante=d.get("nombre_representante") or "",
        )
        presite = pre.desde_dict(d["preinstalacion"]) if d.get("preinstalacion") else None
        return Borrador(acta, datetime.fromisoformat(d["guardado"]), list(d.get("quitadas") or []), presite)
    except (ValueError, KeyError, TypeError):
        return None
