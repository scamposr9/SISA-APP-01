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
        ├── base.py            # Contrato RepositorioActas
        ├── esquema.py         # Columnas del Excel (campos y grupos de ítems)
        ├── excel_formato.py   # Leer/escribir el libro (reutilizable para SharePoint)
        └── excel_local.py     # Excel maestro en disco (hoy); SharePoint irá a su lado
tests/                         # Pruebas de validación, fila de Excel y PDF (pytest)
```

El formulario (`ui/`) solo produce un objeto `Acta`; la validación, el PDF y el Excel trabajan
sobre ese objeto sin depender de Streamlit.

## Excel maestro

- Hoja **Actas**: una fila por acta.
  - Los apartados con varios ítems (Antecedentes, Acciones, Diagnóstico, Artículos,
    Observaciones) tienen **una columna por ítem** ("Antecedente 1", "Antecedente 2"…)
    bajo un encabezado combinado ("Antecedentes Iniciales"). Cada grupo tiene tantas
    columnas como el acta con más ítems; se amplía solo al guardar.
  - "Fecha", horas y "Fecha de registro" son fechas/horas reales de Excel (hora de Perú).
  - "Archivo PDF" es un enlace al PDF del acta.
- Hoja **Artículos**: una fila por artículo empleado, enlazada por "N° de Acta".
- No se permite guardar dos actas con el mismo N.°.
- La estructura de columnas está en `acta_app/storage/esquema.py`.

> En Streamlit Community Cloud el disco no es permanente: descarga "Excel + PDFs (ZIP)"
> desde "Base de datos de actas". La persistencia real llegará con SharePoint.

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
