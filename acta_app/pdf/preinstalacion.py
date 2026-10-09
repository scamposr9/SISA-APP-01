"""PDF del reporte de preinstalación.

El encabezado y los datos generales tienen el estilo del acta; desde «Condiciones Eléctricas»
se replica la tabla del formato en Word (filas grises por apartado, columna de etiquetas a la
izquierda y las mismas divisiones). Las opciones marcadas aparecen con una casilla con X y
solo se muestran las elegidas; la excepción son los complementos faltantes, que se listan
todos (marcados o no), como en el Word.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from reportlab.lib.colors import HexColor

from acta_app import config
from acta_app.models import formatear_fecha
from acta_app.pdf.generator import (
    BOLD,
    CONTENT_W,
    GRIS_ETIQUETA,
    GRIS_SUBTITULO,
    INK,
    LIMITE_INFERIOR,
    MARGIN_X,
    NAVY,
    PAGE_W,
    RED,
    REGULAR,
    Y_NUEVA_PAGINA,
    _Lienzo,
)
from acta_app.preinstalacion import (
    COMPLEMENTOS,
    MEDIDAS,
    SERVICIO_LABORATORIO,
    SERVICIOS_AREA,
    SUPERFICIES,
    Contacto,
    Preinstalacion,
    imagen_toma,
)

TITULO = "REPORTE DE PREINSTALACIÓN"


def _encabezado(lz: _Lienzo, p: Preinstalacion) -> None:
    header_h, title_row_h, logo_col_w = 16, 8, 40
    y = lz.y
    lz.rect(MARGIN_X, y, CONTENT_W, header_h)
    lz.linea(MARGIN_X + logo_col_w, y, MARGIN_X + logo_col_w, y + header_h)
    lz.linea(MARGIN_X + logo_col_w, y + title_row_h, PAGE_W - MARGIN_X, y + title_row_h)
    if config.LOGO_PATH.exists():
        logo_w = 30
        logo_h = logo_w * (141 / 800)
        lz.imagen(config.LOGO_PATH.read_bytes(), MARGIN_X + 4, y + (header_h - logo_h) / 2, logo_w, logo_h)
    derecha_x, derecha_w = MARGIN_X + logo_col_w, CONTENT_W - logo_col_w
    lz.fuente(BOLD, 11, NAVY)
    lz.texto(derecha_x + derecha_w / 2, y + 5.5, config.SISTEMA, align="center")
    celdas = ["Reporte de Preinstalación", formatear_fecha(p.fecha) or "—"]
    sub_w = derecha_w / len(celdas)
    for i in range(1, len(celdas)):
        lz.linea(derecha_x + sub_w * i, y + title_row_h, derecha_x + sub_w * i, y + header_h)
    lz.fuente(REGULAR, 8, GRIS_SUBTITULO)
    for i, valor in enumerate(celdas):
        lz.texto(derecha_x + sub_w * (i + 0.5), y + title_row_h + 5, valor, align="center")
    lz.y += header_h + 8

    lz.fuente(BOLD, 12, NAVY)
    lz.texto(PAGE_W / 2, lz.y, TITULO, align="center")
    lz.fuente(BOLD, 13, RED)
    lz.texto(PAGE_W / 2, lz.y + 7, f"N.° {p.numero or '—'}", align="center")
    lz.y += 15


def _datos_generales(lz: _Lienzo, p: Preinstalacion) -> None:
    gap, label_w, row_h = 6, 20, 7
    box_w = (CONTENT_W - gap) / 2

    def recuadro(x: float, campos: list[tuple[str, str]]) -> None:
        y = lz.y
        lz.rect(x, y, box_w, row_h * len(campos), color=INK)
        lz.linea(x + label_w, y, x + label_w, y + row_h * len(campos), color=INK)
        for i, (etiqueta, valor) in enumerate(campos):
            if i:
                lz.linea(x, y + row_h * i, x + box_w, y + row_h * i, color=INK)
            base = y + row_h * i + row_h / 2 + 1.5
            lz.fuente(REGULAR, 9, GRIS_ETIQUETA)
            lz.texto(x + 2, base, etiqueta)
            lz.texto_ajustado(x + label_w + 2, base, valor or "—", box_w - label_w - 4, tamano=9.5)

    recuadro(MARGIN_X, [("Cliente", p.cliente), ("Ubicación", p.ubicacion), ("Fecha", formatear_fecha(p.fecha)),
                        ("Servicio", config.TIPO_SERVICIO_PRESITE)])
    recuadro(MARGIN_X + box_w + gap, [("Equipo", p.equipo), ("Marca", p.marca), ("Modelo", p.modelo),
                                      ("N.° Serie", p.numero_serie)])
    lz.y += row_h * 4 + 9



# ---------- Tabla con la misma estructura que el formato en Word ----------
GRIS_SECCION = HexColor("#D9D9D9")
BORDE = HexColor("#808080")
ANCHO_ETIQUETA = 38  # columna izquierda («Suministro Eléctrico», «Accesos», …)
ANCHO_DATOS = CONTENT_W - ANCHO_ETIQUETA
TAM, INTERLINEA, ALTO_MIN = 8.5, 4.0, 7.5
LADO_CASILLA = 3.4


@dataclass
class Celda:
    ancho: float
    texto: str = ""
    negrita: bool = False
    casilla: bool | None = None  # None: sin casilla; True/False: casilla marcada o vacía


def _lineas(lz: _Lienzo, celda: Celda) -> list[str]:
    lz.fuente(BOLD if celda.negrita else REGULAR, TAM, INK)
    sangria = LADO_CASILLA + 1.5 if celda.casilla is not None else 0
    return lz.partir(celda.texto, celda.ancho - 4 - sangria) if celda.texto else [""]


def _alto(lz: _Lienzo, celdas: list[Celda]) -> float:
    return max(ALTO_MIN, max(len(_lineas(lz, c)) for c in celdas) * INTERLINEA + 3.2)


def _dibujar_celda(lz: _Lienzo, x: float, y: float, alto: float, celda: Celda, centrar_v: bool = False) -> None:
    lz.rect(x, y, celda.ancho, alto, color=BORDE)
    lineas = _lineas(lz, celda)
    base = y + 4.6
    if centrar_v:
        base = y + (alto - len(lineas) * INTERLINEA) / 2 + 3
    tx = x + 2
    if celda.casilla is not None:
        cy = base - 2.8
        lz.rect(tx, cy, LADO_CASILLA, LADO_CASILLA, color=INK)
        if celda.casilla:
            lz.fuente(BOLD, 8, INK)
            lz.texto(tx + LADO_CASILLA / 2, cy + 2.75, "X", align="center")
        tx += LADO_CASILLA + 1.5
    lz.fuente(BOLD if celda.negrita else REGULAR, TAM, INK)
    for i, linea in enumerate(lineas):
        lz.texto(tx, base + i * INTERLINEA, linea)


def _espacio(lz: _Lienzo, alto: float) -> None:
    if lz.y + alto > LIMITE_INFERIOR:
        lz.nueva_pagina()


def _seccion(lz: _Lienzo, titulo: str, siguiente: float = 10) -> None:
    """Fila gris a todo el ancho (como «Condiciones Eléctricas» en el Word)."""
    _espacio(lz, ALTO_MIN + siguiente)
    lz.rect(MARGIN_X, lz.y, CONTENT_W, ALTO_MIN, relleno=GRIS_SECCION)
    lz.rect(MARGIN_X, lz.y, CONTENT_W, ALTO_MIN, color=BORDE)
    lz.fuente(BOLD, TAM, INK)
    lz.texto(MARGIN_X + 2, lz.y + 4.9, titulo)
    lz.y += ALTO_MIN


def _fila(lz: _Lienzo, celdas: list[Celda], x: float = MARGIN_X) -> None:
    alto = _alto(lz, celdas)
    _espacio(lz, alto)
    for celda in celdas:
        _dibujar_celda(lz, x, lz.y, alto, celda)
        x += celda.ancho
    lz.y += alto


def _grupo(lz: _Lienzo, etiqueta: str, filas: list[list[Celda]], negrita: bool = True) -> None:
    """Etiqueta a la izquierda que abarca varias filas (p. ej. «Accesos»). Si no cabe
    entero en la página, sigue en la siguiente repitiendo la etiqueta."""
    altos = [_alto(lz, f) for f in filas]
    if lz.y + sum(altos) > LIMITE_INFERIOR and sum(altos) <= LIMITE_INFERIOR - Y_NUEVA_PAGINA:
        lz.nueva_pagina()
    inicio = lz.y
    for celdas, alto in zip(filas, altos):
        if lz.y + alto > LIMITE_INFERIOR:
            _dibujar_celda(lz, MARGIN_X, inicio, lz.y - inicio, Celda(ANCHO_ETIQUETA, etiqueta, negrita), True)
            lz.nueva_pagina()
            inicio = lz.y
        x = MARGIN_X + ANCHO_ETIQUETA
        for celda in celdas:
            _dibujar_celda(lz, x, lz.y, alto, celda)
            x += celda.ancho
        lz.y += alto
    _dibujar_celda(lz, MARGIN_X, inicio, lz.y - inicio, Celda(ANCHO_ETIQUETA, etiqueta, negrita), True)


def _opciones(marcadas: list[str], n_celdas: int, ancho: float) -> list[Celda]:
    """Celdas de una fila de opciones: solo las marcadas (con X), de izquierda a derecha;
    las celdas sobrantes quedan vacías para conservar las divisiones del formato."""
    celdas = [Celda(ancho, o, casilla=True) for o in marcadas[:n_celdas]]
    return celdas + [Celda(ancho) for _ in range(n_celdas - len(celdas))]


def _condiciones_electricas(lz: _Lienzo, p: Preinstalacion) -> None:
    _seccion(lz, "Condiciones Eléctricas", siguiente=40)
    tercio = ANCHO_DATOS / 3
    dedicado = [] if p.punto_dedicado is None else ["SI" if p.punto_dedicado else "NO"]
    _fila(lz, [Celda(ANCHO_ETIQUETA, "Suministro Eléctrico"), Celda(tercio, "Es punto dedicado:"),
               *_opciones(dedicado, 2, tercio)])

    # Tipo de toma: los dibujos marcados, cada uno con su casilla con X.
    lado, paso, por_fila = 11, 24, 6
    filas = max(1, -(-len(p.tipos_toma) // por_fila))
    alto = filas * (lado + 4) + 5
    _espacio(lz, alto)
    _dibujar_celda(lz, MARGIN_X, lz.y, alto, Celda(ANCHO_ETIQUETA, "Tipo de Toma Eléctrica"))
    lz.rect(MARGIN_X + ANCHO_ETIQUETA, lz.y, ANCHO_DATOS, alto, color=BORDE)
    for i, tipo in enumerate(p.tipos_toma):
        x = MARGIN_X + ANCHO_ETIQUETA + 3 + paso * (i % por_fila)
        y = lz.y + 3 + (lado + 4) * (i // por_fila)
        lz.rect(x, y + lado / 2 - LADO_CASILLA / 2, LADO_CASILLA, LADO_CASILLA, color=INK)
        lz.fuente(BOLD, 8, INK)
        lz.texto(x + LADO_CASILLA / 2, y + lado / 2 + 1.05, "X", align="center")
        lz.imagen(imagen_toma(tipo), x + LADO_CASILLA + 1.5, y, lado, lado)
        lz.fuente(REGULAR, 6.5, GRIS_ETIQUETA)
        lz.texto(x + LADO_CASILLA + 1.5 + lado / 2, y + lado + 2.6, tipo, align="center")
    lz.y += alto


def _detalles(lz: _Lienzo, p: Preinstalacion) -> None:
    _seccion(lz, "Detalles")
    cuarto = ANCHO_DATOS / 4
    _fila(lz, [Celda(ANCHO_ETIQUETA, "Traslado del Equipo", negrita=True),
               *_opciones([p.traslado_texto(t) for t in p.traslado], 4, cuarto)])
    _grupo(lz, "Accesos", [[Celda(ANCHO_DATOS, a)] for a in p.accesos] or [[Celda(ANCHO_DATOS)]])


def _tipo_area(lz: _Lienzo, p: Preinstalacion) -> None:
    _seccion(lz, "Tipo de Área")
    n, ancho = len(SERVICIOS_AREA), 34
    laboratorio = SERVICIO_LABORATORIO in p.servicios
    # Como en el Word: todos los servicios con su casilla; X solo en el elegido.
    _fila(lz, [Celda(ANCHO_ETIQUETA, "Servicio", negrita=True),
               *[Celda(ancho, s, casilla=s in p.servicios) for s in SERVICIOS_AREA],
               Celda(ANCHO_DATOS - n * ancho, f"Tipo de Laboratorio: {p.tipo_laboratorio}" if laboratorio else "")])

    def valor(superficie: str, medida: str) -> str:
        v = p.medida(superficie, medida)
        return f"{medida}: {v:g} cm" if v is not None else f"{medida}:"

    mitad = ANCHO_DATOS / 2
    _grupo(lz, "Condiciones del área", [
        [Celda(mitad, s) for s in SUPERFICIES],
        *[[Celda(mitad, valor(s, m)) for s in SUPERFICIES] for m in MEDIDAS],
    ])


def _complementos(lz: _Lienzo, p: Preinstalacion) -> None:
    """Todos los complementos, con X en los que faltan (3 por fila, como en el Word)."""
    _seccion(lz, "Complementos Faltantes", siguiente=20)
    tercio = ANCHO_DATOS / 3
    filas = [[Celda(tercio, c, casilla=c in p.complementos_faltantes) for c in COMPLEMENTOS[i:i + 3]]
             for i in range(0, len(COMPLEMENTOS), 3)]
    _grupo(lz, "Condiciones Adicionales", filas)
    _fila(lz, [Celda(ANCHO_ETIQUETA, "Temperatura (°C)", negrita=True),
               Celda(ANCHO_DATOS, f"Temperatura del Área: {p.temperatura}")])


def _contactos(lz: _Lienzo, p: Preinstalacion) -> None:
    _seccion(lz, "Personal de Contacto")
    anchos = (CONTENT_W * 0.32, CONTENT_W * 0.33, CONTENT_W * 0.35)
    for c in p.contactos_usados or [Contacto()]:
        _fila(lz, [Celda(anchos[0], f"Nombre: {c.nombre}"), Celda(anchos[1], f"Cargo: {c.cargo}"),
                   Celda(anchos[2], f"Teléfono de contacto: {c.telefono}")])


def _observaciones(lz: _Lienzo, p: Preinstalacion) -> None:
    """Un recuadro a todo el ancho: «Observaciones:» y debajo cada observación."""
    lz.fuente(REGULAR, TAM, INK)
    lineas = ["Observaciones:"] + [l for o in p.observaciones for l in lz.partir(o, CONTENT_W - 4)]
    i = 0
    while i < len(lineas):
        _espacio(lz, ALTO_MIN + INTERLINEA)
        caben = max(1, int((LIMITE_INFERIOR - lz.y - 3.2) // INTERLINEA))
        tramo = lineas[i:i + caben]
        alto = len(tramo) * INTERLINEA + 3.2
        lz.rect(MARGIN_X, lz.y, CONTENT_W, alto, color=BORDE)
        lz.fuente(REGULAR, TAM, INK)
        for j, linea in enumerate(tramo):
            lz.texto(MARGIN_X + 2, lz.y + 4.4 + j * INTERLINEA, linea)
        lz.y += alto
        i += len(tramo)


def _realizado_por(lz: _Lienzo, p: Preinstalacion) -> None:
    lz.asegurar_espacio(12)
    lz.y += 8
    lz.fuente(BOLD, 9.5, NAVY)
    lz.texto(MARGIN_X, lz.y, "Realizado por:")
    lz.fuente(REGULAR, 9.5, INK)
    lz.texto(MARGIN_X + 26, lz.y, f"{p.realizado_por or '—'} · {config.EMPRESA}")


def generar_pdf(p: Preinstalacion) -> bytes:
    buffer = io.BytesIO()
    lz = _Lienzo(buffer, titulo=f"Reporte de Preinstalación N.° {p.numero}")
    _encabezado(lz, p)
    _datos_generales(lz, p)
    _condiciones_electricas(lz, p)
    _detalles(lz, p)
    _tipo_area(lz, p)
    _complementos(lz, p)
    _contactos(lz, p)
    _observaciones(lz, p)
    _realizado_por(lz, p)
    lz.cerrar()
    return buffer.getvalue()
