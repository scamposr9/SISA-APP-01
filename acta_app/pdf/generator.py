"""PDF del acta con el mismo diseño que `generarPDF()` del prototipo HTML (A4, en mm).

Las coordenadas se expresan en mm medidos desde el borde SUPERIOR de la página, igual
que en jsPDF; `_Lienzo` se encarga de convertirlas al sistema de ReportLab.
"""

from __future__ import annotations

import io

from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from acta_app import config
from acta_app.models import Acta, formatear_fecha, formatear_hora

# ---------- Medidas y colores (idénticos al prototipo) ----------
PAGE_W, PAGE_H = 210, 297
MARGIN_X = 14
CONTENT_W = PAGE_W - 2 * MARGIN_X
LIMITE_INFERIOR = 283  # a partir de aquí se salta de página
Y_NUEVA_PAGINA = 16

NAVY = HexColor(config.NAVY)
RED = HexColor(config.RED)
INK = HexColor(config.INK)
LINE = HexColor(config.GREY_LINE)
GRIS_ETIQUETA = Color(70 / 255, 70 / 255, 70 / 255)
GRIS_SUBTITULO = Color(60 / 255, 60 / 255, 60 / 255)
GRIS_PIE = Color(140 / 255, 140 / 255, 140 / 255)

REGULAR, BOLD = "Helvetica", "Helvetica-Bold"
GROSOR_LINEA = 0.2 * mm  # grosor por defecto de jsPDF


class _Lienzo:
    """Envoltorio mínimo sobre el canvas de ReportLab con coordenadas en mm desde arriba."""

    def __init__(self, buffer: io.BytesIO, titulo: str):
        self.c = canvas.Canvas(buffer, pagesize=A4)
        self.c.setTitle(titulo)
        self.c.setAuthor(config.EMPRESA)
        self.c.setLineWidth(GROSOR_LINEA)
        self.y = 14.0

    # --- conversión ---
    @staticmethod
    def _py(y_mm: float) -> float:
        return (PAGE_H - y_mm) * mm

    # --- texto ---
    def fuente(self, nombre: str, tamano: float, color=INK) -> None:
        self.c.setFont(nombre, tamano)
        self.c.setFillColor(color)

    def texto(self, x: float, y: float, s: str, align: str = "left") -> None:
        dibujar = {
            "left": self.c.drawString,
            "center": self.c.drawCentredString,
            "right": self.c.drawRightString,
        }[align]
        dibujar(x * mm, self._py(y), s)

    def texto_ajustado(
        self, x: float, y: float, s: str, ancho_mm: float, tamano: float, minimo: float = 7
    ) -> None:
        """Texto de una sola línea: reduce la fuente hasta `minimo` para que quepa y, si
        aun así no cabe, lo recorta con '…' (el prototipo simplemente lo cortaba)."""
        while tamano > minimo and stringWidth(s, REGULAR, tamano) > ancho_mm * mm:
            tamano -= 0.5
        self.fuente(REGULAR, tamano, INK)
        if stringWidth(s, REGULAR, tamano) > ancho_mm * mm:
            while s and stringWidth(s + "…", REGULAR, tamano) > ancho_mm * mm:
                s = s[:-1]
            s = s.rstrip() + "…"
        self.texto(x, y, s)

    def partir(self, s: str, ancho_mm: float) -> list[str]:
        """Divide `s` en líneas que caben en `ancho_mm` con la fuente actual.

        Corta por palabras y respeta los saltos de línea escritos por el usuario; una
        palabra más ancha que la columna (p. ej. un código largo sin espacios) se parte
        por caracteres para que nunca invada la columna vecina.
        """
        fuente, tamano, ancho = self.c._fontname, self.c._fontsize, ancho_mm * mm

        def cabe(texto: str) -> bool:
            return stringWidth(texto, fuente, tamano) <= ancho

        lineas: list[str] = []
        for parrafo in s.split("\n"):
            actual = ""
            for palabra in parrafo.split():
                candidato = f"{actual} {palabra}" if actual else palabra
                if cabe(candidato):
                    actual = candidato
                    continue
                if cabe(palabra):  # la palabra entra completa en la línea siguiente
                    lineas.append(actual)
                    actual = palabra
                    continue
                # Palabra más ancha que la columna: se parte por caracteres,
                # empezando en el espacio que queda en la línea actual.
                actual = f"{actual} " if actual else ""
                for ch in palabra:
                    if actual.strip() and not cabe(actual + ch):
                        lineas.append(actual.rstrip())
                        actual = ""
                    actual += ch
            lineas.append(actual)
        return lineas or [""]

    # --- formas ---
    def linea(self, x1: float, y1: float, x2: float, y2: float, color=LINE) -> None:
        self.c.setStrokeColor(color)
        self.c.line(x1 * mm, self._py(y1), x2 * mm, self._py(y2))

    def rect(self, x: float, y: float, w: float, h: float, color=LINE, relleno=None) -> None:
        self.c.setStrokeColor(color)
        if relleno is not None:
            self.c.setFillColor(relleno)
        self.c.rect(x * mm, self._py(y + h), w * mm, h * mm, stroke=relleno is None, fill=relleno is not None)

    def imagen(self, datos: bytes, x: float, y: float, w: float, h: float) -> None:
        self.c.drawImage(
            ImageReader(io.BytesIO(datos)), x * mm, self._py(y + h), w * mm, h * mm, mask="auto"
        )

    # --- paginación ---
    def asegurar_espacio(self, necesario_mm: float) -> None:
        if self.y + necesario_mm > LIMITE_INFERIOR:
            self.nueva_pagina()

    def nueva_pagina(self, y: float = Y_NUEVA_PAGINA) -> None:
        self._pie()
        self.c.showPage()
        self.c.setLineWidth(GROSOR_LINEA)
        self.y = y

    def _pie(self) -> None:
        self.fuente(REGULAR, 7, GRIS_PIE)
        self.texto(MARGIN_X, 292, config.SITIO_WEB)

    def cerrar(self) -> None:
        self._pie()
        self.c.save()


