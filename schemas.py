"""
schemas.py - Esquemas Pydantic para Request/Response
=====================================================
Define los esquemas de validacion para la API REST.
Separacion de concern: entrada (create), salida (response), internos.
"""

from datetime import datetime
from pydantic import BaseModel, Field


# =============================================================================
# PACIENTES
# =============================================================================

class PacienteCreate(BaseModel):
    """Esquema de entrada para crear un paciente."""
    id_externo: str = Field(..., max_length=50, description="ID del paciente")
    nombre: str | None = Field(None, max_length=100)
    edad: int = Field(..., ge=0, le=150)
    sexo: str | None = Field(None, max_length=1, pattern="^[MFO]$")
    peso_kg: float | None = Field(None, ge=0, le=500)
    telefono: str | None = Field(None, max_length=20)
    direccion: str | None = None
    alergias: str | None = None
    medicamentos: str | None = None
    antecedentes: str | None = None


class PacienteResponse(BaseModel):
    """Esquema de salida para paciente."""
    id: int
    id_externo: str
    nombre: str | None
    edad: int
    sexo: str | None
    peso_kg: float | None
    telefono: str | None
    direccion: str | None
    alergias: str | None
    medicamentos: str | None
    antecedentes: str | None
    created_at: datetime | None
    updated_at: datetime | None

    class Config:
        from_attributes = True


# =============================================================================
# EVALUACIONES DE TRIAJE
# =============================================================================

class EvaluacionCreate(BaseModel):
    """Esquema de entrada para crear una evaluacion."""
    paciente_id: int = Field(..., description="ID del paciente en BD")
    nivel_prioridad: int = Field(..., ge=1, le=5)
    color: str = Field(..., max_length=20)
    motivo_clinico: str
    recomendacion: str
    score_riesgo_difuso: float | None = None
    score_riesgo_multifactor: float | None = None
    nivel_riesgo: str | None = None
    metodo_inferencia: str | None = None
    reglas_evaluadas: int | None = None
    reglas_activadas: int | None = None
    traza_inferencia: dict | None = None
    explicaciones: dict | None = None
    nivel_esi: int | None = None
    nivel_mts: int | None = None
    nivel_ctas: int | None = None
    nivel_ats: int | None = None
    datos_entrada: dict
    duracion_ms: int | None = None


class EvaluacionResponse(BaseModel):
    """Esquema de salida para evaluacion."""
    id: int
    paciente_id: int
    id_evaluacion: str
    nivel_prioridad: int
    color: str
    motivo_clinico: str
    recomendacion: str
    score_riesgo_difuso: float | None
    score_riesgo_multifactor: float | None
    nivel_riesgo: str | None
    metodo_inferencia: str | None
    reglas_evaluadas: int | None
    reglas_activadas: int | None
    nivel_esi: int | None
    nivel_mts: int | None
    nivel_ctas: int | None
    nivel_ats: int | None
    fecha_evaluacion: datetime | None
    duracion_ms: int | None

    class Config:
        from_attributes = True


# =============================================================================
# SIGNOS VITALES
# =============================================================================

class SignosVitalesResponse(BaseModel):
    """Esquema de salida para historial de signos vitales."""
    id: int
    evaluacion_id: int
    frecuencia_cardiaca: int
    presion_sistolica: int
    presion_diastolica: int
    temperatura: float
    saturacion_oxigeno: int
    nivel_conciencia: str
    registrado_en: datetime | None

    class Config:
        from_attributes = True


# =============================================================================
# ALERTAS
# =============================================================================

class AlertaResponse(BaseModel):
    """Esquema de salida para alertas."""
    id: int
    evaluacion_id: int
    tipo_alerta: str
    descripcion: str
    signo_vital: str | None
    valor_detectado: str | None
    umbral: str | None
    nivel_gravedad: int
    generada_en: datetime | None

    class Config:
        from_attributes = True


# =============================================================================
# DIAGNOSTICOS
# =============================================================================

class DiagnosticoResponse(BaseModel):
    """Esquema de salida para diagnosticos sugeridos."""
    id: int
    evaluacion_id: int
    codigo_diagnostico: str
    nombre_diagnostico: str
    especialidad: str | None
    probabilidad: float
    evidencia: list | None
    estudios_sugeridos: list | None
    conducta: str | None
    sugerido_en: datetime | None

    class Config:
        from_attributes = True


# =============================================================================
# REGLAS DE CONOCIMIENTO
# =============================================================================

class ReglaCreate(BaseModel):
    """Esquema de entrada para crear una regla."""
    codigo_regla: str = Field(..., max_length=20)
    nombre: str = Field(..., max_length=100)
    descripcion: str
    condiciones: dict
    conclusion: str
    nivel_asignado: int | None = Field(None, ge=1, le=5)
    confianza: float = Field(1.0, ge=0, le=1)
    prioridad: int = 0
    categoria: str | None = None
    activa: bool = True


class ReglaResponse(BaseModel):
    """Esquema de salida para reglas."""
    id: int
    codigo_regla: str
    nombre: str
    descripcion: str
    condiciones: dict
    conclusion: str
    nivel_asignado: int | None
    confianza: float
    prioridad: int
    categoria: str | None
    activa: bool
    created_at: datetime | None
    updated_at: datetime | None

    class Config:
        from_attributes = True


# =============================================================================
# ESTADISTICAS
# =============================================================================

class EstadisticaDiariaResponse(BaseModel):
    """Esquema de salida para estadisticas diarias."""
    fecha: str
    total_evaluaciones: int
    nivel_1: int
    nivel_2: int
    nivel_3: int
    nivel_4: int
    nivel_5: int
    tiempo_promedio_evaluacion_ms: int | None
    diagnostico_mas_comun: str | None

    class Config:
        from_attributes = True


class DashboardResponse(BaseModel):
    """Esquema de salida para dashboard completo."""
    total_pacientes: int
    total_evaluaciones: int
    evaluaciones_hoy: int
    distribucion_niveles: dict
    tiempo_promedio_ms: float | None
    diagnosticos_mas_comunes: list
    ultimas_evaluaciones: list


# =============================================================================
# RESPUESTA GENERICA
# =============================================================================

class MensajeResponse(BaseModel):
    """Respuesta generica con mensaje."""
    mensaje: str
    exito: bool = True
    datos: dict | None = None
