"""
main.py - API Backend del Sistema Experto de Triaje
====================================================
Sistema Experto completo con:
- Motor de reglas clasico (forward chaining)
- Logica difusa (Mamdani FIS)
- Base de conocimiento editable
- Sistema de explicaciones (WHY/HOW/TRACE)
- Soporte clinico: diagnosticos diferenciales
- Multiples protocolos: ESI, MTS, CTAS, ATS
- Base de datos MySQL (XAMPP)

Ejecucion:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload

Documentacion Swagger:
    http://localhost:8000/docs
"""

import uuid
import time
import json
from pathlib import Path
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from models import DatosPaciente, ResultadoTriaje
from schemas import PacienteCreate
from triage_engine import evaluar_triaje
from fuzzy_engine import calcular_score_riesgo_difuso
from knowledge_base import BaseConocimiento
from clinical_support import obtener_soporte_clinico_completo
from i18n import traducir_resultado

# Database
from database import get_db, init_db
from models_db import (
    Paciente, EvaluacionTriaje, SignosVitalesHistorial,
    AlertaGenerada, DiagnosticoSugerido
)
import crud

STATIC_DIR = Path(__file__).parent / "static"


# =============================================================================
# CONFIGURACION DE LA APLICACION
# =============================================================================

app = FastAPI(
    title="Sistema Experto de Triaje Medico",
    description=(
        "Sistema Experto completo con MySQL para clasificacion automatizada de pacientes "
        "en urgencias. Integra: motor de reglas, logica difusa, base de conocimiento, "
        "sistema de explicaciones y soporte clinico con multiples protocolos (ESI, MTS, CTAS, ATS)."
    ),
    version="3.0.0",
    contact={"name": "Equipo de Desarrollo", "email": "dev@triaje-sistema.com"}
)


# =============================================================================
# EVENTOS DE ARRANQUE
# =============================================================================

@app.on_event("startup")
def startup_event():
    """Inicializa la base de datos al arrancar el servidor."""
    init_db()
    print("Base de datos inicializada correctamente")


# =============================================================================
# ENDPOINTS DE TRIAJE (principal)
# =============================================================================

