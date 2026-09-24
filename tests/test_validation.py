from acta_app.models import Acta, Articulo
from acta_app.validation import validar_acta


def test_acta_completa_es_valida(acta_completa):
    assert validar_acta(acta_completa) == []


def test_acta_vacia_lista_todos_los_obligatorios():
    errores = validar_acta(Acta())
    assert "N.° de Acta" in errores
    assert "Tipo de servicio" in errores
    assert "Firma del cliente" in errores
    assert not any(e.startswith("Artículos") for e in errores)  # artículos son opcionales


def test_fila_de_articulo_incompleta_es_error(acta_completa):
    acta_completa.articulos.append(Articulo(codigo="X-1"))
    assert validar_acta(acta_completa) == [
        "Artículos empleados (completa las 3 columnas de cada fila usada)"
    ]
