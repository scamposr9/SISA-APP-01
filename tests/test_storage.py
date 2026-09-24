import io
import zipfile
from datetime import datetime, time

import pytest
from openpyxl import Workbook, load_workbook

from acta_app.models import Articulo
from acta_app.storage import ActaDuplicadaError, RepositorioExcelLocal, fila_plana, registro_desde_acta


@pytest.fixture
def repo(tmp_path):
    return RepositorioExcelLocal(tmp_path / "actas_maestro.xlsx", tmp_path / "pdfs")


def _hoja(repo):
    return load_workbook(repo.ruta_excel)["Actas"]


def _fila(ws, n):
    """Encabezado (fila 2) -> valor de la fila de datos n (1 = primera acta)."""
    return {ws.cell(2, c).value: ws.cell(2 + n, c).value for c in range(1, ws.max_column + 1)}


def test_primera_acta_crea_el_excel(repo, acta_completa):
    resultado = repo.guardar(acta_completa, b"%PDF-1.4", "Acta_2026-00051.pdf")

    assert resultado.total_actas == 1
    assert (repo.dir_pdf / "Acta_2026-00051.pdf").read_bytes() == b"%PDF-1.4"
    ws = _hoja(repo)
    fila = _fila(ws, 1)
    assert fila["N° de Acta"] == "2026-00051"
    assert fila["Cliente"] == "Hospital Rebagliati"
    assert fila["Fecha"] == datetime(2026, 9, 24)  # fecha real de Excel, no texto
    assert fila["Hora Inicio Trabajo"] == time(9, 0)
    assert isinstance(fila["Fecha de registro"], datetime)
    assert "Hora Inicio Traslado" not in fila and "Hora Fin Traslado" not in fila


def test_cada_item_va_en_su_propia_columna_bajo_un_encabezado_combinado(repo, acta_completa):
    acta_completa.antecedentes = ["Ruido en bomba", "Fuga leve", "Alarma de presión"]
    repo.guardar(acta_completa, b"pdf", "a.pdf")

    ws = _hoja(repo)
    fila = _fila(ws, 1)
    assert fila["Antecedente 1"] == "Ruido en bomba"
    assert fila["Antecedente 2"] == "Fuga leve"
    assert fila["Antecedente 3"] == "Alarma de presión"
    assert fila["Acción 1"] == "Se revisó la bomba"
    assert fila["Artículo 1 - Código"] == "SEL-01"
    assert fila["Artículo 1 - Cantidad"] == 2
    # Encabezado combinado "Antecedentes Iniciales" sobre las 3 columnas.
    col = [c for c in range(1, ws.max_column + 1) if ws.cell(2, c).value == "Antecedente 1"][0]
    assert ws.cell(1, col).value == "Antecedentes Iniciales"
    assert any(str(r) == f"{ws.cell(1, col).coordinate}:{ws.cell(1, col + 2).coordinate}"
               for r in ws.merged_cells.ranges)


def test_las_columnas_se_adaptan_al_acta_con_mas_items(repo, acta_completa):
    acta_completa.antecedentes = ["a1"]
    repo.guardar(acta_completa, b"pdf", "1.pdf")
    acta_completa.numero, acta_completa.fecha_registro = "2026-00052", None
    acta_completa.antecedentes = ["b1", "b2", "b3", "b4"]
    repo.guardar(acta_completa, b"pdf", "2.pdf")

    ws = _hoja(repo)
    encabezados = [ws.cell(2, c).value for c in range(1, ws.max_column + 1)]
    assert [e for e in encabezados if e.startswith("Antecedente ")] == [
        "Antecedente 1", "Antecedente 2", "Antecedente 3", "Antecedente 4"
    ]
    primera, segunda = _fila(ws, 1), _fila(ws, 2)
    assert (primera["Antecedente 1"], primera["Antecedente 2"]) == ("a1", None)
    assert segunda["Antecedente 4"] == "b4"
    # La columna que sigue al grupo se mantiene en su lugar lógico.
    assert encabezados[encabezados.index("Antecedente 4") + 1] == "Hora Inicio Trabajo"
    assert ws.tables["TablaActas"].ref.startswith("A2:")


