"""
crud.py - Operaciones CRUD sobre la Base de Datos
==================================================
Create, Read, Update, Delete para todas las entidades del sistema.

Patron Repository: encapsula acceso a datos detras de una interfaz.
"""

from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from models_db import (
    Paciente, EvaluacionTriaje, SignosVitalesHistorial,
    AlertaGenerada, DiagnosticoSugerido, ReglaConocimiento,
    EstadisticaDiaria, SesionUsuario
)


# =============================================================================
# PACIENTES
# =============================================================================

def crear_paciente(db: Session, datos: dict) -> Paciente:
    """Crea un nuevo paciente en la base de datos."""
    db_paciente = Paciente(**datos)
    db.add(db_paciente)
    db.commit()
    db.refresh(db_paciente)
    return db_paciente


def obtener_paciente_por_id(db: Session, paciente_id: int) -> Paciente | None:
    """Obtiene un paciente por su ID interno."""
    return db.query(Paciente).filter(Paciente.id == paciente_id).first()


def obtener_paciente_por_externo(db: Session, id_externo: str) -> Paciente | None:
    """Obtiene un paciente por su ID externo del sistema hospitalario."""
    return db.query(Paciente).filter(Paciente.id_externo == id_externo).first()


def listar_pacientes(db: Session, skip: int = 0, limit: int = 100) -> list[Paciente]:
    """Lista todos los pacientes con paginacion."""
    return db.query(Paciente).offset(skip).limit(limit).all()


def buscar_pacientes(db: Session, termino: str) -> list[Paciente]:
    """Busca pacientes por nombre o ID externo."""
    return db.query(Paciente).filter(
        (Paciente.nombre.ilike(f"%{termino}%")) |
        (Paciente.id_externo.ilike(f"%{termino}%"))
    ).all()


def actualizar_paciente(db: Session, paciente_id: int, datos: dict) -> Paciente | None:
    """Actualiza los datos de un paciente."""
    db_paciente = db.query(Paciente).filter(Paciente.id == paciente_id).first()
    if db_paciente:
        for key, value in datos.items():
            if hasattr(db_paciente, key) and value is not None:
                setattr(db_paciente, key, value)
        db_paciente.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(db_paciente)
    return db_paciente


def eliminar_paciente(db: Session, paciente_id: int) -> bool:
    """Elimina un paciente y todas sus evaluaciones (cascade)."""
    db_paciente = db.query(Paciente).filter(Paciente.id == paciente_id).first()
    if db_paciente:
        db.delete(db_paciente)
        db.commit()
        return True
    return False


# =============================================================================
# EVALUACIONES DE TRIAJE
# =============================================================================

def crear_evaluacion(db: Session, datos: dict, paciente_id: int,
                     id_evaluacion: str) -> EvaluacionTriaje:
    """Crea una nueva evaluacion de triaje."""
    datos["paciente_id"] = paciente_id
    datos["id_evaluacion"] = id_evaluacion
    db_eval = EvaluacionTriaje(**datos)
    db.add(db_eval)
    db.commit()
    db.refresh(db_eval)
    return db_eval


def obtener_evaluacion(db: Session, evaluacion_id: int) -> EvaluacionTriaje | None:
    """Obtiene una evaluacion por su ID."""
    return db.query(EvaluacionTriaje).filter(
        EvaluacionTriaje.id == evaluacion_id
    ).first()


def obtener_evaluacion_por_uuid(db: Session, id_evaluacion: str) -> EvaluacionTriaje | None:
    """Obtiene una evaluacion por su UUID."""
    return db.query(EvaluacionTriaje).filter(
        EvaluacionTriaje.id_evaluacion == id_evaluacion
    ).first()


def listar_evaluaciones(db: Session, skip: int = 0, limit: int = 100,
                       paciente_id: int | None = None) -> list[EvaluacionTriaje]:
    """Lista evaluaciones con filtro opcional por paciente."""
    query = db.query(EvaluacionTriaje)
    if paciente_id:
        query = query.filter(EvaluacionTriaje.paciente_id == paciente_id)
    return query.order_by(desc(EvaluacionTriaje.fecha_evaluacion)).offset(skip).limit(limit).all()


def obtener_evaluaciones_por_nivel(db: Session, nivel: int) -> list[EvaluacionTriaje]:
    """Obtiene todas las evaluaciones de un nivel especifico."""
    return db.query(EvaluacionTriaje).filter(
        EvaluacionTriaje.nivel_prioridad == nivel
    ).order_by(desc(EvaluacionTriaje.fecha_evaluacion)).all()


