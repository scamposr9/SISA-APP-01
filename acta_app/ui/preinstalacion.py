"""Formulario del reporte de preinstalación (Presite) y su guardado."""

from __future__ import annotations

import streamlit as st

from acta_app import config
from acta_app import preinstalacion as pre
from acta_app.catalogo import limpiar
from acta_app.models import ahora, hoy
from acta_app.pdf.preinstalacion import generar_pdf
from acta_app.preinstalacion import Contacto, Preinstalacion
from acta_app.storage import ActaDuplicadaError, AlmacenamientoError, obtener_repositorio
from acta_app.ui.catalogo_ui import cargar_catalogo, cargar_ingenieros
from acta_app.ui.components import etiqueta, lista_dinamica, precargar_lista, seccion

FORM_ID = "pre_form_id"


def k(nombre: str) -> str:
    """Clave de widget del formulario actual (cambia al empezar otro reporte)."""
    return f"pre{st.session_state.get(FORM_ID, 0)}_{nombre}"


def limpiar_formulario() -> None:
    prefijo = k("")
    for clave in [c for c in st.session_state if str(c).startswith(prefijo)]:
        del st.session_state[clave]
    st.session_state[FORM_ID] = st.session_state.get(FORM_ID, 0) + 1


def _desplegable(contenedor, texto: str, campo: str) -> str:
    """Desplegable con las opciones de Equipos.xlsx (acepta valores nuevos). Cliente y
    Ubicación se escriben a mano si el Excel no trae sedes/departamentos."""
    catalogo = cargar_catalogo()
    if campo in ("cliente", "ubicacion") and not catalogo.tiene(campo):
        return contenedor.text_input(etiqueta(texto), key=k(campo)).strip()
    return limpiar(contenedor.selectbox(
        etiqueta(texto), catalogo.opciones(campo, {}), index=None, key=k(campo),
        placeholder="Escribe para buscar o agregar…", accept_new_options=True,
    ))


def _marcar(opciones: list[str], nombre: str, columnas: int | None = None) -> list[str]:
    """Casillas en fila; devuelve las marcadas."""
    cols = st.columns(columnas or len(opciones))
    return [o for i, o in enumerate(opciones) if cols[i % len(cols)].checkbox(o, key=k(f"{nombre}_{i}"))]


def _tipos_toma() -> list[str]:
    """Los dibujos de tomas del formato, cada uno con su casilla (se pueden marcar varios)."""
    marcadas = []
    por_fila = 6
    for inicio in range(0, len(pre.TIPOS_TOMA), por_fila):
        cols = st.columns(por_fila)
        for col, tipo in zip(cols, pre.TIPOS_TOMA[inicio:inicio + por_fila]):
            with col.container(key=k(f"toma_{tipo}").replace(" ", "_"), horizontal_alignment="center"):
                st.image(pre.imagen_toma(tipo), width=64)
                if st.checkbox(tipo, key=k(f"toma_chk_{tipo}")):
                    marcadas.append(tipo)
    return marcadas


def _contactos() -> list[Contacto]:
    """Filas Nombre / Cargo / Teléfono con «+ Agregar contacto» y × para quitar."""
    ids_key, contador_key = k("contactos_ids"), k("contactos_contador")
    if ids_key not in st.session_state:
        st.session_state[ids_key], st.session_state[contador_key] = [0], 1

    def agregar() -> None:
        st.session_state[ids_key].append(st.session_state[contador_key])
        st.session_state[contador_key] += 1

    def quitar(item_id: int) -> None:
        st.session_state[ids_key].remove(item_id)
        for campo in ("nom", "car", "tel"):
            st.session_state.pop(k(f"contacto_{campo}_{item_id}"), None)
        if not st.session_state[ids_key]:
            agregar()

    anchos = [3, 4, 2.4, 0.5]
    for col, titulo in zip(st.columns(anchos), ("Nombre", "Cargo", "Teléfono", "")):
        col.markdown(f'<div class="art-head">{titulo}</div>', unsafe_allow_html=True)
    contactos = []
    for item_id in st.session_state[ids_key]:
        c_nom, c_car, c_tel, c_quitar = st.columns(anchos, vertical_alignment="center")
        valores = [
            col.text_input(titulo, key=k(f"contacto_{campo}_{item_id}"), label_visibility="collapsed",
                           placeholder=ejemplo)
            for col, titulo, campo, ejemplo in (
                (c_nom, "Nombre", "nom", "Nombre"), (c_car, "Cargo", "car", "Ej: Jefa de laboratorio"),
                (c_tel, "Teléfono", "tel", "999 999 999"),
            )
        ]
        c_quitar.button("×", key=k(f"quitar_contacto_{item_id}"), help="Quitar contacto",
                        on_click=quitar, args=(item_id,))
        contactos.append(Contacto(*(limpiar(v) for v in valores)))
    st.button("+ Agregar contacto", key=k("agregar_contacto"), on_click=agregar)
    return contactos


