import pandas as pd
import pytest

from acta_app.catalogo import Catalogo, clave, limpiar


@pytest.fixture
def catalogo(tmp_path):
    equipos = pd.DataFrame(
        {
            "IdeEquipo": [1, 2, 3, 4, 5, 6],
            "Descripcion": ["Analizador Bioquimico", "Analizador Bioquimico", "Impresora", "Impresora",
                            "Hemobascula", "Maleta de Transporte"],
            "Marca": ["ABBOTT DIAGNOSTICS", "ABBOTT DIAGNOSTICS", "HP", "BROTHER", "VASINI STRUMENTI",
                      "VASINI STRUMENTI"],
            "Modelo": ["C4000", "C4000", "M501dn", "HL-L5100DN          ", "EO51P-TC-RF", "EO/1"],
            "Serie": ["C462244", "C462311", "HP-1", "U64219B0N815463     ", "3748", "3748"],
            "Almacen": [None, None, "A1", None, None, None],
        }
    )
    ruta_equipos = tmp_path / "equipos.xlsx"
    equipos.to_excel(ruta_equipos, index=False)
    ruta_clientes = tmp_path / "clientes.xlsx"
    pd.DataFrame(
        {"Cliente": ["Hospital Rebagliati", "Hospital de Rehabilitación"], "Ubicación": ["Jesús María", "Lima"]}
    ).to_excel(ruta_clientes, index=False)
    actas = pd.DataFrame({"Cliente": ["Clínica San Pablo"], "Ubicación": ["Surco"], "N° de Acta": ["1"]})
    return Catalogo.desde_fuentes(ruta_equipos, ruta_clientes, actas)


def test_limpia_espacios_y_compara_sin_tildes_ni_mayusculas():
    assert limpiar("  TRF-4K; K-20        ") == "TRF-4K; K-20"
    assert clave("Rehabilitación") == clave("REHABILITACION")


def test_clientes_del_archivo_y_de_las_actas_guardadas(catalogo):
    assert catalogo.opciones("cliente", {}) == [
        "Clínica San Pablo", "Hospital de Rehabilitación", "Hospital Rebagliati"
    ]


def test_las_opciones_se_filtran_con_lo_ya_elegido(catalogo):
    assert catalogo.opciones("modelo", {"marca": "abbott diagnostics"}) == ["C4000"]
    assert catalogo.opciones("marca", {"equipo": "Impresora"}) == ["BROTHER", "HP"]
    assert catalogo.opciones("serie", {"modelo": "C4000"}) == ["C462244", "C462311"]


def test_un_valor_nuevo_no_deja_la_lista_vacia(catalogo):
    assert catalogo.opciones("modelo", {"marca": "MARCA NUEVA"}) == [
        "C4000", "EO/1", "EO51P-TC-RF", "HL-L5100DN", "M501dn"
    ]
    assert "Modelo X" in catalogo.opciones("modelo", {"modelo": "Modelo X"})


def test_la_serie_autocompleta_equipo_marca_y_modelo(catalogo):
    assert catalogo.autocompletar({"serie": "U64219B0N815463"}) == {
        "equipo": "Impresora", "marca": "BROTHER", "modelo": "HL-L5100DN"
    }


def test_el_modelo_autocompleta_pero_no_inventa_la_serie(catalogo):
    completado = catalogo.autocompletar({"modelo": "C4000"})
    assert completado == {"equipo": "Analizador Bioquimico", "marca": "ABBOTT DIAGNOSTICS"}


def test_no_se_sobrescribe_lo_elegido_y_ambiguo_no_se_completa(catalogo):
    assert catalogo.autocompletar({"equipo": "Impresora"}) == {}
    assert "equipo" not in catalogo.autocompletar({"equipo": "Otro", "serie": "HP-1"})


def test_cliente_autocompleta_su_ubicacion(catalogo):
    assert catalogo.autocompletar({"cliente": "hospital rebagliati"}) == {"ubicacion": "Jesús María"}


def test_sin_archivos_el_catalogo_queda_vacio(tmp_path):
    vacio = Catalogo.desde_fuentes(tmp_path / "no.xlsx", tmp_path / "no.xlsx")
    assert vacio.opciones("cliente", {}) == [] and vacio.autocompletar({"serie": "X"}) == {}


def test_serie_repetida_no_autocompleta_nada_pero_ofrece_las_opciones(catalogo):
    assert catalogo.autocompletar({"serie": "3748"}) == {}
    assert catalogo.opciones("equipo", {"serie": "3748"}) == ["Hemobascula", "Maleta de Transporte"]
