"""Botón «Tomar foto» que abre la cámara TRASERA del celular o la cámara de la computadora.

`st.camera_input` usa la cámara del navegador y en muchos celulares abre la frontal con baja
resolución. Este componente usa en cambio `<input type="file" capture="environment">`, que
abre la app de cámara del teléfono con la cámara trasera y toda su calidad. La foto se
endereza y se reduce (1600 px como máximo, JPG) en el mismo celular antes de enviarla,
para que suba rápido con datos móviles. En una computadora (sin pantalla táctil) muestra la
cámara web en vivo con «Capturar» y «Cancelar»; si no hay cámara o no se da permiso, abre el
selector de archivos.
"""

from __future__ import annotations

import base64

import streamlit as st

_HTML = """
<button id="tomar" type="button" class="boton">📷 Tomar foto con la cámara trasera</button>
<input id="archivo" type="file" accept="image/*" capture="environment" hidden>
<div id="vivo" class="vivo" hidden>
  <video id="video" autoplay playsinline muted></video>
  <div class="acciones">
    <button id="capturar" type="button" class="boton">Capturar</button>
    <button id="cancelar" type="button" class="boton secundario">Cancelar</button>
  </div>
</div>
<div id="estado" class="estado"></div>
"""

_CSS = """
.boton {
  width: 100%; padding: 0.55rem 0.75rem; border-radius: 0.5rem; cursor: pointer;
  border: 1px solid #1B3A6B; background: #1B3A6B; color: #fff; font-size: 0.95rem; font-weight: 600;
}
.boton:disabled { opacity: 0.6; cursor: progress; }
.secundario { background: #fff; color: #1B3A6B; }
.vivo { margin-top: 0.5rem; }
.vivo video { width: 100%; max-height: 360px; border-radius: 0.5rem; background: #000; }
.acciones { display: flex; gap: 0.5rem; margin-top: 0.4rem; }
.estado { font-size: 0.8rem; color: #6B7280; margin-top: 0.3rem; min-height: 1rem; }
"""

# En celulares y tablets (pantalla táctil) se abre la app de cámara del teléfono con la cámara
# trasera; en una computadora, la cámara web en vivo dentro de la app (getUserMedia).
_JS = """
export default function (component) {
  const { parentElement, setStateValue } = component;
  const $ = (id) => parentElement.querySelector("#" + id);
  const boton = $("tomar"), archivo = $("archivo"), vivo = $("vivo"), video = $("video"), estado = $("estado");
  const texto = boton.textContent;
  const esCelular = window.matchMedia("(pointer: coarse)").matches;
  let flujo = null;

  const enviar = (fuente, ancho, alto) => {
    const escala = Math.min(1, 1600 / Math.max(ancho, alto));
    const lienzo = document.createElement("canvas");
    lienzo.width = Math.round(ancho * escala);
    lienzo.height = Math.round(alto * escala);
    lienzo.getContext("2d").drawImage(fuente, 0, 0, lienzo.width, lienzo.height);
    setStateValue("foto", lienzo.toDataURL("image/jpeg", 0.85));
  };
  const apagar = () => {
    if (flujo) flujo.getTracks().forEach((t) => t.stop());
    flujo = null;
    vivo.hidden = true;
    boton.hidden = false;
  };

  boton.onclick = async () => {
    estado.textContent = "";
    if (esCelular || !(navigator.mediaDevices && navigator.mediaDevices.getUserMedia)) {
      archivo.click();
      return;
    }
    try {
      flujo = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } },
        audio: false,
      });
      video.srcObject = flujo;
      vivo.hidden = false;
      boton.hidden = true;
    } catch (e) {
      estado.textContent = "No se pudo abrir la cámara (revisa el permiso del navegador). Se abrirá el selector de archivos.";
      archivo.click();
    }
  };
  $("capturar").onclick = () => {
    if (!video.videoWidth) return;
    enviar(video, video.videoWidth, video.videoHeight);
    apagar();
  };
  $("cancelar").onclick = apagar;

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
      enviar(imagen, imagen.width, imagen.height);
    } catch (e) {
      estado.textContent = "No se pudo leer la foto. Vuelve a intentarlo.";
    } finally {
      boton.disabled = false;
      boton.textContent = texto;
      archivo.value = "";
    }
  };
  return () => apagar();  // al desmontar el componente, se apaga la cámara
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
