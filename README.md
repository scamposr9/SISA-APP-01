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
├── data/                      # Salida generada (ignorada por git)
│   ├── actas_maestro.xlsx     #   Excel maestro: hojas "Actas" y "Artículos"
│   └── pdfs/                  #   PDF de cada acta
└── acta_app/
    ├── config.py              # Constantes: metadatos del formato, opciones, colores, rutas
    ├── models.py              # Dataclasses Acta/Articulo + conversión a fila de Excel
    ├── validation.py          # Reglas de campos obligatorios
    ├── ui/
    │   ├── styles.py          # CSS que imita el prototipo
    │   ├── components.py      # Encabezado, tarjetas, listas dinámicas, tabla, firmas
    │   └── form.py            # Formulario completo -> devuelve un Acta
    ├── pdf/generator.py       # PDF con el diseño del formato físico (ReportLab)
    └── storage/
        ├── base.py            # Contrato RepositorioActas + columnas del Excel
        └── excel_local.py     # Excel maestro en disco (hoy); SharePoint irá a su lado
tests/                         # Pruebas de validación, fila de Excel y PDF (pytest)
```

El formulario (`ui/`) solo produce un objeto `Acta`; la validación, el PDF y el Excel trabajan
sobre ese objeto sin depender de Streamlit.

## Excel maestro

- Hoja **Actas**: una fila por acta, mismas columnas que el prototipo + "Archivo PDF".
  "Fecha" y "Fecha de registro" son fechas reales de Excel (hora de Perú).
- Hoja **Artículos**: una fila por artículo empleado, enlazada por "N° de Acta".
- Ambas son Tablas de Excel (filtros y estilo), requisito para escribir en ellas desde
  SharePoint/Microsoft Graph más adelante.
- No se permite guardar dos actas con el mismo N.°.

> En Streamlit Community Cloud el disco no es permanente: descarga el Excel desde
> "Base de datos de actas" al final de la app. La persistencia real llegará con SharePoint.

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
