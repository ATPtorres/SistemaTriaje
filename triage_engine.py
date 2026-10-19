"""
triage_engine.py - Motor de Reglas y Lógica de Triaje
=====================================================
Implementa la inferencia clínica basada en el modelo ESI (Emergency Severity Index).
Evalúa signos vitales y síntomas en cascada desde el nivel más crítico (1) hasta
el menos crítico (5), asignando prioridad, color y justificación clínica.

Referencia: American College of Emergency Physicians (ACEP) - ESI v4
"""

from datetime import datetime, timezone

from models import (
    DatosPaciente,
    ResultadoTriaje,
    ColorTriage,
    NivelConciencia,
)


# =============================================================================
# CONSTANTES CLÍNICAS - UMBRALES DE REFERENCIA (ADULTOS)
# =============================================================================

class UmbralesCriticos:
    """Valores umbral que disparan evaluación de riesgo vital inmediato."""
    # Saturación de oxígeno
    SPO2_CRITICA = 90          # SpO2 < 90% = hipoxemia severa
    SPO2_ADVERTENCIA = 94      # SpO2 < 94% = hipoxemia moderada

    # Frecuencia cardíaca
    FC_MUY_BAJA = 40           # Bradicardia severa
    FC_MUY_ALTA = 150          # Taquicardia severa
    FC_BAJA = 50               # Bradicardia
    FC_ALTA = 120              # Taquicardia

    # Presión arterial sistólica
    PAS_CRITICA = 80           # Hipotensión severa (shock)
    PAS_BAJA = 90              # Hipotensión
    PAS_ALTA = 200             # Hipertensión severa

    # Temperatura
    TEMP_HIPOTERMIA = 35.0     # Hipotermia
    TEMP_FIEBRE_ALTA = 39.5    # Fiebre alta
    TEMP_FIEBRE = 38.0         # Fiebre

    # Presión diastólica
    PAD_ALTA = 120             # Crisis hipertensiva diastólica


class ConfiguracionMotor:
    """Parámetros de configuración del motor de inferencia."""
    NIVEL_MINIMO = 1
    NIVEL_MAXIMO = 5
    TIEMPO_EVALUACION = datetime.now(timezone.utc).isoformat()


# =============================================================================
# MOTOR DE INFERENCIA DE TRIAJE
# =============================================================================

