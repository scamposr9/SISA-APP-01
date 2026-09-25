"""Catálogo para el autocompletado, leído de un único Excel de equipos (Equipos.xlsx).

Columnas del Excel -> campos del formulario:
    Descripcion -> Equipo · Marca -> Marca · Modelo -> Modelo · Serie -> N.° Serie
    Sedes -> Cliente · Departamentos -> Ubicación
Las demás columnas (IdeEquipo, Almacen, ...) se ignoran.

Las opciones de cada campo se filtran con lo ya elegido en los demás (p. ej. al elegir el
cliente solo aparecen sus equipos) y se completan los campos que quedan determinados.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

# Campo del formulario -> posibles nombres de columna en el Excel (sin distinguir
# mayúsculas ni tildes).
COLUMNAS = {
    "equipo": ["Descripcion", "Descripción", "Equipo"],
    "marca": ["Marca"],
    "modelo": ["Modelo"],
    "serie": ["Serie", "N° Serie", "N.° Serie", "Numero de Serie", "Número de Serie"],
    "cliente": ["Sedes", "Sede", "Cliente", "Clientes"],
    "ubicacion": ["Departamentos", "Departamento", "Ubicación", "Ubicacion"],
}

# Autocompletado por grupos: cada grupo de campos solo se completa a partir de los campos
# indicados. Así, elegir un cliente completa su ubicación pero nunca "adivina" un equipo,
# y el equipo se deduce de su serie o de su modelo. La serie nunca se autocompleta: el
# equipo atendido puede no estar en el inventario.
GRUPOS_AUTOCOMPLETADO = [
    ({"equipo", "marca", "modelo"}, {"equipo", "marca", "modelo", "serie"}),
    ({"cliente", "ubicacion"}, {"cliente", "ubicacion", "serie"}),
]


def limpiar(valor: object) -> str:
    """Quita espacios sobrantes ('TRF-4K; K-20        ' -> 'TRF-4K; K-20')."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    return " ".join(str(valor).split())


def clave(valor: str) -> str:
    """Comparación sin distinguir mayúsculas, tildes ni espacios extra."""
    sin_tildes = unicodedata.normalize("NFKD", limpiar(valor)).encode("ascii", "ignore").decode()
    return sin_tildes.casefold()


def _normalizar(df: pd.DataFrame) -> pd.DataFrame:
    """Renombra las columnas de origen a los campos del formulario y limpia los valores."""
    disponibles = {clave(c): c for c in df.columns}
    datos = {}
    for campo, candidatas in COLUMNAS.items():
        origen = next((disponibles[clave(c)] for c in candidatas if clave(c) in disponibles), None)
        datos[campo] = df[origen].map(limpiar) if origen is not None else ""
    resultado = pd.DataFrame(datos, index=df.index)
    return resultado[(resultado != "").any(axis=1)].drop_duplicates().reset_index(drop=True)


@dataclass
class Catalogo:
    datos: pd.DataFrame  # columnas: equipo, marca, modelo, serie, cliente, ubicacion

    @classmethod
    def desde_excel(cls, ruta: Path) -> Catalogo:
        if not ruta.exists():
            return cls(pd.DataFrame(columns=list(COLUMNAS)))
        return cls(_normalizar(pd.read_excel(ruta, dtype=str)))

    def tiene(self, campo: str) -> bool:
        """¿El Excel trae valores para este campo? (p. ej. si ya incluye las sedes)."""
        return bool((self.datos[campo] != "").any())

    def _filtrar(self, seleccion: dict[str, str], excepto: str | None = None) -> pd.DataFrame:
        filas = self.datos
        for campo, valor in seleccion.items():
            if campo == excepto or campo not in filas.columns or not limpiar(valor):
                continue
            coincide = filas[campo].map(clave) == clave(valor)
            if coincide.any():  # un valor nuevo (fuera del catálogo) no filtra
                filas = filas[coincide]
        return filas

    def opciones(self, campo: str, seleccion: dict[str, str]) -> list[str]:
        """Valores sugeridos para `campo`, compatibles con lo elegido en los demás campos."""
        valores = self._filtrar(seleccion, excepto=campo)[campo]
        if valores[valores != ""].empty:
            valores = self.datos[campo]
        unicos = {clave(v): v for v in valores if v}
        actual = limpiar(seleccion.get(campo))
        if actual and clave(actual) not in unicos:
            unicos[clave(actual)] = actual
        return sorted(unicos.values(), key=clave)

    def autocompletar(self, seleccion: dict[str, str]) -> dict[str, str]:
        """Campos vacíos que quedan determinados por lo ya elegido (valor único posible)."""
        completados: dict[str, str] = {}
        for completables, determinantes in GRUPOS_AUTOCOMPLETADO:
            elegidos = {c: v for c, v in seleccion.items() if c in determinantes and limpiar(v)}
            if not elegidos:
                continue
            filas = self.datos
            for campo, valor in elegidos.items():
                filas = filas[filas[campo].map(clave) == clave(valor)]
            if filas.empty:
                continue
            if "serie" in elegidos and len(filas) > 1:
                # Serie repetida en varios equipos: no se completa nada, decide el ingeniero.
                continue
            for campo in completables - elegidos.keys():
                valores = {v for v in filas[campo] if v}
                if len(valores) == 1:
                    completados[campo] = valores.pop()
        return completados