# ---------- Bloques del acta ----------
def _encabezado(lz: _Lienzo, acta: Acta) -> None:
    header_h, title_row_h, logo_col_w = 16, 8, 40
    y = lz.y
    lz.rect(MARGIN_X, y, CONTENT_W, header_h)
    lz.linea(MARGIN_X + logo_col_w, y, MARGIN_X + logo_col_w, y + header_h)
    lz.linea(MARGIN_X + logo_col_w, y + title_row_h, PAGE_W - MARGIN_X, y + title_row_h)

    if config.LOGO_PATH.exists():
        logo_w = 30
        logo_h = logo_w * (141 / 800)
        lz.imagen(config.LOGO_PATH.read_bytes(), MARGIN_X + 4, y + (header_h - logo_h) / 2, logo_w, logo_h)

    derecha_x = MARGIN_X + logo_col_w
    derecha_w = CONTENT_W - logo_col_w
    lz.fuente(BOLD, 11, NAVY)
    lz.texto(derecha_x + derecha_w / 2, y + 5.5, config.SISTEMA, align="center")

    sub_w = derecha_w / 4
    for i in (1, 2, 3):
        lz.linea(derecha_x + sub_w * i, y + title_row_h, derecha_x + sub_w * i, y + header_h)
    lz.fuente(REGULAR, 8, GRIS_SUBTITULO)
    texto_y = y + title_row_h + (header_h - title_row_h) / 2 + 1.5
    celdas = [config.CODIGO_FORMATO, config.NOMBRE_FORMATO, config.EDICION, formatear_fecha(acta.fecha) or "—"]
    for i, valor in enumerate(celdas):
        lz.texto(derecha_x + sub_w * (i + 0.5), texto_y, valor, align="center")
    lz.y += header_h + 8


def _numero_acta(lz: _Lienzo, acta: Acta) -> None:
    lz.fuente(BOLD, 13, RED)
    lz.texto(PAGE_W / 2, lz.y, f"N.° {acta.numero or '—'}", align="center")
    lz.y += 10


