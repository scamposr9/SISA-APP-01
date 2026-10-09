"""Apartados del reporte de preinstalación dentro del formulario del acta.

Al elegir «Presite» como tipo de servicio, en lugar de los apartados del acta (antecedentes,
horas, acciones, …) aparecen los de la preinstalación. Los datos generales (N.°, fecha,
cliente, equipo, …) son los del acta. Se guarda en Preinstalaciones.xlsx.
"""

from __future__ import annotations

import streamlit as st

from acta_app import preinstalacion as pre
from acta_app.catalogo import limpiar
from acta_app.preinstalacion import Contacto, FotoAnexo, Preinstalacion
from acta_app.ui.camara import camara_trasera
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
        servicio = st.radio(etiqueta("Servicio"), pre.SERVICIOS_AREA, index=None, horizontal=True,
                            key=k("servicio"))
        p.servicios = [servicio] if servicio else []
        if servicio == pre.SERVICIO_LABORATORIO:
            p.tipo_laboratorio = st.selectbox(etiqueta("Tipo de laboratorio"), pre.TIPOS_LABORATORIO, index=None,
                                              key=k("tipo_laboratorio"), placeholder="Elige el tipo…") or ""

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

    with seccion("pre_observaciones", "Observaciones"):
        p.observaciones = lista_dinamica(k("observaciones"), "Opción {n}")

    p.fotos, p.foto_sin_agregar = _fotos()
    return p


ORIGEN_CAMARA, ORIGEN_ARCHIVO = "Cámara trasera", "Subir desde la galería"


def _fotos() -> tuple[list[FotoAnexo], bool]:
    """«Fotos o anexos» (opcional): se agregan de una en una, cada una con lo que muestra.
    Se guardan en Preinstalaciones/Fotos Preinstalaciones/<N.°>/ y van al final del PDF.

    Devuelve (fotos, hay una foto tomada sin describir). Una foto ya tomada y descrita pero
    sin «Agregar foto» también se incluye: así no se pierde si se guarda directamente."""
    fotos: list[FotoAnexo] = st.session_state.setdefault(k("fotos"), [])
    version = st.session_state.setdefault(k("foto_version"), 0)
    clave_foto, clave_texto = k(f"foto_{version}"), k(f"foto_texto_{version}")
    clave_datos = k(f"foto_datos_{version}")  # bytes de la foto elegida (cámara o galería)

    def agregar() -> None:
        datos_foto = st.session_state.get(clave_datos)
        texto = (st.session_state.get(clave_texto) or "").strip()
        if datos_foto is None:
            return
        if not texto:
            st.session_state[k("foto_aviso")] = "Escribe qué muestra la foto antes de agregarla."
            return
        try:
            datos = pre.comprimir_foto(datos_foto)
        except Exception:
            st.session_state[k("foto_aviso")] = "No se pudo leer la imagen. Prueba con otra foto (JPG o PNG)."
            return
        fotos.append(FotoAnexo(datos, texto))
        st.session_state[k("foto_version")] = version + 1  # deja la foto y el texto en blanco
        st.session_state[k("foto_origen")] = None  # y no vuelve a abrir la cámara por su cuenta

    def descartar() -> None:
        st.session_state[k("foto_version")] = version + 1
        st.session_state[k("foto_origen")] = None

    def quitar(i: int) -> None:
        fotos.pop(i)

    with seccion("pre_fotos", "Fotos o anexos", obligatorio=False, nota="(opcional)"):
        for i, foto in enumerate(fotos):
            c_img, c_txt, c_quitar = st.columns([2, 5, 0.6], vertical_alignment="center")
            c_img.image(foto.datos, width="stretch")
            c_txt.markdown(f"**Foto {i + 1}:** {foto.descripcion}")
            c_quitar.button("×", key=k(f"quitar_foto_{i}_{len(fotos)}"), help="Quitar foto",
                            on_click=quitar, args=(i,))
        st.markdown(f"**Agregar foto {len(fotos) + 1}**")
        # Nada se activa hasta que el ingeniero elige cómo agregar la foto.
        origen = st.radio("Origen de la foto", [ORIGEN_CAMARA, ORIGEN_ARCHIVO], index=None, horizontal=True,
                          key=k("foto_origen"), label_visibility="collapsed")
        datos_foto = None
        if origen == ORIGEN_CAMARA:
            datos_foto = camara_trasera(key=clave_foto + "_camara")
        elif origen == ORIGEN_ARCHIVO:
            subida = st.file_uploader("Foto", type=["jpg", "jpeg", "png", "webp"], key=clave_foto + "_galeria",
                                      label_visibility="collapsed")
            datos_foto = subida.getvalue() if subida is not None else None
        else:
            st.caption("Elige «Cámara trasera» para tomar la foto o «Subir desde la galería».")
        st.session_state[clave_datos] = datos_foto
        # La descripción y el botón aparecen recién cuando ya hay una foto.
        pendiente: FotoAnexo | None = None
        sin_describir = False
        if datos_foto is not None:
            st.image(datos_foto, width=260, caption="Vista previa")
            st.caption(f":orange[Esta foto aún no está en el anexo: escribe qué muestra y presiona "
                       f"«Agregar foto {len(fotos) + 1}».]")
            st.text_area("¿Qué muestra esta foto?", key=clave_texto, height=68,
                         placeholder="Ej: Tablero eléctrico del área donde irá el equipo")
            if aviso := st.session_state.pop(k("foto_aviso"), None):
                st.warning(aviso, icon="⚠️")
            c_agregar, c_descartar = st.columns(2)
            c_agregar.button(f"Agregar foto {len(fotos) + 1}", key=k(f"agregar_foto_{version}"), on_click=agregar,
                             icon=":material/add_a_photo:", type="primary", width="stretch")
            c_descartar.button("Descartar esta foto", key=k(f"descartar_foto_{version}"), on_click=descartar,
                               width="stretch")
            texto = (st.session_state.get(clave_texto) or "").strip()
            if texto:
                try:
                    pendiente = FotoAnexo(pre.comprimir_foto(datos_foto), texto)
                except Exception:
                    sin_describir = True
            else:
                sin_describir = True
    return list(fotos) + ([pendiente] if pendiente else []), sin_describir


