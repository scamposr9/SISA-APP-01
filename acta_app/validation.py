"""Reglas de validación del acta (mismas que el prototipo HTML)."""

from acta_app.models import Acta


def validar_acta(acta: Acta) -> list[str]:
    """Devuelve la lista de campos faltantes o inválidos. Lista vacía = acta válida.

    Todos los campos son obligatorios excepto los artículos empleados; pero si
    se usa una fila de artículos, sus 3 columnas deben estar completas.
    """
    errores: list[str] = []

    obligatorios = [
        (acta.numero, "N.° de Acta"),
        (acta.fecha, "Fecha"),
        (acta.ubicacion, "Ubicación"),
        (acta.cliente, "Cliente"),
        (acta.equipo, "Equipo"),
        (acta.marca, "Marca"),
        (acta.modelo, "Modelo"),
        (acta.numero_serie, "N.° Serie"),
        (acta.hora_inicio_traslado, "Hora inicio de traslado"),
        (acta.hora_fin_traslado, "Hora término de traslado"),
        (acta.hora_inicio_trabajo, "Hora inicio de trabajo"),
        (acta.hora_fin_trabajo, "Hora término de trabajo"),
    ]
    errores += [etiqueta for valor, etiqueta in obligatorios if not valor]

    if not acta.tipo_servicio:
        errores.append("Tipo de servicio")
    if not acta.estado_final:
        errores.append("Estado final del servicio")

    listas = [
        (acta.antecedentes, "Antecedentes iniciales"),
        (acta.acciones, "Acciones realizadas"),
        (acta.diagnostico, "Detalle del diagnóstico"),
        (acta.observaciones, "Observaciones y/o recomendaciones"),
    ]
    errores += [etiqueta for puntos, etiqueta in listas if not puntos]

    if not acta.nombre_cliente:
        errores.append("Nombre del cliente")
    if not acta.firma_cliente_png:
        errores.append("Firma del cliente")
    if not acta.nombre_representante:
        errores.append("Nombre del representante de Sistemas Analíticos")
    if not acta.firma_representante_png:
        errores.append("Firma de Sistemas Analíticos")

    if any(not a.esta_completo for a in acta.articulos_usados):
        errores.append("Artículos empleados (completa las 3 columnas de cada fila usada)")

    return errores
