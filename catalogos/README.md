# Catálogos para el autocompletado

La app lee estos archivos (si existen) para sugerir valores al escribir en el formulario:

| Archivo | Columnas que usa | Campos del formulario |
|---|---|---|
| `equipos.xlsx` | Descripcion, Marca, Modelo, Serie | Equipo, Marca, Modelo, N.° Serie |
| `clientes.xlsx` | Cliente, Ubicación | Cliente, Ubicación |

- Las demás columnas (IdeEquipo, Almacen, …) se ignoran.
- Los clientes y ubicaciones de las actas ya guardadas también se sugieren.
- Al reemplazar un archivo en GitHub, Streamlit Cloud se actualiza solo y la app vuelve a
  leerlo (la caché se invalida cuando cambia el archivo).

> ⚠️ Si el repositorio es público, estos archivos quedan visibles para cualquiera.
