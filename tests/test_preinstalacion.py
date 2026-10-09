from datetime import date

import pytest

from acta_app import preinstalacion as pre
from acta_app.pdf.preinstalacion import generar_pdf
from acta_app.preinstalacion import Contacto, FotoAnexo, Preinstalacion


def _png(color="black", tamano=(60, 30)) -> bytes:
    import io

    from PIL import Image

    salida = io.BytesIO()
    Image.new("RGB", tamano, color).save(salida, format="PNG")
    return salida.getvalue()


@pytest.fixture
def reporte() -> Preinstalacion:
    return Preinstalacion(
        numero="2026-P001", fecha=date(2026, 10, 6), cliente="Hospital", ubicacion="Lima",
        equipo="Analizador", marca="MarcaA", modelo="BX-100", punto_dedicado=False,
        tipos_toma=["Tipo 1", "Tipo 5"], traslado=["Estoca", "Estibadores"], estibadores=3,
        accesos=["Puerta #2", "Rampa de 80 cm"], servicios=["Laboratorio"], tipo_laboratorio="Bioquímica",
        medidas={"Piso": {"Largo": 330.0, "Ancho": 220.0, "Altura": 600.0}},
        complementos_faltantes=["Lavaderos"], temperatura="22 °C",
        contactos=[Contacto("Liliana", "Arquitecta", "993 465 734"), Contacto("Carla", "Informática", "905 467 248")],
        observaciones=["Se requiere un nuevo tablero."], realizado_por="Ingeniero",
        nombre_cliente="Liliana", firma_cliente_png=_png(), firma_representante_png=_png(),
    )


def test_reporte_completo_es_valido(reporte):
    assert pre.validar(reporte) == []


def test_validaciones(reporte):
    reporte.traslado = ["No requiere", "Estoca"]
    reporte.estibadores = None
    reporte.contactos = [Contacto("Ana", "", "")]
    errores = pre.validar(reporte)
    assert "Traslado del equipo («No requiere» no va con otras opciones)" in errores
    assert "Contacto 1: cargo, teléfono" in errores
    assert "Cantidad de estibadores (número entero)" not in errores  # no se marcó Estibadores
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
    assert f"{CARPETA}/Preinstalaciones/PDF Preinstalaciones/Preinstalacion_2026-P001.pdf" in sp.archivos
    assert f"{CARPETA}/Preinstalaciones/Preinstalaciones.xlsx" in sp.archivos
    assert repo.existe_preinstalacion("2026-P001")
    with pytest.raises(ActaDuplicadaError):
        repo.guardar_preinstalacion(reporte, b"%PDF", "Preinstalacion_2026-P001.pdf")


def test_contacto_empezado_exige_los_3_datos(reporte):
    reporte.contactos = [Contacto("Liliana", "Arquitecta", "993"), Contacto("", "Jefa", ""), Contacto()]
    assert pre.validar(reporte) == ["Contacto 2: nombre, teléfono"]
    reporte.contactos = [Contacto("Liliana", "", "993")]
    assert pre.validar(reporte) == ["Contacto 1: cargo"]


def test_estibadores_marcado_exige_cantidad(reporte):
    reporte.estibadores = None
    assert pre.validar(reporte) == ["Cantidad de estibadores (número entero)"]


def test_observaciones_obligatorias_y_banco_de_organos(reporte):
    reporte.observaciones = []
    assert pre.validar(reporte) == ["Observaciones"]
    assert pre.SERVICIOS_AREA == ["Banco de Sangre", "Banco de Órganos", "Laboratorio"]
    reporte.observaciones, reporte.servicios = ["ok"], ["Banco de Órganos"]
    assert pre.validar(reporte) == [] and generar_pdf(reporte).startswith(b"%PDF")


def test_un_solo_servicio_y_tipo_de_laboratorio(reporte):
    reporte.tipo_laboratorio = ""
    assert pre.validar(reporte) == ["Tipo de laboratorio"]
    reporte.servicios = ["Banco de Sangre", "Laboratorio"]
    assert pre.validar(reporte) == ["Tipo de área (elige un servicio)"]
    reporte.servicios = ["Banco de Órganos"]
    assert pre.validar(reporte) == []


def test_firmas_obligatorias(reporte):
    reporte.firma_cliente_png, reporte.realizado_por = None, ""
    assert pre.validar(reporte) == ["Firma del cliente", "Nombre del representante de Sistemas Analíticos"]


def test_fotos_comprimidas_y_nombres_de_archivo():
    jpg = pre.comprimir_foto(_png("red", (4000, 3000)))
    from io import BytesIO

    from PIL import Image

    assert Image.open(BytesIO(jpg)).size == (1600, 1200)
    assert pre.nombre_archivo_foto(1, 'Tablero: "eléctrico" / área') == "Foto 01 - Tablero eléctrico  área.jpg"
    assert pre.nombre_archivo_foto(12, "") == "Foto 12.jpg"


def test_pdf_con_firmas_y_anexo_fotografico(reporte):
    from reportlab.pdfgen.canvas import Canvas

    paginas = []
    original = Canvas.showPage
    Canvas.showPage = lambda self: (paginas.append(1), original(self))[1]
    try:
        generar_pdf(reporte)
        sin_fotos = len(paginas)
        paginas.clear()
        reporte.fotos = [FotoAnexo(pre.comprimir_foto(_png("blue", (800, 600))), f"Foto {i}") for i in range(3)]
        assert generar_pdf(reporte).startswith(b"%PDF")
    finally:
        Canvas.showPage = original
    assert len(paginas) == sin_fotos + 2  # anexo: 2 fotos por página


def test_sharepoint_guarda_firmas_y_fotos(reporte):
    from tests.test_sharepoint import CARPETA, SharePointFalso
    from acta_app.storage.sharepoint import RepositorioSharePoint

    sp = SharePointFalso()
    repo = RepositorioSharePoint(sp, carpeta=CARPETA, segundos_cache=0)
    reporte.fotos = [FotoAnexo(b"jpg1", "Tablero eléctrico"), FotoAnexo(b"jpg2", "Puerta de ingreso")]
    repo.guardar_preinstalacion(reporte, b"%PDF", "Preinstalacion_2026-P001.pdf")
    assert f"{CARPETA}/Actas/Firmas Actas/2026-P001/cliente.png" in sp.archivos
    assert f"{CARPETA}/Actas/Firmas Actas/2026-P001/representante.png" in sp.archivos
    fotos = f"{CARPETA}/Preinstalaciones/Fotos Preinstalaciones/2026-P001"
    assert sp.archivos[f"{fotos}/Foto 01 - Tablero eléctrico.jpg"][0] == b"jpg1"
    assert f"{fotos}/Foto 02 - Puerta de ingreso.jpg" in sp.archivos
    fila = pre.leer_filas(sp.archivos[f"{CARPETA}/Preinstalaciones/Preinstalaciones.xlsx"][0])[0]
    assert fila["Fotos (anexo)"] == 2 and fila["Firma Cliente"] == "Firmado" and fila["Nombre Cliente"] == "Liliana"
    assert str(fila["Carpeta de fotos"]).startswith('=HYPERLINK("https://sp.example/')
