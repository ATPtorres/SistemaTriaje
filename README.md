# SistemaTriajeExperto

Prototipo de sistema experto de triaje con API FastAPI, reglas editables, encadenamiento hacia adelante, explicaciones trazables, lógica difusa auxiliar e interfaz web. Persiste en MySQL. Emite prioridades locales; ESI, MTS, CTAS y ATS oficiales permanecen pendientes de implementación y validación clínica.

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

- `triage_engine.py`: fachada del motor único; clasificación y explicación de la misma ejecución.
- `fuzzy_engine.py`: evaluación de riesgo mediante lógica difusa.
- `knowledge_base.py`: carga validada, inferencia y procedencia de hechos.
- `knowledge/triage_rules.json`: fuente editable y versionada de las reglas locales.
- `BASE_CONOCIMIENTO.txt`: guía de la base de conocimiento, sin duplicar reglas.
- `clinical_validation.py`: comparación con etiquetas de referencia; no certifica seguridad clínica.
- `clinical_support.py`: soporte clínico.
- `main.py`: API y acceso a datos.
- `test_triaje.py`: comprobaciones del motor de triaje.

Se excluyen cachés, archivos de entorno, bases de datos locales y el proyecto independiente `control-acceso`.

## Pruebas

```powershell
python -m pip install -r requirements-lock.txt
python -m pytest -q
node --test tests/frontend.test.cjs
```

Las pruebas de integración utilizan SQLite en memoria y no leen ni modifican los pacientes de MySQL. Cubren el guardado completo, la reversión ante errores, los identificadores, los duplicados, los filtros y el monitoreo. Las pruebas de interfaz comprueban el historial y el tratamiento seguro de texto.

## Comportamiento de la API

- Una evaluación se confirma en una sola transacción, incluyendo paciente, signos vitales, alertas y diagnósticos.
- Los identificadores se recortan y deben contener entre 1 y 50 caracteres.
- Los duplicados devuelven HTTP 409; los fallos de persistencia devuelven HTTP 503 sin exponer detalles internos.
- `/health` devuelve HTTP 503 cuando la base de datos o el conocimiento no están disponibles.
- La búsqueda de pacientes respeta `skip` y `limit`; las evaluaciones permiten combinar `paciente_id` y `nivel`.

## Alcance actual

La aplicación está preparada para desarrollo local. La administración del conocimiento requiere sesión de administrador; la operación y consulta de pacientes todavía no tienen cuentas individuales ni permisos clínicos. La corrección de software y las pruebas de regresión no constituyen una validación clínica de las reglas, puntuaciones, traducciones o equivalencias entre protocolos.

## Motor experto y edición del conocimiento

Las observaciones validadas producen hechos derivados; estos activan otras reglas hasta alcanzar un punto fijo. Cada regla se activa una sola vez. Se selecciona la propuesta de mayor urgencia (menor número), independientemente de pesos heurísticos. Los valores de confianza son pesos no calibrados y no representan probabilidades clínicas.

El resultado y su explicación usan una sola ejecución. Cada evaluación guarda la traza completa, hechos y procedencia, reglas decisivas, versión, SHA-256 del JSON normalizado y snapshot íntegro del conocimiento. `/evaluaciones/{id}` devuelve esos datos para auditoría, incluso después de editar el archivo de reglas. Se registra además la versión del motor. No se modifican evaluaciones históricas ni se necesita migración de tablas. El snapshot reproduce la clasificación local con esa versión del motor; no incluye las configuraciones de los indicadores auxiliares.

Para cambiar reglas, editar `knowledge/triage_rules.json`, aumentar `version`, revisar en Git y ejecutar las pruebas. Se puede seleccionar otro archivo mediante `TRIAGE_KNOWLEDGE_PATH` (ruta absoluta recomendada). La API lo lee en cada nueva evaluación; una ejecución conserva su propia copia. Desplegar el archivo completo de forma atómica. Un archivo ausente o inválido impide clasificar; no hay fallback silencioso a reglas antiguas. No se ejecutan expresiones Python desde el JSON ni se permite editar reglas mediante endpoints sin autenticación.

`/knowledge-base` muestra las reglas realmente cargadas y su versión/hash. `/decision-tree` es un catálogo generado a partir de esas reglas, no un algoritmo oficial de triaje. La interfaz muestra la prioridad local, la recomendación y una explicación breve basada en las observaciones asociadas a las reglas decisivas de esa evaluación. Las reglas, los hechos, la traza y el snapshot se consultan en «Auditoría técnica». En el modo quechua, los textos clínicos se muestran en español e indican que su traducción requiere revisión profesional.

## Protocolos y evaluación de referencia

`/protocols` distingue el motor local de los protocolos oficiales no implementados. Las nuevas respuestas de ESI/MTS/CTAS/ATS devuelven nivel `null` y estado `no_implementado`. La clasificación local sigue en `nivel_prioridad` y en `soporte_clinico.protocolos.local.nivel`. Los campos históricos oficiales se conservan sin reinterpretarlos.

