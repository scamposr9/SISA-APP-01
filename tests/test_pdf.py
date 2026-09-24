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
