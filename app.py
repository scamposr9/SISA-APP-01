"""Punto de entrada: `streamlit run app.py`."""

import streamlit as st

from acta_app import config
from acta_app.models import Acta, ahora
from acta_app.pdf import generar_pdf, nombre_archivo_pdf
from acta_app.storage import (
    ActaDuplicadaError,
    AlmacenamientoError,
    fila_plana,
    formatear_valor,
    obtener_repositorio,
    registro_desde_acta,
)
from acta_app.ui.components import encabezado
from acta_app.ui.form import formulario_acta, limpiar_formulario
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
    fila = fila_plana(registro_desde_acta(acta, archivo_pdf="(se asigna al guardar)"))
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
            "En la columna «Archivo PDF» cada nombre es un enlace al PDF. Los enlaces funcionan "
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
banner = st.empty()

acta = formulario_acta()

col_ver, col_guardar = st.columns(2)
ver_fila = col_ver.button("Ver fila de datos", key="btn_ver_fila", width="stretch")
guardar = col_guardar.button("Guardar acta", key="btn_guardar", width="stretch")


def aviso(tipo: str, mensaje: str) -> None:
    """Muestra el aviso arriba (como el prototipo) y junto a los botones."""
    icono = {"warning": "⚠️", "error": "❌", "success": "✅"}[tipo]
    getattr(banner, tipo)(mensaje, icon=icono)
    getattr(st, tipo)(mensaje, icon=icono)


if ver_fila:
    dialogo_fila(acta)

if guardar:
    errores = validar_acta(acta)
    repo = obtener_repositorio()
    if errores:
        aviso("warning", "Falta completar: " + ", ".join(errores))
    elif repo.existe(acta.numero):
        aviso("warning", f"Ya existe un acta con el N.° {acta.numero}. Usa otro número.")
    else:
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

seccion_base_de_datos()
st.markdown(
    f'<div class="app-version">{config.SITIO_WEB} · versión {config.version_desplegada()}</div>',
    unsafe_allow_html=True,
)
