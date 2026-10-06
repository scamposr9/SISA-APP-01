"""Apartados del reporte de preinstalación dentro del formulario del acta.

Al elegir «Presite» como tipo de servicio, en lugar de los apartados del acta (antecedentes,
horas, acciones, …) aparecen los de la preinstalación. Los datos generales (N.°, fecha,
cliente, equipo, …) son los del acta. Se guarda en Preinstalaciones.xlsx.
"""

from __future__ import annotations

import streamlit as st

from acta_app import preinstalacion as pre
from acta_app.catalogo import limpiar
from acta_app.preinstalacion import Contacto, Preinstalacion
from acta_app.ui.catalogo_ui import cargar_ingenieros
from acta_app.ui.components import etiqueta, lista_dinamica, precargar_lista, seccion


def k(nombre: str) -> str:
    """Clave ligada al formulario del acta: al limpiarlo, también se limpia esto."""
    from acta_app.ui.form import k as k_acta

    return k_acta("pre_" + nombre)


def _marcar(opciones: list[str], nombre: str, columnas: int | None = None) -> list[str]:
    """Casillas en fila; devuelve las marcadas."""
    cols = st.columns(columnas or len(opciones))
    return [o for i, o in enumerate(opciones) if cols[i % len(cols)].checkbox(o, key=k(f"{nombre}_{i}"))]


def _tipos_toma() -> list[str]:
    """Los dibujos de tomas del formato, cada uno con su casilla (se pueden marcar varios)."""
    marcadas = []
    por_fila = 7
    for inicio in range(0, len(pre.TIPOS_TOMA), por_fila):
        cols = st.columns(por_fila)
        for col, tipo in zip(cols, pre.TIPOS_TOMA[inicio:inicio + por_fila]):
            with col.container(key=k(f"toma_{tipo}").replace(" ", "_"), horizontal_alignment="center"):
                st.image(pre.imagen_toma(tipo), width=60)
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
                           placeholder=titulo)
            for col, titulo, campo in ((c_nom, "Nombre", "nom"), (c_car, "Cargo", "car"), (c_tel, "Teléfono", "tel"))
        ]
        c_quitar.button("×", key=k(f"quitar_contacto_{item_id}"), help="Quitar contacto",
                        on_click=quitar, args=(item_id,))
        contacto = Contacto(*(limpiar(v) for v in valores))
        if contacto.faltantes:  # empezado pero incompleto: no se podrá guardar
            st.caption(f":red[Completa {', '.join(contacto.faltantes)} de este contacto (o quítalo con ×).]")
        contactos.append(contacto)
    st.button("+ Agregar contacto", key=k("agregar_contacto"), on_click=agregar)
    return contactos


def secciones() -> Preinstalacion:
    """Dibuja los apartados propios de la preinstalación (sin los datos generales)."""
    p = Preinstalacion()

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
            if st.session_state.get(k("estibadores")) is None:
                st.session_state[k("estibadores")] = 1  # empieza en 1; se sube con + o se escribe
            cantidad = st.number_input(etiqueta("¿Cuántos estibadores?"), min_value=1, step=1,
                                       format="%d", key=k("estibadores"))
            p.estibadores = None if cantidad is None else int(cantidad)
            if p.estibadores is None:
                st.caption(":red[Indica cuántos estibadores se necesitan para poder guardar.]")
        st.markdown("**Accesos**")
        if k("accesos_ids") not in st.session_state:
            precargar_lista(k("accesos"), [""] * pre.ACCESOS_INICIALES)
        p.accesos = lista_dinamica(k("accesos"), "Opción {n}")

    with seccion("pre_area", "Tipo de área"):
        p.servicios = _marcar(pre.SERVICIOS_AREA, "servicio", columnas=2)
        if pre.SERVICIO_LABORATORIO in p.servicios:
            p.tipo_laboratorio = st.text_input("Tipo de laboratorio", key=k("tipo_laboratorio")).strip()

    with seccion("pre_condiciones", "Condiciones del área", obligatorio=False, nota="(en centímetros)"):
        for col, superficie in zip(st.columns(2, gap="large"), pre.SUPERFICIES):
            col.markdown(f"**{superficie}**")
            p.medidas[superficie] = {
                medida: col.number_input(f"{medida} (cm)", min_value=0.0, step=1.0, value=None, format="%g",
                                         key=k(f"medida_{superficie}_{medida}"), placeholder="cm")
                for medida in pre.MEDIDAS
            }

    with seccion("pre_complementos", "Complementos faltantes", obligatorio=False):
        p.complementos_faltantes = _marcar(pre.COMPLEMENTOS, "complemento", columnas=3)
        p.temperatura = st.text_input("Temperatura del área (°C)", key=k("temperatura"),
                                      placeholder="Ej: 22 °C, o «No cuenta con termostato»").strip()

    with seccion("pre_contactos", "Personal de contacto",
                 nota="(puedes agregar varios; cada uno con nombre, cargo y teléfono)"):
        p.contactos = _contactos()

    with seccion("pre_observaciones", "Observaciones", obligatorio=False):
        p.observaciones = lista_dinamica(k("observaciones"), "Opción {n}")

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


def precargar(p: Preinstalacion) -> None:
    """Deja los apartados con estos datos (al recuperar un borrador; usar desde un callback)."""
    s = st.session_state
    s[k("punto_dedicado")] = None if p.punto_dedicado is None else ("Sí" if p.punto_dedicado else "No")
    for tipo in p.tipos_toma:
        s[k(f"toma_chk_{tipo}")] = True
    for nombre, opciones, marcadas in (("traslado", pre.TRASLADOS, p.traslado),
                                       ("servicio", pre.SERVICIOS_AREA, p.servicios),
                                       ("complemento", pre.COMPLEMENTOS, p.complementos_faltantes)):
        for i, opcion in enumerate(opciones):
            s[k(f"{nombre}_{i}")] = opcion in marcadas
    s[k("estibadores")] = p.estibadores
    s[k("tipo_laboratorio")] = p.tipo_laboratorio
    s[k("temperatura")] = p.temperatura
    for superficie in pre.SUPERFICIES:
        for medida in pre.MEDIDAS:
            s[k(f"medida_{superficie}_{medida}")] = p.medida(superficie, medida)
    accesos = p.accesos + [""] * max(0, pre.ACCESOS_INICIALES - len(p.accesos))
    precargar_lista(k("accesos"), accesos)
    precargar_lista(k("observaciones"), p.observaciones)
    contactos = p.contactos_usados or [Contacto()]
    s[k("contactos_ids")], s[k("contactos_contador")] = list(range(len(contactos))), len(contactos)
    for i, c in enumerate(contactos):
        s[k(f"contacto_nom_{i}")], s[k(f"contacto_car_{i}")], s[k(f"contacto_tel_{i}")] = c.nombre, c.cargo, c.telefono
    s[k("realizado_por")] = p.realizado_por or (None if cargar_ingenieros() else "")