def _datos_generales(lz: _Lienzo, acta: Acta) -> None:
    """Dos recuadros de 3 filas: Cliente/Equipo/N.° Serie y Ubicación/Marca/Modelo."""
    box_gap, label_w, row_h = 6, 20, 7
    box_w = (CONTENT_W - box_gap) / 2
    box_h = row_h * 3

    def recuadro(x: float, campos: list[tuple[str, str]]) -> None:
        y = lz.y
        lz.rect(x, y, box_w, box_h, color=INK)
        lz.linea(x, y + row_h, x + box_w, y + row_h, color=INK)
        lz.linea(x, y + row_h * 2, x + box_w, y + row_h * 2, color=INK)
        lz.linea(x + label_w, y, x + label_w, y + box_h, color=INK)
        for i, (etiqueta, valor) in enumerate(campos):
            base = y + row_h * i + row_h / 2 + 1.5
            lz.fuente(REGULAR, 9, GRIS_ETIQUETA)
            lz.texto(x + 2, base, etiqueta)
            lz.texto_ajustado(x + label_w + 2, base, valor or "—", box_w - label_w - 4, tamano=9.5)

    recuadro(MARGIN_X, [("Cliente", acta.cliente), ("Equipo", acta.equipo), ("N.° Serie", acta.numero_serie)])
    recuadro(
        MARGIN_X + box_w + box_gap,
        [("Ubicación", acta.ubicacion), ("Marca", acta.marca), ("Modelo", acta.modelo)],
    )
    lz.y += box_h + 8


def _casilla(lz: _Lienzo, x: float, y: float, marcada: bool) -> None:
    lz.rect(x, y - 3.2, 4, 4, color=INK)
    if marcada:
        lz.fuente(BOLD, 8.5, INK)
        lz.texto(x + 2, y - 0.1, "X", align="center")


def _opciones(lz: _Lienzo, titulo: str, x_inicio: float, opciones: list[tuple[str, bool, float]]) -> None:
    """Fila 'Título: [ ] Op1  [X] Op2 ...'; cada opción indica cuánto avanzar después."""
    lz.asegurar_espacio(10)
    lz.fuente(BOLD, 9.5, NAVY)
    lz.texto(MARGIN_X, lz.y, titulo)
    x = MARGIN_X + x_inicio
    for rotulo, marcada, avance in opciones:
        _casilla(lz, x, lz.y, marcada)
        lz.fuente(REGULAR, 9, INK)
        lz.texto(x + 6, lz.y, rotulo)
        x += avance


def _tipo_servicio(lz: _Lienzo, acta: Acta) -> None:
    es_otro = acta.tipo_servicio == config.TIPO_SERVICIO_OTRO
    rotulo_otro = "Otro" + (f": {acta.tipo_servicio_otro}" if es_otro and acta.tipo_servicio_otro else "")
    _opciones(
        lz,
        "Tipo de servicio:",
        34,
        [
            (config.TIPO_SERVICIO_PREVENTIVO, acta.tipo_servicio == config.TIPO_SERVICIO_PREVENTIVO, 42),
            (config.TIPO_SERVICIO_CORRECTIVO, acta.tipo_servicio == config.TIPO_SERVICIO_CORRECTIVO, 42),
            (rotulo_otro, es_otro, 0),
        ],
    )
    lz.y += 9


def _estado_final(lz: _Lienzo, acta: Acta) -> None:
    avances = [32, 34, 0]
    _opciones(
        lz,
        "Estado final del servicio:",
        52,
        [(e, acta.estado_final == e, a) for e, a in zip(config.ESTADOS_FINALES, avances)],
    )
    lz.y += 10


def _lista(lz: _Lienzo, titulo: str, puntos: list[str]) -> None:
    lz.asegurar_espacio(10)
    lz.fuente(BOLD, 9.5, NAVY)
    lz.texto(MARGIN_X, lz.y, titulo)
    lz.y += 5.5
    lz.fuente(REGULAR, 9, INK)
    items = [f"{i}. {p}" for i, p in enumerate(puntos, start=1)] or ["—"]
    for item in items:
        for linea in lz.partir(item, CONTENT_W):
            if lz.y + 6 > LIMITE_INFERIOR:
                lz.nueva_pagina()
                lz.fuente(REGULAR, 9, INK)
            lz.texto(MARGIN_X, lz.y, linea)
            lz.y += 5
    lz.y += 3


def _horas(lz: _Lienzo, acta: Acta) -> None:
    lz.asegurar_espacio(8)
    lz.fuente(REGULAR, 9, GRIS_ETIQUETA)
    lz.texto(MARGIN_X, lz.y, f"Inicio trabajo: {formatear_hora(acta.hora_inicio_trabajo) or '—'}")
    lz.texto(MARGIN_X + 95, lz.y, f"Fin trabajo: {formatear_hora(acta.hora_fin_trabajo) or '—'}")
    lz.y += 9


