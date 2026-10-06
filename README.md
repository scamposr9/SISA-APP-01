# SISA-APP-01 — Acta de Atención Digital (FO-ING-02)

Aplicación web en Python/Streamlit para digitalizar el acta de atención al cliente de campo
de Sistemas Analíticos. El diseño, los campos y las validaciones replican el prototipo HTML
validado con el cliente (`acta_atencion_referencia_para_claude_code.html`).

## Estructura

```
SISA-APP-01/
├── app.py                     # Punto de entrada: arma la página y los botones de acción
├── requirements.txt
├── .streamlit/config.toml     # Tema (colores del prototipo)
├── assets/
│   └── logo.png               # Logo extraído del prototipo HTML
├── catalogos/                 # Solo el README: los datos de equipos viven en SharePoint
├── data/                      # Salida generada (ignorada por git)
│   ├── actas_maestro.xlsx     #   Excel maestro: hojas "Actas" y "Artículos"
│   ├── pdfs/                  #   PDF de cada acta (original y revisiones)
│   └── firmas/                #   Firmas en PNG, para reutilizarlas al corregir
└── acta_app/
    ├── config.py              # Constantes, rutas y versión desplegada (commit de git)
    ├── catalogo.py            # Autocompletado: opciones filtradas y campos determinados
    ├── models.py              # Dataclasses Acta/Articulo + conversión a fila de Excel
    ├── validation.py          # Reglas de campos obligatorios
    ├── ui/
    │   ├── styles.py          # CSS que imita el prototipo
    │   ├── components.py      # Encabezado, tarjetas, listas dinámicas, tabla, firmas
    │   ├── catalogo_ui.py     # Carga del catálogo con caché
    │   └── form.py            # Formulario completo -> devuelve un Acta
    ├── pdf/generator.py       # PDF con el diseño del formato físico (ReportLab)
    └── storage/
        ├── base.py            # Contrato RepositorioActas
        ├── esquema.py         # Columnas del Excel (campos y grupos de ítems)
        ├── excel_formato.py   # Leer/escribir el libro (reutilizable para SharePoint)
        ├── excel_local.py     # Sin SharePoint: Excel y PDFs en el disco del servidor
        └── sharepoint.py      # Con SharePoint: Actas.xlsx, PDF/, Firmas Actas/ y Equipos.xlsx
tests/                         # Pruebas de validación, fila de Excel y PDF (pytest)
```

El formulario (`ui/`) solo produce un objeto `Acta`; la validación, el PDF y el Excel trabajan
sobre ese objeto sin depender de Streamlit.

## Excel maestro

- Hoja **Actas**: una fila por acta.
  - Los apartados con varios ítems (Antecedentes, Acciones, Artículos,
    Observaciones) tienen **una columna por ítem** ("Antecedente 1", "Antecedente 2"…)
    bajo un encabezado combinado ("Antecedentes Iniciales"). Cada grupo tiene tantas
    columnas como el acta con más ítems; se amplía solo al guardar.
  - "Fecha", horas y "Fecha de registro" son fechas/horas reales de Excel (hora de Perú, 24 horas).
  - "PDF original" y "PDF corregido" son enlaces (fórmula HYPERLINK) a los PDF del acta:
    se abren con un clic también en Excel para la web.
- Hoja **Artículos**: una fila por artículo empleado, enlazada por "N° de Acta".
- No se permite guardar dos actas con el mismo N.°.
- **Corregir un acta** (selector en la parte superior de la app): se carga el acta, se
  corrige y se indica motivo y responsable. La fila del Excel se actualiza (no se duplica),
  el PDF original se conserva y se genera `Acta_<N°>_Rev1.pdf`, `_Rev2`, … marcado como
  revisión. Las firmas originales se pueden conservar o volver a tomar.
- La estructura de columnas está en `acta_app/storage/esquema.py`.

## SharePoint

Si los **Secrets** de Streamlit Cloud (*App → Settings → Secrets*) tienen la sección
`[sharepoint]`, la app guarda todo en la carpeta `16. Analisis de Datos/Actas` del sitio
*OperacionesyServicios*:

```toml
[sharepoint]
tenant_id = "<Directory (tenant) ID>"
client_id = "<Application (client) ID>"
client_secret = "<VALOR del client secret (no su ID)>"
# Opcionales (por defecto, los de acta_app/config.py):
# sitio = "https://sistemasanaliticospe.sharepoint.com/sites/OperacionesyServicios"
# biblioteca = "Documentos compartidos"
# carpeta = "16. Analisis de Datos/Actas"
```

- `Actas.xlsx` lo crea la app con la primera acta; los PDF van a `PDF/` y las firmas a
  `Firmas Actas/<N.° de acta>/` (cliente.png y representante.png). Los enlaces del Excel abren cada PDF en SharePoint.
