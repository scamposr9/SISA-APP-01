"""Formulario completo del acta FO-ING-02. Solo arma la interfaz y devuelve un `Acta`."""

import streamlit as st

from acta_app import config
from acta_app.catalogo import limpiar
from acta_app.models import Acta, hoy
from acta_app.ui.catalogo_ui import cargar_catalogo
from acta_app.ui.components import (
    etiqueta,
    firma,
    lista_dinamica,
    seccion,
    tabla_articulos,
)

PASO_MINUTOS = 300  # el reloj del prototipo avanza de 5 en 5 minutos


FORM_ID = "form_id"


def k(nombre: str) -> str:
    """Clave de widget ligada al formulario actual (p. ej. 'f0_cliente').

    Streamlit conserva el valor de un widget mientras su clave exista; para empezar un
    acta nueva en blanco se cambia el id del formulario y así todas las claves son nuevas.
    """
    return f"f{st.session_state.get(FORM_ID, 0)}_{nombre}"


def limpiar_formulario() -> None:
    """Deja el formulario en blanco para registrar otra acta (usar como on_click)."""
    prefijo = k("")
    for clave in [c for c in st.session_state if str(c).startswith(prefijo)]:
        del st.session_state[clave]
    st.session_state[FORM_ID] = st.session_state.get(FORM_ID, 0) + 1


# ---------- Autocompletado ----------
# Cliente y Ubicación se escriben a mano hasta tener la lista oficial de clientes.
CAMPOS_CATALOGO = ["equipo", "marca", "modelo", "serie"]


def _seleccion() -> dict[str, str]:
    return {c: st.session_state.get(k(c)) or "" for c in CAMPOS_CATALOGO}


def _autocompletar() -> None:
    """Al elegir un valor, completa los campos vacíos que quedan determinados
    (p. ej. una serie única define equipo, marca y modelo). Si hay varias coincidencias
    no se completa nada: decide el ingeniero con el desplegable."""
    for campo, valor in cargar_catalogo().autocompletar(_seleccion()).items():
        st.session_state[k(campo)] = valor


def _campo_catalogo(contenedor, texto: str, campo: str) -> str:
    """Desplegable con búsqueda: al escribir 'analiz' sugiere 'Analizador Bioquimico', etc.
    Acepta valores nuevos que no estén en el catálogo."""
    valor = contenedor.selectbox(
        etiqueta(texto),
        cargar_catalogo().opciones(campo, _seleccion()),
        index=None,
        key=k(campo),
        placeholder="Escribe para buscar o agregar…",
        accept_new_options=True,
        on_change=_autocompletar,
    )
    return limpiar(valor)


def _limpiar_otro() -> None:
    if st.session_state.get(k("tipo_servicio")) != config.TIPO_SERVICIO_OTRO:
        st.session_state[k("tipo_servicio_otro")] = ""


