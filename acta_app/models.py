"""Modelo de datos del acta, independiente de Streamlit, del PDF y del Excel."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time

from acta_app.config import TIPO_SERVICIO_OTRO, ZONA_HORARIA


@dataclass
class Articulo:
    codigo: str = ""
    descripcion: str = ""
    cantidad: int | None = None

    @property
    def esta_vacio(self) -> bool:
        return not self.codigo and not self.descripcion and self.cantidad is None

    @property
    def esta_completo(self) -> bool:
        return bool(self.codigo) and bool(self.descripcion) and self.cantidad is not None


@dataclass
class ActividadChecklist:
    """Actividad del protocolo de mantenimiento preventivo, marcada si se realizó."""

    texto: str
    hecha: bool = False

    # En el Excel cada actividad va en una columna de «Acciones Realizadas» con este prefijo.
    MARCA_HECHA, MARCA_PENDIENTE = "[X] ", "[ ] "

    def como_texto(self) -> str:
        return (self.MARCA_HECHA if self.hecha else self.MARCA_PENDIENTE) + self.texto

    @classmethod
    def desde_texto(cls, texto: str) -> ActividadChecklist | None:
        for marca, hecha in ((cls.MARCA_HECHA, True), (cls.MARCA_PENDIENTE, False)):
            if texto.startswith(marca):
                return cls(texto[len(marca):].strip(), hecha)
        return None


@dataclass
class Acta:
    numero: str = ""
    fecha: date | None = None
    cliente: str = ""
    ubicacion: str = ""
    equipo: str = ""
    marca: str = ""
    modelo: str = ""
    numero_serie: str = ""

    tipo_servicio: str | None = None
    tipo_servicio_otro: str = ""  # solo actas anteriores con «Otro: <texto>»

    antecedentes: list[str] = field(default_factory=list)

    hora_inicio_trabajo: time | None = None
    hora_fin_trabajo: time | None = None

    # Mantenimiento preventivo: actividades del protocolo del equipo (ver protocolos.py).
    checklist: list[ActividadChecklist] = field(default_factory=list)
    acciones: list[str] = field(default_factory=list)  # acciones escritas por el ingeniero

    estado_final: str | None = None

    articulos: list[Articulo] = field(default_factory=list)

    observaciones: list[str] = field(default_factory=list)

    nombre_cliente: str = ""
    firma_cliente_png: bytes | None = None
    nombre_representante: str = ""
    firma_representante_png: bytes | None = None

    # Se fija al guardar, para que el PDF y el Excel registren el mismo instante.
    fecha_registro: datetime | None = None

    # ---------- Corrección (revisión 0 = acta original) ----------
    revision: int = 0
    fecha_correccion: datetime | None = None
    corregido_por: str = ""
    motivo_correccion: str = ""

    # ---------- Valores derivados, en el mismo formato que el prototipo ----------
    @property
    def tipo_servicio_texto(self) -> str:
        if self.tipo_servicio == TIPO_SERVICIO_OTRO and self.tipo_servicio_otro:
            return f"{TIPO_SERVICIO_OTRO}: {self.tipo_servicio_otro}"  # actas anteriores
        return self.tipo_servicio or ""

    @property
    def articulos_usados(self) -> list[Articulo]:
        return [a for a in self.articulos if not a.esta_vacio]


def ahora() -> datetime:
    """Fecha y hora actuales en hora de Perú (sin zona, lista para Excel)."""
    return datetime.now(ZONA_HORARIA).replace(tzinfo=None, microsecond=0)


def hoy() -> date:
    return ahora().date()


def formatear_fecha(valor: date | None) -> str:
    return valor.strftime("%d/%m/%Y") if valor else ""


def formatear_hora(valor: time | None) -> str:
    """Formato de 12 horas usado en el prototipo: '08:30 AM'."""
    return valor.strftime("%I:%M %p") if valor else ""
