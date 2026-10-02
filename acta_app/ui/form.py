"""Formulario completo del acta FO-ING-02. Solo arma la interfaz y devuelve un `Acta`."""

import hashlib

import streamlit as st

from acta_app import config
from acta_app.catalogo import clave, limpiar
from acta_app.models import Acta, ActividadChecklist, duracion, hoy, redondear_a_5_minutos
from acta_app.ui.catalogo_ui import cargar_catalogo, cargar_ingenieros, cargar_protocolos, cargar_repuestos
from acta_app.ui.components import (
    etiqueta,
    firma_o_camara,
    lista_dinamica,
    poner_primer_punto,
    precargar_hora,
    precargar_articulos,
    precargar_lista,
    quitar_punto,
    seccion,
    selector_hora,
    tabla_articulos,
)

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


# ---------- Corrección de actas ----------
CORRECCION = "correccion"  # acta cargada para corregir (st.session_state)
USAR_FIRMAS_ORIGINALES = "usar_firmas_originales"


def cargar_en_formulario(acta: Acta) -> None:
    """Llena el formulario con un acta guardada para corregirla (usar desde un callback,
    antes de que se dibujen los widgets)."""
    limpiar_formulario()
    st.session_state[CORRECCION] = acta
    st.session_state[USAR_FIRMAS_ORIGINALES] = True
    valores = {
        "acta_numero": acta.numero,
        "fecha": acta.fecha or hoy(),
        "ubicacion": acta.ubicacion if not _usa_desplegable("ubicacion") else acta.ubicacion or None,
        "cliente": acta.cliente if not _usa_desplegable("cliente") else acta.cliente or None,
        "equipo": acta.equipo or None,
        "marca": acta.marca or None,
        "modelo": acta.modelo or None,
        "serie": acta.numero_serie or None,
        # Actas anteriores con «Otro» escrito a mano: al corregirlas hay que elegir una opción.
        "tipo_servicio": acta.tipo_servicio if acta.tipo_servicio in config.TIPOS_SERVICIO else None,
        "estado_final": acta.estado_final,
        "nombre_cliente": acta.nombre_cliente,
        "nombre_representante": acta.nombre_representante or (None if cargar_ingenieros() else ""),
    }
    for nombre, valor in valores.items():
        st.session_state[k(nombre)] = valor
    # Las horas de actas anteriores se redondean a 5 minutos (el selector va de 5 en 5).
    precargar_hora(k("hora_inicio_trabajo"), redondear_a_5_minutos(acta.hora_inicio_trabajo))
    precargar_hora(k("hora_fin_trabajo"), redondear_a_5_minutos(acta.hora_fin_trabajo))
    for nombre, puntos in (
        ("antecedentes", acta.antecedentes),
        ("acciones", acta.acciones),
        ("observaciones", acta.observaciones),
    ):
        precargar_lista(k(nombre), puntos)
    precargar_articulos(k("articulos"), acta.articulos)
    # Checklist guardado: se conserva tal cual si no cambian marca ni modelo.
    st.session_state[k("checklist_guardado")] = [c.texto for c in acta.checklist]
    for actividad in acta.checklist:
        st.session_state[_clave_actividad(actividad.texto)] = actividad.hecha


def salir_de_correccion() -> None:
    st.session_state.pop(CORRECCION, None)
    limpiar_formulario()


def acta_en_correccion() -> Acta | None:
    return st.session_state.get(CORRECCION)


# ---------- Autocompletado ----------
CAMPOS_CATALOGO = ["cliente", "ubicacion", "equipo", "marca", "modelo", "serie"]


def _seleccion() -> dict[str, str]:
    return {c: st.session_state.get(k(c)) or "" for c in CAMPOS_CATALOGO}


def _autocompletar() -> None:
    """Al elegir un valor, completa los campos vacíos que quedan determinados
    (p. ej. una serie única define equipo, marca, modelo, cliente y ubicación; un cliente,
    su ubicación). Si hay varias coincidencias no se completa nada: decide el ingeniero."""
    for campo, valor in cargar_catalogo().autocompletar(_seleccion()).items():
        st.session_state[k(campo)] = valor


def _usa_desplegable(campo: str) -> bool:
    """Cliente y Ubicación son desplegables solo si el Excel trae sedes/departamentos;
    si no, se escriben a mano."""
    return campo not in ("cliente", "ubicacion") or cargar_catalogo().tiene(campo)


def _campo_catalogo(contenedor, texto: str, campo: str) -> str:
    """Desplegable con búsqueda: al escribir 'analiz' sugiere 'Analizador Bioquimico', etc.
    Acepta valores nuevos que no estén en el catálogo."""
    if not _usa_desplegable(campo):
        return contenedor.text_input(etiqueta(texto), key=k(campo)).strip()
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


# ---------- Mantenimiento preventivo ----------
def _al_cambiar_tipo() -> None:
    """El preventivo siempre lleva «Mantenimiento Preventivo» en Antecedentes iniciales."""
    if st.session_state.get(k("tipo_servicio")) == config.TIPO_SERVICIO_PREVENTIVO:
        poner_primer_punto(k("antecedentes"), config.ANTECEDENTE_PREVENTIVO)
    else:
        quitar_punto(k("antecedentes"), config.ANTECEDENTE_PREVENTIVO)


