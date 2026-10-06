"""PDF del reporte de preinstalación, con el mismo estilo que el del acta.

Las opciones marcadas aparecen con una casilla con X y solo se muestran las elegidas;
la excepción son los complementos faltantes, que se listan todos (marcados o no), como en
el formato en Word.
"""

from __future__ import annotations

import io

from reportlab.lib.colors import white

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
    _casilla,
    _Lienzo,
    _lista,
)
from acta_app.preinstalacion import (
    COMPLEMENTOS,
    MEDIDAS,
    SERVICIO_LABORATORIO,
    SUPERFICIES,
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

    recuadro(MARGIN_X, [("Cliente", p.cliente), ("Ubicación", p.ubicacion), ("Fecha", formatear_fecha(p.fecha))])
    recuadro(MARGIN_X + box_w + gap, [("Equipo", p.equipo), ("Marca", p.marca), ("Modelo", p.modelo)])
    lz.y += row_h * 3 + 9


def _titulo(lz: _Lienzo, texto: str, espacio: float = 18) -> None:
    """Barra azul con el nombre del apartado (como las filas grises del Word)."""
    lz.asegurar_espacio(espacio)
    lz.rect(MARGIN_X, lz.y, CONTENT_W, 6.5, relleno=NAVY)
    lz.fuente(BOLD, 9.5, white)
    lz.texto(MARGIN_X + 2.5, lz.y + 4.6, texto.upper())
    lz.y += 12


def _etiqueta(lz: _Lienzo, texto: str) -> None:
    lz.fuente(BOLD, 9.5, NAVY)
    lz.texto(MARGIN_X, lz.y, texto)


def _marcadas(lz: _Lienzo, titulo: str, opciones: list[str], x_inicio: float = 48) -> None:
    """'Título:  [X] Opción  [X] Opción' (solo las marcadas; pasa a otra línea si no caben)."""
    lz.asegurar_espacio(8)
    _etiqueta(lz, titulo)
    x = MARGIN_X + x_inicio
    if not opciones:
        lz.fuente(REGULAR, 9, INK)
        lz.texto(x, lz.y, "—")
    for opcion in opciones:
        ancho = 6 + lz.c.stringWidth(opcion, REGULAR, 9) / 2.8346 + 6
        if x + ancho > PAGE_W - MARGIN_X and x > MARGIN_X + x_inicio:
            lz.y += 6.5
            x = MARGIN_X + x_inicio
        _casilla(lz, x, lz.y, marcada=True)
        lz.fuente(REGULAR, 9, INK)
        lz.texto(x + 6, lz.y, opcion)
        x += ancho
    lz.y += 8


def _condiciones_electricas(lz: _Lienzo, p: Preinstalacion) -> None:
    _titulo(lz, "Condiciones eléctricas", espacio=40)
    dedicado = [] if p.punto_dedicado is None else ["Sí" if p.punto_dedicado else "No"]
    _marcadas(lz, "¿Es punto dedicado?", dedicado)

    # Tipo de toma: solo los dibujos marcados, cada uno con su casilla con X.
    lado, paso = 12, 26
    lz.asegurar_espacio(lado + 10)
    _etiqueta(lz, "Tipo de toma eléctrica:")
    x0 = MARGIN_X + 48
    x, y = x0, lz.y - 4
    for tipo in p.tipos_toma:
        if x + paso > PAGE_W - MARGIN_X:
            x, y = x0, y + lado + 4
        _casilla(lz, x, y + lado / 2 + 2, marcada=True)
        lz.imagen(imagen_toma(tipo), x + 5.5, y, lado, lado)
        x += paso
    lz.y = y + lado + 8


def _detalles(lz: _Lienzo, p: Preinstalacion) -> None:
    _titulo(lz, "Detalles")
    _marcadas(lz, "Traslado del equipo:", [p.traslado_texto(t) for t in p.traslado])
    _lista(lz, "Accesos", p.accesos)


def _tipo_area(lz: _Lienzo, p: Preinstalacion) -> None:
    _titulo(lz, "Tipo de área")
    servicios = [
        f"{s}: {p.tipo_laboratorio}" if s == SERVICIO_LABORATORIO and p.tipo_laboratorio else s
        for s in p.servicios
    ]
    _marcadas(lz, "Servicio:", servicios, x_inicio=22)


def _condiciones_area(lz: _Lienzo, p: Preinstalacion) -> None:
    """Tabla Medida × (Mesa de trabajo, Piso), en centímetros."""
    _titulo(lz, "Condiciones del área", espacio=40)
    col_w, fila_h = CONTENT_W / 3, 7
    xs = [MARGIN_X + col_w * i for i in range(3)]
    lz.rect(MARGIN_X, lz.y, CONTENT_W, fila_h, relleno=NAVY)
    lz.fuente(BOLD, 9, white)
    for x, texto in zip(xs, ["Medida", *SUPERFICIES]):
        lz.texto(x + col_w / 2, lz.y + 4.8, texto, align="center")
    lz.y += fila_h
    for medida in MEDIDAS:
        for x in xs:
            lz.rect(x, lz.y, col_w, fila_h)
        lz.fuente(REGULAR, 9, GRIS_ETIQUETA)
        lz.texto(xs[0] + col_w / 2, lz.y + 4.8, medida, align="center")
        lz.fuente(REGULAR, 9.5, INK)
        for x, superficie in zip(xs[1:], SUPERFICIES):
            valor = p.medida(superficie, medida)
            lz.texto(x + col_w / 2, lz.y + 4.8, f"{valor:g} cm" if valor is not None else "—", align="center")
        lz.y += fila_h
    lz.y += 8


def _complementos(lz: _Lienzo, p: Preinstalacion) -> None:
    """Todos los complementos, con X en los que faltan (3 por fila, como en el Word)."""
    _titulo(lz, "Complementos faltantes")
    col_w = CONTENT_W / 3
    for i, complemento in enumerate(COMPLEMENTOS):
        x = MARGIN_X + col_w * (i % 3)
        _casilla(lz, x, lz.y, marcada=complemento in p.complementos_faltantes)
        lz.fuente(REGULAR, 9, INK)
        lz.texto(x + 6, lz.y, complemento)
        if i % 3 == 2:
            lz.y += 7
    lz.y += 3
    lz.asegurar_espacio(8)
    _etiqueta(lz, "Temperatura del área (°C):")
    lz.fuente(REGULAR, 9, INK)
    lineas = lz.partir(p.temperatura or "—", CONTENT_W - 48)
    for linea in lineas:
        lz.texto(MARGIN_X + 48, lz.y, linea)
        lz.y += 5
    lz.y += 5


def _contactos(lz: _Lienzo, p: Preinstalacion) -> None:
    _titulo(lz, "Personal de contacto", espacio=30)
    anchos = [CONTENT_W * 0.32, CONTENT_W * 0.43, CONTENT_W * 0.25]
    xs = [MARGIN_X, MARGIN_X + anchos[0], MARGIN_X + anchos[0] + anchos[1]]
    header_h, interlinea = 7, 4.5

    def encabezado() -> None:
        lz.rect(MARGIN_X, lz.y, CONTENT_W, header_h, relleno=NAVY)
        lz.fuente(BOLD, 9, white)
        for x, titulo in zip(xs, ["Nombre", "Cargo", "Teléfono de contacto"]):
            lz.texto(x + 2, lz.y + 4.8, titulo)
        lz.y += header_h

    encabezado()
    for c in p.contactos_usados or []:
        lz.fuente(REGULAR, 9, INK)
        columnas = [lz.partir(v or "—", w - 4) for v, w in zip((c.nombre, c.cargo, c.telefono), anchos)]
        alto = max(len(col) for col in columnas) * interlinea + 2.5
        if lz.y + alto > LIMITE_INFERIOR:
            lz.nueva_pagina()
            encabezado()
        for x, w in zip(xs, anchos):
            lz.rect(x, lz.y, w, alto)
        lz.fuente(REGULAR, 9, INK)
        for x, lineas in zip(xs, columnas):
            for i, linea in enumerate(lineas):
                lz.texto(x + 2, lz.y + 5 + i * interlinea, linea)
        lz.y += alto
    lz.y += 8


def _realizado_por(lz: _Lienzo, p: Preinstalacion) -> None:
    lz.asegurar_espacio(12)
    lz.y += 4
    _etiqueta(lz, "Realizado por:")
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
    _condiciones_area(lz, p)
    _complementos(lz, p)
    _contactos(lz, p)
    _lista(lz, "Observaciones", p.observaciones)
    _realizado_por(lz, p)
    lz.cerrar()
    return buffer.getvalue()
