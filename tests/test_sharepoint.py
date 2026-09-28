"""RepositorioSharePoint con un SharePoint simulado en memoria, y AlmacenGraph contra un
Microsoft Graph simulado (sin red)."""

import io
from datetime import datetime

import pytest
from openpyxl import load_workbook

from acta_app.models import Articulo
from acta_app.storage import ActaDuplicadaError, AlmacenamientoError
from acta_app.storage.sharepoint import (
    AlmacenGraph,
    Archivo,
    ConflictoDeVersion,
    RepositorioSharePoint,
)

CARPETA = "16. Analisis de Datos/Actas"


class SharePointFalso:
    """Almacén en memoria con eTags, como una biblioteca de SharePoint."""

    def __init__(self):
        self.archivos: dict[str, tuple[bytes, int]] = {}
        self.carpetas = {CARPETA}
        self.antes_de_escribir = None  # para simular a otro usuario guardando

    def _url(self, ruta):
        return f"https://sp.example/{ruta}"

    def leer(self, ruta):
        if ruta not in self.archivos:
            return None
        datos, version = self.archivos[ruta]
        return Archivo(datos=datos, version=f'"v{version}"', enlace=self._url(ruta))

    def escribir(self, ruta, datos, version_esperada=None, solo_si_no_existe=False):
        if self.antes_de_escribir and ruta.endswith(".xlsx"):
            accion, self.antes_de_escribir = self.antes_de_escribir, None
            accion()
        actual = self.archivos.get(ruta)
        if solo_si_no_existe and actual is not None:
            raise ConflictoDeVersion(ruta)
        if version_esperada and (actual is None or f'"v{actual[1]}"' != version_esperada):
            raise ConflictoDeVersion(ruta)
        self.archivos[ruta] = (datos, (actual[1] + 1) if actual else 1)
        return self._url(ruta)

    def eliminar(self, ruta):
        self.archivos.pop(ruta, None)

    def enlace(self, ruta):
        existe = ruta in self.archivos or ruta in self.carpetas or any(
            r.startswith(ruta + "/") for r in self.archivos
        )
        return self._url(ruta) if existe else None


@pytest.fixture
def sp():
    return SharePointFalso()


@pytest.fixture
def repo(sp):
    return RepositorioSharePoint(sp, carpeta=CARPETA, segundos_cache=0)


def _fila(sp, n=1):
    ws = load_workbook(io.BytesIO(sp.archivos[f"{CARPETA}/Actas.xlsx"][0]))["Actas"]
    return {ws.cell(2, c).value: ws.cell(2 + n, c) for c in range(1, ws.max_column + 1)}


def test_primera_acta_crea_actas_xlsx_y_sube_pdf_y_firmas(repo, sp, acta_completa):
    resultado = repo.guardar(acta_completa, b"%PDF", "Acta_2026-00051.pdf")

    assert resultado.total_actas == 1
    assert resultado.ubicacion_pdf == f"https://sp.example/{CARPETA}/PDF/Acta_2026-00051.pdf"
    assert sp.archivos[f"{CARPETA}/PDF/Acta_2026-00051.pdf"][0] == b"%PDF"
    assert f"{CARPETA}/Firmas/2026-00051_cliente.png" in sp.archivos
    fila = _fila(sp)
    assert fila["N° de Acta"].value == "2026-00051"
    assert fila["PDF original"].hyperlink.target == resultado.ubicacion_pdf


def test_numero_repetido_no_se_guarda(repo, acta_completa):
    repo.guardar(acta_completa, b"%PDF", "a.pdf")
    with pytest.raises(ActaDuplicadaError):
        repo.guardar(acta_completa, b"%PDF", "b.pdf")
    assert repo.numeros() == ["2026-00051"]


def test_si_otro_usuario_guarda_al_mismo_tiempo_no_se_pierde_ninguna_acta(repo, sp, acta_completa):
    repo.guardar(acta_completa, b"%PDF", "1.pdf")

    # Mientras este usuario guarda la 00052, otro guarda la 00053.
    otro = RepositorioSharePoint(sp, carpeta=CARPETA, segundos_cache=0)

    def guardar_otra():
        from copy import deepcopy

        otra = deepcopy(acta_completa)
        otra.numero, otra.fecha_registro = "2026-00053", None
        otro.guardar(otra, b"%PDF", "3.pdf")

    sp.antes_de_escribir = guardar_otra
    acta_completa.numero, acta_completa.fecha_registro = "2026-00052", None
    repo.guardar(acta_completa, b"%PDF", "2.pdf")

    assert sorted(repo.numeros()) == ["2026-00051", "2026-00052", "2026-00053"]


def test_corregir_actualiza_la_fila_y_conserva_el_pdf_original(repo, sp, acta_completa):
    acta_completa.articulos = [Articulo("A-1", "Filtro", 2)]
    repo.guardar(acta_completa, b"%PDF orig", "Acta_2026-00051.pdf")

    acta = repo.obtener("2026-00051")
    assert acta.firma_cliente_png  # firmas recuperadas desde SharePoint
    acta.cliente = "Cliente corregido"
    acta.revision, acta.corregido_por, acta.motivo_correccion = 1, "Ana", "Error de tipeo"
    acta.fecha_correccion = datetime(2026, 9, 28, 10, 0)
    resultado = repo.corregir(acta, b"%PDF rev1", "Acta_2026-00051_Rev1.pdf")

    assert resultado.total_actas == 1
    fila = _fila(sp)
    assert fila["Cliente"].value == "Cliente corregido"
    assert fila["PDF original"].hyperlink.target.endswith("/PDF/Acta_2026-00051.pdf")
    assert fila["PDF corregido"].hyperlink.target.endswith("/PDF/Acta_2026-00051_Rev1.pdf")
    assert sp.archivos[f"{CARPETA}/PDF/Acta_2026-00051.pdf"][0] == b"%PDF orig"