@app.post(
    "/triaje",
    response_model=ResultadoTriaje,
    summary="Evaluar triaje de paciente (Sistema Experto + MySQL)",
    tags=["Triaje"],
    responses={200: {"model": ResultadoTriaje}, 422: {"description": "Error de validacion"}, 500: {"description": "Error interno"}}
)
async def clasificar_paciente(paciente: DatosPaciente, db: Session = Depends(get_db)):
    """
    Endpoint principal del Sistema Experto de Triaje.
    
    Pipeline de evaluacion:
    1. Motor de reglas clasico (forward chaining) -> Nivel ESI
    2. Motor de logica difusa (Mamdani FIS) -> Score de riesgo
    3. Base de conocimiento -> Explicaciones WHY/HOW/TRACE
    4. Soporte clinico -> Diagnosticos diferenciales + Protocolos
    5. Guardar todo en MySQL
    """
    inicio = time.time()

    try:
        # Paso 1: Motor de reglas clasico
        resultado = evaluar_triaje(paciente)

        # Paso 2: Logica difusa
        score_difuso, meta_difuso = calcular_score_riesgo_difuso(
            paciente.signos_vitales.frecuencia_cardiaca,
            paciente.signos_vitales.saturacion_oxigeno,
            paciente.signos_vitales.presion_sistolica,
            paciente.signos_vitales.temperatura,
            paciente.edad
        )

        # Paso 3: Base de conocimiento y explicaciones
        kb = BaseConocimiento()
        kb.establecer_hechos(paciente.model_dump())
        nivel_kb, traza_kb, explicacion_kb = kb.forward_chaining()

        # Paso 4: Soporte clinico
        datos_paciente = paciente.model_dump()
        soporte = obtener_soporte_clinico_completo(datos_paciente, resultado.nivel_prioridad)
        score_risk = soporte.get("score_riesgo", {})

        # Paso 5: Guardar en MySQL
        id_eval = f"EVAL-{uuid.uuid4().hex[:12].upper()}"
        duracion_ms = int((time.time() - inicio) * 1000)

        # Buscar o crear paciente
        db_paciente = crud.obtener_paciente_por_externo(db, paciente.id_paciente)
        if not db_paciente:
            db_paciente = crud.crear_paciente(db, {
                "id_externo": paciente.id_paciente,
                "edad": paciente.edad,
                "peso_kg": paciente.peso_kg
            })

        # Guardar evaluacion
        eval_data = {
            "id_evaluacion": id_eval,
            "nivel_prioridad": resultado.nivel_prioridad,
            "color": resultado.color,
            "motivo_clinico": resultado.motivo_clinico,
            "recomendacion": resultado.recomendacion,
            "score_riesgo_difuso": round(score_difuso, 1),
            "score_riesgo_multifactor": score_risk.get("score"),
            "nivel_riesgo": score_risk.get("nivel_riesgo"),
            "metodo_inferencia": "Forward Chaining + Fuzzy Logic (Mamdani)",
            "reglas_evaluadas": len(traza_kb),
            "reglas_activadas": len([p for p in traza_kb if p["activa"]]),
            "traza_inferencia": traza_kb[:20],
            "explicaciones": explicacion_kb,
            "nivel_esi": soporte.get("protocolos", {}).get("esi", {}).get("nivel"),
            "nivel_mts": soporte.get("protocolos", {}).get("mts", {}).get("nivel_mts"),
            "nivel_ctas": soporte.get("protocolos", {}).get("ctas", {}).get("nivel_ctas"),
            "nivel_ats": soporte.get("protocolos", {}).get("ats", {}).get("nivel_ats"),
            "datos_entrada": datos_paciente,
            "duracion_ms": duracion_ms,
        }
        db_eval = crud.crear_evaluacion(db, eval_data, db_paciente.id, id_eval)

        # Guardar signos vitales
        crud.crear_signos_vitales(db, {
            "frecuencia_cardiaca": paciente.signos_vitales.frecuencia_cardiaca,
            "presion_sistolica": paciente.signos_vitales.presion_sistolica,
            "presion_diastolica": paciente.signos_vitales.presion_diastolica,
            "temperatura": paciente.signos_vitales.temperatura,
            "saturacion_oxigeno": paciente.signos_vitales.saturacion_oxigeno,
            "nivel_conciencia": paciente.nivel_conciencia.value,
        }, db_eval.id)

        # Guardar alertas
        if resultado.signos_alerta:
            alertas_data = []
            for alerta in resultado.signos_alerta:
                alertas_data.append({
                    "tipo_alerta": "Critica" if resultado.nivel_prioridad <= 2 else "Alta",
                    "descripcion": alerta,
                    "nivel_gravedad": resultado.nivel_prioridad,
                })
            crud.crear_alertas_batch(db, alertas_data, db_eval.id)

        # Guardar diagnosticos
        if soporte.get("diagnosticos"):
            diag_mapped = []
            for d in soporte["diagnosticos"]:
                diag_mapped.append({
                    "codigo_diagnostico": d.get("codigo", "N/A"),
                    "nombre_diagnostico": d.get("nombre", ""),
                    "especialidad": d.get("especialidad"),
                    "probabilidad": d.get("probabilidad", 0),
                    "evidencia": d.get("evidencia"),
                    "estudios_sugeridos": d.get("estudios_sugeridos"),
                    "conducta": d.get("conducta"),
                })
            crud.crear_diagnosticos_batch(db, diag_mapped, db_eval.id)

        # Enriquecer resultado
        resultado.score_riesgo_difuso = round(score_difuso, 1)
        resultado.metadata_motor = {
            "id_evaluacion": id_eval,
            "metodo_inferencia": "Forward Chaining + Fuzzy Logic (Mamdani)",
            "reglas_evaluadas": len(traza_kb),
            "reglas_activadas": len([p for p in traza_kb if p["activa"]]),
            "explicaciones": explicacion_kb,
            "traza_completa": traza_kb,
            "logica_difusa": {
                "score": round(score_difuso, 1),
                "num_reglas_activas": meta_difuso.get("num_reglas_activas", 0),
            },
            "guardado_en_bd": True,
            "duracion_ms": duracion_ms,
        }
        resultado.soporte_clinico = soporte

        # Traducir respuesta si el cliente pidio quechua
        idioma = getattr(paciente, "idioma", "es")
        resultado = traducir_resultado(resultado, idioma)

        return resultado

    except ValidationError as e:
        raise HTTPException(status_code=422, detail=f"Error de validacion: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


# =============================================================================
# ENDPOINTS DE PACIENTES
# =============================================================================

@app.post("/pacientes", tags=["Pacientes"], summary="Crear paciente")
async def crear_paciente_endpoint(datos: PacienteCreate, db: Session = Depends(get_db)):
    """Crea un nuevo paciente en la base de datos."""
    try:
        paciente = crud.crear_paciente(db, datos.model_dump(exclude_unset=True))
        return {"mensaje": "Paciente creado", "id": paciente.id, "id_externo": paciente.id_externo}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/pacientes", tags=["Pacientes"], summary="Listar pacientes")
async def listar_pacientes_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    buscar: str = Query(None, description="Buscar por nombre o ID"),
    db: Session = Depends(get_db)
):
    """Lista todos los pacientes con paginacion y busqueda."""
    if buscar:
        pacientes = crud.buscar_pacientes(db, buscar)
    else:
        pacientes = crud.listar_pacientes(db, skip, limit)
    return {"total": len(pacientes), "pacientes": [
        {"id": p.id, "id_externo": p.id_externo, "nombre": p.nombre,
         "edad": p.edad, "sexo": p.sexo}
        for p in pacientes
    ]}


