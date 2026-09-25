# Catálogos para el autocompletado

La app lee estos archivos (si existen) para sugerir valores al escribir en el formulario:

| Archivo | Columnas que usa | Campos del formulario |
|---|---|---|
| `equipos.xlsx` | Descripcion, Marca, Modelo, Serie | Equipo, Marca, Modelo, N.° Serie |
| `clientes.xlsx` | Cliente, Ubicación | *(pendiente: por ahora Cliente y Ubicación se escriben a mano)* |

- Las demás columnas (IdeEquipo, Almacen, …) se ignoran.
- Si una serie se repite en varios equipos, no se autocompleta nada: el ingeniero elige.
- Al reemplazar un archivo en GitHub, Streamlit Cloud se actualiza solo y la app vuelve a
  leerlo (la caché se invalida cuando cambia el archivo).

> ⚠️ El repositorio debe mantenerse privado: estos archivos contienen datos de la empresa.
