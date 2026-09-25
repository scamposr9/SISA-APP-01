"""Estructura de columnas del Excel maestro.

- `Campo`: una columna con un solo valor (Cliente, Fecha, ...).
- `Grupo`: un apartado con varios ítems (Antecedentes, Acciones, ...). Cada ítem va en su
  propia columna ("Antecedente 1", "Antecedente 2", ...) bajo un encabezado combinado
  ("Antecedentes Iniciales"). El número de columnas de cada grupo lo fija el acta que más
  ítems tenga en ese apartado.

Un `Registro` es un acta tal como se guarda en el Excel, independiente del formato de la
hoja; así se puede releer el Excel, agregar un acta y volver a escribirlo con el ancho
de grupos que corresponda.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, time

from acta_app import config
from acta_app.models import Acta, Articulo

FORMATO_FECHA = "dd/mm/yyyy"
FORMATO_FECHA_HORA = "dd/mm/yyyy hh:mm:ss AM/PM"
FORMATO_HORA = "hh:mm AM/PM"

# El PDF inicial nunca se reemplaza; una corrección agrega su propio PDF (Rev1, Rev2, ...).
COLUMNA_PDF_ORIGINAL = "PDF original"
COLUMNA_PDF_CORREGIDO = "PDF corregido"
COLUMNAS_PDF = (COLUMNA_PDF_ORIGINAL, COLUMNA_PDF_CORREGIDO)
# Encabezados de versiones anteriores del Excel que siguen reconociéndose.
ALIAS_ENCABEZADOS = {"Archivo PDF": COLUMNA_PDF_ORIGINAL}


@dataclass(frozen=True)
class Campo:
    nombre: str
    valor: Callable[[Acta], object]
    formato: str | None = None
    ancho: int = 16
    texto_largo: bool = False


@dataclass(frozen=True)
class Grupo:
    titulo: str  # encabezado combinado (fila 1)
    prefijo: str  # sub-columna: "Antecedente 1" / "Artículo 1 - Código"
    items: Callable[[Acta], list[tuple]]
    subcampos: tuple[str, ...] = ()  # vacío: un solo valor por ítem
    anchos: tuple[int, ...] = (40,)

    @property
    def columnas_por_item(self) -> int:
        return len(self.subcampos) or 1

    def encabezados(self, n_items: int) -> list[str]:
        if not self.subcampos:
            return [f"{self.prefijo} {i}" for i in range(1, n_items + 1)]
        return [f"{self.prefijo} {i} - {sub}" for i in range(1, n_items + 1) for sub in self.subcampos]

    def interpretar(self, encabezado: str) -> tuple[int, int] | None:
        """'Artículo 2 - Cantidad' -> (índice de ítem 1, índice de subcampo 2)."""
        m = re.fullmatch(rf"{re.escape(self.prefijo)} (\d+)(?: - (.+))?", encabezado)
        if not m:
            return None
        sub = m.group(2)
        if self.subcampos:
            if sub not in self.subcampos:
                return None
            return int(m.group(1)) - 1, self.subcampos.index(sub)
        return (int(m.group(1)) - 1, 0) if sub is None else None


def _textos(extraer: Callable[[Acta], list[str]]) -> Callable[[Acta], list[tuple]]:
    return lambda acta: [(t,) for t in extraer(acta)]


ESQUEMA: list[Campo | Grupo] = [
    Campo("N° de Acta", lambda a: a.numero, ancho=14),
    Campo("Fecha", lambda a: a.fecha, FORMATO_FECHA, ancho=12),
    Campo("Cliente", lambda a: a.cliente, ancho=30),
    Campo("Ubicación", lambda a: a.ubicacion, ancho=22),
    Campo("Equipo", lambda a: a.equipo, ancho=22),
    Campo("Marca", lambda a: a.marca),
    Campo("Modelo", lambda a: a.modelo),
    Campo("N° Serie", lambda a: a.numero_serie),
    Campo("Tipo de Servicio", lambda a: a.tipo_servicio_texto, ancho=20),
    Grupo("Antecedentes Iniciales", "Antecedente", _textos(lambda a: a.antecedentes)),
    Campo("Hora Inicio Trabajo", lambda a: a.hora_inicio_trabajo, FORMATO_HORA, ancho=12),
    Campo("Hora Fin Trabajo", lambda a: a.hora_fin_trabajo, FORMATO_HORA, ancho=12),
    Grupo("Acciones Realizadas", "Acción", _textos(lambda a: a.acciones)),
    Grupo("Detalle del Diagnóstico", "Diagnóstico", _textos(lambda a: a.diagnostico)),
    Campo("Estado Final del Servicio", lambda a: a.estado_final or "", ancho=18),
    Grupo(
        "Artículos Empleados",
        "Artículo",
        lambda a: [(x.codigo, x.descripcion, x.cantidad) for x in a.articulos_usados],
        subcampos=("Código", "Descripción", "Cantidad"),
        anchos=(14, 30, 10),
    ),
    Grupo("Observaciones y/o Recomendaciones", "Observación", _textos(lambda a: a.observaciones)),
    Campo("Nombre Cliente", lambda a: a.nombre_cliente, ancho=24),
    Campo("Firma Cliente", lambda a: "Firmado" if a.firma_cliente_png else "Pendiente", ancho=12),
    Campo("Nombre Representante Sistemas Analíticos", lambda a: a.nombre_representante, ancho=26),
    Campo(
        "Firma Sistemas Analíticos",
        lambda a: "Firmado" if a.firma_representante_png else "Pendiente",
        ancho=12,
    ),
    Campo("Fecha de registro", lambda a: a.fecha_registro, FORMATO_FECHA_HORA, ancho=22),
    Campo("Revisión", lambda a: a.revision, ancho=10),
    Campo("Fecha de corrección", lambda a: a.fecha_correccion, FORMATO_FECHA_HORA, ancho=22),
    Campo("Corregido por", lambda a: a.corregido_por, ancho=22),
    Campo("Motivo de corrección", lambda a: a.motivo_correccion, ancho=40, texto_largo=True),
    # Los nombres y enlaces de los PDF los asigna el repositorio al guardar.
    Campo(COLUMNA_PDF_ORIGINAL, lambda a: None, ancho=26),
    Campo(COLUMNA_PDF_CORREGIDO, lambda a: None, ancho=30),
]

CAMPOS = {c.nombre: c for c in ESQUEMA if isinstance(c, Campo)}
GRUPOS = [g for g in ESQUEMA if isinstance(g, Grupo)]


@dataclass
class Registro:
    valores: dict[str, object] = field(default_factory=dict)  # Campo -> valor
    items: dict[str, list[tuple]] = field(default_factory=dict)  # Grupo -> ítems
    enlaces: dict[str, str] = field(default_factory=dict)  # Campo -> hipervínculo

    @property
    def numero(self) -> str:
        return str(self.valores.get("N° de Acta") or "")


    def poner_pdf(self, columna: str, nombre: str, enlace: str | None) -> None:
        self.valores[columna] = nombre
        if enlace:
            self.enlaces[columna] = enlace


def registro_desde_acta(acta: Acta) -> Registro:
    registro = Registro()
    for bloque in ESQUEMA:
        if isinstance(bloque, Campo):
            registro.valores[bloque.nombre] = bloque.valor(acta)
        else:
            registro.items[bloque.titulo] = bloque.items(acta)
    return registro


def acta_desde_registro(registro: Registro) -> Acta:
    """Reconstruye el acta guardada (sin firmas) para cargarla en el formulario."""
    v = registro.valores

    def texto(nombre: str) -> str:
        return "" if v.get(nombre) is None else str(v[nombre]).strip()

    def lista(titulo: str) -> list[str]:
        return [str(item[0]).strip() for item in registro.items.get(titulo, []) if item[0]]

    tipo = texto("Tipo de Servicio")
    tipo_otro = ""
    if tipo.startswith(config.TIPO_SERVICIO_OTRO):
        tipo, _, tipo_otro = tipo.partition(":")
        tipo, tipo_otro = config.TIPO_SERVICIO_OTRO, tipo_otro.strip()

    return Acta(
        numero=texto("N° de Acta"),
        fecha=_a_fecha(v.get("Fecha")),
        cliente=texto("Cliente"),
        ubicacion=texto("Ubicación"),
        equipo=texto("Equipo"),
        marca=texto("Marca"),
        modelo=texto("Modelo"),
        numero_serie=texto("N° Serie"),
        tipo_servicio=tipo or None,
        tipo_servicio_otro=tipo_otro,
        antecedentes=lista("Antecedentes Iniciales"),
        hora_inicio_trabajo=_a_hora(v.get("Hora Inicio Trabajo")),
        hora_fin_trabajo=_a_hora(v.get("Hora Fin Trabajo")),
        acciones=lista("Acciones Realizadas"),
        diagnostico=lista("Detalle del Diagnóstico"),
        estado_final=texto("Estado Final del Servicio") or None,
        articulos=[
            Articulo(
                codigo="" if c is None else str(c).strip(),
                descripcion="" if d is None else str(d).strip(),
                cantidad=None if q in (None, "") else int(q),
            )
            for c, d, q in registro.items.get("Artículos Empleados", [])
        ],
        observaciones=lista("Observaciones y/o Recomendaciones"),
        nombre_cliente=texto("Nombre Cliente"),
        nombre_representante=texto("Nombre Representante Sistemas Analíticos"),
        fecha_registro=v.get("Fecha de registro") if isinstance(v.get("Fecha de registro"), datetime) else None,
        revision=int(v.get("Revisión") or 0),
        fecha_correccion=v.get("Fecha de corrección") if isinstance(v.get("Fecha de corrección"), datetime) else None,
        corregido_por=texto("Corregido por"),
        motivo_correccion=texto("Motivo de corrección"),
    )


def _a_fecha(valor: object) -> date | None:
    if isinstance(valor, datetime):
        return valor.date()
    return valor if isinstance(valor, date) else None


def _a_hora(valor: object) -> time | None:
    if isinstance(valor, datetime):
        return valor.time()
    return valor if isinstance(valor, time) else None


# ---------- Disposición de columnas ----------
@dataclass
class Columna:
    encabezado: str
    bloque: Campo | Grupo
    item: int = 0
    subcampo: int = 0

    @property
    def ancho(self) -> int:
        if isinstance(self.bloque, Campo):
            return self.bloque.ancho
        anchos = self.bloque.anchos
        return anchos[self.subcampo] if self.subcampo < len(anchos) else anchos[-1]

    @property
    def texto_largo(self) -> bool:
        if isinstance(self.bloque, Campo):
            return self.bloque.texto_largo
        return self.ancho >= 30

    @property
    def formato(self) -> str | None:
        return self.bloque.formato if isinstance(self.bloque, Campo) else None

    def valor(self, registro: Registro) -> object:
        if isinstance(self.bloque, Campo):
            return registro.valores.get(self.bloque.nombre)
        items = registro.items.get(self.bloque.titulo, [])
        if self.item >= len(items):
            return None
        return items[self.item][self.subcampo]


def disposicion(registros: list[Registro]) -> list[Columna]:
    """Columnas de la hoja; cada grupo tiene tantas como el acta con más ítems (mínimo 1)."""
    columnas: list[Columna] = []
    for bloque in ESQUEMA:
        if isinstance(bloque, Campo):
            columnas.append(Columna(bloque.nombre, bloque))
            continue
        n = max([len(r.items.get(bloque.titulo, [])) for r in registros] + [1])
        encabezados = iter(bloque.encabezados(n))
        for item in range(n):
            for sub in range(bloque.columnas_por_item):
                columnas.append(Columna(next(encabezados), bloque, item, sub))
    return columnas


def interpretar_encabezados(encabezados: list[str]) -> list[Columna | None]:
    """Reconoce las columnas de una hoja ya escrita (None = columna desconocida)."""
    resultado: list[Columna | None] = []
    for encabezado in encabezados:
        encabezado = ALIAS_ENCABEZADOS.get(str(encabezado or ""), str(encabezado or ""))
        columna = None
        if encabezado in CAMPOS:
            columna = Columna(encabezado, CAMPOS[encabezado])
        else:
            for grupo in GRUPOS:
                posicion = grupo.interpretar(encabezado)
                if posicion:
                    columna = Columna(encabezado, grupo, *posicion)
                    break
        resultado.append(columna)
    return resultado


def fila_plana(registro: Registro) -> dict[str, object]:
    """Encabezado -> valor para un solo registro (vista previa y DataFrames)."""
    return {c.encabezado: c.valor(registro) for c in disposicion([registro])}


def formatear_valor(valor: object) -> str:
    if valor is None:
        return ""
    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y %I:%M:%S %p")
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    if isinstance(valor, time):
        return valor.strftime("%I:%M %p")
    return str(valor)