@app.get("/pacientes/{paciente_id}", tags=["Pacientes"], summary="Obtener paciente")
async def obtener_paciente_endpoint(paciente_id: int, db: Session = Depends(get_db)):
    """Obtiene un paciente por su ID."""
    paciente = crud.obtener_paciente_por_id(db, paciente_id)
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    return {"id": paciente.id, "id_externo": paciente.id_externo, "nombre": paciente.nombre,
            "edad": paciente.edad, "sexo": paciente.sexo, "created_at": str(paciente.created_at)}


# =============================================================================
# ENDPOINTS DE EVALUACIONES
# =============================================================================

@app.get("/evaluaciones", tags=["Evaluaciones"], summary="Listar evaluaciones")
async def listar_evaluaciones_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    paciente_id: int = Query(None),
    nivel: int = Query(None, ge=1, le=5),
    db: Session = Depends(get_db)
):
    """Lista evaluaciones con filtros opcionales."""
    if nivel:
        evals = crud.obtener_evaluaciones_por_nivel(db, nivel)
        evals = evals[skip:skip + limit]
    else:
        evals = crud.listar_evaluaciones(db, skip, limit, paciente_id)

    return {"total": len(evals), "evaluaciones": [
        {
            "id": e.id, "id_evaluacion": e.id_evaluacion,
            "paciente_id": e.paciente_id, "nivel": e.nivel_prioridad,
            "color": e.color, "score_difuso": e.score_riesgo_difuso,
            "fecha": e.fecha_evaluacion.isoformat() if e.fecha_evaluacion else None,
            "duracion_ms": e.duracion_ms
        }
        for e in evals
    ]}


