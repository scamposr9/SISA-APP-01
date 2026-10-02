"""Encuesta de satisfacción del cliente, en su propia página (app.py?encuesta=<N.° de acta>)."""

from __future__ import annotations

import streamlit as st

from acta_app import config
from acta_app.models import EncuestaSatisfaccion
from acta_app.storage import (
    ActaNoEncontradaError,
    AlmacenamientoError,
    EncuestaYaRespondidaError,
    obtener_repositorio,
)
from acta_app.ui.components import encabezado, seccion

PARAMETRO = "encuesta"
_COLORES = {0: config.RED, len(config.ESCALA_ENCUESTA) - 1: "#1E8449"}
_CARAS = {0: " 🙁", len(config.ESCALA_ENCUESTA) - 1: " 🙂"}
MENSAJE_COMENTARIOS = (
    "Tu opinión nos ayuda a mejorar. Comparte tus comentarios y sugerencias con nosotros. (Opcional)"
)


def abrir_encuesta(numero: str) -> None:
    """Callback: lleva a la página de la encuesta de esa acta (la dirección queda con
    ?encuesta=<N.°>, que más adelante se podrá compartir como enlace o QR)."""
    st.query_params[PARAMETRO] = numero


def numero_en_la_direccion() -> str | None:
    return st.query_params.get(PARAMETRO) or None


def _clave(numero: str, nombre: str) -> str:
    return f"encuesta_{numero}_{nombre}"


def _encabezado_escala() -> str:
    celdas = "".join(
        f'<div class="esc-head" style="color:{_COLORES.get(i, "inherit")}">{texto}<br>{i + 1}{_CARAS.get(i, "")}</div>'
        for i, texto in enumerate(config.ESCALA_ENCUESTA)
    )
    return f'<div class="esc-escala">{celdas}</div>'


def pagina_encuesta(numero: str) -> None:
    """Muestra la encuesta del acta y, al terminar, solo el agradecimiento."""
    encabezado()
    if st.session_state.get(_clave(numero, "terminada")):
        st.success("¡Gracias por responder la encuesta! Tus respuestas quedaron registradas.", icon="✅")
        return
    try:
        acta = obtener_repositorio().obtener(numero)
    except ActaNoEncontradaError:
        st.error(f"No se encontró el acta N.° {numero}.", icon="❌")
        return
    except AlmacenamientoError as exc:
        st.error(str(exc), icon="❌")
        return
    if acta.encuesta is not None:
        st.info("La encuesta de esta acta ya fue respondida. ¡Gracias!", icon="ℹ️")
        return

    st.markdown("### Encuesta de satisfacción del servicio")
    datos = [f"N.° de acta {acta.numero}", acta.nombre_representante, acta.equipo, acta.tipo_servicio_texto]
    st.caption(" · ".join(d for d in datos if d))

    puntajes: dict[str, int | None] = {}
    with st.container(key="encuesta"):
        with seccion(
            "enc_aspectos",
            "1. ¿Qué tan satisfecho está con los siguientes aspectos del servicio? "
            "(1 = muy insatisfecho, 5 = muy satisfecho)",
        ):
            _, c_escala = st.columns([2.2, 3.3])
            c_escala.markdown(_encabezado_escala(), unsafe_allow_html=True)
            for i, aspecto in enumerate(config.ASPECTOS_ENCUESTA):
                c_txt, c_opciones = st.columns([2.2, 3.3], vertical_alignment="center")
                c_txt.markdown(f'<div class="esc-aspecto">{aspecto}</div>', unsafe_allow_html=True)
                puntajes[aspecto] = c_opciones.radio(
                    aspecto,
                    [1, 2, 3, 4, 5],
                    index=None,
                    horizontal=True,
                    # Sin número en la casilla (va arriba, en la escala). Cada opción necesita un
                    # texto distinto para que Streamlit las diferencie: espacios invisibles.
                    format_func=lambda v: "\u200b" * v,
                    key=_clave(numero, f"p{i}"),
                    label_visibility="collapsed",
                )
        with seccion("enc_comentarios", "2. " + MENSAJE_COMENTARIOS, obligatorio=False):
            comentario = st.text_area(
                MENSAJE_COMENTARIOS, key=_clave(numero, "comentario"), height=100,
                label_visibility="collapsed",
            )

    if st.button("Terminar encuesta", type="primary", width="stretch"):
        faltan = [a for a, p in puntajes.items() if p is None]
        if faltan:
            st.warning("Falta calificar: " + ", ".join(faltan), icon="⚠️")
            return
        encuesta = EncuestaSatisfaccion(puntajes={a: int(p) for a, p in puntajes.items()},
                                        comentario=comentario.strip())
        try:
            obtener_repositorio().guardar_encuesta(numero, encuesta)
        except EncuestaYaRespondidaError:
            st.info("La encuesta de esta acta ya fue respondida. ¡Gracias!", icon="ℹ️")
            return
        except (AlmacenamientoError, ActaNoEncontradaError) as exc:
            st.error(f"No se pudo guardar la encuesta: {exc}", icon="❌")
            return
        st.session_state[_clave(numero, "terminada")] = True
        st.rerun()
