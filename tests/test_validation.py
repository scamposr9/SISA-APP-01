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


def test_tipo_de_servicio_debe_ser_una_de_las_cinco_opciones(acta_completa):
    for tipo in ["Mant. Preventivo", "Mant. Correctivo", "Presite", "Instalación", "Actualización"]:
        acta_completa.tipo_servicio = tipo
        assert validar_acta(acta_completa) == []
    acta_completa.tipo_servicio = "Otro"
    assert "Tipo de servicio" in validar_acta(acta_completa)


def test_con_checklist_las_acciones_escritas_son_opcionales(acta_completa):
    from acta_app.models import ActividadChecklist

    acta_completa.acciones = []
    assert "Acciones realizadas" in validar_acta(acta_completa)
    acta_completa.checklist = [ActividadChecklist("Limpieza", False)]
    assert validar_acta(acta_completa) == []


def test_hora_de_termino_debe_ser_posterior_a_la_de_inicio(acta_completa):
    from datetime import time

    acta_completa.hora_inicio_trabajo, acta_completa.hora_fin_trabajo = time(16, 5), time(8, 30)
    assert any("Hora de término" in e for e in validar_acta(acta_completa))
    acta_completa.hora_fin_trabajo = time(16, 5)
    assert any("Hora de término" in e for e in validar_acta(acta_completa))


def test_redondeo_a_5_minutos_y_duracion():
    from datetime import time

    from acta_app.models import duracion, redondear_a_5_minutos

    assert redondear_a_5_minutos(time(8, 32)) == time(8, 30)
    assert redondear_a_5_minutos(time(8, 33)) == time(8, 35)
    assert redondear_a_5_minutos(time(9, 58)) == time(10, 0)
    assert redondear_a_5_minutos(time(23, 59)) == time(23, 55)
    assert duracion(time(8, 30), time(16, 5)) == "7 h 35 min"
    assert duracion(time(8, 30), time(8, 50)) == "20 min"
    assert duracion(time(9, 0), time(8, 0)) == ""
