# domain

**Responsabilidad:** entidades, value objects y reglas clínicas DETERMINISTAS (signos de alarma, clasificación de urgencia, rutas de atención).

**Puede importar:** solo la librería estándar de Python.
**NO puede importar:** application, adapters, bootstrap, FastAPI, SDKs de LLM, ORM, HTTP.

Toda regla clínica referencia su ID (RN-xx) y tiene pruebas en tests/unit.