def formulario() -> Preinstalacion:
    p = Preinstalacion()

    col_label, col_num, _ = st.columns([1, 1.2, 1])
    col_label.markdown('<div class="acta-number-label">N.°</div>', unsafe_allow_html=True)
    p.numero = col_num.text_input("N.° de reporte", key=k("numero"), placeholder="2026-P001",
                                  label_visibility="collapsed").strip()

    with seccion("pre_datos", "Datos generales", obligatorio=False):
        c1, c2 = st.columns(2)
        st.session_state.setdefault(k("fecha"), hoy())
        p.fecha = c1.date_input(etiqueta("Fecha"), format="DD/MM/YYYY", key=k("fecha"))
        p.ubicacion = _desplegable(c2, "Ubicación", "ubicacion")
        c1, c2 = st.columns(2)
        p.cliente = _desplegable(c1, "Cliente", "cliente")
        p.equipo = _desplegable(c2, "Equipo a instalar", "equipo")
        c1, c2 = st.columns(2)
        p.marca = _desplegable(c1, "Marca", "marca")
        p.modelo = _desplegable(c2, "Modelo", "modelo")

    with seccion("pre_electricas", "Condiciones eléctricas"):
        respuesta = st.radio(etiqueta("Suministro eléctrico: ¿es punto dedicado?"), ["Sí", "No"], index=None,
                             horizontal=True, key=k("punto_dedicado"))
        p.punto_dedicado = None if respuesta is None else respuesta == "Sí"
        st.markdown("**Tipo de toma eléctrica** (marca una o varias)")
        p.tipos_toma = _tipos_toma()

    with seccion("pre_detalles", "Detalles"):
        st.markdown("**Traslado del equipo**")
        p.traslado = _marcar(pre.TRASLADOS, "traslado")
        if pre.TRASLADO_ESTIBADORES in p.traslado:
            cantidad = st.number_input(etiqueta("¿Cuántos estibadores?"), min_value=1, step=1, value=None,
                                       key=k("estibadores"), placeholder="Ej: 3")
            p.estibadores = None if cantidad is None else int(cantidad)
        st.markdown("**Accesos** (describe el camino del equipo hasta su ubicación final)")
        if k("accesos_ids") not in st.session_state:
            precargar_lista(k("accesos"), [""] * pre.ACCESOS_INICIALES)
        p.accesos = lista_dinamica(k("accesos"), "Ej: El acceso más cercano es la puerta #2…")

    with seccion("pre_area", "Tipo de área"):
        p.servicios = _marcar(pre.SERVICIOS_AREA, "servicio", columnas=2)
        if pre.SERVICIO_LABORATORIO in p.servicios:
            p.tipo_laboratorio = st.text_input("Tipo de laboratorio", key=k("tipo_laboratorio"),
                                               placeholder="Ej: Clínico, Microbiología…").strip()

    with seccion("pre_condiciones", "Condiciones del área", obligatorio=False, nota="(en centímetros)"):
        for col, superficie in zip(st.columns(2, gap="large"), pre.SUPERFICIES):
            col.markdown(f"**{superficie}**")
            p.medidas[superficie] = {
                medida: col.number_input(f"{medida} (cm)", min_value=0.0, step=1.0, value=None, format="%g",
                                         key=k(f"medida_{superficie}_{medida}"), placeholder="cm")
                for medida in pre.MEDIDAS
            }

    with seccion("pre_complementos", "Complementos faltantes", obligatorio=False,
                 nota="(marca los que faltan; en el PDF salen todos)"):
        p.complementos_faltantes = _marcar(pre.COMPLEMENTOS, "complemento", columnas=3)
        p.temperatura = st.text_input("Temperatura del área (°C)", key=k("temperatura"),
                                      placeholder="Ej: 22 °C, o «No cuenta con termohigrómetro»").strip()

    with seccion("pre_contactos", "Personal de contacto", nota="(puedes agregar varios)"):
        p.contactos = _contactos()

    with seccion("pre_observaciones", "Observaciones", obligatorio=False):
        p.observaciones = lista_dinamica(k("observaciones"), "Ej: Se requiere colocar un nuevo tablero…")

    with seccion("pre_realizado", "Realizado por"):
        nombres = cargar_ingenieros()
        if nombres:
            p.realizado_por = st.selectbox("Realizado por", nombres, index=None, key=k("realizado_por"),
                                           placeholder="Escribe para buscar tu nombre…",
                                           label_visibility="collapsed") or ""
        else:
            p.realizado_por = st.text_input("Realizado por", key=k("realizado_por"),
                                            label_visibility="collapsed").strip()
    return p


@st.dialog("Reporte de preinstalación guardado")
def _dialogo_guardado(p: Preinstalacion, pdf: bytes, nombre_pdf: str, total: int, enlace_pdf: str) -> None:
    st.write(
        f"El reporte N.° {p.numero} se agregó a {config.SHAREPOINT_PREINSTALACIONES} "
        f"({total} {'reporte registrado' if total == 1 else 'reportes registrados'} en total) y se generó su PDF."
    )
    st.download_button("Descargar PDF", data=pdf, file_name=nombre_pdf, mime="application/pdf",
                       on_click="ignore", type="primary", width="stretch")
    if enlace_pdf.startswith("http"):
        st.link_button("Abrir el PDF en SharePoint", enlace_pdf, width="stretch")
    if st.button("Registrar otra preinstalación", on_click=limpiar_formulario, width="stretch"):
        st.rerun()


def pagina(registrado_por: str) -> None:
    """Formulario + botón Guardar."""
    p = formulario()
    if not st.button("Guardar preinstalación", key=k("guardar"), type="primary", width="stretch"):
        return
    errores = pre.validar(p)
    if errores:
        st.warning("Falta completar: " + ", ".join(errores), icon="⚠️")
        return
    repo = obtener_repositorio()
    p.fecha_registro, p.registrado_por = ahora(), registrado_por
    pdf, nombre_pdf = generar_pdf(p), pre.nombre_archivo_pdf(p)
    try:
        resultado = repo.guardar_preinstalacion(p, pdf, nombre_pdf)
    except ActaDuplicadaError:
        st.warning(f"Ya existe un reporte de preinstalación con el N.° {p.numero}. Usa otro número.", icon="⚠️")
        return
    except AlmacenamientoError as exc:
        st.error(str(exc), icon="❌")
        return
    st.success(f"Reporte de preinstalación N.° {p.numero} guardado.", icon="✅")
    _dialogo_guardado(p, pdf, nombre_pdf, resultado.total_actas, resultado.ubicacion_pdf)
