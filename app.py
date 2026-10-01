"""Punto de entrada: `streamlit run app.py`."""

import streamlit as st

from acta_app import config
from acta_app.models import Acta, ahora
from acta_app.pdf import generar_pdf, nombre_archivo_pdf
from acta_app.storage import (
    ActaDuplicadaError,
    ActaNoEncontradaError,
    AlmacenamientoError,
    configuracion_sharepoint,
    fila_plana,
    formatear_valor,
    obtener_repositorio,
    registro_desde_acta,
    usa_sharepoint,
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
from acta_app.ui.catalogo_ui import refrescar_catalogo
from acta_app.ui.styles import aplicar_estilos
from acta_app.validation import validar_acta

st.set_page_config(
    page_title="Acta de Atención Digital - Sistemas Analíticos",
    layout="centered",
)
aplicar_estilos()


def correo_usuario() -> str:
    """Correo de la cuenta Microsoft (claim email o, si no viene, preferred_username)."""
    return str(st.user.get("email") or st.user.get("preferred_username") or "").strip().lower()


def correo_permitido(correo: str) -> bool:
    return correo.endswith("@" + config.DOMINIO_PERMITIDO.lower())


def exigir_inicio_de_sesion() -> None:
    """Si los Secrets tienen la sección [auth], solo entran cuentas de la empresa
    (inicio de sesión con Microsoft). Sin esa sección, la app queda abierta como hoy."""
    try:
        con_login = "auth" in st.secrets
    except Exception:
        con_login = False
    if not con_login:
        return
    if st.user.is_logged_in:
        if correo_permitido(correo_usuario()):
            return
        encabezado()
        st.error(
            f"La cuenta {correo_usuario() or '(sin correo)'} no pertenece a @{config.DOMINIO_PERMITIDO}. "
            "Cierra sesión y entra con tu correo de Sistemas Analíticos."
        )
        st.button("Cerrar sesión", on_click=st.logout, width="stretch")
        st.stop()
    encabezado()
    st.info("Inicia sesión con tu cuenta de Sistemas Analíticos para registrar actas.")
    st.button("Iniciar sesión con Microsoft", on_click=st.login, type="primary", width="stretch")
    st.stop()


exigir_inicio_de_sesion()


@st.dialog("Vista previa de la fila (Excel)", width="large")
def dialogo_fila(acta: Acta) -> None:
    # Mismas columnas que tendrá la fila en el Excel maestro (un ítem por columna).
    registro = registro_desde_acta(acta)
    registro.valores["PDF original"] = "(se asigna al guardar)"
    fila = fila_plana(registro)
    texto = "\n".join(f"{k}: {formatear_valor(v) or '—'}" for k, v in fila.items())
    st.code(texto, language=None, wrap_lines=True)


@st.dialog("Acta guardada correctamente")
def dialogo_guardado(acta: Acta, pdf: bytes, nombre_pdf: str, total_actas: int, enlace_pdf: str = "") -> None:
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
    if enlace_pdf.startswith("http"):
        st.link_button("Abrir el PDF en SharePoint", enlace_pdf, width="stretch")
    # La limpieza va en el callback (antes de dibujar) y st.rerun() recarga toda la página,
    # no solo la ventana.
    if st.button("Registrar una nueva acta", on_click=limpiar_formulario, width="stretch"):
        st.rerun()


MODO_NUEVA, MODO_CORREGIR = "Nueva acta", "Corregir un acta"


def volver_a_nueva_acta() -> None:
    salir_de_correccion()
    st.session_state["modo"] = MODO_NUEVA


@st.dialog("Corrección guardada")
def dialogo_correccion(acta: Acta, pdf: bytes, nombre_pdf: str, enlace_pdf: str = "") -> None:
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
    if enlace_pdf.startswith("http"):
        st.link_button("Abrir el PDF corregido en SharePoint", enlace_pdf, width="stretch")
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
    except AlmacenamientoError as exc:
        st.session_state["aviso_correccion"] = str(exc)


def selector_correccion() -> Acta | None:
    """Elegir el acta a corregir. Devuelve el acta original cargada (o None)."""
    with seccion("corregir", "Corregir un acta", obligatorio=False):
        try:
            numeros = obtener_repositorio().numeros()
        except AlmacenamientoError as exc:
            st.error(str(exc))
            return None
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
    """Dónde quedan las actas: carpeta de SharePoint o, sin SharePoint, descargas."""
    repo = obtener_repositorio()
    try:
        excel = repo.excel_bytes()
        total = 0 if excel is None else len(repo.leer_actas())
        carpeta = repo.enlace_carpeta()
    except AlmacenamientoError as exc:
        st.error(f"No se pudo leer la base de datos de actas: {exc}")
        return
    etiqueta_total = "acta registrada" if total == 1 else "actas registradas"
    with st.expander(f"Base de datos de actas ({total} {etiqueta_total})"):
        if carpeta:
            st.link_button("Abrir la carpeta de actas en SharePoint", carpeta, width="stretch")
            st.caption(
                "Allí están Actas.xlsx (con los enlaces a cada PDF), la carpeta PDF y "
                "Equipos.xlsx. Solo pueden abrirlos las cuentas con acceso a la carpeta."
            )
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
        if carpeta:
            return
        st.download_button(
            "Descargar Excel + PDFs (ZIP)",
            data=repo.exportar_zip,  # se arma solo al pulsar el botón
            file_name=f"actas_{ahora():%Y%m%d_%H%M}.zip",
            mime="application/zip",
            on_click="ignore",
            width="stretch",
        )
        st.caption(
            "En las columnas «PDF original» y «PDF corregido» cada nombre es un enlace al PDF. "
            "Funcionan al descomprimir el ZIP (Excel y carpeta «pdfs» juntos)."
        )


def seccion_conexion() -> None:
    """Estado del almacenamiento y verificación de la conexión con SharePoint."""
    if not usa_sharepoint():
        st.caption(
            "⚠️ Sin conexión a SharePoint: las actas se guardan en el servidor de la app, que "
            "se borra al reiniciarla. Descarga el ZIP para conservarlas."
        )
        return
    cfg = configuracion_sharepoint() or {}
    with st.expander("Conexión con SharePoint"):
        st.caption(
            f"Carpeta: {cfg.get('carpeta', config.SHAREPOINT_CARPETA)} · "
            f"sitio {cfg.get('sitio', config.SHAREPOINT_SITIO).rsplit('/', 1)[-1]}"
        )
        c1, c2 = st.columns(2)
        if c1.button("Probar conexión", width="stretch"):
            for ok, mensaje in obtener_repositorio().probar_conexion():
                (st.success if ok else st.error)(mensaje, icon="✅" if ok else "❌")
        if c2.button("Actualizar catálogo de equipos", width="stretch"):
            refrescar_catalogo()
            st.success("Se volverá a leer Equipos.xlsx de SharePoint.", icon="✅")
        if st.button("Ordenar firmas antiguas en carpetas por acta", width="stretch"):
            try:
                with st.spinner("Moviendo firmas…"):
                    movidas = obtener_repositorio().ordenar_firmas()
            except AlmacenamientoError as exc:
                st.error(str(exc), icon="❌")
            else:
                st.success(
                    f"Listo: {movidas} firma(s) movidas a Firmas/<N.° de acta>/."
                    if movidas else "No había firmas sueltas por ordenar.",
                    icon="✅",
                )


encabezado()
st.markdown(
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
    try:
        existe = repo.existe(acta.numero)
    except AlmacenamientoError as exc:
        aviso("error", str(exc))
        return
    if existe:
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
        dialogo_guardado(acta, pdf, nombre_pdf, resultado.total_actas, resultado.ubicacion_pdf)


def guardar_correccion(acta: Acta) -> None:
    acta.fecha_correccion = ahora()
    pdf = generar_pdf(acta)
    nombre_pdf = nombre_archivo_pdf(acta)
    try:
        resultado = obtener_repositorio().corregir(acta, pdf, nombre_pdf)
    except (AlmacenamientoError, ActaNoEncontradaError) as exc:
        mensaje = str(exc) if isinstance(exc, AlmacenamientoError) else f"No se encontró el acta N.° {acta.numero}."
        aviso("error", mensaje)
    else:
        banner.success(f"Corrección del acta N.° {acta.numero} guardada (revisión {acta.revision}).", icon="✅")
        dialogo_correccion(acta, pdf, nombre_pdf, resultado.ubicacion_pdf)


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
seccion_conexion()
usuario = ""
try:
    if "auth" in st.secrets and st.user.is_logged_in:
        usuario = f" · {st.user.get('email') or st.user.get('name') or ''}"
        st.button("Cerrar sesión", on_click=st.logout, type="tertiary")
except Exception:
    pass
st.markdown(
    f'<div class="app-version">{config.SITIO_WEB} · versión {config.version_desplegada()}{usuario}</div>',
    unsafe_allow_html=True,
)