def _clave_actividad(texto: str) -> str:
    return k("chk_" + hashlib.sha1(clave(texto).encode()).hexdigest()[:12])


def _marcar_todas(actividades: list[str], valor: bool) -> None:
    for texto in actividades:
        st.session_state[_clave_actividad(texto)] = valor


def _quitar_actividad(texto: str) -> None:
    st.session_state[k("chk_quitadas")].append(clave(texto))
    st.session_state.pop(_clave_actividad(texto), None)


def _checklist_preventivo(acta: Acta, original: Acta | None) -> list[ActividadChecklist]:
    """Checklist de «Parte mantenida» según la marca y el modelo del equipo."""
    guardado = st.session_state.get(k("checklist_guardado")) or []
    mismo_equipo = original is not None and (clave(original.marca), clave(original.modelo)) == (
        clave(acta.marca), clave(acta.modelo)
    )
    protocolo = cargar_protocolos().buscar(acta.equipo, acta.marca, acta.modelo)
    if guardado and mismo_equipo:
        actividades, origen = guardado, "checklist del acta original"
    elif protocolo:
        actividades = protocolo.actividades
        origen = " · ".join(v for v in (protocolo.equipo, protocolo.marca, protocolo.modelo) if v)
    else:
        if acta.modelo:
            st.info(
                f"No hay protocolo para {acta.marca or 'esta marca'} {acta.modelo} en "
                f"«{config.SHAREPOINT_PROTOCOLOS}». Escribe las acciones realizadas abajo.",
                icon="ℹ️",
            )
        else:
            st.caption("Elige la marca y el modelo del equipo para cargar el checklist del mantenimiento.")
        return []

    # Equipo con varios registros en el Excel (p. ej. uno por cliente): sus actividades se
    # unen y el ingeniero puede quitar las que no correspondan a este cliente.
    se_puede_quitar = protocolo is not None and protocolo.repetido
    quitadas: list[str] = st.session_state.setdefault(k("chk_quitadas"), [])
    if se_puede_quitar:
        actividades = [a for a in actividades if clave(a) not in quitadas]

    st.markdown(f"**Checklist del mantenimiento preventivo** · {origen}")
    if se_puede_quitar:
        st.caption(
            f"Este equipo tiene {protocolo.registros} registros en «{config.SHAREPOINT_PROTOCOLOS}» "
            "(sus actividades se juntaron). Quita con × las que no correspondan a este cliente."
        )
    c1, c2, c3 = st.columns([1, 1, 2])
    c1.button("Marcar todas", key=k("chk_todas"), on_click=_marcar_todas, args=(actividades, True))
    c2.button("Desmarcar todas", key=k("chk_ninguna"), on_click=_marcar_todas, args=(actividades, False))
    if se_puede_quitar and quitadas:
        c3.button(
            f"Restaurar {len(quitadas)} actividad(es) quitada(s)", key=k("chk_restaurar"),
            on_click=quitadas.clear,
        )
    checklist = []
    for texto in actividades:
        if se_puede_quitar:
            c_chk, c_quitar = st.columns([12, 1], vertical_alignment="center")
            hecha = c_chk.checkbox(texto, key=_clave_actividad(texto))
            c_quitar.button(
                "×", key=_clave_actividad(texto) + "_quitar", help="Quitar esta actividad del acta",
                on_click=_quitar_actividad, args=(texto,),
            )
        else:
            hecha = st.checkbox(texto, key=_clave_actividad(texto))
        checklist.append(ActividadChecklist(texto, hecha))
    hechas = sum(a.hecha for a in checklist)
    st.caption(
        f"{hechas} de {len(checklist)} actividades realizadas. Las no marcadas saldrán en el PDF "
        "con la casilla vacía."
    )
    return checklist