def test_catalogo_y_enlaces(repo, sp):
    assert repo.leer_equipos() is None
    sp.archivos[f"{CARPETA}/Equipos.xlsx"] = (b"xlsx", 1)
    assert repo.leer_equipos() == b"xlsx"
    assert repo.enlace_carpeta() == f"https://sp.example/{CARPETA}"
    assert repo.exportar_zip() is None


def test_probar_conexion_informa_cada_paso(repo):
    pasos = repo.probar_conexion()
    assert all(ok for ok, _ in pasos[:1])
    assert any("puede escribir" in m for ok, m in pasos if ok)
    assert any("Actas.xlsx aún no existe" in m for _, m in pasos)


# ---------- AlmacenGraph contra un Graph simulado ----------
class Respuesta:
    def __init__(self, status, json=None, content=b"", headers=None):
        self.status_code, self._json, self.content = status, json or {}, content
        self.headers, self.text = headers or {}, str(json or "")

    def json(self):
        return self._json


class GraphFalso:
    def __init__(self):
        self.peticiones = []
        self.respuestas = {}

    def request(self, metodo, url, headers=None, **kwargs):
        self.peticiones.append((metodo, url, headers, kwargs))
        for (m, fragmento), respuesta in self.respuestas.items():
            if m == metodo and fragmento in url:
                return respuesta(kwargs, headers) if callable(respuesta) else respuesta
        return Respuesta(404)


@pytest.fixture
def graph(monkeypatch):
    falso = GraphFalso()
    falso.respuestas[("GET", "/sites/sistemasanaliticospe.sharepoint.com:/sites/OperacionesyServicios")] = \
        Respuesta(200, {"id": "SITIO"})
    falso.respuestas[("GET", "/sites/SITIO/drives")] = Respuesta(200, {"value": [
        {"id": "OTRA", "name": "Activos del sitio", "webUrl": "https://x/sites/OperacionesyServicios/SiteAssets"},
        {"id": "DOCS", "name": "Documentos",
         "webUrl": "https://x/sites/OperacionesyServicios/Documentos%20compartidos"},
    ]})
    almacen = AlmacenGraph("t", "c", "s", sesion=falso)
    monkeypatch.setattr(almacen, "_token", lambda: "TOKEN")
    return falso, almacen


def test_graph_encuentra_la_biblioteca_por_su_url_y_codifica_la_ruta(graph):
    falso, almacen = graph
    falso.respuestas[("GET", "/drives/DOCS/root:/16.%20Analisis%20de%20Datos/Actas/Actas.xlsx")] = \
        Respuesta(200, {"id": "ITEM", "eTag": '"e1"', "webUrl": "https://x/Actas.xlsx"})
    falso.respuestas[("GET", "/drives/DOCS/items/ITEM/content")] = Respuesta(200, content=b"XLSX")

    archivo = almacen.leer(f"{CARPETA}/Actas.xlsx")
    assert (archivo.datos, archivo.version, archivo.enlace) == (b"XLSX", '"e1"', "https://x/Actas.xlsx")
    assert all(h["Authorization"] == "Bearer TOKEN" for _, _, h, _ in falso.peticiones)


def test_graph_escribe_con_if_match_y_detecta_conflictos(graph):
    falso, almacen = graph
    falso.respuestas[("PUT", "/root:/16.%20Analisis%20de%20Datos/Actas/Actas.xlsx:/content")] = \
        lambda kw, h: Respuesta(412) if h.get("If-Match") == '"viejo"' else Respuesta(200, {"webUrl": "https://x/a"})

    assert almacen.escribir(f"{CARPETA}/Actas.xlsx", b"x", version_esperada='"nuevo"') == "https://x/a"
    with pytest.raises(ConflictoDeVersion):
        almacen.escribir(f"{CARPETA}/Actas.xlsx", b"x", version_esperada='"viejo"')


def test_graph_sin_permiso_en_el_sitio_explica_que_falta(graph):
    falso, almacen = graph
    falso.respuestas[("PUT", "/content")] = Respuesta(403, {"error": "accessDenied"})
    with pytest.raises(AlmacenamientoError, match="Sites.Selected"):
        almacen.escribir(f"{CARPETA}/PDF/a.pdf", b"x")


def test_graph_archivo_inexistente_devuelve_none(graph):
    _, almacen = graph
    assert almacen.leer(f"{CARPETA}/Equipos.xlsx") is None
    assert almacen.enlace(f"{CARPETA}/nada") is None


def test_tenant_invalido_da_un_error_claro_y_no_rompe_la_app():
    almacen = AlmacenGraph("tenant-que-no-existe", "c", "s", sesion=GraphFalso())
    with pytest.raises(AlmacenamientoError, match="tenant_id"):
        almacen.leer(f"{CARPETA}/Actas.xlsx")
