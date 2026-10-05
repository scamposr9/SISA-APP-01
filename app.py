"""Punto de entrada: `streamlit run app.py`."""

import streamlit as st

from acta_app import config
from acta_app.models import Acta, ahora
from acta_app.pdf import generar_pdf, nombre_archivo_pdf
from acta_app.storage import (
    ActaDuplicadaError,
    ActaNoEncontradaError,
    AlmacenamientoError,
    EncuestaYaRespondidaError,
    configuracion_sharepoint,
    fila_plana,
    formatear_valor,
    obtener_repositorio,
    registro_desde_acta,
    usa_sharepoint,
)
from acta_app.ui.components import encabezado, etiqueta, seccion
from acta_app.encuesta_correo import enviar_invitacion, errores_correo, normalizar_correo
from acta_app.ui.encuesta import (
    abrir_encuesta,
    codigo_en_la_direccion,
    numero_en_la_direccion,
    pagina_encuesta,
)
from acta_app.ui.form import (
    acta_en_correccion,
    cargar_en_formulario,
    formulario_acta,
    k,
    limpiar_formulario,
    salir_de_correccion,
)
from acta_app.equipos_nuevos import es_equipo_nuevo
from acta_app.protocolos import Protocolos
from acta_app.repuestos import Repuestos
from acta_app.ui.catalogo_ui import cargar_catalogo, refrescar_catalogo
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


def es_desarrollador() -> bool:
    """¿Ve las secciones de administración (base de datos y conexión con SharePoint)?

    Con inicio de sesión activo, solo los correos de `desarrolladores` en la sección [app]
    de los Secrets. Sin inicio de sesión (p. ej. en una computadora de pruebas), todos."""
    try:
        if "auth" not in st.secrets:
            return True
        lista = st.secrets.get("app", {}).get("desarrolladores", [])
    except Exception:  # sin archivo de Secrets
        return True
    correo = correo_usuario()
    return bool(correo) and correo in {str(c).strip().lower() for c in lista}


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


# Enlace de la encuesta enviado al cliente (?encuesta=<N.°>&t=<código>): se abre sin iniciar
# sesión, solo la encuesta, y solo si el código es el de la invitación vigente de esa acta.
if (numero_encuesta := numero_en_la_direccion()) and (codigo_encuesta := codigo_en_la_direccion()):
    pagina_encuesta(numero_encuesta, codigo_encuesta)
    st.stop()

exigir_inicio_de_sesion()

# Sin código (?encuesta=<N.°>): solo para pruebas de los desarrolladores.
if numero_encuesta := numero_en_la_direccion():
    if es_desarrollador():
        pagina_encuesta(numero_encuesta)
    else:
        encabezado()
        st.error("La encuesta se abre con el enlace enviado al correo del cliente.", icon="❌")
    st.stop()


@st.dialog("Vista previa de la fila (Excel)", width="large")
def dialogo_fila(acta: Acta) -> None:
    # Mismas columnas que tendrá la fila en el Excel maestro (un ítem por columna).
    registro = registro_desde_acta(acta)
    registro.valores["PDF original"] = "(se asigna al guardar)"
    fila = fila_plana(registro)
    texto = "\n".join(f"{k}: {formatear_valor(v) or '—'}" for k, v in fila.items())
    st.code(texto, language=None, wrap_lines=True)


@st.dialog("Acta guardada correctamente")
def dialogo_guardado(acta: Acta, pdf: bytes, nombre_pdf: str, total_actas: int, enlace_pdf: str = "",
                     envio: tuple[bool, str] | None = None) -> None:
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
    if envio is not None:
        enviado, mensaje = envio
        (st.success if enviado else st.error)(mensaje, icon="📧" if enviado else "❌")
    if es_desarrollador() and st.button("Abrir encuesta de satisfacción (prueba)", on_click=abrir_encuesta,
                                        args=(acta.numero,), width="stretch"):
        st.rerun()
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