def formulario_acta() -> Acta:
    """Dibuja el formulario. Si hay un acta cargada para corregir, el N.° no se puede
    cambiar y se pueden conservar sus firmas originales."""
    original = acta_en_correccion()
    acta = Acta()

    # ---------- N.° de acta ----------
    col_label, col_num, _ = st.columns([1, 1.2, 1])
    col_label.markdown('<div class="acta-number-label">N.°</div>', unsafe_allow_html=True)
    acta.numero = col_num.text_input(
        "N.° de Acta",
        key=k("acta_numero"),
        placeholder="2026-00051",
        label_visibility="collapsed",
        disabled=original is not None,
    ).strip()

    # ---------- Datos generales ----------
    with seccion("datos", "Datos generales", obligatorio=False):
        c1, c2 = st.columns(2)
        # La fecha de hoy es el valor inicial, salvo que el acta se haya cargado para corregir.
        st.session_state.setdefault(k("fecha"), hoy())
        acta.fecha = c1.date_input(etiqueta("Fecha"), format="DD/MM/YYYY", key=k("fecha"))
        acta.ubicacion = _campo_catalogo(c2, "Ubicación", "ubicacion")
        c1, c2 = st.columns(2)
        acta.cliente = _campo_catalogo(c1, "Cliente", "cliente")
        acta.equipo = _campo_catalogo(c2, "Equipo", "equipo")
        c1, c2 = st.columns(2)
        acta.marca = _campo_catalogo(c1, "Marca", "marca")
        acta.modelo = _campo_catalogo(c2, "Modelo", "modelo")
        acta.numero_serie = _campo_catalogo(st, "N.° Serie", "serie")

    # ---------- Tipo de servicio ----------
    with seccion("tipo_servicio", "Tipo de servicio"):
        acta.tipo_servicio = st.radio(
            "Tipo de servicio",
            config.TIPOS_SERVICIO,
            index=None,
            horizontal=True,
            key=k("tipo_servicio"),
            on_change=_al_cambiar_tipo,
            label_visibility="collapsed",
        )

    # ---------- Antecedentes ----------
    with seccion("antecedentes", "Antecedentes iniciales"):
        acta.antecedentes = lista_dinamica(
            k("antecedentes"), "Ej: El cliente reportó ruido inusual en el equipo..."
        )
        preventivo = acta.tipo_servicio == config.TIPO_SERVICIO_PREVENTIVO
        if preventivo and config.ANTECEDENTE_PREVENTIVO not in acta.antecedentes:
            acta.antecedentes.insert(0, config.ANTECEDENTE_PREVENTIVO)

    # ---------- Registro de horas ----------
    with seccion("horas", "Registro de horas", obligatorio=False):
        c1, c2 = st.columns(2, gap="large")
        with c1:
            acta.hora_inicio_trabajo = selector_hora("Hora de inicio de trabajo", k("hora_inicio_trabajo"))
        with c2:
            acta.hora_fin_trabajo = selector_hora("Hora de término de trabajo", k("hora_fin_trabajo"))
        inicio, fin = acta.hora_inicio_trabajo, acta.hora_fin_trabajo
        if inicio and fin and fin <= inicio:
            st.warning("La hora de término debe ser posterior a la de inicio.", icon="⚠️")
        else:
            total = duracion(inicio, fin)
            st.caption("🕒 Formato de 24 horas" + (f" · Duración del trabajo: **{total}**" if total else ""))

    # ---------- Acciones realizadas ----------
    with seccion(
        "acciones", "Acciones realizadas", nota="(detalla cada parte verificada, corregida o probada)"
    ):
        if preventivo:
            acta.checklist = _checklist_preventivo(acta, original)
        if acta.checklist:
            st.markdown("**Acciones adicionales** (opcional)")
        acta.acciones = lista_dinamica(k("acciones"), "Ej: Se revisó el sistema de refrigeración...")

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
        acta.articulos = tabla_articulos(k("articulos"), cargar_repuestos())

    # ---------- Observaciones ----------
    with seccion("observaciones", "Observaciones y/o recomendaciones"):
        acta.observaciones = lista_dinamica(
            k("observaciones"), "Ej: Se recomienda cambiar el filtro en la próxima visita..."
        )

    # ---------- Conformidad (firmas) ----------
    with seccion("firmas", "Conformidad"):
        conservar = original is not None and st.checkbox(
            "Conservar las firmas del acta original",
            key=USAR_FIRMAS_ORIGINALES,
            help="Desmarca para que el cliente y el representante vuelvan a firmar la corrección.",
        )
        c1, c2 = st.columns(2, gap="large")
        with c1:
            if conservar:
                acta.firma_cliente_png = _firma_original(original.firma_cliente_png, "Cliente")
            else:
                acta.firma_cliente_png = firma_o_camara(k("firma_cliente"), "Cliente")
            acta.nombre_cliente = st.text_input(etiqueta("Nombre del cliente"), key=k("nombre_cliente")).strip()
        with c2:
            if conservar:
                acta.firma_representante_png = _firma_original(original.firma_representante_png, config.EMPRESA)
            else:
                acta.firma_representante_png = firma_o_camara(k("firma_representante"), config.EMPRESA)
            acta.nombre_representante = _nombre_representante()

    return acta


def _nombre_representante() -> str:
    """Desplegable con los ingenieros de «Firmas Ingenieros/Nombres Ingenieria» (al escribir
    se filtran los nombres). Sin esa lista, se escribe a mano."""
    nombres = cargar_ingenieros()
    if not nombres:
        return st.text_input(etiqueta("Nombre del representante"), key=k("nombre_representante")).strip()
    actual = st.session_state.get(k("nombre_representante"))
    if actual and actual not in nombres:  # acta anterior con un nombre que ya no está en la lista
        nombres = [actual, *nombres]
    return st.selectbox(
        etiqueta("Nombre del representante"),
        nombres,
        index=None,
        key=k("nombre_representante"),
        placeholder="Escribe para buscar tu nombre…",
    ) or ""


def _firma_original(png: bytes | None, rotulo: str) -> bytes | None:
    if png:
        st.image(png, width=380)
    else:
        st.warning("No se encontró la firma original; desmarca la casilla para firmar de nuevo.")
    st.markdown(f'<div class="sign-label">{rotulo}</div>', unsafe_allow_html=True)
    return png