def contar_evaluaciones_hoy(db: Session) -> int:
    """Cuenta las evaluaciones realizadas hoy."""
    from sqlalchemy import func as sa_func
    return db.query(EvaluacionTriaje).filter(
        func.date(EvaluacionTriaje.fecha_evaluacion) == sa_func.date(sa_func.now())
    ).count()


# =============================================================================
# SIGNOS VITALES
# =============================================================================

def crear_signos_vitales(db: Session, datos: dict, evaluacion_id: int) -> SignosVitalesHistorial:
    """Registra signos vitales para una evaluacion."""
    datos["evaluacion_id"] = evaluacion_id
    db_sv = SignosVitalesHistorial(**datos)
    db.add(db_sv)
    db.commit()
    db.refresh(db_sv)
    return db_sv


def obtener_historial_signos(db: Session, paciente_id: int, limit: int = 50) -> list:
    """Obtiene el historial de signos vitales de un paciente."""
    return db.query(SignosVitalesHistorial).join(
        EvaluacionTriaje
    ).filter(
        EvaluacionTriaje.paciente_id == paciente_id
    ).order_by(
        desc(SignosVitalesHistorial.registrado_en)
    ).limit(limit).all()


# =============================================================================
# ALERTAS
# =============================================================================

def crear_alerta(db: Session, datos: dict, evaluacion_id: int) -> AlertaGenerada:
    """Crea una alerta clinica."""
    datos["evaluacion_id"] = evaluacion_id
    db_alerta = AlertaGenerada(**datos)
    db.add(db_alerta)
    db.commit()
    db.refresh(db_alerta)
    return db_alerta


def crear_alertas_batch(db: Session, alertas: list[dict], evaluacion_id: int) -> list[AlertaGenerada]:
    """Crea multiples alertas en lote."""
    db_alertas = []
    for alerta in alertas:
        alerta["evaluacion_id"] = evaluacion_id
        db_alerta = AlertaGenerada(**alerta)
        db.add(db_alerta)
        db_alertas.append(db_alerta)
    db.commit()
    for a in db_alertas:
        db.refresh(a)
    return db_alertas


def obtener_alertas_evaluacion(db: Session, evaluacion_id: int) -> list[AlertaGenerada]:
    """Obtiene todas las alertas de una evaluacion."""
    return db.query(AlertaGenerada).filter(
        AlertaGenerada.evaluacion_id == evaluacion_id
    ).all()


# =============================================================================
# DIAGNOSTICOS
# =============================================================================

def crear_diagnosticos_batch(db: Session, diagnosticos: list[dict],
                            evaluacion_id: int) -> list[DiagnosticoSugerido]:
    """Crea multiples diagnosticos sugeridos."""
    db_diags = []
    for diag in diagnosticos:
        diag["evaluacion_id"] = evaluacion_id
        db_diag = DiagnosticoSugerido(**diag)
        db.add(db_diag)
        db_diags.append(db_diag)
    db.commit()
    for d in db_diags:
        db.refresh(d)
    return db_diags


def obtener_diagnosticos_evaluacion(db: Session, evaluacion_id: int) -> list[DiagnosticoSugerido]:
    """Obtiene los diagnosticos de una evaluacion."""
    return db.query(DiagnosticoSugerido).filter(
        DiagnosticoSugerido.evaluacion_id == evaluacion_id
    ).order_by(desc(DiagnosticoSugerido.probabilidad)).all()


def diagnosticos_mas_comunes(db: Session, limit: int = 10) -> list[dict]:
    """Obtiene los diagnosticos mas frecuentes."""
    return db.query(
        DiagnosticoSugerido.nombre_diagnostico,
        func.count(DiagnosticoSugerido.id).label("total")
    ).group_by(
        DiagnosticoSugerido.nombre_diagnostico
    ).order_by(
        desc("total")
    ).limit(limit).all()


# =============================================================================
# REGLAS DE CONOCIMIENTO
# =============================================================================

def crear_regla(db: Session, datos: dict) -> ReglaConocimiento:
    """Crea una nueva regla en la base de conocimiento."""
    db_regla = ReglaConocimiento(**datos)
    db.add(db_regla)
    db.commit()
    db.refresh(db_regla)
    return db_regla


def listar_reglas(db: Session, activas_only: bool = False) -> list[ReglaConocimiento]:
    """Lista todas las reglas de conocimiento."""
    query = db.query(ReglaConocimiento)
    if activas_only:
        query = query.filter(ReglaConocimiento.activa == True)
    return query.order_by(desc(ReglaConocimiento.prioridad)).all()


