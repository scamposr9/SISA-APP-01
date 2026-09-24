import io
from datetime import date, time

import pytest
from PIL import Image, ImageDraw

from acta_app.models import Acta, Articulo


def _firma_png() -> bytes:
    imagen = Image.new("RGBA", (380, 130), (255, 255, 255, 255))
    ImageDraw.Draw(imagen).line([(30, 90), (120, 40), (250, 90)], fill=(22, 48, 92, 255), width=3)
    buffer = io.BytesIO()
    imagen.save(buffer, "PNG")
    return buffer.getvalue()


@pytest.fixture
def acta_completa() -> Acta:
    return Acta(
        numero="2026-00051",
        fecha=date(2026, 9, 24),
        cliente="Hospital Rebagliati",
        ubicacion="Lima",
        equipo="HPLC",
        marca="Agilent",
        modelo="1260",
        numero_serie="SN123",
        tipo_servicio="Mant. Preventivo",
        antecedentes=["Ruido en bomba"],
        hora_inicio_trabajo=time(9, 0),
        hora_fin_trabajo=time(13, 30),
        acciones=["Se revisó la bomba"],
        diagnostico=["Sello desgastado"],
        estado_final="Operativo",
        articulos=[Articulo("SEL-01", "Sello de pistón", 2), Articulo()],
        observaciones=["Cambiar filtro"],
        nombre_cliente="Juan Pérez",
        firma_cliente_png=_firma_png(),
        nombre_representante="Ana Ruiz",
        firma_representante_png=_firma_png(),
    )