@app.get("/evaluaciones/{evaluacion_id}", tags=["Evaluaciones"], summary="Detalle de evaluacion")
async def detalle_evaluacion_endpoint(evaluacion_id: str, db: Session = Depends(get_db)):
    """Obtiene el detalle completo de una evaluacion (por ID interno o UUID)."""
    if evaluacion_id.isdigit():
        eval_db = crud.obtener_evaluacion(db, int(evaluacion_id))
    else:
        eval_db = crud.obtener_evaluacion_por_uuid(db, evaluacion_id)
    if not eval_db:
        raise HTTPException(status_code=404, detail="Evaluacion no encontrada")

    sv = crud.obtener_historial_signos(db, eval_db.paciente_id, 1)
    alertas = crud.obtener_alertas_evaluacion(db, eval_db.id)
    diagnosticos = crud.obtener_diagnosticos_evaluacion(db, eval_db.id)

    return {
        "evaluacion": {
            "id": eval_db.id, "id_evaluacion": eval_db.id_evaluacion,
            "nivel": eval_db.nivel_prioridad, "color": eval_db.color,
            "motivo": eval_db.motivo_clinico, "recomendacion": eval_db.recomendacion,
            "score_difuso": eval_db.score_riesgo_difuso,
            "score_multifactor": eval_db.score_riesgo_multifactor,
            "nivel_riesgo": eval_db.nivel_riesgo,
            "metodo": eval_db.metodo_inferencia,
            "reglas_evaluadas": eval_db.reglas_evaluadas,
            "reglas_activadas": eval_db.reglas_activadas,
            "fecha": eval_db.fecha_evaluacion.isoformat() if eval_db.fecha_evaluacion else None,
            "duracion_ms": eval_db.duracion_ms,
            "protocolos": {
                "esi": eval_db.nivel_esi,
                "mts": eval_db.nivel_mts,
                "ctas": eval_db.nivel_ctas,
                "ats": eval_db.nivel_ats,
            }
        },
        "signos_vitales": [
            {
                "fc": s.frecuencia_cardiaca, "pas": s.presion_sistolica,
                "pad": s.presion_diastolica, "temp": s.temperatura,
                "spo2": s.saturacion_oxigeno, "conciencia": s.nivel_conciencia,
                "registrado": s.registrado_en.isoformat() if s.registrado_en else None
            }
            for s in sv
        ],
        "alertas": [
            {"tipo": a.tipo_alerta, "descripcion": a.descripcion,
             "nivel": a.nivel_gravedad}
            for a in alertas
        ],
        "diagnosticos": [
            {"nombre": d.nombre_diagnostico, "probabilidad": d.probabilidad,
             "especialidad": d.especialidad, "conducta": d.conducta}
            for d in diagnosticos
        ]
    }


# =============================================================================
# ENDPOINTS DE BASE DE CONOCIMIENTO
# =============================================================================

@app.get("/knowledge-base", summary="Consultar base de conocimiento", tags=["Conocimiento"])
async def consultar_base_conocimiento():
    """Retorna todas las reglas de la base de conocimiento del sistema experto."""
    kb = BaseConocimiento()
    return {
        "total_reglas": len(kb.reglas),
        "reglas": kb.listar_reglas_activas(),
        "arbol_decision": "Disponible en /decision-tree"
    }


@app.get("/decision-tree", summary="Arbol de decision visual", tags=["Conocimiento"])
async def arbol_decision():
    """Retorna el arbol de decision serializado para visualizacion."""
    kb = BaseConocimiento()

    def serializar_nodo(nodo):
        return {
            "id": nodo.id,
            "tipo": nodo.tipo,
            "texto": nodo.texto,
            "nivel": nodo.valor,
            "color": nodo.color,
            "hijos": [serializar_nodo(h) for h in nodo.hijos]
        }

    return serializar_nodo(kb.arbol) if kb.arbol else {"error": "Arbol no disponible"}


@app.get("/protocols", summary="Protocolos de triaje disponibles", tags=["Conocimiento"])
async def listar_protocolos():
    """Lista los protocolos de triaje implementados en el sistema."""
    return {
        "protocolos": [
            {"id": "ESI", "nombre": "Emergency Severity Index", "version": "v4", "organizacion": "ACEP"},
            {"id": "MTS", "nombre": "Manchester Triage System", "version": "2014", "organizacion": "Manchester Triage Group"},
            {"id": "CTAS", "nombre": "Canadian Triage and Acuity Scale", "version": "v5", "organizacion": "CAEP"},
            {"id": "ATS", "nombre": "Australasian Triage Scale", "version": "2006", "organizacion": "ACEM"},
        ]
    }


