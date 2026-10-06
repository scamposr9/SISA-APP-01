"""Componentes reutilizables del formulario: encabezado, secciones, listas, tabla y firmas."""

from __future__ import annotations

import base64
import io
from contextlib import contextmanager
from datetime import time

from PIL import Image, ImageEnhance, ImageOps
import streamlit as st
from streamlit_drawable_canvas import st_canvas

from acta_app import config
from acta_app.models import Articulo, hoy
from acta_app.repuestos import Repuestos

REQ = '<span class="req-star">*</span>'


# ---------- Encabezado ----------
@st.cache_data
def _logo_base64() -> str:
    return base64.b64encode(config.LOGO_PATH.read_bytes()).decode()


def encabezado(celdas: list[str] | None = None) -> None:
    """Membrete del formato. `celdas` reemplaza la fila de código / nombre / edición
    (p. ej. en el reporte de preinstalación); la fecha de hoy va siempre al final."""
    hoy_texto = hoy().strftime("%d/%m/%Y")
    # Con celdas propias, una columna igual para cada una (el formato del acta usa el CSS).
    estilo = "" if celdas is None else f' style="grid-template-columns: repeat({len(celdas) + 1}, 1fr)"'
    celdas = celdas if celdas is not None else [config.CODIGO_FORMATO, config.NOMBRE_FORMATO, config.EDICION]
    fila = "".join(f"<div>{c}</div>" for c in [*celdas, hoy_texto])
    st.markdown(
        f"""
        <div class="letterhead">
          <div class="logo-cell">
            <img src="data:image/png;base64,{_logo_base64()}" alt="{config.EMPRESA}">
          </div>
          <div>
            <div class="title-row1">{config.SISTEMA}</div>
            <div class="title-row2"{estilo}>{fila}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------- Tarjeta de sección ----------
@contextmanager
def seccion(clave: str, titulo: str, obligatorio: bool = True, nota: str | None = None):
    """Contenedor con borde y título azul, equivalente a `.card` del prototipo."""
    with st.container(key=f"card_{clave}"):
        estrella = REQ if obligatorio else ""
        extra = f' <span class="opt">{nota}</span>' if nota else ""
        st.markdown(f'<div class="card-title">{titulo}{estrella}{extra}</div>', unsafe_allow_html=True)
        yield


def etiqueta(texto: str, obligatorio: bool = True) -> str:
    """Etiqueta de widget con asterisco rojo (Streamlit admite colores en markdown)."""
    return f"{texto} :red[**\\***]" if obligatorio else texto


# ---------- Selector de hora (24 horas, de 5 en 5 minutos) ----------
HORAS = [f"{h:02d}" for h in range(24)]
MINUTOS = [f"{m:02d}" for m in range(0, 60, 5)]


def precargar_hora(clave: str, valor: time | None) -> None:
    """Deja el selector `clave` con esta hora (para corregir un acta)."""
    st.session_state[f"{clave}_h"] = f"{valor.hour:02d}" if valor else None
    st.session_state[f"{clave}_m"] = f"{valor.minute:02d}" if valor else None


def selector_hora(texto: str, clave: str) -> time | None:
    """Hora [00-23] : Minutos [00, 05 … 55]. Devuelve None hasta elegir ambos."""
    st.markdown(f'<div class="hora-label">{texto} {REQ}</div>', unsafe_allow_html=True)
    c_hora, c_sep, c_min = st.columns([1, 0.15, 1], vertical_alignment="bottom")
    hora = c_hora.selectbox("Hora", HORAS, index=None, placeholder="HH", key=f"{clave}_h")
    c_sep.markdown('<div class="hora-sep">:</div>', unsafe_allow_html=True)
    minuto = c_min.selectbox("Minutos", MINUTOS, index=None, placeholder="MM", key=f"{clave}_m")
    if hora is None or minuto is None:
        return None
    return time(int(hora), int(minuto))


# ---------- Lista dinámica de puntos ----------
def precargar_lista(clave: str, valores: list[str]) -> None:
    """Deja la lista dinámica `clave` con estos puntos (para corregir un acta)."""
    valores = valores or [""]
    st.session_state[f"{clave}_ids"] = list(range(len(valores)))
    st.session_state[f"{clave}_contador"] = len(valores)
    for i, valor in enumerate(valores):
        st.session_state[f"{clave}_txt_{i}"] = valor


def poner_primer_punto(clave: str, texto: str) -> None:
    """Deja `texto` como primer punto de la lista si aún no está (usar desde un callback)."""
    ids = st.session_state.get(f"{clave}_ids")
    if ids is None:
        precargar_lista(clave, [texto])
        return
    if any(st.session_state.get(f"{clave}_txt_{i}", "").strip() == texto for i in ids):
        return
    if ids and not st.session_state.get(f"{clave}_txt_{ids[0]}", "").strip():
        st.session_state[f"{clave}_txt_{ids[0]}"] = texto
        return
    nuevo = st.session_state[f"{clave}_contador"]
    st.session_state[f"{clave}_contador"] = nuevo + 1
    st.session_state[f"{clave}_txt_{nuevo}"] = texto
    ids.insert(0, nuevo)


def quitar_punto(clave: str, texto: str) -> None:
    """Quita de la lista los puntos que sean exactamente `texto` (usar desde un callback)."""
    ids = st.session_state.get(f"{clave}_ids") or []
    for i in [i for i in ids if st.session_state.get(f"{clave}_txt_{i}", "").strip() == texto]:
        st.session_state.pop(f"{clave}_txt_{i}", None)
        ids.remove(i)
    if not ids:
        precargar_lista(clave, [""])


def lista_dinamica(clave: str, placeholder: str) -> list[str]:
    """Lista numerada de textos con botones '+ Agregar punto' y '×' para quitar.

    Cada punto tiene un id estable para que, al quitar uno, los demás conserven su texto.
    Devuelve solo los puntos no vacíos, sin espacios sobrantes.
    """
    ids_key, contador_key = f"{clave}_ids", f"{clave}_contador"
    if ids_key not in st.session_state:
        st.session_state[ids_key] = [0]
        st.session_state[contador_key] = 1

    def agregar() -> None:
        st.session_state[ids_key].append(st.session_state[contador_key])
        st.session_state[contador_key] += 1

    def quitar(item_id: int) -> None:
        st.session_state[ids_key].remove(item_id)
        st.session_state.pop(f"{clave}_txt_{item_id}", None)

    for numero, item_id in enumerate(st.session_state[ids_key], start=1):
        col_num, col_txt, col_quitar = st.columns([0.4, 10, 0.6], vertical_alignment="top")
        col_num.markdown(f'<div class="line-num">{numero}.</div>', unsafe_allow_html=True)
        col_txt.text_area(
            f"Punto {numero}",
            key=f"{clave}_txt_{item_id}",
            placeholder=placeholder.format(n=numero) if "{n}" in placeholder else placeholder,
            height=68,
            label_visibility="collapsed",
        )
        col_quitar.button(
            "×", key=f"quitar_{clave}_{item_id}", help="Quitar punto", on_click=quitar, args=(item_id,)
        )

    st.button("+ Agregar punto", key=f"agregar_{clave}", on_click=agregar)

    valores = (st.session_state.get(f"{clave}_txt_{i}", "") for i in st.session_state[ids_key])
    return [v.strip() for v in valores if v and v.strip()]


# ---------- Artículos empleados ----------
COL_CODIGO, COL_DESCRIPCION, COL_CANTIDAD = "Código", "Descripción", "Cantidad"


def precargar_articulos(clave: str, articulos: list[Articulo]) -> None:
    """Deja las filas de artículos con estos valores (para corregir un acta)."""
    articulos = articulos or [Articulo()]
    st.session_state[f"{clave}_ids"] = list(range(len(articulos)))
    st.session_state[f"{clave}_contador"] = len(articulos)
    for i, articulo in enumerate(articulos):
        st.session_state[f"{clave}_cod_{i}"] = articulo.codigo or None
        st.session_state[f"{clave}_des_{i}"] = articulo.descripcion
        st.session_state[f"{clave}_can_{i}"] = articulo.cantidad


def tabla_articulos(clave: str, repuestos: Repuestos) -> list[Articulo]:
    """Una fila por artículo: Código (con sugerencias de Repuestos.xlsx), Descripción (se completa al elegir un código conocido) y
    Cantidad. Acepta códigos que no estén en el catálogo."""
    ids_key, contador_key = f"{clave}_ids", f"{clave}_contador"
    if ids_key not in st.session_state:
        st.session_state[ids_key] = [0]
        st.session_state[contador_key] = 1

    def agregar() -> None:
        st.session_state[ids_key].append(st.session_state[contador_key])
        st.session_state[contador_key] += 1

    def quitar(item_id: int) -> None:
        st.session_state[ids_key].remove(item_id)
        for campo in ("cod", "des", "can"):
            st.session_state.pop(f"{clave}_{campo}_{item_id}", None)
        if not st.session_state[ids_key]:
            agregar()

    def al_elegir_codigo(item_id: int) -> None:
        """Código del catálogo (elegido o escrito igual, sin importar mayúsculas):
        completa la descripción y deja el código como está en Repuestos.xlsx."""
        escrito = st.session_state.get(f"{clave}_cod_{item_id}") or ""
        descripcion = repuestos.descripcion(escrito)
        if descripcion:
            st.session_state[f"{clave}_cod_{item_id}"] = repuestos.codigo(escrito)
            st.session_state[f"{clave}_des_{item_id}"] = descripcion

    anchos = [2.6, 4, 1.3, 0.5]
    for col, titulo in zip(st.columns(anchos), (COL_CODIGO, COL_DESCRIPCION, COL_CANTIDAD, "")):
        col.markdown(f'<div class="art-head">{titulo}</div>', unsafe_allow_html=True)

    codigos = repuestos.opciones()
    articulos = []
    for item_id in st.session_state[ids_key]:
        c_cod, c_des, c_can, c_quitar = st.columns(anchos, vertical_alignment="center")
        actual = st.session_state.get(f"{clave}_cod_{item_id}")
        opciones = codigos if not actual or repuestos.descripcion(actual) else [actual, *codigos]
        codigo = c_cod.selectbox(
            COL_CODIGO,
            opciones,
            index=None,
            key=f"{clave}_cod_{item_id}",
            placeholder="Escribe el código…",
            accept_new_options=True,
            on_change=al_elegir_codigo,
            args=(item_id,),
            label_visibility="collapsed",
        )
        descripcion = c_des.text_input(
            COL_DESCRIPCION, key=f"{clave}_des_{item_id}", label_visibility="collapsed"
        )
        cantidad = c_can.number_input(
            COL_CANTIDAD, min_value=1, step=1, value=None, key=f"{clave}_can_{item_id}",
            placeholder="Cant.", label_visibility="collapsed",
        )
        c_quitar.button(
            "×", key=f"quitar_{clave}_{item_id}", help="Quitar artículo", on_click=quitar, args=(item_id,)
        )
        articulos.append(Articulo(
            codigo=_texto(codigo), descripcion=_texto(descripcion),
            cantidad=None if cantidad is None else int(cantidad),
        ))

    st.button("+ Agregar artículo", key=f"agregar_{clave}", on_click=agregar)
    if not codigos:
        st.caption("Sin catálogo de repuestos: escribe el código y la descripción a mano.")
    return articulos


def _texto(valor) -> str:
    return "" if valor is None else " ".join(str(valor).split())


# ---------- Firma ----------
def firma(clave: str, rotulo: str) -> bytes | None:
    """Pad de firma a mano alzada con botón 'Borrar firma'.

    Devuelve la firma como PNG, o None si no se ha trazado nada.
    """
    # Cambiar la versión de la key vuelve a montar el canvas vacío.
    version_key = f"{clave}_version"
    st.session_state.setdefault(version_key, 0)

    def borrar() -> None:
        st.session_state[version_key] += 1

    resultado = st_canvas(
        stroke_width=2,
        stroke_color=config.NAVY,
        background_color="#FFFFFF",
        height=130,
        width=380,
        drawing_mode="freedraw",
        return_image_data=True,
        key=f"{clave}_{st.session_state[version_key]}",
    )
    st.markdown(f'<div class="sign-label">{rotulo}</div>', unsafe_allow_html=True)
    st.button("Borrar firma", key=f"borrar_{clave}", on_click=borrar, type="tertiary", width="stretch")

    trazos = (resultado.json_data or {}).get("objects", [])
    return resultado.image_bytes if trazos else None


def _procesar_foto_firma(datos: bytes) -> bytes:
    """Convierte la fotografía en una evidencia tipo escaneo de firma/sello.

    - Corrige orientación EXIF.
    - Detecta automáticamente la zona clara correspondiente al papel.
    - Recorta parte del entorno.
    - Mejora contraste y nitidez.
    - Conserva colores de sellos.
    - La adapta a la proporción del espacio de firma del PDF.
    """
    with Image.open(io.BytesIO(datos)) as original:
        imagen = ImageOps.exif_transpose(original).convert("RGB")

        # Reducir temporalmente para analizar el papel más rápido.
        analisis = imagen.copy()
        analisis.thumbnail((900, 900), Image.Resampling.LANCZOS)

        # Buscar píxeles suficientemente claros: normalmente corresponden al papel.
        gris = analisis.convert("L")
        mascara = gris.point(lambda p: 255 if p >= 145 else 0)

        bbox = mascara.getbbox()

        if bbox:
            escala_x = imagen.width / analisis.width
            escala_y = imagen.height / analisis.height

            izquierda = int(bbox[0] * escala_x)
            arriba = int(bbox[1] * escala_y)
            derecha = int(bbox[2] * escala_x)
            abajo = int(bbox[3] * escala_y)

            # Pequeño margen para no cortar firma/sello en los bordes.
            margen_x = int((derecha - izquierda) * 0.04)
            margen_y = int((abajo - arriba) * 0.06)

            izquierda = max(0, izquierda - margen_x)
            arriba = max(0, arriba - margen_y)
            derecha = min(imagen.width, derecha + margen_x)
            abajo = min(imagen.height, abajo + margen_y)

            # Evitar recortes absurdamente pequeños por reflejos.
            ancho = derecha - izquierda
            alto = abajo - arriba

            if ancho > imagen.width * 0.25 and alto > imagen.height * 0.15:
                imagen = imagen.crop(
                    (izquierda, arriba, derecha, abajo)
                )

        # Mejoras suaves para conservar tinta y sellos de colores.
        imagen = ImageEnhance.Contrast(imagen).enhance(1.15)
        imagen = ImageEnhance.Sharpness(imagen).enhance(1.2)

        # Fondo blanco con la proporción del espacio de firma del PDF.
        ancho_salida = 1400
        alto_salida = 480

        imagen.thumbnail(
            (ancho_salida, alto_salida),
            Image.Resampling.LANCZOS,
        )

        lienzo = Image.new(
            "RGB",
            (ancho_salida, alto_salida),
            "white",
        )

        x = (ancho_salida - imagen.width) // 2
        y = (alto_salida - imagen.height) // 2

        lienzo.paste(imagen, (x, y))

        salida = io.BytesIO()
        lienzo.save(
            salida,
            format="PNG",
            optimize=True,
        )

        return salida.getvalue()


def firma_o_camara(clave: str, rotulo: str) -> bytes | None:
    """Permite firmar en pantalla o fotografiar una firma/sello físico.

    Los dos métodos devuelven una imagen PNG, por lo que el modelo del Acta y
    el generador PDF no necesitan distinguir de dónde provino la firma.
    """
    metodo = st.radio(
        f"Método de conformidad - {rotulo}",
        [
            "Firmar en pantalla",
            "Fotografiar firma / sello",
        ],
        horizontal=True,
        key=f"{clave}_metodo",
        label_visibility="collapsed",
    )

    if metodo == "Firmar en pantalla":
        return firma(clave, rotulo)

    version_key = f"{clave}_camara_version"
    st.session_state.setdefault(version_key, 0)

    def repetir_foto() -> None:
        st.session_state[version_key] += 1

    st.caption(
        "Fotografía únicamente el recuadro de la hoja que contiene la "
        "firma y/o sello. Acerca la cámara y evita incluir rostros u otra "
        "información innecesaria del documento."
    )

    captura = st.camera_input(
        f"Fotografiar firma o sello de {rotulo}",
        key=f"{clave}_camara_{st.session_state[version_key]}",
        label_visibility="collapsed",
    )

    if captura is None:
        st.markdown(
            f'<div class="sign-label">{rotulo}</div>',
            unsafe_allow_html=True,
        )
        return None

    try:
        procesada = _procesar_foto_firma(
            captura.getvalue()
        )
    except Exception:
        st.error(
            "No se pudo procesar la fotografía. Vuelve a tomarla."
        )
        st.button(
            "Volver a tomar foto",
            key=f"repetir_{clave}",
            on_click=repetir_foto,
            type="tertiary",
            width="stretch",
        )
        return None

    st.image(
        procesada,
        width="stretch",
        caption="Vista previa de la firma/sello que aparecerá en el PDF",
    )

    st.markdown(
        f'<div class="sign-label">{rotulo}</div>',
        unsafe_allow_html=True,
    )

    st.button(
        "Volver a tomar foto",
        key=f"repetir_{clave}",
        on_click=repetir_foto,
        type="tertiary",
        width="stretch",
    )

    return procesada
