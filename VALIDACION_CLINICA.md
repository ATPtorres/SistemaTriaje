# Estado: validación clínica pendiente

Este repositorio permite probar software y comparar prioridades con etiquetas de referencia. No acredita seguridad clínica, validez diagnóstica ni equivalencia con protocolos oficiales. Las reglas actuales conservan el comportamiento del motor local previo; esa conservación no demuestra que el comportamiento sea médicamente correcto.

## Evidencia disponible

- `tests/fixtures/triage_regression.json`: 62 casos **sintéticos**, con valores de frontera, síntomas y combinaciones. Sus etiquetas proceden del motor local en `0a81337`, no de adjudicación profesional.
- Pruebas de encadenamiento de varios pasos, conflictos entre urgencia y pesos, edición de reglas, reconstrucción desde snapshot, entradas inválidas, persistencia e interfaz.
- `clinical_validation.py`: genera una matriz de confusión (filas: referencia; columnas: predicción), concordancia exacta, subtriaje (nivel local numéricamente mayor que la referencia), sobretriaje y sensibilidad por nivel. Un nivel sin casos tiene sensibilidad `null`, nunca un aprobado implícito.

Un resultado perfecto con casos sintéticos solo indica regresión de software. No se fijan criterios de aceptación médica ni se cambia automáticamente el estado de validación con esas métricas.

## Datos necesarios para una revisión clínica

1. Profesionales responsables y población/ámbito de uso: adultos, pediatría, servicio, país y contexto asistencial.
2. Edición y documentación oficial autorizada de cada protocolo que se desee implementar, con revisión de sus requisitos de entrada. No basta convertir números entre escalas.
3. Casos desidentificados, representativos y separados de los usados para ajustar reglas, con prioridad adjudicada por profesionales y documentación del procedimiento de consenso. No subir historias clínicas identificables al repositorio.
4. Criterios de aceptación acordados previamente, incluyendo subtriaje, análisis por nivel y por subgrupos, incertidumbre estadística, casos faltantes y pruebas prospectivas si corresponden.
5. Revisión de traducciones clínicas, factores de riesgo, heurísticas diagnósticas y puntuaciones; revisión de privacidad, autenticación y operación antes de uso asistencial.
6. Registro firmado de hallazgos, cambios y versión/hash exactos evaluados. Este registro requiere revisión humana; no lo genera una prueba automatizada.

ESI, MTS, CTAS y ATS permanecen `no_implementado` en la API. Los antiguos campos de nivel oficial se conservan por compatibilidad, pero las nuevas evaluaciones guardan `null`; los valores históricos no se convierten en validación retrospectiva. El único nivel emitido es la prioridad del motor **local**.

## Formato del conjunto de referencia

```json
{
  "tipo": "adjudicado",
  "referencia": "Identificador y versión del conjunto desidentificado",
  "revisor": "Responsable de la adjudicación",
  "casos": [
    {
      "paciente": {
        "id_paciente": "CASO-ANONIMO-001",
        "edad": 35,
        "nivel_conciencia": "Alerta",
        "signos_vitales": {
          "frecuencia_cardiaca": 75,
          "presion_sistolica": 120,
          "presion_diastolica": 80,
          "temperatura": 36.5,
          "saturacion_oxigeno": 98
        }
      },
      "nivel_referencia": 5
    }
  ]
}
```

El ejemplo solo muestra el formato; no constituye un caso adjudicado real. El tipo `adjudicado` exige indicar revisor, pero el programa no puede verificar la autenticidad de esa adjudicación. El informe conserva `validacion_clinica: pendiente` en todos los casos.

```bash
python clinical_validation.py --cases /ruta/datos-desidentificados.json --output /ruta/informe.json
```

El informe solo incluye métricas agregadas, versión y SHA-256 del conocimiento. Los nombres de referencia/revisor son metadatos aportados por quien ejecuta la comparación; no deben contener datos de pacientes. No se imprimen casos ni identificadores en los informes o errores del comando.
