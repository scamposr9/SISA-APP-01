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
    tipo_servicio_otro: str = ""

    antecedentes: list[str] = field(default_factory=list)

    hora_inicio_traslado: time | None = None
    hora_fin_traslado: time | None = None
    hora_inicio_trabajo: time | None = None
    hora_fin_trabajo: time | None = None

    acciones: list[str] = field(default_factory=list)
    diagnostico: list[str] = field(default_factory=list)

    estado_final: str | None = None

    articulos: list[Articulo] = field(default_factory=list)

    observaciones: list[str] = field(default_factory=list)

    nombre_cliente: str = ""
    firma_cliente_png: bytes | None = None
    nombre_representante: str = ""
    firma_representante_png: bytes | None = None

    # Se fija al guardar, para que el PDF y el Excel registren el mismo instante.
    fecha_registro: datetime | None = None

    # ---------- Valores derivados, en el mismo formato que el prototipo ----------
    @property
    def tipo_servicio_texto(self) -> str:
        if self.tipo_servicio == TIPO_SERVICIO_OTRO and self.tipo_servicio_otro:
            return f"{TIPO_SERVICIO_OTRO}: {self.tipo_servicio_otro}"
        return self.tipo_servicio or ""

    @property
    def articulos_usados(self) -> list[Articulo]:
        return [a for a in self.articulos if not a.esta_vacio]

    def a_fila(self) -> dict[str, str]:
        """Convierte el acta en una fila (columna -> valor) para el Excel maestro."""
        return {
            "N° de Acta": self.numero,
            "Fecha": formatear_fecha(self.fecha),
            "Cliente": self.cliente,
            "Ubicación": self.ubicacion,
            "Equipo": self.equipo,
            "Marca": self.marca,
            "Modelo": self.modelo,
            "N° Serie": self.numero_serie,
            "Tipo de Servicio": self.tipo_servicio_texto,
            "Antecedentes Iniciales": unir_puntos(self.antecedentes),
            "Hora Inicio Traslado": formatear_hora(self.hora_inicio_traslado),
            "Hora Fin Traslado": formatear_hora(self.hora_fin_traslado),
            "Hora Inicio Trabajo": formatear_hora(self.hora_inicio_trabajo),
            "Hora Fin Trabajo": formatear_hora(self.hora_fin_trabajo),
            "Acciones Realizadas": unir_puntos(self.acciones),
            "Detalle del Diagnóstico": unir_puntos(self.diagnostico),
            "Estado Final del Servicio": self.estado_final or "",
            "Artículos Empleados": " | ".join(
                f"{a.codigo} - {a.descripcion} (x{a.cantidad})" for a in self.articulos_usados
            ),
            "Observaciones": unir_puntos(self.observaciones),
            "Nombre Cliente": self.nombre_cliente,
            "Firma Cliente": "Firmado" if self.firma_cliente_png else "Pendiente",
            "Nombre Representante Sistemas Analíticos": self.nombre_representante,
            "Firma Sistemas Analíticos": "Firmado" if self.firma_representante_png else "Pendiente",
            "Fecha de registro": (self.fecha_registro or ahora()).strftime("%d/%m/%Y %I:%M:%S %p"),
        }


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


def unir_puntos(puntos: list[str]) -> str:
    return " | ".join(f"{i}. {p}" for i, p in enumerate(puntos, start=1))
