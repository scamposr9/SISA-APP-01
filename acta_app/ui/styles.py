"""CSS que replica el aspecto visual del prototipo HTML dentro de Streamlit."""

import streamlit as st

from acta_app.config import GREY_BG, GREY_LINE, INK, NAVY, NAVY_DARK, RED

_CSS = f"""
<style>
  html, body, [class*="css"] {{ font-family: Calibri, Arial, sans-serif; }}
  .stApp {{ background: {GREY_BG}; }}
  .block-container {{ max-width: 900px; padding-top: 3.5rem; padding-bottom: 4rem; }}

  /* ---------- Encabezado (tabla del formato impreso) ---------- */
  .letterhead {{
    display: grid; grid-template-columns: auto 1fr; background: #fff;
    border: 1px solid {GREY_LINE}; border-bottom: 3px solid {NAVY}; margin-bottom: 16px;
  }}
  .letterhead .logo-cell {{
    display: flex; align-items: center; padding: 10px 16px;
    border-right: 1px solid {GREY_LINE};
  }}
  .letterhead .logo-cell img {{ height: 26px; width: auto; display: block; }}
  .letterhead .title-row1 {{
    text-align: center; font-weight: 700; color: {NAVY}; font-size: 14px;
    padding: 4px 8px; border-bottom: 1px solid {GREY_LINE};
  }}
  .letterhead .title-row2 {{ display: grid; grid-template-columns: 1fr 2fr 1fr 1fr; font-size: 12px; color: {INK}; }}
  .letterhead .title-row2 > div {{ padding: 4px 8px; text-align: center; border-right: 1px solid {GREY_LINE}; }}
  .letterhead .title-row2 > div:last-child {{ border-right: none; }}
  @media (max-width: 640px) {{
    .letterhead {{ grid-template-columns: 1fr; }}
    .letterhead .logo-cell {{ border-right: none; border-bottom: 1px solid {GREY_LINE}; justify-content: center; }}
    .letterhead .title-row2 {{ grid-template-columns: 1fr 1fr; }}
  }}

  /* ---------- Notas superiores ---------- */
  .top-note {{
    padding: 12px 14px; background: #EEF2F8; border: 1px solid #C9D6EA; border-radius: 6px;
    font-size: 12.5px; color: #33456B; line-height: 1.5; margin-bottom: 14px;
  }}
  .required-note {{ font-size: 12.5px; color: #444; font-weight: 600; margin-bottom: 6px; }}
  .req-star {{ color: {RED}; font-weight: 700; margin-left: 2px; }}

  /* ---------- N.° de acta en rojo ---------- */
  .acta-number-label {{
    color: {RED}; font-weight: 700; font-size: 20px; text-align: right; padding-top: 6px;
  }}
  [class*="_acta_numero"] [data-testid="stTextInputRootElement"] {{
    border: none; border-bottom: 2px solid {RED}; border-radius: 0; background: transparent;
  }}
  [class*="_acta_numero"] input {{
    color: {RED}; font-weight: 700; font-size: 20px; text-align: center;
  }}

  /* ---------- Tarjetas (una por sección) ---------- */
  [class*="st-key-card_"] {{
    background: #fff; border: 1px solid {GREY_LINE} !important; border-radius: 6px;
    padding: 18px 18px 20px; margin-bottom: 4px;
  }}
  .card-title {{
    font-size: 14px; color: {NAVY}; font-weight: 700; margin: 0 0 4px;
    padding-bottom: 8px; border-bottom: 1px solid {GREY_LINE};
  }}
  .card-title .opt {{ color: #6B7280; font-weight: 400; font-size: 12px; }}

  /* ---------- Listas dinámicas ---------- */
  .line-num {{ font-size: 12px; color: #6B7280; padding-top: 10px; text-align: right; }}
  [class*="st-key-quitar_"] button {{
    border: none; background: none; color: #B0B7C3; font-size: 18px; padding: 4px;
  }}
  [class*="st-key-quitar_"] button:hover {{ color: {RED}; background: none; }}
  [class*="st-key-agregar_"] button {{
    background: none; border: 1px dashed {NAVY}; color: {NAVY}; font-weight: 600; font-size: 13px;
  }}
  [class*="st-key-agregar_"] button:hover {{ background: #EEF2F8; color: {NAVY}; border-color: {NAVY}; }}

  /* ---------- Firmas ---------- */
  .sign-label {{ text-align: center; font-size: 13px; font-weight: 600; margin-top: 4px; }}
  [class*="st-key-borrar_"] button {{ color: {NAVY}; text-decoration: underline; font-size: 12px; }}

  .app-version {{ text-align: center; font-size: 11px; color: #8A94A6; margin-top: 10px; }}

  /* ---------- Botones de acción ---------- */
  .st-key-btn_guardar button {{ background: {NAVY}; color: #fff; border: none; font-weight: 700; }}
  .st-key-btn_guardar button:hover {{ background: {NAVY_DARK}; color: #fff; }}
  .st-key-btn_ver_fila button {{ background: #fff; color: {NAVY}; border: 1px solid {NAVY}; font-weight: 700; }}
</style>
"""


def aplicar_estilos() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
