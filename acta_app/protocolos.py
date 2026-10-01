"""Protocolos de mantenimiento preventivo (Mantenimientos Preventivos.xlsx en SharePoint).

De cada protocolo solo se usan Equipo, Marca, Modelo y la columna «Parte mantenida», que
se convierte en el checklist de «Acciones realizadas». Se ignoran el N.° de serie, los
clientes del encabezado, las columnas del cronograma y las observaciones (OBS), que
quedan a criterio del ingeniero.

El lector acepta las dos formas habituales del Excel, en una o varias hojas:
  * Bloques: «EQUIPO: …», «MARCA: …», «MODELO: …» en el encabezado (valor en la misma
    celda o a la derecha) y debajo una tabla con la columna «Parte mantenida».
  * Tabla: una fila por actividad con columnas Equipo / Marca / Modelo / Parte mantenida
    (las celdas vacías o combinadas repiten el valor de arriba).
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

from openpyxl import load_workbook

from acta_app.catalogo import clave, limpiar

_ETIQUETAS = {"equipo": "equipo", "descripcion": "equipo", "marca": "marca", "modelo": "modelo"}
_NUMERACION = re.compile(r"^\s*(\d+(\.\d+)*|[a-z])\s*[.)\-]\s+", re.IGNORECASE)


@dataclass
class Protocolo:
    equipo: str = ""
    marca: str = ""
    modelo: str = ""
    actividades: list[str] = field(default_factory=list)
    hoja: str = ""


def _modelos(texto: str) -> set[str]:
    """'TRF-4K; K-20' -> {'trf-4k; k-20', 'trf-4k', 'k-20'}: un protocolo puede cubrir varios."""
    partes = {clave(p) for p in re.split(r"[;/,]| y ", texto) if clave(p)}
    return partes | ({clave(texto)} if clave(texto) else set())


@dataclass
class Protocolos:
    lista: list[Protocolo] = field(default_factory=list)

    def buscar(self, equipo: str, marca: str, modelo: str) -> Protocolo | None:
        """Protocolo de esa marca y modelo (el equipo solo desempata). Si la marca no
        coincide con ninguno, se acepta el modelo solo cuando es único."""
        if not clave(modelo):
            return None
        modelos = _modelos(modelo)
        candidatos = [p for p in self.lista if _modelos(p.modelo) & modelos]
        con_marca = [p for p in candidatos if clave(p.marca) == clave(marca)] if clave(marca) else []
        elegidos = con_marca or (candidatos if len(candidatos) == 1 else [])
        if len(elegidos) > 1 and clave(equipo):
            elegidos = [p for p in elegidos if clave(p.equipo) == clave(equipo)] or elegidos
        return elegidos[0] if elegidos else None

    @classmethod
    def desde_bytes(cls, datos: bytes) -> Protocolos:
        wb = load_workbook(io.BytesIO(datos), data_only=True, read_only=True)
        protocolos: list[Protocolo] = []
        for ws in wb.worksheets:
            protocolos += _leer_hoja(ws.title, [list(fila) for fila in ws.iter_rows(values_only=True)])
        wb.close()
        # Un mismo equipo/marca/modelo repetido (p. ej. por cliente): se unen sus actividades.
        unidos: dict[tuple[str, str, str], Protocolo] = {}
        for p in protocolos:
            llave = (clave(p.equipo), clave(p.marca), clave(p.modelo))
            if llave in unidos:
                existentes = {clave(a) for a in unidos[llave].actividades}
                unidos[llave].actividades += [a for a in p.actividades if clave(a) not in existentes]
            else:
                unidos[llave] = p
        return cls([p for p in unidos.values() if p.actividades and (p.modelo or p.marca)])


def _etiqueta(celda: str) -> tuple[str, str] | None:
    """'MARCA: Abbott' -> ('marca', 'Abbott'); 'Modelo' -> ('modelo', '')."""
    nombre, separador, resto = celda.partition(":")
    campo = _ETIQUETAS.get(clave(nombre).strip(" .°"))
    if campo is None:
        return None
    return campo, limpiar(resto) if separador else ""


def _es_columna_parte(celda: str) -> bool:
    texto = clave(celda)
    return "parte" in texto and "manten" in texto


def _leer_hoja(nombre_hoja: str, filas: list[list[object]]) -> list[Protocolo]:
    protocolos: list[Protocolo] = []
    actual = Protocolo(hoja=nombre_hoja)
    col_parte: int | None = None
    cols_tabla: dict[str, int] = {}  # forma «tabla»: columnas Equipo/Marca/Modelo

    def cerrar() -> None:
        nonlocal actual
        if actual.actividades:
            protocolos.append(actual)
        actual = Protocolo(equipo=actual.equipo, marca=actual.marca, modelo=actual.modelo, hoja=nombre_hoja)

    for fila in filas:
        textos = [limpiar(c) for c in fila]
        no_vacias = [(i, t) for i, t in enumerate(textos) if t]
        if not no_vacias:
            continue

        # ¿Fila de encabezado de la tabla de actividades?
        encabezado = next((i for i, t in no_vacias if _es_columna_parte(t)), None)
        if encabezado is not None:
            cerrar()
            col_parte = encabezado
            cols_tabla = {}
            for i, t in no_vacias:
                if i != encabezado and (campo := _ETIQUETAS.get(clave(t).strip(" .°:"))):
                    cols_tabla.setdefault(campo, i)
            continue

        # Observaciones (OBS): a criterio del ingeniero. Se ignoran la fila y todo lo que
        # sigue debajo (p. ej. renglones «1-», «2-» para escribir) hasta el próximo protocolo.
        if clave(no_vacias[0][1]).startswith("obs"):
            col_parte = None
            continue

        # Etiquetas del encabezado del protocolo (EQUIPO / MARCA / MODELO).
        etiquetas_en_fila = False
        for posicion, (i, t) in enumerate(no_vacias):
            if col_parte is not None and i == col_parte:
                continue
            etiqueta = _etiqueta(t)
            if etiqueta is None or (cols_tabla and i in cols_tabla.values()):
                continue
            campo, valor = etiqueta
            if not valor and posicion + 1 < len(no_vacias):
                valor = no_vacias[posicion + 1][1]
            if valor and _etiqueta(valor) is None:
                if not etiquetas_en_fila:
                    cerrar()  # empieza otro protocolo
                    col_parte = None if not cols_tabla else col_parte
                etiquetas_en_fila = True
                setattr(actual, campo, valor)
        if etiquetas_en_fila or col_parte is None:
            continue

        # Fila de la tabla de actividades.
        if cols_tabla:
            nuevos = {c: textos[i] for c, i in cols_tabla.items() if i < len(textos) and textos[i]}
            if any(clave(v) != clave(getattr(actual, c)) for c, v in nuevos.items()):
                cerrar()
                for c, v in nuevos.items():
                    setattr(actual, c, v)
        actividad = textos[col_parte] if col_parte < len(textos) else ""
        actividad = _NUMERACION.sub("", actividad).strip()
        if not re.search(r"[^\W\d_]", actividad):
            continue  # sin letras: «1-», «2.», «-», «X»… no es una actividad
        if actividad and not _es_columna_parte(actividad) and clave(actividad) not in (
            {clave(a) for a in actual.actividades}
        ):
            actual.actividades.append(actividad)

    cerrar()
    return protocolos
