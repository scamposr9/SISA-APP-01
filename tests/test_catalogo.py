import pandas as pd
import pytest

from acta_app.catalogo import Catalogo, clave, limpiar


@pytest.fixture
def catalogo(tmp_path):
    # Mismo formato que Equipos.xlsx: Sedes -> Cliente, Departamentos -> Ubicación.
    equipos = pd.DataFrame(
        {
            "IdeEquipo": [1, 2, 3, 4, 5, 6],
            "Descripcion": ["Analizador Bioquimico", "Analizador Bioquimico", "Impresora", "Impresora",
                            "Hemobascula", "Maleta de Transporte"],
            "Marca": ["ABBOTT DIAGNOSTICS", "ABBOTT DIAGNOSTICS", "HP", "BROTHER", "VASINI STRUMENTI",
                      "VASINI STRUMENTI"],
            "Modelo": ["C4000", "C4000", "M501dn", "HL-L5100DN          ", "EO51P-TC-RF", "EO/1"],
            "Serie": ["C462244", "C462311", "HP-1", "U64219B0N815463     ", "3748", "3748"],
            "Sedes": ["Hospital Rebagliati", "Hospital de Rehabilitación", "Hospital Rebagliati",
                      "Clínica San Pablo", "Hospital Rebagliati", "Clínica San Pablo"],
            "Departamentos": ["Lima", "Callao", "Lima", "Lima", "Lima", "Lima"],
            "Almacen": [None, None, "A1", None, None, None],
        }
    )
    ruta = tmp_path / "Equipos.xlsx"
    equipos.to_excel(ruta, index=False)
    return Catalogo.desde_excel(ruta)


def test_limpia_espacios_y_compara_sin_tildes_ni_mayusculas():
    assert limpiar("  TRF-4K; K-20        ") == "TRF-4K; K-20"
    assert clave("Rehabilitación") == clave("REHABILITACION")


def test_sedes_son_clientes_y_departamentos_son_ubicaciones(catalogo):
    assert catalogo.opciones("cliente", {}) == [
        "Clínica San Pablo", "Hospital de Rehabilitación", "Hospital Rebagliati"
    ]
    assert catalogo.opciones("ubicacion", {}) == ["Callao", "Lima"]
    assert catalogo.tiene("cliente") and catalogo.tiene("ubicacion")


def test_las_opciones_se_filtran_con_lo_ya_elegido(catalogo):
    assert catalogo.opciones("modelo", {"marca": "abbott diagnostics"}) == ["C4000"]
    assert catalogo.opciones("marca", {"equipo": "Impresora"}) == ["BROTHER", "HP"]
    assert catalogo.opciones("serie", {"modelo": "C4000"}) == ["C462244", "C462311"]
    # Al elegir el cliente solo aparecen sus equipos.
    assert catalogo.opciones("equipo", {"cliente": "Clínica San Pablo"}) == [
        "Impresora", "Maleta de Transporte"
    ]


def test_un_valor_nuevo_no_deja_la_lista_vacia(catalogo):
    assert catalogo.opciones("modelo", {"marca": "MARCA NUEVA"}) == [
        "C4000", "EO/1", "EO51P-TC-RF", "HL-L5100DN", "M501dn"
    ]
    assert "Modelo X" in catalogo.opciones("modelo", {"modelo": "Modelo X"})


def test_serie_unica_autocompleta_equipo_y_sede(catalogo):
    assert catalogo.autocompletar({"serie": "U64219B0N815463"}) == {
        "equipo": "Impresora", "marca": "BROTHER", "modelo": "HL-L5100DN",
        "cliente": "Clínica San Pablo", "ubicacion": "Lima",
    }


def test_serie_repetida_no_autocompleta_nada_pero_ofrece_las_opciones(catalogo):
    assert catalogo.autocompletar({"serie": "3748"}) == {}
    assert catalogo.opciones("equipo", {"serie": "3748"}) == ["Hemobascula", "Maleta de Transporte"]


def test_cliente_completa_su_ubicacion_pero_no_adivina_el_equipo(catalogo):
    assert catalogo.autocompletar({"cliente": "hospital de rehabilitacion"}) == {"ubicacion": "Callao"}


def test_el_modelo_autocompleta_pero_no_inventa_la_serie(catalogo):
    assert catalogo.autocompletar({"modelo": "C4000"}) == {
        "equipo": "Analizador Bioquimico", "marca": "ABBOTT DIAGNOSTICS"
    }


def test_no_se_sobrescribe_lo_elegido_y_ambiguo_no_se_completa(catalogo):
    assert catalogo.autocompletar({"equipo": "Impresora"}) == {}
    assert "equipo" not in catalogo.autocompletar({"equipo": "Otro", "serie": "HP-1"})


def test_excel_sin_sedes_deja_cliente_y_ubicacion_manuales(tmp_path):
    ruta = tmp_path / "equipos.xlsx"
    pd.DataFrame({"Descripcion": ["Impresora"], "Marca": ["HP"], "Modelo": ["M1"], "Serie": ["S1"]}).to_excel(
        ruta, index=False
    )
    catalogo = Catalogo.desde_excel(ruta)
    assert not catalogo.tiene("cliente") and not catalogo.tiene("ubicacion")
    assert catalogo.autocompletar({"serie": "S1"}) == {"equipo": "Impresora", "marca": "HP", "modelo": "M1"}


def test_sin_archivo_el_catalogo_queda_vacio(tmp_path):
    vacio = Catalogo.desde_excel(tmp_path / "no.xlsx")
    assert vacio.opciones("cliente", {}) == [] and vacio.autocompletar({"serie": "X"}) == {}
