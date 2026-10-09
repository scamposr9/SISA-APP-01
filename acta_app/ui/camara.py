"""Botón «Tomar foto» que abre directamente la cámara TRASERA del celular.

`st.camera_input` usa la cámara del navegador y en muchos celulares abre la frontal con baja
resolución. Este componente usa en cambio `<input type="file" capture="environment">`, que
abre la app de cámara del teléfono con la cámara trasera y toda su calidad. La foto se
endereza y se reduce (1600 px como máximo, JPG) en el mismo celular antes de enviarla,
para que suba rápido con datos móviles. En una computadora abre el selector de archivos.
"""

from __future__ import annotations

import base64

import streamlit as st

_HTML = """
<button id="tomar" type="button" class="boton">📷 Tomar foto con la cámara trasera</button>
<input id="archivo" type="file" accept="image/*" capture="environment" hidden>
<div id="estado" class="estado"></div>
"""

_CSS = """
.boton {
  width: 100%; padding: 0.55rem 0.75rem; border-radius: 0.5rem; cursor: pointer;
  border: 1px solid #1B3A6B; background: #1B3A6B; color: #fff; font-size: 0.95rem; font-weight: 600;
}
.boton:disabled { opacity: 0.6; cursor: progress; }
.estado { font-size: 0.8rem; color: #6B7280; margin-top: 0.3rem; min-height: 1rem; }
"""

_JS = """
export default function (component) {
  const { parentElement, setStateValue } = component;
  const boton = parentElement.querySelector("#tomar");
  const archivo = parentElement.querySelector("#archivo");
  const estado = parentElement.querySelector("#estado");
  const texto = boton.textContent;
  boton.onclick = () => archivo.click();
  archivo.onchange = async () => {
    const foto = archivo.files && archivo.files[0];
    if (!foto) return;
    boton.disabled = true;
    boton.textContent = "Procesando foto…";
    try {
      let imagen;
      try {
        imagen = await createImageBitmap(foto, { imageOrientation: "from-image" });
      } catch (e) {
        imagen = await createImageBitmap(foto);
      }
      const escala = Math.min(1, 1600 / Math.max(imagen.width, imagen.height));
      const lienzo = document.createElement("canvas");
      lienzo.width = Math.round(imagen.width * escala);
      lienzo.height = Math.round(imagen.height * escala);
      lienzo.getContext("2d").drawImage(imagen, 0, 0, lienzo.width, lienzo.height);
      setStateValue("foto", lienzo.toDataURL("image/jpeg", 0.85));
      estado.textContent = "";
    } catch (e) {
      estado.textContent = "No se pudo leer la foto. Vuelve a intentarlo.";
    } finally {
      boton.disabled = false;
      boton.textContent = texto;
      archivo.value = "";
    }
  };
}
"""

_componente = st.components.v2.component("camara_trasera", html=_HTML, css=_CSS, js=_JS)


def camara_trasera(key: str) -> bytes | None:
    """Foto tomada (JPG) o None si todavía no se tomó ninguna con este `key`."""
    resultado = _componente(key=key, on_foto_change=lambda: None)
    valor = getattr(resultado, "foto", None) if resultado is not None else None
    if not valor or "," not in str(valor):
        return None
    try:
        return base64.b64decode(str(valor).split(",", 1)[1])
    except ValueError:
        return None
