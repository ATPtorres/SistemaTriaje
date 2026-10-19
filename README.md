# SistemaTriajeExperto

Sistema experto de triaje médico con API FastAPI, motor de reglas, lógica difusa, base de conocimiento editable e interfaz web. Incluye soporte para protocolos ESI, MTS, CTAS y ATS, y persistencia en MySQL.

## Instalación local

1. Instalar Python 3.12 y MySQL (por ejemplo, con XAMPP).
2. Instalar las dependencias:

   ```powershell
   python -m pip install -r requirements.txt
   python -m pip install sqlalchemy pymysql
   ```

3. Crear la base de datos `triaje_sistema` y ajustar la conexión en `database.py` para el entorno local.
4. Inicializar las tablas y ejecutar la API:

   ```powershell
   python init_db.py
   python -m uvicorn main:app --host 127.0.0.1 --port 8000
   ```

5. Abrir http://localhost:8000/docs para consultar la documentación de la API. La interfaz está en `static/index.html`; con Apache/XAMPP también se puede acceder mediante `index.php`.

Los scripts `start.php` y `stop.php` facilitan el arranque y parada en Windows; revisar la ruta local de Python en `start.php` antes de utilizarlos.

## Contenido

- `triage_engine.py`: motor de reglas.
- `fuzzy_engine.py`: evaluación de riesgo mediante lógica difusa.
- `knowledge_base.py` y `BASE_CONOCIMIENTO.txt`: conocimiento del sistema.
- `clinical_support.py`: soporte clínico.
- `main.py`: API y acceso a datos.
- `test_triaje.py`: comprobaciones del motor de triaje.

Se excluyen cachés, archivos de entorno, bases de datos locales y el proyecto independiente `control-acceso`.
