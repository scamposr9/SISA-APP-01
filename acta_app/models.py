"""Modelo de datos del acta, independiente de Streamlit, del PDF y del Excel."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time

from acta_app.config import ASPECTOS_ENCUESTA, NOTA_MAXIMA_ENCUESTA, TIPO_SERVICIO_OTRO, ZONA_HORARIA


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
    # Con checklist, las acciones escritas por el ingeniero van como «[X] … (Extra)».
    SUFIJO_EXTRA = " (Extra)"

    @classmethod
    def texto_extra(cls, accion: str) -> str:
        return f"{cls.MARCA_HECHA}{accion}{cls.SUFIJO_EXTRA}"

    @classmethod
    def accion_de_texto_extra(cls, texto: str) -> str | None:
        """'[X] Limpieza del suelo (Extra)' -> 'Limpieza del suelo'; None si no es extra."""
        if texto.startswith(cls.MARCA_HECHA) and texto.endswith(cls.SUFIJO_EXTRA):
            return texto[len(cls.MARCA_HECHA):-len(cls.SUFIJO_EXTRA)].strip()
        return None

    def como_texto(self) -> str:
        return (self.MARCA_HECHA if self.hecha else self.MARCA_PENDIENTE) + self.texto

    @classmethod
    def desde_texto(cls, texto: str) -> ActividadChecklist | None:
        if cls.accion_de_texto_extra(texto) is not None:
            return None  # acción adicional del ingeniero, no del protocolo
        for marca, hecha in ((cls.MARCA_HECHA, True), (cls.MARCA_PENDIENTE, False)):
            if texto.startswith(marca):
                return cls(texto[len(marca):].strip(), hecha)
        return None


@dataclass
class EncuestaSatisfaccion:
    """Respuesta del cliente al terminar el servicio (cada aspecto de 1 a 5)."""

    puntajes: dict[str, int] = field(default_factory=dict)  # aspecto -> 1..5
    comentario: str = ""
    fecha: datetime | None = None

    @property
    def nota(self) -> float:
        """Suma de los aspectos llevada a escala de 0 a 20 (todo 5 -> 20; todo 1 -> 4)."""
        maximo = 5 * len(ASPECTOS_ENCUESTA)
        return round(sum(self.puntajes.get(a, 0) for a in ASPECTOS_ENCUESTA) * NOTA_MAXIMA_ENCUESTA / maximo, 1)


@dataclass
class AccesoEncuesta:
    """QR de la encuesta que el ingeniero muestra al cliente (enlace de un solo uso)."""

    generado: datetime
    vence: datetime
    clave_hash: str  # SHA-256 del código del enlace; el código en sí no se guarda

    def vigente(self, momento: datetime | None = None) -> bool:
        return (momento or ahora()) <= self.vence


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

    # Encuesta de satisfacción (se responde después de guardar el acta).
    encuesta: EncuestaSatisfaccion | None = None
    acceso_encuesta: AccesoEncuesta | None = None

    # Con tipo de servicio «Presite»: apartados del reporte de preinstalación (no se guardan
    # en Actas.xlsx sino en Preinstalaciones.xlsx). Es un `preinstalacion.Preinstalacion`.
    preinstalacion: object | None = field(default=None, compare=False, repr=False)

    # ---------- Valores derivados, en el mismo formato que el prototipo ----------
    @property
    def tipo_servicio_texto(self) -> str:
        if self.tipo_servicio == TIPO_SERVICIO_OTRO and self.tipo_servicio_otro:
            return f"{TIPO_SERVICIO_OTRO}: {self.tipo_servicio_otro}"  # actas anteriores
        return self.tipo_servicio or ""

    @property
    def acciones_como_texto(self) -> list[str]:
        """Acciones para el Excel y el PDF: el checklist («[X] …» / «[ ] …») y, si lo hay,
        las acciones adicionales como «[X] … (Extra)»; si no, las acciones tal cual."""
        if not self.checklist:
            return list(self.acciones)
        return [c.como_texto() for c in self.checklist] + [
            ActividadChecklist.texto_extra(a) for a in self.acciones
        ]

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


def redondear_a_5_minutos(valor: time | None) -> time | None:
    """08:32 -> 08:30, 08:33 -> 08:35 (sin pasar de 23:55): el selector va de 5 en 5."""
    if valor is None:
        return None
    minutos = min(round((valor.hour * 60 + valor.minute) / 5) * 5, 23 * 60 + 55)
    return time(minutos // 60, minutos % 60)


def duracion(inicio: time | None, fin: time | None) -> str:
    """'7 h 35 min' (vacío si falta alguna hora o el fin no es posterior al inicio)."""
    if inicio is None or fin is None:
        return ""
    minutos = (fin.hour * 60 + fin.minute) - (inicio.hour * 60 + inicio.minute)
    if minutos <= 0:
        return ""
    return f"{minutos // 60} h {minutos % 60:02d} min" if minutos >= 60 else f"{minutos} min"


def formatear_hora(valor: time | None) -> str:
    """Formato de 24 horas: '16:05'."""
    return valor.strftime("%H:%M") if valor else ""
