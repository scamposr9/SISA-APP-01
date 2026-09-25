"""Componentes reutilizables del formulario: encabezado, secciones, listas, tabla y firmas."""

from __future__ import annotations

import base64
from contextlib import contextmanager

import pandas as pd
import streamlit as st
from streamlit_drawable_canvas import st_canvas

from acta_app import config
from acta_app.models import Articulo, hoy

REQ = '<span class="req-star">*</span>'


# ---------- Encabezado ----------
@st.cache_data
def _logo_base64() -> str:
    return base64.b64encode(config.LOGO_PATH.read_bytes()).decode()


def encabezado() -> None:
    hoy_texto = hoy().strftime("%d/%m/%Y")
    st.markdown(
        f"""
        <div class="letterhead">
          <div class="logo-cell">
            <img src="data:image/png;base64,{_logo_base64()}" alt="{config.EMPRESA}">
          </div>
          <div>
            <div class="title-row1">{config.SISTEMA}</div>
            <div class="title-row2">
              <div>{config.CODIGO_FORMATO}</div>
              <div>{config.NOMBRE_FORMATO}</div>
              <div>{config.EDICION}</div>
              <div>{hoy_texto}</div>
            </div>
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


# ---------- Lista dinámica de puntos ----------
def precargar_lista(clave: str, valores: list[str]) -> None:
    """Deja la lista dinámica `clave` con estos puntos (para corregir un acta)."""
    valores = valores or [""]
    st.session_state[f"{clave}_ids"] = list(range(len(valores)))
    st.session_state[f"{clave}_contador"] = len(valores)
    for i, valor in enumerate(valores):
        st.session_state[f"{clave}_txt_{i}"] = valor


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
            placeholder=placeholder,
            height=68,
            label_visibility="collapsed",
        )
        col_quitar.button(
            "×", key=f"quitar_{clave}_{item_id}", help="Quitar punto", on_click=quitar, args=(item_id,)
        )

    st.button("+ Agregar punto", key=f"agregar_{clave}", on_click=agregar)

    valores = (st.session_state.get(f"{clave}_txt_{i}", "") for i in st.session_state[ids_key])
    return [v.strip() for v in valores if v and v.strip()]


# ---------- Tabla de artículos empleados ----------
COL_CODIGO, COL_DESCRIPCION, COL_CANTIDAD = "Código", "Descripción", "Cantidad"


def _tabla_inicial(articulos: list[Articulo]) -> pd.DataFrame:
    """Artículos dados + filas vacías hasta completar las del formato físico."""
    vacias = max(config.FILAS_ARTICULOS_INICIALES - len(articulos), 0)
    filas = [(a.codigo, a.descripcion, a.cantidad) for a in articulos] + [("", "", None)] * vacias
    return pd.DataFrame(
        {
            COL_CODIGO: pd.Series([f[0] for f in filas], dtype="string"),
            COL_DESCRIPCION: pd.Series([f[1] for f in filas], dtype="string"),
            COL_CANTIDAD: pd.Series([f[2] for f in filas], dtype="Int64"),
        }
    )


def precargar_articulos(clave: str, articulos: list[Articulo]) -> None:
    st.session_state[f"{clave}_df_inicial"] = _tabla_inicial(articulos)


def tabla_articulos(clave: str) -> list[Articulo]:
    """Tabla editable con filas agregables; 'Cantidad' solo acepta enteros."""
    inicial_key = f"{clave}_df_inicial"
    if inicial_key not in st.session_state:
        st.session_state[inicial_key] = _tabla_inicial([])

    df = st.data_editor(
        st.session_state[inicial_key],
        key=f"{clave}_editor",
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        column_config={
            COL_CODIGO: st.column_config.TextColumn(COL_CODIGO, width="small"),
            COL_DESCRIPCION: st.column_config.TextColumn(COL_DESCRIPCION, width="large"),
            COL_CANTIDAD: st.column_config.NumberColumn(
                COL_CANTIDAD, min_value=1, step=1, format="%d", width="small"
            ),
        },
    )
    st.caption("Usa la última fila (＋) para agregar ítems. Selecciona una fila y pulsa 🗑 para quitarla.")

    articulos = []
    for _, fila in df.iterrows():
        cantidad = fila[COL_CANTIDAD]
        articulos.append(
            Articulo(
                codigo=_texto(fila[COL_CODIGO]),
                descripcion=_texto(fila[COL_DESCRIPCION]),
                cantidad=None if pd.isna(cantidad) else int(cantidad),
            )
        )
    return articulos


def _texto(valor) -> str:
    return "" if valor is None or pd.isna(valor) else str(valor).strip()


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