Los indicadores difuso/multifactorial y los patrones diagnósticos son auxiliares no validados y no modifican el nivel. El campo heredado `probabilidad` expresa un peso heurístico, no una probabilidad médica calibrada.

```bash
python clinical_validation.py --cases tests/fixtures/triage_regression.json --output /tmp/informe-triaje.json
```

Los 62 casos incluidos son sintéticos y prueban conservación del comportamiento anterior, con sus limitaciones. El comando informa concordancia, subtriaje, sobretriaje y sensibilidad por nivel; rechaza conjuntos vacíos o mal formados. Ver [VALIDACION_CLINICA.md](VALIDACION_CLINICA.md) para los datos y la revisión externa que faltan. La validación clínica permanece pendiente, independientemente del resultado de las pruebas de software.

## Síntomas adicionales y acceso controlado

Abrir `/conocimiento`. El operador puede consultar el catálogo. Para crear, probar, publicar o desactivar ampliaciones se requiere una sesión de administrador, además del acceso local y la verificación de origen. Configurar una vez con `python setup_local_access.py`; las credenciales se escriben en `acceso-local.txt` y el hash en `.env`, ambos excluidos de Git. La contraseña se deriva con PBKDF2; la cookie es HttpOnly y SameSite Strict, expira en ocho horas y queda invalidada si cambia el hash. El acceso a pacientes sigue siendo local y no tiene usuarios individuales.

Las nuevas ampliaciones se guardan como borradores. «Probar borrador» ejecuta tres casos sintéticos (no evaluado, ausente y presente) sin guardar pacientes. El administrador puede publicar la regla después de revisarla. Se registran autor, estado y responsable/fecha de publicación en `revisiones_ampliaciones`. El ensayo no constituye aprobación clínica. Los síntomas activos existentes se conservan como publicados; no se alteran evaluaciones históricas.

El servidor solo genera la regla «síntoma presente → proponer prioridad 2, 3 o 4». No admite edición de reglas base, umbrales, efectos arbitrarios, colores o recomendaciones. La prioridad final sigue siendo la más urgente. El JSON original nunca se escribe desde la interfaz. Los snapshots incluyen reglas base y publicadas, sus IDs y hash.

Todos los síntomas, originales y adicionales, admiten presente/ausente/no evaluado. Un valor omitido o `null` no produce un hecho de ausencia. Los clientes anteriores que envían booleanos explícitos siguen siendo compatibles. En los 62 casos históricos se hicieron explícitos los `false` que el modelo anterior aplicaba por defecto: se conservaron sus etiquetas y significado original, no se introdujo adjudicación clínica.

«Evaluar Triaje» simula sin persistir. «Guardar» registra la evaluación. Cada intento de guardado desde la interfaz lleva un `id_solicitud` UUID; el reintento con los mismos datos devuelve el resultado original. Reutilizar el ID con datos distintos devuelve 409. La clave y respuesta se guardan en la misma transacción que la evaluación, incluyendo protección frente a solicitudes concurrentes. Un guardado nuevo tras una respuesta exitosa genera otra clave.

El indicador difuso devuelve `null` y un motivo cuando faltan entradas, están fuera de sus rangos o no hay área de inferencia. No se inventa un puntaje intermedio ni se modifica la prioridad principal. La defuzzificación agrupa reglas con el mismo consecuente. La validación estructural rechaza cadenas derivadas sin punto de entrada; no demuestra corrección clínica de las reglas.

## Esquema, fechas y verificación reproducible

`migrations.py` registra la actualización aditiva `4.2.0-additive`. Al iniciar se crean las tablas nuevas sin eliminar tablas ni modificar registros de pacientes. No hay downgrade automático. Las futuras modificaciones de columnas requieren una nueva migración explícita, no solo cambiar el modelo.

Las fechas se almacenan en UTC. Las estadísticas calculan los límites del día en `TRIAGE_TIMEZONE` (por defecto `America/La_Paz`) y consultan intervalos UTC indexables. La tendencia devuelve días consecutivos, incluyendo los días sin evaluaciones.

`requirements-lock.txt` fija el entorno Python verificado. El workflow `.github/workflows/tests.yml` ejecuta Python, interfaz y la integración de base de datos. Para ejecutar las mismas pruebas de API sobre MySQL, usar `TEST_MYSQL_URL` apuntando exclusivamente a una base temporal cuyo nombre empiece por `triaje_test_`; la prueba limpia sus tablas. Nunca utilizar la base de pacientes para pruebas. El entorno local de pruebas estándar sigue usando SQLite aislado.

Para comparar las prioridades del conocimiento combinado con casos de referencia:

```powershell
python clinical_validation.py --cases tests/fixtures/triage_regression.json --include-extensions
```

También se puede pasar `--knowledge` con un snapshot combinado exportado para reproducir exactamente su versión. La validación clínica permanece pendiente.