def _articulos(lz: _Lienzo, acta: Acta) -> None:
    """Tabla con encabezado azul y texto blanco; se omite si no hay artículos."""
    articulos = acta.articulos_usados
    if not articulos:
        return

    lz.asegurar_espacio(16)
    lz.fuente(BOLD, 9.5, NAVY)
    lz.texto(MARGIN_X, lz.y, "Artículos empleados")
    lz.y += 5

    col_codigo, col_cantidad = 38, 22
    col_desc = CONTENT_W - col_codigo - col_cantidad
    xs = [MARGIN_X, MARGIN_X + col_codigo, MARGIN_X + col_codigo + col_desc]
    anchos = [col_codigo, col_desc, col_cantidad]
    header_h, row_pad, text_pad, interlinea = 7, 2.5, 4, 4.5

    def encabezado_tabla() -> None:
        lz.rect(MARGIN_X, lz.y, CONTENT_W, header_h, relleno=NAVY)
        lz.fuente(BOLD, 9, white)
        for x, titulo in zip(xs, ["Código", "Descripción", "Cantidad"]):
            lz.texto(x + 2, lz.y + header_h - 2.3, titulo)
        lz.y += header_h

    lz.asegurar_espacio(header_h + 8)
    encabezado_tabla()

    for art in articulos:
        lz.fuente(REGULAR, 9, INK)
        valores = [art.codigo, art.descripcion, "" if art.cantidad is None else str(art.cantidad)]
        columnas = [lz.partir(v or "—", w - text_pad) for v, w in zip(valores, anchos)]
        alto = max(len(c) for c in columnas) * interlinea + row_pad

        if lz.y + alto > LIMITE_INFERIOR:
            lz.nueva_pagina()
            encabezado_tabla()

        for x, w in zip(xs, anchos):
            lz.rect(x, lz.y, w, alto)
        lz.fuente(REGULAR, 9, INK)
        for x, lineas in zip(xs, columnas):
            for i, linea in enumerate(lineas):
                lz.texto(x + 2, lz.y + 5 + i * interlinea, linea)
        lz.y += alto
    lz.y += 6


def _firmas(lz: _Lienzo, acta: Acta) -> None:
    firma_w, firma_h = 70, 24
    lz.y += 12
    if lz.y + firma_h + 18 > 280:
        lz.nueva_pagina(y=20)

    lz.fuente(BOLD, 9.5, NAVY)
    lz.texto(MARGIN_X, lz.y, "Conformidad")
    lz.y += 10

    izq_x, der_x = MARGIN_X, PAGE_W - MARGIN_X - firma_w
    linea_y = lz.y + firma_h
    for x, png in ((izq_x, acta.firma_cliente_png), (der_x, acta.firma_representante_png)):
        if png:
            lz.imagen(png, x, lz.y, firma_w, firma_h)
        lz.linea(x, linea_y, x + firma_w, linea_y, color=INK)

    for x, rotulo, nombre in (
        (izq_x, "Cliente", acta.nombre_cliente),
        (der_x, config.EMPRESA, acta.nombre_representante),
    ):
        centro = x + firma_w / 2
        lz.fuente(REGULAR, 9, INK)
        lz.texto(centro, linea_y + 5, rotulo, align="center")
        lz.fuente(BOLD, 9, INK)
        lz.texto(centro, linea_y + 11, nombre or "—", align="center")
    lz.y = linea_y + 11


# ---------- API pública ----------
def generar_pdf(acta: Acta) -> bytes:
    """Genera el PDF del acta y lo devuelve como bytes."""
    buffer = io.BytesIO()
    lz = _Lienzo(buffer, titulo=f"Acta de Atención N.° {acta.numero}")

    _encabezado(lz, acta)
    _numero_acta(lz, acta)
    _datos_generales(lz, acta)
    _tipo_servicio(lz, acta)
    _lista(lz, "Antecedentes iniciales", acta.antecedentes)
    _horas(lz, acta)
    _lista(lz, "Acciones realizadas", acta.acciones)
    _lista(lz, "Detalle del diagnóstico", acta.diagnostico)
    _estado_final(lz, acta)
    _articulos(lz, acta)
    _lista(lz, "Observaciones y/o recomendaciones", acta.observaciones)
    _firmas(lz, acta)

    lz.cerrar()
    return buffer.getvalue()


def nombre_archivo_pdf(acta: Acta) -> str:
    """Mismo criterio que el prototipo: 'Acta_<número>.pdf' con caracteres seguros."""
    seguro = "".join(ch if (ch.isascii() and ch.isalnum()) or ch == "-" else "_" for ch in acta.numero) or "sin_numero"
    return f"Acta_{seguro}.pdf"
