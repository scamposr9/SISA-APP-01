# Catálogo para el autocompletado

La app lee `equipos.xlsx` (con SharePoint será `Equipos.xlsx` en la carpeta Actas) y sugiere
valores al escribir en el formulario:

| Columna del Excel | Campo del formulario |
|---|---|
| Descripcion | Equipo |
| Marca | Marca |
| Modelo | Modelo |
| Serie | N.° Serie |
| Sedes | Cliente |
| Departamentos | Ubicación |

- Las demás columnas (IdeEquipo, Almacen, …) se ignoran.
- Si el Excel no trae Sedes/Departamentos, Cliente y Ubicación se escriben a mano.
- Una serie única completa equipo, marca, modelo, cliente y ubicación. Si la serie se
  repite en varios equipos no se completa nada: el ingeniero elige en los desplegables.
- Un cliente completa su ubicación (si tiene una sola), pero nunca "adivina" el equipo.
- **No cambies los nombres de las columnas**; si cambian, hay que ajustar
  `acta_app/catalogo.py`.

> ⚠️ El repositorio debe mantenerse privado: este archivo contiene datos de la empresa.
