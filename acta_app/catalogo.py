"""Catálogo para el autocompletado: equipos (inventario) y clientes.

- Equipos: `catalogos/equipos.xlsx` (columnas Descripcion, Marca, Modelo, Serie).
- Clientes (aún no se usa en el formulario: Cliente y Ubicación se escriben a mano hasta
  tener la lista oficial): `catalogos/clientes.xlsx` (Cliente, Ubicación) y las actas
  ya guardadas.

Las opciones de cada campo se filtran con lo ya elegido en los demás (p. ej. al elegir la
marca solo aparecen sus modelos) y los campos que quedan determinados se autocompletan.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

# Campo del formulario -> posibles nombres de columna en el Excel de origen.
COLUMNAS_EQUIPOS = {
    "equipo": ["Descripcion", "Descripción", "Equipo"],
    "marca": ["Marca"],
    "modelo": ["Modelo"],
    "serie": ["Serie", "N° Serie", "N.° Serie", "Numero de Serie", "Número de Serie"],
}
COLUMNAS_CLIENTES = {
    "cliente": ["Cliente"],
    "ubicacion": ["Ubicación", "Ubicacion", "Sede", "Dirección", "Direccion"],
}
# Se autocompletan cuando quedan determinados. La serie no: el equipo atendido puede no
# estar en el inventario y un modelo con una sola unidad no implica esa serie.
AUTOCOMPLETABLES = {"equipo", "marca", "modelo", "ubicacion"}


def limpiar(valor: object) -> str:
    """Quita espacios sobrantes ('TRF-4K; K-20        ' -> 'TRF-4K; K-20')."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    return " ".join(str(valor).split())


def clave(valor: str) -> str:
    """Comparación sin distinguir mayúsculas, tildes ni espacios extra."""
    sin_tildes = unicodedata.normalize("NFKD", limpiar(valor)).encode("ascii", "ignore").decode()
    return sin_tildes.casefold()


def _normalizar(df: pd.DataFrame, columnas: dict[str, list[str]]) -> pd.DataFrame:
    """Renombra las columnas de origen a los campos del formulario y limpia los valores."""
    disponibles = {clave(c): c for c in df.columns}
    datos = {}
    for campo, candidatas in columnas.items():
        origen = next((disponibles[clave(c)] for c in candidatas if clave(c) in disponibles), None)
        datos[campo] = df[origen].map(limpiar) if origen is not None else ""
    resultado = pd.DataFrame(datos, index=df.index)
    return resultado[(resultado != "").any(axis=1)].drop_duplicates().reset_index(drop=True)


def leer_excel(ruta: Path, columnas: dict[str, list[str]]) -> pd.DataFrame:
    if not ruta.exists():
        return pd.DataFrame(columns=list(columnas))
    return _normalizar(pd.read_excel(ruta, dtype=str), columnas)


@dataclass
class Catalogo:
    equipos: pd.DataFrame  # columnas: equipo, marca, modelo, serie
    clientes: pd.DataFrame  # columnas: cliente, ubicacion

    @classmethod
    def desde_fuentes(
        cls,
        ruta_equipos: Path,
        ruta_clientes: Path | None = None,
        actas: pd.DataFrame | None = None,
    ) -> Catalogo:
        clientes = (
            leer_excel(ruta_clientes, COLUMNAS_CLIENTES)
            if ruta_clientes is not None
            else pd.DataFrame(columns=list(COLUMNAS_CLIENTES))
        )
        if actas is not None and not actas.empty:
            desde_actas = _normalizar(actas, COLUMNAS_CLIENTES)
            clientes = pd.concat([clientes, desde_actas]).drop_duplicates().reset_index(drop=True)
        return cls(leer_excel(ruta_equipos, COLUMNAS_EQUIPOS), clientes)

    def _tabla(self, campo: str) -> pd.DataFrame:
        return self.equipos if campo in COLUMNAS_EQUIPOS else self.clientes

    def _filtrar(self, tabla: pd.DataFrame, seleccion: dict[str, str], excepto: str | None) -> pd.DataFrame:
        filas = tabla
        for campo, valor in seleccion.items():
            if campo == excepto or campo not in tabla.columns or not limpiar(valor):
                continue
            coincide = filas[campo].map(clave) == clave(valor)
            if coincide.any():  # un valor nuevo (fuera del catálogo) no filtra
                filas = filas[coincide]
        return filas

    def opciones(self, campo: str, seleccion: dict[str, str]) -> list[str]:
        """Valores sugeridos para `campo`, compatibles con lo elegido en los demás campos."""
        tabla = self._tabla(campo)
        valores = self._filtrar(tabla, seleccion, excepto=campo)[campo]
        if valores[valores != ""].empty:
            valores = tabla[campo]
        unicos = {clave(v): v for v in valores if v}
        actual = limpiar(seleccion.get(campo))
        if actual and clave(actual) not in unicos:
            unicos[clave(actual)] = actual
        return sorted(unicos.values(), key=clave)

    def autocompletar(self, seleccion: dict[str, str]) -> dict[str, str]:
        """Campos vacíos que quedan determinados por lo ya elegido (valor único posible)."""
        completados: dict[str, str] = {}
        for tabla in (self.equipos, self.clientes):
            elegidos = {c: v for c, v in seleccion.items() if c in tabla.columns and limpiar(v)}
            if not elegidos:
                continue
            filas = tabla
            for campo, valor in elegidos.items():
                filas = filas[filas[campo].map(clave) == clave(valor)]
            if filas.empty:
                continue
            if "serie" in elegidos and len(filas) > 1:
                # Serie repetida en varios equipos: no se completa nada, decide el ingeniero.
                continue
            for campo in tabla.columns:
                if campo in AUTOCOMPLETABLES and campo not in elegidos:
                    valores = {v for v in filas[campo] if v}
                    if len(valores) == 1:
                        completados[campo] = valores.pop()
        return completados