def actualizar_regla(db: Session, regla_id: int, datos: dict) -> ReglaConocimiento | None:
    """Actualiza una regla de conocimiento."""
    db_regla = db.query(ReglaConocimiento).filter(
        ReglaConocimiento.id == regla_id
    ).first()
    if db_regla:
        for key, value in datos.items():
            if hasattr(db_regla, key) and value is not None:
                setattr(db_regla, key, value)
        db_regla.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(db_regla)
    return db_regla


def eliminar_regla(db: Session, regla_id: int) -> bool:
    """Elimina una regla de conocimiento."""
    db_regla = db.query(ReglaConocimiento).filter(
        ReglaConocimiento.id == regla_id
    ).first()
    if db_regla:
        db.delete(db_regla)
        db.commit()
        return True
    return False


# =============================================================================
# ESTADISTICAS
# =============================================================================

def obtener_o_crear_estadistica_hoy(db: Session) -> EstadisticaDiaria:
    """Obtiene o crea el registro de estadistica del dia."""
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    stats = db.query(EstadisticaDiaria).filter(
        EstadisticaDiaria.fecha == hoy
    ).first()

    if not stats:
        stats = EstadisticaDiaria(fecha=hoy)
        db.add(stats)
        db.commit()
        db.refresh(stats)

    return stats


def actualizar_estadisticas(db: Session):
    """Recalcula las estadisticas del dia actual."""
    from sqlalchemy import func as sa_func
    stats = obtener_o_crear_estadistica_hoy(db)

    # Contar por nivel
    for nivel in range(1, 6):
        count = db.query(EvaluacionTriaje).filter(
            EvaluacionTriaje.nivel_prioridad == nivel,
            func.date(EvaluacionTriaje.fecha_evaluacion) == sa_func.date(sa_func.now())
        ).count()
        setattr(stats, f"nivel_{nivel}", count)

    # Total
    stats.total_evaluaciones = sum(
        getattr(stats, f"nivel_{i}") for i in range(1, 6)
    )

    # Tiempo promedio
    avg_time = db.query(func.avg(EvaluacionTriaje.duracion_ms)).filter(
        func.date(EvaluacionTriaje.fecha_evaluacion) == sa_func.date(sa_func.now())
    ).scalar()
    stats.tiempo_promedio_evaluacion_ms = int(avg_time) if avg_time else None

    # Diagnostico mas comun hoy
    top_diag = db.query(
        DiagnosticoSugerido.nombre_diagnostico,
        func.count(DiagnosticoSugerido.id)
    ).join(
        EvaluacionTriaje
    ).filter(
        func.date(EvaluacionTriaje.fecha_evaluacion) == sa_func.date(sa_func.now())
    ).group_by(
        DiagnosticoSugerido.nombre_diagnostico
    ).order_by(
        desc(func.count(DiagnosticoSugerido.id))
    ).first()

    stats.diagnostico_mas_comun = top_diag[0] if top_diag else None

    stats.calculado_en = datetime.now(timezone.utc)
    db.commit()
    db.refresh(stats)
    return stats


def obtener_dashboard(db: Session) -> dict:
    """Genera el dashboard completo de estadisticas."""
    stats = actualizar_estadisticas(db)

    # Total pacientes
    total_pacientes = db.query(func.count(Paciente.id)).scalar() or 0

    # Evaluaciones totales
    total_evaluaciones = db.query(func.count(EvaluacionTriaje.id)).scalar() or 0

    # Ultimas 10 evaluaciones
    ultimas = db.query(EvaluacionTriaje).order_by(
        desc(EvaluacionTriaje.fecha_evaluacion)
    ).limit(10).all()

    return {
        "total_pacientes": total_pacientes,
        "total_evaluaciones": total_evaluaciones,
        "evaluaciones_hoy": stats.total_evaluaciones,
        "distribucion_niveles": {
            "nivel_1": stats.nivel_1,
            "nivel_2": stats.nivel_2,
            "nivel_3": stats.nivel_3,
            "nivel_4": stats.nivel_4,
            "nivel_5": stats.nivel_5,
        },
        "tiempo_promedio_ms": stats.tiempo_promedio_evaluacion_ms,
        "diagnostico_mas_comun": stats.diagnostico_mas_comun,
        "ultimas_evaluaciones": [
            {
                "id": e.id,
                "nivel": e.nivel_prioridad,
                "color": e.color,
                "fecha": e.fecha_evaluacion.isoformat() if e.fecha_evaluacion else None,
            }
            for e in ultimas
        ]
    }
