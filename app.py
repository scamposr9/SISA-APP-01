"""Punto de entrada: `streamlit run app.py`."""

import streamlit as st

from acta_app import config
from acta_app.models import Acta, ahora
from acta_app.pdf import generar_pdf, nombre_archivo_pdf
from acta_app.storage import (
    ActaDuplicadaError,
    ActaNoEncontradaError,
    AlmacenamientoError,
    fila_plana,
    formatear_valor,
    obtener_repositorio,
    registro_desde_acta,
)
from acta_app.ui.components import encabezado, etiqueta, seccion
from acta_app.ui.form import (
    acta_en_correccion,
    cargar_en_formulario,
    formulario_acta,
    k,
    limpiar_formulario,
    salir_de_correccion,
)
from acta_app.ui.styles import aplicar_estilos
from acta_app.validation import validar_acta

st.set_page_config(
    page_title="Acta de Atención Digital - Sistemas Analíticos",
    page_icon=str(config.LOGO_PATH),
    layout="centered",
)
aplicar_estilos()


@st.dialog("Vista previa de la fila (Excel)", width="large")
def dialogo_fila(acta: Acta) -> None:
    # Mismas columnas que tendrá la fila en el Excel maestro (un ítem por columna).
    registro = registro_desde_acta(acta)
    registro.valores["PDF original"] = "(se asigna al guardar)"
    fila = fila_plana(registro)
    texto = "\n".join(f"{k}: {formatear_valor(v) or '—'}" for k, v in fila.items())
    st.code(texto, language=None, wrap_lines=True)


@st.dialog("Acta guardada correctamente")
def dialogo_guardado(acta: Acta, pdf: bytes, nombre_pdf: str, total_actas: int) -> None:
    st.write(
        f"El acta N.° {acta.numero} se agregó como una nueva fila al Excel maestro "
        f"({total_actas} {'acta registrada' if total_actas == 1 else 'actas registradas'} en total) "
        "y se generó el PDF con el mismo formato "
        "del acta física."
    )
    st.download_button(
        "Descargar PDF",
        data=pdf,
        file_name=nombre_pdf,
        mime="application/pdf",
        on_click="ignore",
        type="primary",
        width="stretch",
    )
    # La limpieza va en el callback (antes de dibujar) y st.rerun() recarga toda la página,
    # no solo la ventana.
    if st.button("Registrar una nueva acta", on_click=limpiar_formulario, width="stretch"):
        st.rerun()


MODO_NUEVA, MODO_CORREGIR = "Nueva acta", "Corregir un acta"


def volver_a_nueva_acta() -> None:
    salir_de_correccion()
    st.session_state["modo"] = MODO_NUEVA


@st.dialog("Corrección guardada")
def dialogo_correccion(acta: Acta, pdf: bytes, nombre_pdf: str) -> None:
    st.write(
        f"Se actualizó la fila del acta N.° {acta.numero} en el Excel maestro con los datos "
        f"corregidos (revisión {acta.revision}). El PDF original se conserva y se creó "
        f"«{nombre_pdf}»; ambos quedan enlazados en la fila."
    )
    st.download_button(
        "Descargar PDF corregido",
        data=pdf,
        file_name=nombre_pdf,
        mime="application/pdf",
        on_click="ignore",
        type="primary",
        width="stretch",
    )
    if st.button("Volver a registrar actas nuevas", on_click=volver_a_nueva_acta, width="stretch"):
        st.rerun()


def _cargar_para_corregir() -> None:
    numero = st.session_state.get("acta_a_corregir")
    if not numero:
        return
    try:
        cargar_en_formulario(obtener_repositorio().obtener(numero))
    except ActaNoEncontradaError:
        st.session_state["aviso_correccion"] = f"No se encontró el acta N.° {numero}."


def selector_correccion() -> Acta | None:
    """Elegir el acta a corregir. Devuelve el acta original cargada (o None)."""
    numeros = obtener_repositorio().numeros()
    with seccion("corregir", "Corregir un acta", obligatorio=False):
        if not numeros:
            st.info("Todavía no hay actas guardadas para corregir.")
            return None
        c1, c2 = st.columns([2, 1], vertical_alignment="bottom")
        c1.selectbox(
            "N.° de acta a corregir",
            numeros,
            index=None,
            key="acta_a_corregir",
            placeholder="Escribe o elige el número…",
        )
        c2.button("Cargar acta", on_click=_cargar_para_corregir, width="stretch")
        if aviso := st.session_state.pop("aviso_correccion", None):
            st.warning(aviso)
        original = acta_en_correccion()
        if original is None:
            st.caption("Al cargarla, sus datos aparecen abajo para que los corrijas.")
            return None
        st.info(
            f"Corrigiendo el acta N.° {original.numero} (revisión actual: {original.revision}). "
            f"Al guardar se actualiza su fila en el Excel y se crea el PDF de la revisión "
            f"{original.revision + 1}; el PDF original se conserva."
        )
        st.text_area(
            etiqueta("Motivo de la corrección"),
            key=k("motivo_correccion"),
            placeholder="Ej: Se corrigió el número de serie del equipo.",
            height=80,
        )
        st.text_input(etiqueta("Corregido por"), key=k("corregido_por"))
        return original


def aplicar_datos_de_correccion(acta: Acta, original: Acta) -> Acta:
    acta.revision = original.revision + 1
    acta.fecha_registro = original.fecha_registro
    acta.corregido_por = (st.session_state.get(k("corregido_por")) or "").strip()
    acta.motivo_correccion = (st.session_state.get(k("motivo_correccion")) or "").strip()
    return acta


