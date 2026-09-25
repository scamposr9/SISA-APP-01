from pypdf import PdfReader

import io

from acta_app.models import Articulo
from acta_app.pdf import generar_pdf, nombre_archivo_pdf


def _texto(pdf: bytes) -> str:
    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)


def test_pdf_contiene_los_datos_del_acta(acta_completa):
    texto = _texto(generar_pdf(acta_completa))
    for esperado in [
        "SISTEMA INTEGRADO DE GESTIÓN",
        "FO-ING-02",
        "N.° 2026-00051",
        "Hospital Rebagliati",
        "1. Ruido en bomba",
        "SEL-01",
        "Juan Pérez",
        "Ana Ruiz",
    ]:
        assert esperado in texto


def test_muchos_articulos_generan_varias_paginas(acta_completa):
    acta_completa.articulos = [Articulo(f"A-{i}", "Repuesto", 1) for i in range(60)]
    pdf = generar_pdf(acta_completa)
    assert len(PdfReader(io.BytesIO(pdf)).pages) >= 2


def test_nombre_de_archivo_seguro(acta_completa):
    acta_completa.numero = "2026/00051 ñ"
    assert nombre_archivo_pdf(acta_completa) == "Acta_2026_00051__.pdf"


def test_palabras_largas_sin_espacios_no_invaden_otras_columnas(acta_completa):
    import pymupdf

    from acta_app.pdf.generator import CONTENT_W, MARGIN_X

    acta_completa.articulos = [
        Articulo("X" * 40, "X" * 120, 3),
        Articulo("CODIGO-1", "Descripción normal con espacios " * 6, 4),
    ]
    acta_completa.observaciones = ["Y" * 200]
    pdf = generar_pdf(acta_completa)

    limite_derecho = (MARGIN_X + CONTENT_W) * 72 / 25.4
    col_codigo_fin = (MARGIN_X + 38) * 72 / 25.4
    for pagina in pymupdf.open(stream=pdf, filetype="pdf"):
        for x0, _, x1, _, palabra, *_ in pagina.get_text("words"):
            assert x1 <= limite_derecho + 0.5, palabra
            if palabra.startswith("XXXX") and x0 < col_codigo_fin:
                assert x1 <= col_codigo_fin, "el código invade la columna Descripción"


def _lienzo():
    from acta_app.pdf.generator import REGULAR, _Lienzo

    lienzo = _Lienzo(io.BytesIO(), titulo="prueba")
    lienzo.fuente(REGULAR, 9)
    return lienzo


def test_partir_empieza_la_palabra_larga_en_la_misma_linea_del_numero():
    lineas = _lienzo().partir("1. " + "X" * 300, 100)
    assert lineas[0].startswith("1. XXX")
    assert "".join(lineas).replace(" ", "") == "1." + "X" * 300


def test_partir_respeta_palabras_y_saltos_de_linea():
    lineas = _lienzo().partir("uno dos tres\ncuatro", 100)
    assert lineas == ["uno dos tres", "cuatro"]


def test_pdf_de_revision_indica_la_correccion(acta_completa):
    from datetime import datetime

    acta_completa.revision, acta_completa.corregido_por = 1, "Ana Ruiz"
    acta_completa.motivo_correccion = "Se corrigió el número de serie"
    acta_completa.fecha_correccion = datetime(2026, 9, 25, 10, 30)
    texto = _texto(generar_pdf(acta_completa))
    assert "REVISIÓN 1" in texto
    assert "Motivo: Se corrigió el número de serie" in texto
    assert nombre_archivo_pdf(acta_completa) == "Acta_2026-00051_Rev1.pdf"


def test_pdf_muestra_la_fecha_y_solo_las_opciones_marcadas(acta_completa):
    acta_completa.tipo_servicio = "Mant. Correctivo"
    acta_completa.estado_final = "En Observación"
    texto = _texto(generar_pdf(acta_completa))
    assert "Fecha:" in texto and "24/09/2026" in texto
    assert "Mant. Correctivo" in texto and "En Observación" in texto
    for no_marcada in ["Mant. Preventivo", "Otro", "Operativo", "Inoperativo"]:
        assert no_marcada not in texto, no_marcada


def test_tipo_otro_muestra_su_especificacion(acta_completa):
    acta_completa.tipo_servicio, acta_completa.tipo_servicio_otro = "Otro", "Calibración anual"
    texto = _texto(generar_pdf(acta_completa))
    assert "Otro: Calibración anual" in texto and "Mant. Preventivo" not in texto
