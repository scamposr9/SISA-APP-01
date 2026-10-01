import io

from openpyxl import Workbook

from acta_app.protocolos import Protocolos


def _bytes(wb: Workbook) -> bytes:
    salida = io.BytesIO()
    wb.save(salida)
    return salida.getvalue()


def test_formato_en_bloques_ignora_serie_clientes_cronograma_y_obs():
    wb = Workbook()
    ws = wb.active
    ws.title = "Centrífugas"
    filas = [
        ["PROTOCOLO DE MANTENIMIENTO PREVENTIVO"],
        ["CLIENTE:", "Hospital Rebagliati", None, "SEDE:", "Lima"],
        ["EQUIPO:", "Centrífuga", None, "N° SERIE:", "SN-1"],
        ["MARCA:", "Hettich", None, "MODELO:", "Rotina 380"],
        ["N°", "PARTE MANTENIDA", "CRONOGRAMA 2026", "ENE", "FEB"],
        [1, "1. Limpieza general del equipo", None, "X", None],
        [2, "Revisión de escobillas", None, None, "X"],
        [None, None],
        ["OBS:", "Cliente solicita visita en marzo"],
        ["EQUIPO: Analizador"],
        ["MARCA: Abbott", None, None, "MODELO: Architect c4000; C8000"],
        ["N°", "Parte mantenida", "Cronograma 2026"],
        [1, "Calibración de pipetas", "X"],
        [2, "Cambio de filtros", None],
    ]
    for fila in filas:
        ws.append(fila)

    protocolos = Protocolos.desde_bytes(_bytes(wb))

    centrifuga = protocolos.buscar("", "HETTICH", "rotina 380")
    assert centrifuga.equipo == "Centrífuga"
    assert centrifuga.actividades == ["Limpieza general del equipo", "Revisión de escobillas"]
    analizador = protocolos.buscar("", "Abbott", "C8000")
    assert analizador.actividades == ["Calibración de pipetas", "Cambio de filtros"]
    assert protocolos.buscar("", "Abbott", "Otro modelo") is None
    assert len(protocolos.lista) == 2


def test_formato_tabla_con_celdas_combinadas_vacias():
    wb = Workbook()
    ws = wb.active
    for fila in [
        ["Equipo", "Marca", "Modelo", "N° Serie", "Parte mantenida", "Cronograma 2026", "OBS"],
        ["Autoclave", "Tuttnauer", "3870EA", "S1", "Revisión de empaquetadura", "X", "ojo"],
        [None, None, None, None, "Limpieza de cámara", "", ""],
        ["Autoclave", "Tuttnauer", "2540M", "S2", "Prueba de presión", "X", ""],
    ]:
        ws.append(fila)

    protocolos = Protocolos.desde_bytes(_bytes(wb))

    assert protocolos.buscar("Autoclave", "Tuttnauer", "3870EA").actividades == [
        "Revisión de empaquetadura", "Limpieza de cámara",
    ]
    assert protocolos.buscar("", "tuttnauer", "2540m").actividades == ["Prueba de presión"]


def test_modelo_unico_se_acepta_aunque_la_marca_no_coincida():
    wb = Workbook()
    ws = wb.active
    for fila in [["MARCA:", "Mindray"], ["MODELO:", "BC-5150"], ["Parte mantenida"], ["Limpieza"]]:
        ws.append(fila)
    protocolos = Protocolos.desde_bytes(_bytes(wb))
    assert protocolos.buscar("", "", "BC-5150").actividades == ["Limpieza"]