@app.get("/fuzzy-membership", summary="Funciones de pertenencia difusas", tags=["Conocimiento"])
async def funciones_pertenencia():
    """Retorna las funciones de pertenencia de las variables linguisticas difusas."""
    from fuzzy_engine import crear_sistema_difuso_triaje
    motor = crear_sistema_difuso_triaje()

    resultado = {}
    for nombre, var in motor.variables_entrada.items():
        resultado[nombre] = {
            "unit": var.unit,
            "rango": var.rango,
            "conjuntos": {}
        }
        for conj_name, conf in var.conjuntos.items():
            resultado[nombre]["conjuntos"][conj_name] = {
                "tipo": conf["tipo"],
                "params": conf["params"]
            }

    return resultado


# =============================================================================
# ENDPOINTS DE ANALYTICS (MySQL)
# =============================================================================

@app.get("/statistics", summary="Estadisticas del sistema (MySQL)", tags=["Analytics"])
async def estadisticas_sistema(db: Session = Depends(get_db)):
    """Dashboard de estadisticas en tiempo real desde MySQL."""
    return crud.obtener_dashboard(db)


@app.get("/estadisticas/diaria", tags=["Analytics"], summary="Estadistica del dia")
async def estadistica_diaria(db: Session = Depends(get_db)):
    """Estadisticas pre-calculadas del dia actual."""
    stats = crud.obtener_o_crear_estadistica_hoy(db)
    return {
        "fecha": stats.fecha,
        "total_evaluaciones": stats.total_evaluaciones,
        "por_nivel": {
            "nivel_1": stats.nivel_1, "nivel_2": stats.nivel_2,
            "nivel_3": stats.nivel_3, "nivel_4": stats.nivel_4,
            "nivel_5": stats.nivel_5
        },
        "tiempo_promedio_ms": stats.tiempo_promedio_evaluacion_ms,
        "diagnostico_mas_comun": stats.diagnostico_mas_comun,
    }


@app.get("/estadisticas/tendencia", tags=["Analytics"], summary="Tendencia de evaluaciones")
async def tendencia_evaluaciones(dias: int = Query(7, ge=1, le=30), db: Session = Depends(get_db)):
    """Tendencia de evaluaciones por nivel en los ultimos N dias."""
    from sqlalchemy import func
    from models_db import EstadisticaDiaria

    stats = db.query(EstadisticaDiaria).order_by(
        EstadisticaDiaria.fecha.desc()
    ).limit(dias).all()

    return {
        "periodo": f"Ultimos {dias} dias",
        "datos": [
            {
                "fecha": s.fecha,
                "total": s.total_evaluaciones,
                "nivel_1": s.nivel_1, "nivel_2": s.nivel_2,
                "nivel_3": s.nivel_3, "nivel_4": s.nivel_4,
                "nivel_5": s.nivel_5,
            }
            for s in reversed(stats)
        ]
    }


@app.get("/estadisticas/diagnosticos-frecuentes", tags=["Analytics"])
async def diagnosticos_frecuentes(db: Session = Depends(get_db)):
    """Top 10 diagnosticos mas frecuentes en el sistema."""
    diag = crud.diagnosticos_mas_comunes(db, 10)
    return {"diagnosticos": [{"nombre": d[0], "total": d[1]} for d in diag]}


@app.get("/health", summary="Health check", tags=["Monitoreo"])
async def health_check(db: Session = Depends(get_db)):
    """Verifica que el sistema y la base de datos esten operativos."""
    from sqlalchemy import text
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except:
        db_status = "disconnected"

    return {
        "status": "healthy",
        "service": "sistema-triaje-experto",
        "version": "3.0.0",
        "database": db_status,
        "modulos": ["triage_engine", "fuzzy_engine", "knowledge_base", "clinical_support"],
        "protocolos": ["ESI", "MTS", "CTAS", "ATS"]
    }


@app.get("/", response_class=HTMLResponse, summary="Interfaz web", tags=["UI"])
async def root():
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


# =============================================================================
# PUNTO DE ENTRADA
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