def reenviar_encuesta() -> None:
    """Corrige el correo de la encuesta de un acta: envía un enlace nuevo y anula el anterior."""
    try:
        numeros = obtener_repositorio().numeros()
    except AlmacenamientoError as exc:
        st.error(str(exc), icon="❌")
        return
    numero = st.selectbox("Acta", numeros, index=None, placeholder="N.° de acta", key="reenvio_numero")
    correo = st.text_input("Nuevo correo del cliente", key="reenvio_correo")
    confirmacion = st.text_input("Confirma el correo", key="reenvio_conf")
    if st.button("Enviar encuesta", type="primary", key="reenvio_enviar"):
        errores = errores_correo(correo, confirmacion) or ([] if correo else ["Escribe el correo del cliente"])
        if not numero or errores:
            st.warning("Elige el acta. " * (not numero) + " ".join(errores), icon="⚠️")
            return
        try:
            acta = obtener_repositorio().obtener(numero)
        except (AlmacenamientoError, ActaNoEncontradaError) as exc:
            st.error(str(exc), icon="❌")
            return
        enviado, mensaje = enviar_encuesta(acta, normalizar_correo(correo))
        (st.success if enviado else st.error)(mensaje, icon="📧" if enviado else "❌")


def mostrar_repuestos() -> None:
    """Lo que la app entendió de Repuestos.xlsx, para verificarlo."""
    try:
        datos = obtener_repositorio().leer_repuestos()
        repuestos = Repuestos.desde_bytes(datos) if datos else None
    except Exception as exc:  # Excel ilegible o sin conexión
        st.error(f"No se pudo leer «{config.SHAREPOINT_REPUESTOS}»: {exc}", icon="❌")
        return
    if repuestos is None:
        st.warning(f"«{config.SHAREPOINT_REPUESTOS}» no está en la carpeta de actas.", icon="⚠️")
        return
    for hoja in repuestos.hojas:
        st.write(f"Hoja **{hoja.nombre}**: columnas «{hoja.columna_codigo}» y «{hoja.columna_descripcion}», "
                 f"{hoja.filas} fila(s) con código y descripción.")
    if not repuestos.codigos:
        st.warning("No se encontró una fila de encabezados con «Código» y «Descripción».", icon="⚠️")
        return
    st.success(f"{len(repuestos.codigos)} código(s) distinto(s) para el autocompletado.", icon="✅")
    st.dataframe(
        [{"Código": c, "Descripción": repuestos.descripcion(c)} for c in repuestos.opciones()[:200]],
        hide_index=True,
    )


def mostrar_protocolos() -> None:
    """Lo que la app entendió de Mantenimientos Preventivos.xlsx, para verificarlo."""
    try:
        datos = obtener_repositorio().leer_protocolos()
        protocolos = Protocolos.desde_bytes(datos) if datos else None
    except Exception as exc:  # Excel ilegible o sin conexión
        st.error(f"No se pudo leer «{config.SHAREPOINT_PROTOCOLOS}»: {exc}", icon="❌")
        return
    if protocolos is None:
        st.warning(f"«{config.SHAREPOINT_PROTOCOLOS}» no está en la carpeta de actas.", icon="⚠️")
        return
    if not protocolos.lista:
        st.warning(
            "Se abrió el Excel pero no se encontró ningún protocolo: revisa que tenga MARCA, "
            "MODELO y una columna «Parte mantenida».",
            icon="⚠️",
        )
        return
    hojas_usadas = sum(len(p.hojas) for p in protocolos.lista)
    st.success(
        f"{len(protocolos.lista)} protocolo(s) detectado(s) a partir de {hojas_usadas} hoja(s) "
        f"del Excel (las hojas con el mismo equipo, marca y modelo se juntan).",
        icon="✅",
    )
    st.dataframe(
        [
            {"Hojas": ", ".join(p.hojas), "Equipo": p.equipo, "Marca": p.marca, "Modelo": p.modelo,
             "Registros": p.registros, "Actividades": len(p.actividades),
             "Primera actividad": p.actividades[0]}
            for p in protocolos.lista
        ],
        hide_index=True,
    )

    if protocolos.descartes:
        st.warning(f"{len(protocolos.descartes)} hoja(s) del Excel no se pudieron leer como protocolo:", icon="⚠️")
        st.dataframe([{"Hoja": h, "Motivo": m} for h, m in protocolos.descartes], hide_index=True)

    catalogo = cargar_catalogo()
    sin_equipo = [p for p in protocolos.lista if not _protocolo_en_catalogo(p, catalogo)]
    if sin_equipo:
        st.warning(
            f"{len(sin_equipo)} protocolo(s) no coinciden con ningún equipo de Equipos.xlsx (misma "
            "marca y modelo). El checklist solo aparece si el ingeniero escribe esa marca y ese modelo.",
            icon="⚠️",
        )
        st.dataframe(
            [{"Hojas": ", ".join(p.hojas), "Equipo": p.equipo, "Marca": p.marca, "Modelo": p.modelo}
             for p in sin_equipo],
            hide_index=True,
        )
    else:
        st.info("Todos los protocolos coinciden con algún equipo de Equipos.xlsx.", icon="ℹ️")