def formulario_acta() -> Acta:
    acta = Acta()

    # ---------- N.° de acta ----------
    col_label, col_num, _ = st.columns([1, 1.2, 1])
    col_label.markdown('<div class="acta-number-label">N.°</div>', unsafe_allow_html=True)
    acta.numero = col_num.text_input(
        "N.° de Acta", key=k("acta_numero"), placeholder="2026-00051", label_visibility="collapsed"
    ).strip()

    # ---------- Datos generales ----------
    with seccion("datos", "Datos generales", obligatorio=False):
        c1, c2 = st.columns(2)
        acta.fecha = c1.date_input(etiqueta("Fecha"), value=hoy(), format="DD/MM/YYYY", key=k("fecha"))
        acta.ubicacion = c2.text_input(etiqueta("Ubicación"), key=k("ubicacion")).strip()
        c1, c2 = st.columns(2)
        acta.cliente = c1.text_input(etiqueta("Cliente"), key=k("cliente")).strip()
        acta.equipo = _campo_catalogo(c2, "Equipo", "equipo")
        c1, c2 = st.columns(2)
        acta.marca = _campo_catalogo(c1, "Marca", "marca")
        acta.modelo = _campo_catalogo(c2, "Modelo", "modelo")
        acta.numero_serie = _campo_catalogo(st, "N.° Serie", "serie")

    # ---------- Tipo de servicio ----------
    with seccion("tipo_servicio", "Tipo de servicio"):
        c1, c2 = st.columns([2, 1], vertical_alignment="bottom")
        acta.tipo_servicio = c1.radio(
            "Tipo de servicio",
            config.TIPOS_SERVICIO,
            index=None,
            horizontal=True,
            key=k("tipo_servicio"),
            on_change=_limpiar_otro,
            label_visibility="collapsed",
        )
        acta.tipo_servicio_otro = c2.text_input(
            "Otro",
            key=k("tipo_servicio_otro"),
            placeholder="especificar",
            disabled=acta.tipo_servicio != config.TIPO_SERVICIO_OTRO,
            label_visibility="collapsed",
        ).strip()

    # ---------- Antecedentes ----------
    with seccion("antecedentes", "Antecedentes iniciales"):
        acta.antecedentes = lista_dinamica(
            k("antecedentes"), "Ej: El cliente reportó ruido inusual en el equipo..."
        )

    # ---------- Registro de horas ----------
    with seccion("horas", "Registro de horas", obligatorio=False):
        c1, c2 = st.columns(2)
        acta.hora_inicio_trabajo = c1.time_input(
            etiqueta("Hora de inicio de trabajo"),
            value=None,
            step=PASO_MINUTOS,
            key=k("hora_inicio_trabajo"),
        )
        acta.hora_fin_trabajo = c2.time_input(
            etiqueta("Hora de término de trabajo"),
            value=None,
            step=PASO_MINUTOS,
            key=k("hora_fin_trabajo"),
        )

    # ---------- Acciones realizadas ----------
    with seccion(
        "acciones", "Acciones realizadas", nota="(detalla cada parte verificada, corregida o probada)"
    ):
        acta.acciones = lista_dinamica(k("acciones"), "Ej: Se revisó el sistema de refrigeración...")

    # ---------- Detalle del diagnóstico ----------
    with seccion("diagnostico", "Detalle del diagnóstico"):
        acta.diagnostico = lista_dinamica(
            k("diagnostico"), "Ej: Se detectó desgaste en la correa principal..."
        )

    # ---------- Estado final ----------
    with seccion("estado_final", "Estado final del servicio"):
        acta.estado_final = st.radio(
            "Estado final del servicio",
            config.ESTADOS_FINALES,
            index=None,
            horizontal=True,
            key=k("estado_final"),
            label_visibility="collapsed",
        )

    # ---------- Artículos empleados (opcional) ----------
    with seccion(
        "articulos",
        "Artículos empleados",
        obligatorio=False,
        nota="(si llenas una fila, completa las 3 columnas)",
    ):
        acta.articulos = tabla_articulos(k("articulos"))

    # ---------- Observaciones ----------
    with seccion("observaciones", "Observaciones y/o recomendaciones"):
        acta.observaciones = lista_dinamica(
            k("observaciones"), "Ej: Se recomienda cambiar el filtro en la próxima visita..."
        )

    # ---------- Conformidad (firmas) ----------
    with seccion("firmas", "Conformidad"):
        c1, c2 = st.columns(2, gap="large")
        with c1:
            acta.firma_cliente_png = firma(k("firma_cliente"), "Cliente")
            acta.nombre_cliente = st.text_input(etiqueta("Nombre del cliente"), key=k("nombre_cliente")).strip()
        with c2:
            acta.firma_representante_png = firma(k("firma_representante"), config.EMPRESA)
            acta.nombre_representante = st.text_input(
                etiqueta("Nombre del representante"), key=k("nombre_representante")
            ).strip()

    return acta
