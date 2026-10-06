from datetime import time

from acta_app.borrador import a_json, desde_json, huella, tiene_datos
from acta_app.models import Acta, ActividadChecklist, Articulo
from acta_app.storage.excel_local import RepositorioExcelLocal


def test_borrador_ida_y_vuelta_sin_firmas(acta_completa):
    acta_completa.checklist = [ActividadChecklist("Limpieza de filtros", True), ActividadChecklist("Lubricación")]
    acta_completa.hora_inicio_trabajo = time(9, 5)
    acta_completa.articulos = [Articulo("FLT-01", "Filtro", 2), Articulo()]
    acta_completa.firma_cliente_png = b"PNG"

    borrador = desde_json(a_json(acta_completa, quitadas=["lubricacion"]))

    a = borrador.acta
    assert (a.numero, a.fecha, a.cliente, a.modelo, a.tipo_servicio) == (
        acta_completa.numero, acta_completa.fecha, acta_completa.cliente, acta_completa.modelo,
        acta_completa.tipo_servicio,
    )
    assert a.hora_inicio_trabajo == time(9, 5)
    assert a.checklist == acta_completa.checklist
    assert a.articulos == [Articulo("FLT-01", "Filtro", 2)]
    assert a.observaciones == acta_completa.observaciones
    assert a.firma_cliente_png is None and a.firma_representante_png is None
    assert borrador.quitadas == ["lubricacion"]
    assert borrador.tiene_datos


def test_huella_ignora_la_hora_y_detecta_cambios(acta_completa):
    antes = huella(acta_completa)
    assert huella(acta_completa) == antes
    acta_completa.observaciones = [*acta_completa.observaciones, "Otra"]
    assert huella(acta_completa) != antes


def test_formulario_solo_con_fecha_no_es_borrador(acta_completa):
    assert not tiene_datos(Acta(fecha=acta_completa.fecha))
    assert tiene_datos(Acta(cliente="Clínica"))


def test_json_dañado_no_rompe():
    assert desde_json(b"{no es json") is None
    assert desde_json(b"{}") is None


def test_repositorio_local_guarda_lee_y_borra_borradores(tmp_path, acta_completa):
    repo = RepositorioExcelLocal(ruta_excel=tmp_path / "actas.xlsx", dir_pdf=tmp_path / "pdfs")
    assert repo.leer_borrador("ana@x.com") is None
    repo.guardar_borrador("ana@x.com", a_json(acta_completa))
    assert desde_json(repo.leer_borrador("ana@x.com")).acta.numero == acta_completa.numero
    assert repo.leer_borrador("otro@x.com") is None  # un borrador por usuario
    repo.borrar_borrador("ana@x.com")
    assert repo.leer_borrador("ana@x.com") is None


def test_borrador_con_preinstalacion(acta_completa):
    from acta_app.preinstalacion import Contacto, Preinstalacion

    acta_completa.tipo_servicio = "Presite"
    acta_completa.preinstalacion = Preinstalacion(
        punto_dedicado=True, tipos_toma=["Tipo 1", "Tipo 13"], traslado=["Estibadores"], estibadores=2,
        accesos=["Puerta 2"], medidas={"Piso": {"Largo": 330.0, "Ancho": None, "Altura": None}},
        contactos=[Contacto("Ana", "Jefa", "999")], realizado_por="Ing",
    )
    p = desde_json(a_json(acta_completa)).preinstalacion
    assert (p.punto_dedicado, p.tipos_toma, p.estibadores, p.accesos) == (True, ["Tipo 1", "Tipo 13"], 2, ["Puerta 2"])
    assert p.medida("Piso", "Largo") == 330.0
    assert p.contactos == [Contacto("Ana", "Jefa", "999")]
    assert desde_json(a_json(Acta(cliente="x"))).preinstalacion is None
