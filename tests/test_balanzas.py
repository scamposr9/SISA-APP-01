from acta_app import balanzas
from acta_app.balanzas import PruebasBalanza
from acta_app.borrador import a_json, desde_json
from acta_app.pdf import generar_pdf
from acta_app.storage.excel_local import RepositorioExcelLocal


def _pruebas() -> PruebasBalanza:
    pesos = [float(p) for p in balanzas.PESOS_REQUERIDOS]
    return PruebasBalanza([p - 2 for p in pesos], pesos)


def test_deteccion_de_balanzas_y_de_la_actividad():
    assert balanzas.es_balanza("Balanza analítica") and balanzas.es_balanza("", "BALANZA")
    assert not balanzas.es_balanza("Centrífuga")
    assert balanzas.es_actividad_de_pruebas("Pruebas de funcionamiento")
    assert balanzas.es_actividad_de_pruebas("Prueba de Funcionamiento.")
    assert not balanzas.es_actividad_de_pruebas("Limpieza del plato")


def test_validacion_de_la_tabla():
    p = _pruebas()
    assert balanzas.validar(p) == []
    p.mostrados[1] = None
    p.ajustados[11] = None
    assert balanzas.validar(p) == [
        "Pruebas de funcionamiento: Displayed Weight (gm) en 300",
        "Pruebas de funcionamiento: Adjustment Weight (gm) en 2500",
    ]


def test_excel_de_balanzas_agrega_y_reemplaza_en_correccion(tmp_path, acta_completa):
    repo = RepositorioExcelLocal(ruta_excel=tmp_path / "actas.xlsx", dir_pdf=tmp_path / "pdfs")
    acta_completa.equipo = "Balanza"
    acta_completa.pruebas_balanza = _pruebas()
    assert repo.registrar_balanza(acta_completa, "Acta_2026-00051.pdf", "") == 1
    acta_completa.pruebas_balanza.ajustados[0] = 101.0
    assert repo.registrar_balanza(acta_completa, "Acta_2026-00051_Rev1.pdf", "") == 1  # misma fila
    leidas = repo.leer_pruebas_balanza("2026-00051")
    assert leidas.mostrados[6] == 1288.0 and leidas.ajustados[0] == 101.0
    fila = balanzas.leer_filas(repo.ruta_balanzas.read_bytes())[0]
    assert fila["Cliente"] == acta_completa.cliente and fila["PDF"] == "Acta_2026-00051_Rev1.pdf"
    assert fila["Displayed Weight 1290 gm"] == 1288
    assert repo.leer_pruebas_balanza("2026-99999") is None


def test_pdf_y_borrador_con_pruebas(acta_completa):
    acta_completa.pruebas_balanza = _pruebas()
    assert generar_pdf(acta_completa).startswith(b"%PDF")
    recuperada = desde_json(a_json(acta_completa)).acta.pruebas_balanza
    assert recuperada == acta_completa.pruebas_balanza