- Si otra persona guarda al mismo tiempo, la app lo detecta (eTag) y reintenta sin perder filas.
- `Equipos.xlsx` en la misma carpeta alimenta el autocompletado (se relee cada 5 minutos o
  con «Actualizar catálogo de equipos»). Los datos de la empresa no se guardan en GitHub.
- **Mantenimiento preventivo:** al elegir «Mant. Preventivo», Antecedentes iniciales lleva
  «Mantenimiento Preventivo» y, según la marca y el modelo del equipo, «Acciones realizadas»
  muestra el checklist de la columna «Parte mantenida» de `Mantenimientos Preventivos.xlsx`
  (se ignoran serie, clientes, cronograma y OBS). En el PDF cada actividad sale con su casilla
  marcada (X) o vacía, y las acciones adicionales como «[X] … (Extra)»; en el Excel igual, en las columnas de Acciones.
  Si un mismo equipo/marca/modelo aparece varias veces en el Excel (p. ej. por cliente), sus
  actividades se juntan y el ingeniero puede quitar con × las que no correspondan; con un solo
  registro, el checklist no se puede recortar.
  «Conexión con SharePoint → Ver protocolos… detectados» muestra lo que la app leyó del Excel.
- **Artículos empleados:** el código sugiere los repuestos de `Repuestos.xlsx` (todas sus
  hojas, columnas de código y descripción; filas repetidas se toman una vez) y al elegir un código conocido se completa su
  descripción. Se aceptan códigos que no estén en el catálogo.
- **Nombre del representante:** desplegable con los ingenieros de
  `Firmas Ingenieros/Nombres Ingenieria.xlsx` (columna «Nombre…»; también sirve una carpeta
  `Nombres Ingenieria` con un Excel o una subcarpeta por ingeniero); al escribir se filtran los nombres.
- **Encuesta de satisfacción por QR:** en la ventana «Acta guardada», «Visualizar encuesta con
  QR» muestra un código QR que el cliente escanea con su celular. Abre la encuesta sin iniciar
  sesión: 5 aspectos del 1 al 5 y un comentario opcional; la suma se lleva a escala de 20 (todo
  5 = 20). El QR vale 24 horas y una sola vez (respondida la encuesta, no se puede volver a
  usar). En `Actas.xlsx`, después de «PDF corregido», el bloque «Encuesta de satisfacción del
  servicio» guarda las respuestas, cuándo se generó el QR, cuándo vence y el hash del código
  (nunca el código). En la vista de desarrolladores, «QR de la encuesta de un acta guardada»
  genera otro QR (anula el anterior). Una corrección del acta conserva la encuesta. Opcional en
  Secrets: `[app] url_app` si la dirección de la app cambia.
- **Equipos nuevos:** si se guarda un acta cuya serie no está en `Equipos.xlsx`, el equipo se
  anota en `Equipos_nuevos.xlsx` (misma carpeta; se crea con el primero), con el N.° de acta y
  quién lo registró. El autocompletado ya lo sugiere; una persona revisa esa lista, copia las
  filas correctas a `Equipos.xlsx` (las 6 primeras columnas son las mismas) y las borra de la lista.
- «Conexión con SharePoint → Probar conexión», al final de la app, verifica acceso y escritura.
- La app usa el permiso de aplicación **Sites.Selected**: TI debe asignarle escritura sobre el sitio.

Sin la sección `[sharepoint]`, todo se guarda en el disco del servidor, que en Streamlit
Community Cloud se borra al reiniciar: descarga "Excel + PDFs (ZIP)".

### Vista de desarrolladores

Con el inicio de sesión activo, las secciones «Base de datos de actas» y «Conexión con
SharePoint» solo se muestran a los correos listados en los Secrets:

```toml
[app]
desarrolladores = ["correo1@sistemasanaliticos.com", "correo2@sistemasanaliticos.com"]
```

Los demás usuarios ven solo el formulario. Sin inicio de sesión, las secciones se ven siempre.

### Inicio de sesión con Microsoft (opcional)

Con una sección `[auth]` en los Secrets, la app pide iniciar sesión con Microsoft y solo deja
pasar correos `@sistemasanaliticos.com` (`config.DOMINIO_PERMITIDO`). Requiere la Redirect URI
`https://sisa-app.streamlit.app/oauth2callback` (plataforma *Web*) en Azure:

```toml
[auth]
redirect_uri = "https://sisa-app.streamlit.app/oauth2callback"
cookie_secret = "<texto aleatorio largo>"
client_id = "<Application (client) ID>"
client_secret = "<VALOR del client secret>"
server_metadata_url = "https://login.microsoftonline.com/<tenant ID>/v2.0/.well-known/openid-configuration"
```

## Ejecutar

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Pruebas

```bash
pip install -r requirements-dev.txt
pytest
```
