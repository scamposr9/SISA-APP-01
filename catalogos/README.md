# Catálogo para el autocompletado

Los datos de equipos **no se guardan en GitHub**. La app lee `Equipos.xlsx` directamente de
la carpeta de actas en SharePoint (`16. Analisis de Datos/Actas`).

Solo para pruebas en una computadora sin SharePoint se puede dejar aquí un
`equipos.xlsx` local: git lo ignora y nunca se sube.

| Columna del Excel | Campo del formulario |
|---|---|
| Descripcion | Equipo |
| Marca | Marca |
| Modelo | Modelo |
| Serie | N.° Serie |
| Sedes | Cliente |
| Departamentos | Ubicación |

- Si el Excel no trae Sedes/Departamentos, Cliente y Ubicación se escriben a mano.
- Una serie única completa equipo, marca, modelo, cliente y ubicación. Si la serie se
  repite en varios equipos no se completa nada: el ingeniero elige.
- **No cambies los nombres de las columnas**; si cambian, hay que ajustar
  `acta_app/catalogo.py`.
