"""Punto de entrada: `streamlit run app.py`."""

import streamlit as st

from acta_app import config
from acta_app.models import Acta
from acta_app.ui.components import encabezado
from acta_app.ui.form import formulario_acta
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
    fila = acta.a_fila()
    st.code("\n".join(f"{k}: {v or '—'}" for k, v in fila.items()), language=None, wrap_lines=True)


encabezado()
st.markdown(
    '<div class="top-note"><strong>Prototipo (MVP).</strong> Esta acta se ve y se completa igual que '
    "el formato físico FO-ING-02. Al presionar <em>Guardar acta</em>, cada campo se convierte en una "
    "columna y esta acta se agrega como una fila nueva a la base de datos de actas.</div>"
    '<div class="required-note"><span class="req-star">*</span> Campo obligatorio</div>',
    unsafe_allow_html=True,
)
banner = st.empty()

acta = formulario_acta()

col_ver, col_guardar = st.columns(2)
ver_fila = col_ver.button("Ver fila de datos", key="btn_ver_fila", width="stretch")
guardar = col_guardar.button("Guardar acta", key="btn_guardar", width="stretch")

if ver_fila:
    dialogo_fila(acta)

if guardar:
    errores = validar_acta(acta)
    if errores:
        mensaje = "Falta completar: " + ", ".join(errores)
        banner.warning(mensaje, icon="⚠️")
        st.warning(mensaje, icon="⚠️")
    else:
        # Paso siguiente: generar el PDF y agregar la fila al Excel maestro.
        banner.success(f"Acta N.° {acta.numero} validada correctamente.", icon="✅")
        st.success(
            "Formulario completo y válido. La generación del PDF y el guardado en el Excel "
            "maestro se conectan en el siguiente paso.",
            icon="✅",
        )