def _protocolo_en_catalogo(protocolo, catalogo) -> bool:
    """¿Algún equipo de Equipos.xlsx tiene un modelo y una marca que llevan a este protocolo?"""
    datos = catalogo.datos
    if datos.empty:
        return False
    unicos = datos[["equipo", "marca", "modelo"]].drop_duplicates()
    return any(
        Protocolos([protocolo]).buscar(e, m, mo) is protocolo
        for e, m, mo in unicos.itertuples(index=False)
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
        with st.popover("Reenviar encuesta a otro correo", width="stretch"):
            reenviar_encuesta()
        if st.button("Ver repuestos detectados (Repuestos.xlsx)", width="stretch"):
            mostrar_repuestos()
        if st.button("Ver protocolos de mantenimiento preventivo detectados", width="stretch"):
            mostrar_protocolos()


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


def anotar_si_es_equipo_nuevo(acta: Acta) -> None:
    """Si la serie no está en el catálogo, anota el equipo en Equipos_nuevos.xlsx para
    revisarlo. Un fallo aquí no afecta al acta, que ya está guardada."""
    try:
        if not es_equipo_nuevo(cargar_catalogo(), acta):
            return
        try:
            registrado_por = correo_usuario() if st.user.is_logged_in else ""
        except Exception:  # sin [auth] en los Secrets
            registrado_por = ""
        if obtener_repositorio().registrar_equipo_nuevo(acta, registrado_por or acta.nombre_representante):
            refrescar_catalogo()
            st.info(
                f"Equipo nuevo (serie {acta.numero_serie}) anotado en Equipos_nuevos.xlsx para "
                "revisarlo y pasarlo a Equipos.xlsx.",
                icon="🆕",
            )
    except AlmacenamientoError as exc:
        st.warning(f"El acta se guardó, pero no se pudo anotar el equipo nuevo: {exc}", icon="⚠️")


def configuracion_correo() -> tuple[str, str]:
    """(buzón remitente, dirección pública de la app); se pueden cambiar en [correo]."""
    try:
        cfg = st.secrets.get("correo", {})
    except Exception:  # sin archivo de Secrets
        cfg = {}
    return cfg.get("remitente", config.CORREO_REMITENTE), cfg.get("url_app", config.URL_APP)


def enviar_encuesta(acta: Acta, correo: str) -> tuple[bool, str]:
    """Envía la invitación a la encuesta. Devuelve (enviado, mensaje para mostrar)."""
    remitente, url_app = configuracion_correo()
    try:
        envio = enviar_invitacion(obtener_repositorio(), acta, correo, remitente, url_app)
    except EncuestaYaRespondidaError:
        return False, f"La encuesta del acta N.° {acta.numero} ya fue respondida; no se envió de nuevo."
    except (AlmacenamientoError, ActaNoEncontradaError) as exc:
        return False, f"El acta se guardó, pero no se pudo enviar la encuesta a {correo}: {exc}"
    return True, (f"Encuesta enviada a {envio.correo}. El enlace vence el "
                  f"{envio.vence:%d/%m/%Y a las %H:%M}.")


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
        anotar_si_es_equipo_nuevo(acta)
        envio = enviar_encuesta(acta, acta.correo_cliente) if acta.correo_cliente else None
        dialogo_guardado(acta, pdf, nombre_pdf, resultado.total_actas, resultado.ubicacion_pdf, envio)


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
        anotar_si_es_equipo_nuevo(acta)
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

if es_desarrollador():
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