class MotorTriaje:
    """
    Motor de inferencia clínica para triaje de urgencias.
    
    Utiliza evaluación en cascada (cascade evaluation):
    1. Primero descarta condiciones de riesgo vital inmediato (Nivel 1-2)
    2. Luego evalúa complejidad de recursos necesarios (Nivel 3-5)
    
    Cada nivel tiene sus propias reglas de evaluación que se ejecutan
    secuencialmente hasta encontrar la primera coincidencia.
    """

    def __init__(self):
        self.umbrales = UmbralesCriticos()
        self.signos_alerta: list[str] = []

    # -------------------------------------------------------------------------
    # MÉTODO PRINCIPAL
    # -------------------------------------------------------------------------

    def evaluar(self, paciente: DatosPaciente) -> ResultadoTriaje:
        """
        Evalúa al paciente y retorna el resultado de triaje.
        
        Flujo de evaluación en cascada:
        - Nivel 1: Riesgo vital inmediato → Resucitación
        - Nivel 2: Emergencia de alto riesgo → Emergencia
        - Nivel 3: Múltiples recursos → Urgente
        - Nivel 4: Un recurso → Menos urgente
        - Nivel 5: Sin recursos → No urgente
        
        Args:
            paciente: Datos completos del paciente a evaluar
            
        Returns:
            ResultadoTriaje con nivel, color, motivo y recomendación
        """
        self.signos_alerta = []
        sv = paciente.signos_vitales
        sx = paciente.sintomas
        conciencia = paciente.nivel_conciencia

        # =========================================================================
        # NIVEL 1 - RESUCITACIÓN (ROJO)
        # Riesgo vital inmediato que requiere intervención sin demora
        # =========================================================================
        nivel1, motivo1 = self._evaluar_nivel_1(sv, sx, conciencia)
        if nivel1:
            return self._construir_resultado(
                paciente.id_paciente, 1, ColorTriage.ROJO,
                motivo1, "Intervención inmediata: activar código de trauma/paro cardíaco"
            )

        # =========================================================================
        # NIVEL 2 - EMERGENCIA (NARANJA)
        # Paciente con alto riesgo de deterioro o estado alterado
        # =========================================================================
        nivel2, motivo2 = self._evaluar_nivel_2(sv, sx, conciencia, paciente.edad)
        if nivel2:
            return self._construir_resultado(
                paciente.id_paciente, 2, ColorTriage.NARANJA,
                motivo2, "Atención preferente: maximal 10 minutos, monitoreo continuo"
            )

        # =========================================================================
        # NIVEL 3 - URGENTE (AMARILLO)
        # Paciente estable pero con múltiples signos alterados
        # =========================================================================
        nivel3, motivo3 = self._evaluar_nivel_3(sv, sx, conciencia)
        if nivel3:
            return self._construir_resultado(
                paciente.id_paciente, 3, ColorTriage.AMARILLO,
                motivo3, "Evaluación médica: maximal 30 minutos, posible estancia"
            )

        # =========================================================================
        # NIVEL 4 - MENOS URGENTE (VERDE)
        # Paciente estable, requiere al menos un recurso diagnóstico
        # =========================================================================
        nivel4, motivo4 = self._evaluar_nivel_4(sv, sx)
        if nivel4:
            return self._construir_resultado(
                paciente.id_paciente, 4, ColorTriage.VERDE,
                motivo4, "Consulta médica: maximal 60 minutos, alta probable"
            )

        # =========================================================================
        # NIVEL 5 - NO URGENTE (AZUL)
        # Paciente estable, sin signos de alarma, sin recursos necesarios
        # =========================================================================
        return self._construir_resultado(
            paciente.id_paciente, 5, ColorTriage.AZUL,
            "Paciente estable, sin alteraciones vitales ni síntomas de alarma.",
            "Consulta de medicina general: maximal 120 minutos"
        )

    # -------------------------------------------------------------------------
    # EVALUACIÓN NIVEL 1 - RESUCITACIÓN
    # -------------------------------------------------------------------------

    def _evaluar_nivel_1(self, sv, sx, conciencia) -> tuple[bool, str]:
        """
        Evalúa condiciones de riesgo vital inmediato.
        
        Criterios ESI Nivel 1:
        - Inconsciencia (sin respuesta)
        - Paro cardiorrespiratorio o respiración ineficaz
        - SpO2 < 90% con signos de distrés
        - Convulsiones activas
        - Dolor torácico con signos de inestabilidad hemodinámica
        """
        razones = []

        # Inconsciencia - sin respuesta a ningún estímulo
        if conciencia == NivelConciencia.I:
            razones.append("Paciente inconsciente (sin respuesta a estímulos)")

        # Convulsiones activas
        if sx.convulsiones:
            razones.append("Convulsiones activas")

        # SpO2 crítica con dificultad respiratoria
        if sv.saturacion_oxigeno < self.umbrales.SPO2_CRITICA:
            razones.append(
                f"Saturación de oxígeno crítica: {sv.saturacion_oxigeno}% "
                f"(umbral: <{self.umbrales.SPO2_CRITICA}%)"
            )
            self.signos_alerta.append("Hipoxemia severa")

        # Paro cardíaco: FC extremadamente baja o ausente
        if sv.frecuencia_cardiaca <= 20:
            razones.append("Frecuencia cardíaca incompatível con vida")
            self.signos_alerta.append("Bradicardia severa/muerte cardíaca")

        # Hipotensión severa con alteración de conciencia
        if sv.presion_sistolica < self.umbrales.PAS_CRITICA:
            if conciencia in (NivelConciencia.D, NivelConciencia.I):
                razones.append(
                    f"Shock hipovolémico: PAS {sv.presion_sistolica}mmHg "
                    f"con alteración de conciencia"
                )
                self.signos_alerta.append("Shock hipotensivo")

        # Sangrado masivo con inestabilidad
        if sx.sangrado_activo and sv.presion_sistolica < self.umbrales.PAS_BAJA:
            razones.append(
                f"Sangrado activo con hipotensión (PAS: {sv.presion_sistolica}mmHg)"
            )
            self.signos_alerta.append("Hemorragia activa con inestabilidad")

        if razones:
            return True, " | ".join(razones)
        return False, ""

    # -------------------------------------------------------------------------
    # EVALUACIÓN NIVEL 2 - EMERGENCIA
    # -------------------------------------------------------------------------

    def _evaluar_nivel_2(self, sv, sx, conciencia, edad) -> tuple[bool, str]:
        """
        Evalúa condiciones de alto riesgo que requieren atención urgente.
        
        Criterios ESI Nivel 2:
        - Estado mental alterado (Verbal o Dolor)
        - Signos vitales en rango crítico
        - Dolor torácico (cualquier causa)
        - Edad extrema con síntomas
        """
        razones = []

        # Alteración del nivel de conciencia (responde solo a voz o dolor)
        if conciencia in (NivelConciencia.V, NivelConciencia.D):
            razones.append(
                f"Nivel de conciencia alterado: {conciencia.value}"
            )
            self.signos_alerta.append("Alteración neurológica")

        # Dolor torácico (cualquier paciente con dolor torácico es mínimo Nivel 2)
        if sx.dolor_toracico:
            razones.append("Dolor torácico reportado")
            self.signos_alerta.append("Dolor torácico")

        # Dificultad respiratoria severa
        if sx.dificultad_respiratoria:
            if sv.saturacion_oxigeno < self.umbrales.SPO2_ADVERTENCIA:
                razones.append(
                    f"Dificultad respiratoria con SpO2 {sv.saturacion_oxigeno}%"
                )
                self.signos_alerta.append("Insuficiencia respiratoria")
            elif sv.frecuencia_cardiaca > self.umbrales.FC_ALTA:
                razones.append("Dificultad respiratoria con taquicardia")
                self.signos_alerta.append("Taquicardia compensatoria")

        # Taquicardia severa sin causa aparente
        if (sv.frecuencia_cardiaca > self.umbrales.FC_MUY_ALTA and
                not sx.dolor_toracico and not sx.dificultad_respiratoria):
            razones.append(
                f"Taquicardia severa: {sv.frecuencia_cardiaca} lpm "
                f"(umbral: >{self.umbrales.FC_MUY_ALTA} lpm)"
            )
            self.signos_alerta.append("Taquicardia severa")

        # Bradicardia sintomática
        if sv.frecuencia_cardiaca < self.umbrales.FC_BAJA:
            if conciencia != NivelConciencia.A:
                razones.append(
                    f"Bradicardia sintomática: {sv.frecuencia_cardiaca} lpm"
                )
                self.signos_alerta.append("Bradicardia")

        # Hipotensión
        if sv.presion_sistolica < self.umbrales.PAS_BAJA:
            if conciencia == NivelConciencia.A:
                razones.append(
                    f"Hipotensión arterial: PAS {sv.presion_sistolica}mmHg"
                )
                self.signos_alerta.append("Hipotensión")

        # Fiebre alta con alteración neurológica
        if sv.temperatura > self.umbrales.TEMP_FIEBRE_ALTA:
            if conciencia != NivelConciencia.A:
                razones.append(
                    f"Fiebre alta ({sv.temperatura}°C) con alteración de conciencia"
                )
                self.signos_alerta.append("Fiebre con compromiso neurológico")

        # Hipertensión severa
        if sv.presion_sistolica > 200 or sv.presion_diastolica > self.umbrales.PAD_ALTA:
            razones.append(
                f"Crisis hipertensiva: {sv.presion_sistolica}/{sv.presion_diastolica}mmHg"
            )
            self.signos_alerta.append("Crisis hipertensiva")

        # Pacientes muy jóvenes con fiebre o síntomas sistémicos
        if edad < 2 and (sv.temperatura > self.umbrales.TEMP_FIEBRE or sx.dificultad_respiratoria):
            razones.append(f"Paciente pediatrico ({edad} años) con síntomas sistémicos")
            self.signos_alerta.append("Paciente pediatrico de riesgo")

        if razones:
            return True, " | ".join(razones)
        return False, ""

    # -------------------------------------------------------------------------
    # EVALUACIÓN NIVEL 3 - URGENTE
    # -------------------------------------------------------------------------

    def _evaluar_nivel_3(self, sv, sx, conciencia) -> tuple[bool, str]:
        """
        Evalúa pacientes que requieren múltiples recursos diagnósticos.
        
        Criterios ESI Nivel 3:
        - 2 o más signos vitales fuera de rango normal
        - Síntomas significativos sin compromiso vital
        - Dolor intenso sin signos de inestabilidad
        """
        razones = []
        alteraciones_vitales = 0

        # Contar alteraciones vitales
        if sv.frecuencia_cardiaca < self.umbrales.FC_BAJA or sv.frecuencia_cardiaca > self.umbrales.FC_ALTA:
            alteraciones_vitales += 1
            razones.append(f"FC alterada: {sv.frecuencia_cardiaca} lpm")

        if sv.presion_sistolica < self.umbrales.PAS_BAJA or sv.presion_sistolica > 180:
            alteraciones_vitales += 1
            razones.append(f"PAS alterada: {sv.presion_sistolica}mmHg")

        if sv.saturacion_oxigeno < self.umbrales.SPO2_ADVERTENCIA:
            alteraciones_vitales += 1
            razones.append(f"SpO2 reducida: {sv.saturacion_oxigeno}%")

        if sv.temperatura > self.umbrales.TEMP_FIEBRE or sv.temperatura < self.umbrales.TEMP_HIPOTERMIA:
            alteraciones_vitales += 1
            if sv.temperatura > self.umbrales.TEMP_FIEBRE:
                razones.append(f"Fiebre: {sv.temperatura}°C")
            else:
                razones.append(f"Hipotermia: {sv.temperatura}°C")

        # Múltiples alteraciones vitales → Nivel 3
        if alteraciones_vitales >= 2:
            self.signos_alerta.append(f"{alteraciones_vitales} constantes vitales alteradas")
            return True, "Múltiples alteraciones vitales: " + " | ".join(razones)

        # Dolor intenso sin inestabilidad hemodinámica
        if sx.dolor_intenso:
            if sv.presion_sistolica >= self.umbrales.PAS_BAJA:
                razones.append("Dolor intenso (EVA >= 7) con signos vitales estables")
                return True, " | ".join(razones)

        # Sangrado activo sin hipotensión
        if sx.sangrado_activo:
            if sv.presion_sistolica >= self.umbrales.PAS_BAJA:
                razones.append("Sangrado activo con presión arterial conservada")
                self.signos_alerta.append("Hemorragia activa compensada")
                return True, " | ".join(razones)

        # Trauma significativo con síntomas asociados
        if sx.trauma_significativo:
            recursos = self._contar_recursos_necesarios(sv, sx)
            if recursos >= 2:
                razones.append("Trauma significativo que requiere múltiples evaluaciones")
                return True, " | ".join(razones)

        # Fiebre con alteración de conducta
        if sv.temperatura > self.umbrales.TEMP_FIEBRE and sx.alteracion_conducta:
            razones.append("Fiebre con alteración conductual")
            return True, " | ".join(razones)

        return False, ""

    # -------------------------------------------------------------------------
    # EVALUACIÓN NIVEL 4 - MENOS URGENTE
    # -------------------------------------------------------------------------

    def _evaluar_nivel_4(self, sv, sx) -> tuple[bool, str]:
        """
        Evalúa pacientes estables que requieren al menos un recurso.
        
        Criterios ESI Nivel 4:
        - Una alteración vital leve
        - Síntomas que requieren evaluación pero sin riesgo
        """
        razones = []

        # Fiebre leve
        if self.umbrales.TEMP_FIEBRE <= sv.temperatura <= self.umbrales.TEMP_FIEBRE_ALTA:
            razones.append(f"Fiebre: {sv.temperatura}°C")

        # FC ligeramente alterada
        if self.umbrales.FC_BAJA <= sv.frecuencia_cardiaca < 60:
            razones.append(f"Bradicardia leve: {sv.frecuencia_cardiaca} lpm")
        elif 100 < sv.frecuencia_cardiaca <= self.umbrales.FC_ALTA:
            razones.append(f"Taquicardia leve: {sv.frecuencia_cardiaca} lpm")

        # PA ligeramente alterada
        if 85 <= sv.presion_sistolica < self.umbrales.PAS_BAJA:
            razones.append(f"Hipotensión leve: PAS {sv.presion_sistolica}mmHg")

        # Dificultad respiratoria leve (sin desaturación significativa)
        if sx.dificultad_respiratoria and sv.saturacion_oxigeno >= self.umbrales.SPO2_ADVERTENCIA:
            razones.append("Dificultad respiratoria leve con SpO2 conservada")

        if razones:
            return True, " | ".join(razones)
        return False, ""

    # -------------------------------------------------------------------------
    # MÉTODOS AUXILIARES
    # -------------------------------------------------------------------------

    def _contar_recursos_necesarios(self, sv, sx) -> int:
        """
        Estima la cantidad de recursos diagnósticos/terapéuticos necesarios.
        Basado en criterios ESI para stratificación de recursos.
        """
        recursos = 0

        # Recursos potenciales basados en criterios ESI
        if sx.dolor_toracico:
            recursos += 1    # ECG, troponinas, Rx tórax
        if sx.dificultad_respiratoria:
            recursos += 1    # Gasometría, Rx tórax, nebulización
        if sx.sangrado_activo:
            recursos += 1    # Curación, laboratorios, posible sutura
        if sx.trauma_significativo:
            recursos += 1    # Rx, TAC, interconsultas
        if sv.frecuencia_cardiaca < self.umbrales.FC_BAJA or sv.frecuencia_cardiaca > self.umbrales.FC_ALTA:
            recursos += 1    # ECG, laboratorios
        if sv.saturacion_oxigeno < self.umbrales.SPO2_ADVERTENCIA:
            recursos += 1    # Gasometría, oxígeno suplementario
        if sv.temperatura > self.umbrales.TEMP_FIEBRE:
            recursos += 1    # Laboratorios, hemocultivos

        return recursos

    def _construir_resultado(
        self,
        id_paciente: str,
        nivel: int,
        color: ColorTriage,
        motivo: str,
        recomendacion: str
    ) -> ResultadoTriaje:
        """
        Construye el objeto ResultadoTriaje con todos los campos.
        
        Args:
            id_paciente: Identificador del paciente
            nivel: Nivel de prioridad (1-5)
            color: Color de triaje
            motivo: Justificación clínica
            recomendacion: Acción recomendada
            
        Returns:
            ResultadoTriaje completo
        """
        return ResultadoTriaje(
            id_paciente=id_paciente,
            nivel_prioridad=nivel,
            color=color.value,
            motivo_clinico=motivo,
            signos_alerta=self.signos_alerta,
            recomendacion=recomendacion
        )


# =============================================================================
# FUNCIÓN DE UTILIDAD PÚBLICA
# =============================================================================

def evaluar_triaje(paciente: DatosPaciente) -> ResultadoTriaje:
    """
    Función principal de entrada para evaluar el triaje de un paciente.
    
    Uso:
        from triage_engine import evaluar_triaje
        from models import DatosPaciente
        
        paciente = DatosPaciente(...)
        resultado = evaluar_triaje(paciente)
    
    Args:
        paciente: Datos del paciente a evaluar
        
    Returns:
        ResultadoTriaje con clasificación completa
    """
    motor = MotorTriaje()
    return motor.evaluar(paciente)
