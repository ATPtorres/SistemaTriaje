"""
models.py - Modelos de datos para el Sistema Experto de Triaje
==============================================================
Define las estructuras Pydantic para entrada y salida del sistema.
Basado en el modelo Emergency Severity Index (ESI) de 5 niveles.
"""

from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field


# =============================================================================
# ENUMERACIONES
# =============================================================================

class NivelConciencia(str, Enum):
    """Escala AVDI de Evaluación del Nivel de Conciencia."""
    A = "Alerta"              # Paciente despierto, orientado
    V = "Verbal"              # Responde solo a estímulos verbales
    D = "Dolor"               # Responde solo a estímulo doloroso
    I = "Inconsciente"        # Sin respuesta a ningún estímulo


class ColorTriage(str, Enum):
    """Códigos de color asociados a cada nivel de triaje ESI."""
    ROJO = "Rojo"
    NARANJA = "Naranja"
    AMARILLO = "Amarillo"
    VERDE = "Verde"
    AZUL = "Azul"


class NivelPrioridad(int, Enum):
    """Niveles de prioridad según el modelo ESI."""
    RESUCITACION = 1      # Riesgo vital inmediato
    EMERGENCIA = 2        # Emergencia alta
    URGENTE = 3           # Urgente - requiere múltiples recursos
    MENOS_URGENTE = 4     # Menos urgente - un recurso
    NO_URGENTE = 5        # No urgente


# =============================================================================
# MODELOS DE ENTRADA
# =============================================================================

class SignosVitales(BaseModel):
    """
    Constantes vitales del paciente al momento de la evaluación.
    
    Rangos de referencia para adultos:
    - Frecuencia cardíaca: 60-100 lpm
    - Presión sistólica: 90-140 mmHg
    - Presión diastólica: 60-90 mmHg
    - Temperatura: 36.1-37.2 °C
    - Saturación de oxígeno: 95-100 %
    """
    frecuencia_cardiaca: int = Field(
        ..., 
        ge=20, le=300,
        description="Frecuencia cardíaca en latidos por minuto (lpm)",
        examples=[72]
    )
    presion_sistolica: int = Field(
        ..., 
        ge=40, le=300,
        description="Presión arterial sistólica en mmHg",
        examples=[120]
    )
    presion_diastolica: int = Field(
        ..., 
        ge=20, le=200,
        description="Presión arterial diastólica en mmHg",
        examples=[80]
    )
    temperatura: float = Field(
        ..., 
        ge=30.0, le=45.0,
        description="Temperatura corporal en grados Celsius",
        examples=[36.5]
    )
    saturacion_oxigeno: int = Field(
        ..., 
        ge=0, le=100,
        description="Saturación de oxígeno (SpO2) en porcentaje",
        examples=[98]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "frecuencia_cardiaca": 72,
                "presion_sistolica": 120,
                "presion_diastolica": 80,
                "temperatura": 36.5,
                "saturacion_oxigeno": 98
            }]
        }
    }


class Sintomas(BaseModel):
    """
    Síntomas clave reportados o detectados en el paciente.
    Cada campo es booleano para facilitar la evaluación por reglas.
    """
    dolor_toracico: bool = Field(
        default=False,
        description="Dolor o malestar en el pecho"
    )
    dificultad_respiratoria: bool = Field(
        default=False,
        description="Disnea o dificultad para respirar"
    )
    sangrado_activo: bool = Field(
        default=False,
        description="Hemorragia activa visible"
    )
    convulsiones: bool = Field(
        default=False,
        description="Actividad convulsiva actual o reciente"
    )
    alteracion_conducta: bool = Field(
        default=False,
        description="Comportamiento inusual, agitación o confusión"
    )
    trauma_significativo: bool = Field(
        default=False,
        description="Lesión por mecanismo de alto impacto (accidente, caída alta)"
    )
    dolor_intenso: bool = Field(
        default=False,
        description="Dolor severo reportado (EVA >= 7)"
    )


class DatosPaciente(BaseModel):
    """
    Modelo completo de entrada para la evaluación de triaje.
    Agrupa demographics, signos vitales, nivel de conciencia y síntomas.
    """
    id_paciente: str = Field(
        ..., 
        description="Identificador único del paciente (historia clínica o temporal)",
        examples=["P-001"]
    )
    edad: int = Field(
        ..., 
        ge=0, le=150,
        description="Edad del paciente en años",
        examples=[72]
    )
    peso_kg: float | None = Field(
        default=None,
        ge=0, le=500,
        description="Peso del paciente en kilogramos (opcional)"
    )
    signos_vitales: SignosVitales = Field(
        ...,
        description="Signos vitales del paciente"
    )
    nivel_conciencia: NivelConciencia = Field(
        ..., 
        description="Nivel de conciencia según escala AVDI",
        examples=["Alerta"]
    )
    sintomas: Sintomas = Field(
        default_factory=Sintomas,
        description="Síntomas clave del paciente"
    )
    idioma: Literal["es", "qu"] = Field(
        default="es",
        description="Idioma de la respuesta: es (español) o qu (quechua)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "id_paciente": "P-001",
                "edad": 72,
                "signos_vitales": {
                    "frecuencia_cardiaca": 145,
                    "presion_sistolica": 78,
                    "presion_diastolica": 45,
                    "temperatura": 36.2,
                    "saturacion_oxigeno": 83
                },
                "nivel_conciencia": "Dolor",
                "sintomas": {
                    "dolor_toracico": True,
                    "dificultad_respiratoria": True,
                    "sangrado_activo": False,
                    "convulsiones": False,
                    "alteracion_conducta": False,
                    "trauma_significativo": False,
                    "dolor_intenso": False
                }
            }]
        }
    }


# =============================================================================
# MODELOS DE SALIDA
# =============================================================================

class ResultadoTriaje(BaseModel):
    """
    Respuesta estructurada del sistema de triaje.
    Contiene el nivel asignado, color, motivo clínico y timestamp.
    """
    id_paciente: str = Field(
        ..., 
        description="ID del paciente evaluado"
    )
    nivel_prioridad: int = Field(
        ..., 
        ge=1, le=5,
        description="Nivel de prioridad ESI (1=resucitación, 5=no urgente)"
    )
    color: str = Field(
        ..., 
        description="Código de color asociado al nivel"
    )
    motivo_clinico: str = Field(
        ..., 
        description="Justificación clínica de la clasificación asignada"
    )
    signos_alerta: list[str] = Field(
        default_factory=list,
        description="Lista de signos de alarma detectados"
    )
    recomendacion: str = Field(
        ..., 
        description="Recomendación de acción inmediata"
    )
    score_riesgo_difuso: float | None = Field(
        default=None,
        description="Score de riesgo calculado por logica difusa (0-100)"
    )
    metadata_motor: dict | None = Field(
        default=None,
        description="Metadata del motor de inferencia (traza, explicaciones)"
    )
    soporte_clinico: dict | None = Field(
        default=None,
        description="Soporte clinico: diagnosticos, protocolos, score multifactor"
    )