def test_archivo_pdf_es_un_enlace_al_pdf(repo, acta_completa):
    repo.guardar(acta_completa, b"pdf", "Acta_2026-00051.pdf")
    ws = _hoja(repo)
    col = [c for c in range(1, ws.max_column + 1) if ws.cell(2, c).value == "Archivo PDF"][0]
    celda = ws.cell(3, col)
    assert celda.value == "Acta_2026-00051.pdf"
    assert celda.hyperlink.target == "pdfs/Acta_2026-00051.pdf"


def test_releer_y_agregar_conserva_los_datos_anteriores(repo, acta_completa):
    acta_completa.articulos = [Articulo("A-1", "Filtro", 2), Articulo("B-2", "Sello", 1)]
    repo.guardar(acta_completa, b"pdf", "1.pdf")
    acta_completa.numero, acta_completa.fecha_registro = "2026-00052", None
    acta_completa.articulos = []
    repo.guardar(acta_completa, b"pdf", "2.pdf")

    ws = _hoja(repo)
    primera = _fila(ws, 1)
    assert (primera["Artículo 2 - Código"], primera["Artículo 2 - Cantidad"]) == ("B-2", 1)
    assert ws.cell(3, [c for c in range(1, ws.max_column + 1)
                       if ws.cell(2, c).value == "Archivo PDF"][0]).hyperlink.target == "pdfs/1.pdf"
    df = repo.leer_actas()
    assert list(df["N° de Acta"]) == ["2026-00051", "2026-00052"]


def test_hoja_articulos_una_fila_por_articulo(repo, acta_completa):
    acta_completa.articulos = [Articulo("A-1", "Filtro", 2), Articulo(), Articulo("B-2", "Sello", 1)]
    repo.guardar(acta_completa, b"pdf", "a.pdf")

    ws = load_workbook(repo.ruta_excel)["Artículos"]
    filas = [[c.value for c in fila] for fila in ws.iter_rows(min_row=2)]
    assert [(f[0], f[3], f[5]) for f in filas] == [("2026-00051", "A-1", 2), ("2026-00051", "B-2", 1)]


def test_numero_repetido_no_se_guarda(repo, acta_completa):
    repo.guardar(acta_completa, b"pdf", "a.pdf")
    acta_completa.numero = " 2026-00051 "  # mismo número con espacios
    assert repo.existe(acta_completa.numero)
    with pytest.raises(ActaDuplicadaError):
        repo.guardar(acta_completa, b"pdf", "b.pdf")
    assert len(repo.leer_actas()) == 1


def test_zip_contiene_excel_y_pdfs(repo, acta_completa):
    repo.guardar(acta_completa, b"%PDF", "Acta_2026-00051.pdf")
    nombres = zipfile.ZipFile(io.BytesIO(repo.exportar_zip())).namelist()
    assert nombres == ["actas_maestro.xlsx", "pdfs/Acta_2026-00051.pdf"]


def test_excel_del_formato_anterior_se_respalda(repo, acta_completa):
    wb = Workbook()
    wb.active.title = "Actas"
    wb.active.append(["N° de Acta", "Fecha"])
    wb.active.append(["2026-00001", "01/01/2026"])
    repo.ruta_excel.parent.mkdir(parents=True, exist_ok=True)
    wb.save(repo.ruta_excel)

    repo.guardar(acta_completa, b"pdf", "a.pdf")
    assert list(repo.leer_actas()["N° de Acta"]) == ["2026-00051"]
    assert len(list(repo.ruta_excel.parent.glob("actas_maestro_v0.5_respaldo_*.xlsx"))) == 1


def test_sin_excel_no_hay_actas(repo):
    assert not repo.existe("2026-00001")
    assert repo.excel_bytes() is None and repo.exportar_zip() is None
    assert repo.leer_actas().empty


def test_vista_previa_muestra_un_item_por_columna(acta_completa):
    fila = fila_plana(registro_desde_acta(acta_completa))
    assert fila["Antecedente 1"] == "Ruido en bomba"
    assert fila["Artículo 1 - Descripción"] == "Sello de pistón"
