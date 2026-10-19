# SistemaTriajeExperto

Sistema experto de triaje médico con API FastAPI, motor de reglas, lógica difusa, base de conocimiento editable e interfaz web. Incluye soporte para protocolos ESI, MTS, CTAS y ATS, y persistencia en MySQL.

## Instalación local

1. Instalar Python 3.12 y MySQL (por ejemplo, con XAMPP).
2. Instalar las dependencias:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Crear la base de datos `triaje_sistema`, copiar `.env.example` a `.env` y ajustar `DATABASE_URL` con las credenciales del entorno. Las variables del sistema tienen prioridad sobre `.env`.
4. Inicializar las tablas y ejecutar la API:

   ```powershell
   python init_db.py
   python -m uvicorn main:app --host 127.0.0.1 --port 8000
   ```

5. Abrir http://localhost:8000 para usar la interfaz y http://localhost:8000/docs para consultar la documentación de la API. Con Apache/XAMPP también se puede acceder mediante el panel `index.php`.

Los scripts `start.php` y `stop.php` facilitan el arranque y parada en Windows; revisar la ruta local de Python en `start.php` antes de utilizarlos.

## Contenido

- `triage_engine.py`: motor de reglas.
- `fuzzy_engine.py`: evaluación de riesgo mediante lógica difusa.
- `knowledge_base.py` y `BASE_CONOCIMIENTO.txt`: conocimiento del sistema.
- `clinical_support.py`: soporte clínico.
- `main.py`: API y acceso a datos.
- `test_triaje.py`: comprobaciones del motor de triaje.

Se excluyen cachés, archivos de entorno, bases de datos locales y el proyecto independiente `control-acceso`.

## Pruebas

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
node --test tests/frontend.test.cjs
```

Las pruebas de integración utilizan SQLite en memoria y no leen ni modifican los pacientes de MySQL. Cubren el guardado completo, la reversión ante errores, los identificadores, los duplicados, los filtros y el monitoreo. Las pruebas de interfaz comprueban el historial y el tratamiento seguro de texto.

## Comportamiento de la API

- Una evaluación se confirma en una sola transacción, incluyendo paciente, signos vitales, alertas y diagnósticos.
- Los identificadores se recortan y deben contener entre 1 y 50 caracteres.
- Los duplicados devuelven HTTP 409; los fallos de persistencia devuelven HTTP 503 sin exponer detalles internos.
- `/health` devuelve HTTP 503 cuando la base de datos no responde.
- La búsqueda de pacientes respeta `skip` y `limit`; las evaluaciones permiten combinar `paciente_id` y `nivel`.

## Alcance actual

La aplicación está preparada para desarrollo local. Aún no incorpora autenticación ni control de acceso a historias clínicas. La corrección de software y las pruebas de regresión no constituyen una validación clínica de las reglas, puntuaciones, traducciones o equivalencias entre protocolos.
