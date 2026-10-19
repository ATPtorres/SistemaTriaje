"""
models_db.py - Modelos SQLAlchemy para Base de Datos
=====================================================
Define las tablas de la base de datos triaje_sistema:

Tablas:
- pacientes: Datos demograficos del paciente
- triaje_evaluaciones: Resultados de cada evaluacion de triaje
- signos_vitales_historial: Historial de signos vitales registrados
- alertas_generadas: Alertas clinicas detectadas
- diagnosticos_sugeridos: Diagnosticos diferenciales propuestos
- reglas_conocimiento: Base de conocimiento del sistema experto
- sesiones_usuario: Registro de sesiones de uso del sistema

Referencia: Modelo relacional 3NF para sistemas clinicos
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime,
    ForeignKey, Enum as SQLEnum, JSON, Index
)
from sqlalchemy.orm import relationship
from database import Base


# =============================================================================
# TABLA: PACIENTES
# =============================================================================

class Paciente(Base):
    """
    Almacena datos demograficos del paciente.
    Un paciente puede tener multiples evaluaciones de triaje.
    """
    __tablename__ = "pacientes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_externo = Column(String(50), unique=True, nullable=False, index=True,
                       comment="ID del paciente en el sistema hospitalario")
    nombre = Column(String(100), nullable=True, comment="Nombre completo")
    edad = Column(Integer, nullable=False, comment="Edad en anos")
    sexo = Column(String(1), nullable=True, comment="M=Masculino, F=Femenino, O=Otro")
    peso_kg = Column(Float, nullable=True, comment="Peso en kilogramos")
    telefono = Column(String(20), nullable=True, comment="Numero de contacto")
    direccion = Column(Text, nullable=True, comment="Direccion del paciente")
    alergias = Column(Text, nullable=True, comment="Alergias conocidas")
    medicamentos = Column(Text, nullable=True, comment="Medicamentos actuales")
    antecedentes = Column(Text, nullable=True, comment="Antecedentes clinicos relevantes")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc))

    # Relaciones
    evaluaciones = relationship("EvaluacionTriaje", back_populates="paciente",
                               cascade="all, delete-orphan")


# =============================================================================
# TABLA: EVALUACIONES DE TRIAJE
# =============================================================================

class EvaluacionTriaje(Base):
    """
    Registro completo de cada evaluacion de triaje realizada.
    Contiene el resultado final del sistema experto.
    """
    __tablename__ = "triaje_evaluaciones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    paciente_id = Column(Integer, ForeignKey("pacientes.id"), nullable=False, index=True)
    id_evaluacion = Column(String(50), unique=True, nullable=False, index=True,
                          comment="ID unico de la evaluacion")

    # Resultado del triaje
    nivel_prioridad = Column(Integer, nullable=False, comment="Nivel ESI 1-5")
    color = Column(String(20), nullable=False, comment="Color del nivel")
    motivo_clinico = Column(Text, nullable=False, comment="Justificacion clinica")
    recomendacion = Column(Text, nullable=False, comment="Accion recomendada")

    # Scores calculados
    score_riesgo_difuso = Column(Float, nullable=True, comment="Score logica difusa 0-100")
    score_riesgo_multifactor = Column(Float, nullable=True, comment="Score multifactor")
    nivel_riesgo = Column(String(20), nullable=True, comment="Bajo/Moderado/Alto/Critico")

    # Metadata del motor de inferencia
    metodo_inferencia = Column(String(100), nullable=True,
                              comment="Forward Chaining + Fuzzy Logic")
    reglas_evaluadas = Column(Integer, nullable=True, comment="Num reglas evaluadas")
    reglas_activadas = Column(Integer, nullable=True, comment="Num reglas activadas")
    traza_inferencia = Column(JSON, nullable=True, comment="Traza completa del motor")
    explicaciones = Column(JSON, nullable=True, comment="WHY/HOW/TRACE")

    # Protocolos internacionales
    nivel_esi = Column(Integer, nullable=True, comment="Nivel ESI")
    nivel_mts = Column(Integer, nullable=True, comment="Nivel Manchester")
    nivel_ctas = Column(Integer, nullable=True, comment="Nivel CTAS Canada")
    nivel_ats = Column(Integer, nullable=True, comment="Nivel ATS Australia")

    # Datos crudos de entrada (para auditoria)
    datos_entrada = Column(JSON, nullable=False, comment="JSON con datos del paciente")

    # Timestamps
    fecha_evaluacion = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    duracion_ms = Column(Integer, nullable=True, comment="Tiempo de procesamiento en ms")

    # Relaciones
    paciente = relationship("Paciente", back_populates="evaluaciones")
    signos_vitales = relationship("SignosVitalesHistorial", back_populates="evaluacion",
                                 cascade="all, delete-orphan")
    alertas = relationship("AlertaGenerada", back_populates="evaluacion",
                          cascade="all, delete-orphan")
    diagnosticos = relationship("DiagnosticoSugerido", back_populates="evaluacion",
                               cascade="all, delete-orphan")


# =============================================================================
# TABLA: SIGNOS VITALES HISTORIAL
# =============================================================================

class SignosVitalesHistorial(Base):
    """
    Historial de signos vitales registrados en cada evaluacion.
    Permite graficas de tendencia temporal.
    """
    __tablename__ = "signos_vitales_historial"

    id = Column(Integer, primary_key=True, autoincrement=True)
    evaluacion_id = Column(Integer, ForeignKey("triaje_evaluaciones.id"),
                          nullable=False, index=True)

    frecuencia_cardiaca = Column(Integer, nullable=False, comment="FC en lpm")
    presion_sistolica = Column(Integer, nullable=False, comment="PAS en mmHg")
    presion_diastolica = Column(Integer, nullable=False, comment="PAD en mmHg")
    temperatura = Column(Float, nullable=False, comment="Temp en C")
    saturacion_oxigeno = Column(Integer, nullable=False, comment="SpO2 en %")
    nivel_conciencia = Column(String(20), nullable=False, comment="AVDI")

    # Timestamp
    registrado_en = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relacion
    evaluacion = relationship("EvaluacionTriaje", back_populates="signos_vitales")


# =============================================================================
# TABLA: ALERTAS GENERADAS
# =============================================================================

class AlertaGenerada(Base):
    """
    Alertas clinicas detectadas por el sistema experto.
    Cada alerta esta vinculada a una evaluacion especifica.
    """
    __tablename__ = "alertas_generadas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    evaluacion_id = Column(Integer, ForeignKey("triaje_evaluaciones.id"),
                          nullable=False, index=True)

    tipo_alerta = Column(String(50), nullable=False,
                        comment="Critica/Alta/Media/Baja")
    descripcion = Column(Text, nullable=False, comment="Descripcion de la alerta")
    signo_vital = Column(String(30), nullable=True, comment="Signo vital relacionado")
    valor_detectado = Column(String(50), nullable=True, comment="Valor que disparo la alerta")
    umbral = Column(String(50), nullable=True, comment="Umbral de referencia")
    nivel_gravedad = Column(Integer, nullable=False, comment="1=Critica, 5=Baja")

    # Timestamp
    generada_en = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relacion
    evaluacion = relationship("EvaluacionTriaje", back_populates="alertas")


# =============================================================================
# TABLA: DIAGNOSTICOS SUGERIDOS
# =============================================================================

class DiagnosticoSugerido(Base):
    """
    Diagnosticos diferenciales sugeridos por el motor de soporte clinico.
    """
    __tablename__ = "diagnosticos_sugeridos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    evaluacion_id = Column(Integer, ForeignKey("triaje_evaluaciones.id"),
                          nullable=False, index=True)

    codigo_diagnostico = Column(String(20), nullable=False, comment="Codigo CIE-10 o interno")
    nombre_diagnostico = Column(String(200), nullable=False, comment="Nombre del diagnostico")
    especialidad = Column(String(100), nullable=True, comment="Especialidad medica")
    probabilidad = Column(Float, nullable=False, comment="Probabilidad 0-1")
    evidencia = Column(JSON, nullable=True, comment="Evidencias que lo soportan")
    estudios_sugeridos = Column(JSON, nullable=True, comment="Estudios recomendados")
    conducta = Column(Text, nullable=True, comment="Conducta a seguir")

    # Timestamp
    sugerido_en = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relacion
    evaluacion = relationship("EvaluacionTriaje", back_populates="diagnosticos")


# =============================================================================
# TABLA: REGLAS DE CONOCIMIENTO
# =============================================================================

class ReglaConocimiento(Base):
    """
    Base de conocimiento del sistema experto almacenada en BD.
    Permite modificar reglas sin reiniciar el servidor.
    """
    __tablename__ = "reglas_conocimiento"

    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo_regla = Column(String(20), unique=True, nullable=False, index=True)
    nombre = Column(String(100), nullable=False)
    descripcion = Column(Text, nullable=False)
    condiciones = Column(JSON, nullable=False, comment="Condiciones IF en JSON")
    conclusion = Column(Text, nullable=False, comment="Conclusion THEN")
    nivel_asignado = Column(Integer, nullable=True, comment="Nivel de triaje 1-5")
    confianza = Column(Float, default=1.0, comment="Factor de confianza 0-1")
    prioridad = Column(Integer, default=0, comment="Mayor = se evalua primero")
    categoria = Column(String(50), nullable=True, comment="critico/emergencia/urgente/etc")
    activa = Column(Boolean, default=True, comment="Regla activa o desactivada")

    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc))


# =============================================================================
# TABLA: SESIONES DE USUARIO
# =============================================================================

class SesionUsuario(Base):
    """
    Registro de sesiones de uso del sistema.
    Para auditoria y metricas de uso.
    """
    __tablename__ = "sesiones_usuario"

    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario = Column(String(100), nullable=False, comment="Nombre del usuario")
    rol = Column(String(50), nullable=True, comment="Medico/Enfermera/Admin")
    ip_address = Column(String(45), nullable=True, comment="Direccion IP")
    user_agent = Column(Text, nullable=True, comment="Navegador/dispositivo")

    # Metricas
    total_evaluaciones = Column(Integer, default=0)
    duracion_minutos = Column(Integer, nullable=True)

    # Timestamps
    inicio_sesion = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    fin_sesion = Column(DateTime, nullable=True)


# =============================================================================
# TABLA: ESTADISTICAS DIARIAS (Materialized)
# =============================================================================

class EstadisticaDiaria(Base):
    """
    Estadisticas pre-calculadas por dia para reportes.
    Se actualiza periodicamente con un job de background.
    """
    __tablename__ = "estadisticas_diarias"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fecha = Column(String(10), nullable=False, index=True, comment="YYYY-MM-DD")

    # Conteo por nivel
    total_evaluaciones = Column(Integer, default=0)
    nivel_1 = Column(Integer, default=0)
    nivel_2 = Column(Integer, default=0)
    nivel_3 = Column(Integer, default=0)
    nivel_4 = Column(Integer, default=0)
    nivel_5 = Column(Integer, default=0)

    # Tiempos promedio
    tiempo_promedio_evaluacion_ms = Column(Integer, nullable=True)

    # Diagnostics mas comunes
    diagnostico_mas_comun = Column(String(200), nullable=True)

    # Timestamp
    calculado_en = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Unicidad por fecha
    __table_args__ = (
        Index('ix_estadistica_fecha', 'fecha', unique=True),
    )
