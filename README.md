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
│   ├── actas_maestro.xlsx     #   Excel maestro, una fila por acta   (paso 4)
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
    └── storage/               # Guardado en el Excel maestro          (paso 4)
tests/                         # Pruebas de validación, fila de Excel y PDF (pytest)
```

El formulario (`ui/`) solo produce un objeto `Acta`; la validación, el PDF y el Excel trabajan
sobre ese objeto sin depender de Streamlit.

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