def seccion_base_de_datos() -> None:
    """Descargas del Excel maestro y los PDFs (en la nube el disco no es permanente)."""
    repo = obtener_repositorio()
    excel = repo.excel_bytes()
    total = 0 if excel is None else len(repo.leer_actas())
    etiqueta = "acta registrada" if total == 1 else "actas registradas"
    with st.expander(f"Base de datos de actas ({total} {etiqueta})"):
        if excel is None:
            st.caption("Todavía no se ha guardado ninguna acta.")
            return
        st.download_button(
            "Descargar Excel maestro",
            data=excel,
            file_name=f"actas_maestro_{ahora():%Y%m%d_%H%M}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            on_click="ignore",
            width="stretch",
        )
        st.download_button(
            "Descargar Excel + PDFs (ZIP)",
            data=repo.exportar_zip,  # se arma solo al pulsar el botón
            file_name=f"actas_{ahora():%Y%m%d_%H%M}.zip",
            mime="application/zip",
            on_click="ignore",
            width="stretch",
        )
        st.caption(
            "En las columnas «PDF original» y «PDF corregido» cada nombre es un enlace al PDF. Funcionan "
            "al descomprimir el ZIP (Excel y carpeta «pdfs» juntos). Con SharePoint, abrirán el "
            "PDF directamente en la biblioteca."
        )


encabezado()
st.markdown(
    '<div class="top-note"><strong>Prototipo (MVP).</strong> Esta acta se ve y se completa igual que '
    "el formato físico FO-ING-02. Al presionar <em>Guardar acta</em>, cada campo se convierte en una "
    "columna y esta acta se agrega como una fila nueva a la base de datos de actas.</div>"
    '<div class="required-note"><span class="req-star">*</span> Campo obligatorio</div>',
    unsafe_allow_html=True,
)
modo = st.segmented_control(
    "Modo",
    [MODO_NUEVA, MODO_CORREGIR],
    default=MODO_NUEVA,
    required=True,
    key="modo",
    on_change=salir_de_correccion,
    label_visibility="collapsed",
)
banner = st.empty()

original = selector_correccion() if modo == MODO_CORREGIR else None
if modo == MODO_CORREGIR and original is None:
    acta = None
else:
    acta = formulario_acta()
    if original is not None:
        acta = aplicar_datos_de_correccion(acta, original)
    col_ver, col_guardar = st.columns(2)
    ver_fila = col_ver.button("Ver fila de datos", key="btn_ver_fila", width="stretch")
    texto_guardar = "Guardar corrección" if original is not None else "Guardar acta"
    guardar = col_guardar.button(texto_guardar, key="btn_guardar", width="stretch")


def aviso(tipo: str, mensaje: str) -> None:
    """Muestra el aviso arriba (como el prototipo) y junto a los botones."""
    icono = {"warning": "⚠️", "error": "❌", "success": "✅"}[tipo]
    getattr(banner, tipo)(mensaje, icon=icono)
    getattr(st, tipo)(mensaje, icon=icono)


def guardar_acta_nueva(acta: Acta) -> None:
    repo = obtener_repositorio()
    if repo.existe(acta.numero):
        aviso("warning", f"Ya existe un acta con el N.° {acta.numero}. Usa otro número.")
        return
    acta.fecha_registro = ahora()
    pdf = generar_pdf(acta)
    nombre_pdf = nombre_archivo_pdf(acta)
    try:
        resultado = repo.guardar(acta, pdf, nombre_pdf)
    except ActaDuplicadaError:
        aviso("warning", f"Ya existe un acta con el N.° {acta.numero}. Usa otro número.")
    except AlmacenamientoError as exc:
        aviso("error", str(exc))
    else:
        banner.success(f"Acta N.° {acta.numero} guardada correctamente.", icon="✅")
        dialogo_guardado(acta, pdf, nombre_pdf, resultado.total_actas)


def guardar_correccion(acta: Acta) -> None:
    acta.fecha_correccion = ahora()
    pdf = generar_pdf(acta)
    nombre_pdf = nombre_archivo_pdf(acta)
    try:
        obtener_repositorio().corregir(acta, pdf, nombre_pdf)
    except (AlmacenamientoError, ActaNoEncontradaError) as exc:
        mensaje = str(exc) if isinstance(exc, AlmacenamientoError) else f"No se encontró el acta N.° {acta.numero}."
        aviso("error", mensaje)
    else:
        banner.success(f"Corrección del acta N.° {acta.numero} guardada (revisión {acta.revision}).", icon="✅")
        dialogo_correccion(acta, pdf, nombre_pdf)


if acta is not None and ver_fila:
    dialogo_fila(acta)

if acta is not None and guardar:
    errores = validar_acta(acta)
    if original is not None:
        errores += [e for e, v in (("Motivo de la corrección", acta.motivo_correccion),
                                   ("Corregido por", acta.corregido_por)) if not v]
    if errores:
        aviso("warning", "Falta completar: " + ", ".join(errores))
    elif original is not None:
        guardar_correccion(acta)
    else:
        guardar_acta_nueva(acta)

seccion_base_de_datos()
st.markdown(
    f'<div class="app-version">{config.SITIO_WEB} · versión {config.version_desplegada()}</div>',
    unsafe_allow_html=True,
)
