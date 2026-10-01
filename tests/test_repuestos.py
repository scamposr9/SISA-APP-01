import io

from openpyxl import Workbook

from acta_app.repuestos import Repuestos


def _bytes(wb):
    salida = io.BytesIO()
    wb.save(salida)
    return salida.getvalue()


def test_lee_las_dos_hojas_sin_repetir_codigos():
    wb = Workbook()
    ws = wb.active
    ws.title = "Almacén"
    for fila in [["REPUESTOS 2026"], [], ["N°", "Código", "Descripción", "Stock"],
                 [1, "FLT-01", "Filtro de aire", 3], [2, 12345.0, "Lámpara halógena 12V", 1],
                 [3, "flt-01", "Filtro de aire (repetido)", 2], [4, None, "sin código", 1]]:
        ws.append(fila)
    ws2 = wb.create_sheet("Importados")
    for fila in [["Proveedor", "Nombre proveedor", "Cod. Artículo", "Descripcion del repuesto"],
                 ["ACME", "Acme SAC", "FLT-01", "Otra descripción"], ["ACME", "Acme SAC", "BMB-7", "Bomba peristáltica"]]:
        ws2.append(fila)

    repuestos = Repuestos.desde_bytes(_bytes(wb))

    assert repuestos.opciones() == ["12345", "BMB-7", "FLT-01"]
    assert repuestos.descripcion(" flt-01 ") == "Filtro de aire"
    assert repuestos.descripcion("BMB-7") == "Bomba peristáltica"
    assert repuestos.etiqueta("12345") == "12345 · Lámpara halógena 12V"
    assert repuestos.descripcion("NO-EXISTE") is None
    assert repuestos.codigo("bmb-7 ") == "BMB-7" and repuestos.codigo("X-1") == "X-1"
    assert [(h.nombre, h.columna_codigo, h.columna_descripcion) for h in repuestos.hojas] == [
        ("Almacén", "Código", "Descripción"),
        ("Importados", "Cod. Artículo", "Descripcion del repuesto"),
    ]
