from datetime import date

import pytest

from acta_app import preinstalacion as pre
from acta_app.pdf.preinstalacion import generar_pdf
from acta_app.preinstalacion import Contacto, Preinstalacion


@pytest.fixture
def reporte() -> Preinstalacion:
    return Preinstalacion(
        numero="2026-P001", fecha=date(2026, 10, 6), cliente="Hospital", ubicacion="Lima",
        equipo="Analizador", marca="MarcaA", modelo="BX-100", punto_dedicado=False,
        tipos_toma=["Tipo 1", "Tipo 5"], traslado=["Estoca", "Estibadores"], estibadores=3,
        accesos=["Puerta #2", "Rampa de 80 cm"], servicios=["Laboratorio"], tipo_laboratorio="Clínico",
        medidas={"Piso": {"Largo": 330.0, "Ancho": 220.0, "Altura": 600.0}},
        complementos_faltantes=["Lavaderos"], temperatura="22 °C",
        contactos=[Contacto("Liliana", "Arquitecta", "993 465 734"), Contacto("Carla", "Informática", "905 467 248")],
        observaciones=["Se requiere un nuevo tablero."], realizado_por="Ingeniero",
    )


def test_reporte_completo_es_valido(reporte):
    assert pre.validar(reporte) == []


def test_validaciones(reporte):
    reporte.traslado = ["No requiere", "Estoca"]
    reporte.estibadores = None
    reporte.contactos = [Contacto("Ana", "", "")]
    errores = pre.validar(reporte)
    assert "Traslado del equipo («No requiere» no va con otras opciones)" in errores
    assert "Personal de contacto (cada contacto necesita nombre y teléfono)" in errores
    assert "¿Es punto dedicado?" in pre.validar(Preinstalacion())


def test_excel_crece_con_los_contactos_y_conserva_enlaces(reporte):
    contenido, total = pre.agregar(None, reporte, "Preinstalacion_2026-P001.pdf", "https://sp/x.pdf")
    otro = Preinstalacion(**{**reporte.__dict__, "numero": "2026-P002",
                             "contactos": [Contacto(f"C{i}", "", "1") for i in range(3)]})
    contenido, total = pre.agregar(contenido, otro, "Preinstalacion_2026-P002.pdf", "")
    filas = pre.leer_filas(contenido)
    assert total == 2
    assert filas[0]["PDF"].startswith('=HYPERLINK("https://sp/x.pdf"')
    assert filas[1]["Contacto 3 - Nombre"] == "C2"
    assert filas[0]["Contacto 2 - Teléfono"] == "905 467 248"
    assert filas[0]["Traslado del equipo"] == "Estoca, Estibadores (3)"
    assert filas[0]["Falta: Lavaderos"] == "X" and not filas[0]["Falta: Calefacción"]
    assert pre.existe(filas, " 2026-p002 ")
    assert not pre.existe(filas, "2026-P003")


def test_pdf(reporte):
    assert generar_pdf(reporte).startswith(b"%PDF")
    assert all(pre.imagen_toma(t).startswith(b"\x89PNG") for t in pre.TIPOS_TOMA)


def test_sharepoint_rechaza_numero_repetido(reporte):
    from acta_app.storage import ActaDuplicadaError
    from acta_app.storage.sharepoint import RepositorioSharePoint
    from tests.test_sharepoint import CARPETA, SharePointFalso

    sp = SharePointFalso()
    repo = RepositorioSharePoint(sp, carpeta=CARPETA, segundos_cache=0)
    resultado = repo.guardar_preinstalacion(reporte, b"%PDF", "Preinstalacion_2026-P001.pdf")
    assert resultado.total_actas == 1
    assert f"{CARPETA}/PDF Preinstalaciones/Preinstalacion_2026-P001.pdf" in sp.archivos
    assert repo.existe_preinstalacion("2026-P001")
    with pytest.raises(ActaDuplicadaError):
        repo.guardar_preinstalacion(reporte, b"%PDF", "Preinstalacion_2026-P001.pdf")
