"""
clinical_support.py - Soporte Clinico y Protocolos Multiples
=============================================================
Modulo de apoyo a la decision clinica que implementa:

1. DIAGNOSTICOS PROBABLES:
   - Inferencia bayesiana simplificada
   - Matching de patron sintomatico
   - Lista de diferencial ordenada por probabilidad

2. PROTOCOLOS DE TRIAJE MULTIPLES:
   - ESI (Emergency Severity Index) - ACEP
   - MTS (Manchester Triage System)
   - CTAS (Canadian Triage and Acuity Scale)
   - ATS (Australasian Triage Scale)

3. SCORE DE RIESGO MULTI-FACTORIZADO:
   - Puntaje combinado de multiples factores
   - Edad como factor modificador
   - Comorbilidades implicitas

Referencias:
- Gilboy et al. (2012). Emergency Severity Index (ESI): A Triage Tool
- Mackway-Jones & Marsden (2006). Manchester Triage Group
- Bullard et al. (2008). CTAS Standards
"""

from dataclasses import dataclass, field


# =============================================================================
# MODELOS DE DIAGNOSTICO
# =============================================================================

@dataclass
class DiagnosticoDiferencial:
    """Diagnostico probable con evidencia que lo soporta."""
    codigo: str
    nombre: str
    especialidad: str
    probabilidad: float  # 0-1
    evidencia: list[str]  # Evidencias que lo soportan
    estudios_sugeridos: list[str]
    conducta: str


# =============================================================================
# PATRONES SINTOMATICOS (KNOWLEDGE PATTERNS)
# =============================================================================

PATRONES_DIAGNOSTICOS: list[dict] = [
    {
        "id": "IAM",
        "nombre": "Infarto Agudo de Miocardio",
        "especialidad": "Cardiologia",
        "requiere": {"dolor_toracico": True, "edad_min": 35},
        "asocia": {"dificultad_respiratoria", "dolor_intenso"},
        "excluye": {"trauma_significativo"},
        "estudios": ["ECG 12 derivaciones", "Troponina I/T", "Rx torax", "BHC"],
        "conducta": "Activar protocolo IAM. ECG inmediato. Monitoreo cardiaco continuo.",
        "peso_base": 0.7
    },
    {
        "id": "ACV",
        "nombre": "Accidente Cerebrovascular",
        "especialidad": "Neurologia",
        "requiere": {"alteracion_conducta": True, "edad_min": 50},
        "asocia": {"dificultad_respiratoria"},
        "excluye": {"convulsiones", "fiebre"},
        "estudios": ["TAC craneo sin contraste", "Glucemia capilar", "BHC", "Coagulograma"],
        "conducta": "Activar protocolo ACV. ventana terapeutica 4.5h.",
        "peso_base": 0.65
    },
    {
        "id": "SEP",
        "nombre": "Sepsis / Shock Septico",
        "especialidad": "Medicina Interna",
        "requiere": {"fiebre": True},
        "asocia": {"dificultad_respiratoria", "alteracion_conducta", "dolor_intenso"},
        "excluye": {},
        "estudios": ["Hemocultivos x2", "BHC", "PCR", "Procalcitonina", "Gasometria arterial", "Lactato"],
        "conducta": "Bolus de cristaloides. Antibiotico empirico en 1h. Reanimacion according to Surviving Sepsis Campaign.",
        "peso_base": 0.6
    },
    {
        "id": "TCE",
        "nombre": "Traumatismo Craneoencefalico",
        "especialidad": "Traumatologia / Neurocirugia",
        "requiere": {"trauma_significativo": True},
        "asocia": {"alteracion_conducta", "convulsiones", "sangrado_activo"},
        "excluye": {},
        "estudios": ["TAC craneo", "Rx columnas cervical", "BHC", "Coagulograma"],
        "conducta": "Inmovilizacion cervical. Valoracion por neurocirugia. GCS Serial.",
        "peso_base": 0.65
    },
    {
        "id": "IRA",
        "nombre": "Insuficiencia Respiratoria Aguda",
        "especialidad": "Neumologia",
        "requiere": {"dificultad_respiratoria": True},
        "asocia": {"dolor_toracico", "dolor_intenso"},
        "excluye": {},
        "estudios": ["Gasometria arterial", "Rx torax", "D-dimero", "Espirometria basica"],
        "conducta": "Oxigeno suplementario. Considerar ventilacion no invasiva. Neumologia.",
        "peso_base": 0.55
    },
    {
        "id": "HDA",
        "nombre": "Hemorragia Digestiva Alta",
        "especialidad": "Gastroenterologia",
        "requiere": {"sangrado_activo": True},
        "asocia": {"dolor_intenso", "alteracion_conducta"},
        "excluye": {"dolor_toracico", "dificultad_respiratoria"},
        "estudios": ["BHC", "Grupo sanguineo", "Coagulograma", "Esofagogastroduodenoscopia"],
        "conducta": "NPO. Suero IV. Transfusion segun Hb. Gastrourgencia.",
        "peso_base": 0.6
    },
    {
        "id": "EAP",
        "nombre": "Enfermedad Aguda Pulmonar (Neumonia)",
        "especialidad": "Neumologia / Infectologia",
        "requiere": {"fiebre": True, "dificultad_respiratoria": True},
        "asocia": {"dolor_toracico", "dolor_intenso"},
        "excluye": {},
        "estudios": ["Rx torax", "BHC", "PCR", "Hemocultivos", "Exudado faringeo"],
        "conducta": "Antibiotico empirico. Oxigeno si SpO2 < 94%. Control de fiebre.",
        "peso_base": 0.5
    },
    {
        "id": "ECV",
        "nombre": "Convulsiones / Estado Epileptico",
        "especialidad": "Neurologia",
        "requiere": {"convulsiones": True},
        "asocia": {"alteracion_conducta", "dificultad_respiratoria"},
        "excluye": {},
        "estudios": ["Glucemia", "Electrolitos", "TAC craneo", "EEG"],
        "conducta": "Benzodiazepina IV. Proteger via aerea. Neurologia.",
        "peso_base": 0.7
    },
    {
        "id": "SH",
        "nombre": "Shock Hipovolemico",
        "especialidad": "Cirugia General / Emergencia",
        "requiere": {"sangrado_activo": True},
        "asocia": {"alteracion_conducta", "dificultad_respiratoria"},
        "excluye": {},
        "estudios": ["BHC", "Gasometria", "Lactato", "Tipo y cruz", "Ecografia FAST"],
        "conducta": "Acceso venoso x2. Bolus de cristaloides. Transfusion. Cirugia.",
        "peso_base": 0.75
    },
    {
        "id": "CRISIS_HTA",
        "nombre": "Crisis Hipertensiva",
        "especialidad": "Medicina Interna / Cardiologia",
        "requiere": {"crisis_hipertensiva": True},
        "asocia": {"dolor_toracico", "dificultad_respiratoria", "alteracion_conducta"},
        "excluye": {},
        "estudios": ["ECG", "BHC", "Creatinina", "Egograma", "Rx torax"],
        "conducta": "Reduccion controlada de PA. Evitar descenso mayor a 25% en 1h.",
        "peso_base": 0.6
    },
    {
        "id": "PED_FIEBRE",
        "nombre": "Fiebre en paciente pediatrico",
        "especialidad": "Pediatria",
        "requiere": {"edad_menor_5": True, "fiebre": True},
        "asocia": {"dificultad_respiratoria", "alteracion_conducta"},
        "excluye": {},
        "estudios": ["BHC PCR", "Urocultivo", "Hemocultivo", "Rx torax"],
        "conducta": "Antipiretico. Hidratacion. Valoracion por pediatria. Buscar foco.",
        "peso_base": 0.45
    },
]


# =============================================================================
# PROTOCOLOS DE TRIAJE MULTIPLES
# =============================================================================

class ProtocoloESI:
    """
    Emergency Severity Index (ESI) v4
    American College of Emergency Physicians (ACEP)
    
    5 Niveles basados en:
    - Riesgo vital inmediato
    - Nivel de conciencia
    - Recursos necesarios
    """
    nombre = "ESI (Emergency Severity Index)"
    version = "v4"
    organizacion = "ACEP"

    @staticmethod
    def clasificar(nivel_motor: int) -> dict:
        niveles = {
            1: {"color": "Rojo", "tiempo": "Inmediato", "recursos": "Multi-organico", "descripcion": "Resucitacion"},
            2: {"color": "Naranja", "tiempo": "<10 min", "recursos": "Multiple", "descripcion": "Emergencia"},
            3: {"color": "Amarillo", "tiempo": "<30 min", "recursos": "Multiple", "descripcion": "Urgente"},
            4: {"color": "Verde", "tiempo": "<60 min", "recursos": "1 recurso", "descripcion": "Menos urgente"},
            5: {"color": "Azul", "tiempo": "<120 min", "recursos": "0 recursos", "descripcion": "No urgente"},
        }
        info = niveles.get(nivel_motor, niveles[5])
        return {
            "protocolo": "ESI",
            "nivel": nivel_motor,
            "color": info["color"],
            "tiempo_espera": info["tiempo"],
            "recursos_necesarios": info["recursos"],
            "descripcion": info["descripcion"]
        }


class ProtocoloMTS:
    """
    Manchester Triage System (MTS)
    Mackway-Jones & Marsden (2006)
    
    5 niveles con colores diferentes al ESI.
    Usa flujos de presentacion (presenting complaint flows).
    """
    nombre = "MTS (Manchester Triage System)"
    version = "2014"
    organizacion = "Manchester Triage Group"

    @staticmethod
    def clasificar(nivel_motor: int, sintomas: dict = None) -> dict:
        # Mapeo ESI -> MTS (similar pero con diferencias)
        mapeo = {
            1: {"nivel_mts": 1, "color": "Rojo", "descripcion": "Reanimacion inmediata",
                "tiempo": "Inmediato"},
            2: {"nivel_mts": 2, "color": "Naranja", "descripcion": "Emergencia",
                "tiempo": "<10 min"},
            3: {"nivel_mts": 3, "color": "Amarillo", "descripcion": "Urgencia",
                "tiempo": "<30 min"},
            4: {"nivel_mts": 4, "color": "Verde", "descripcion": "Poco urgente",
                "tiempo": "<60 min"},
            5: {"nivel_mts": 5, "color": "Azul", "descripcion": "No urgente",
                "tiempo": "<120 min"},
        }
        info = mapeo.get(nivel_motor, mapeo[5])
        info["protocolo"] = "MTS"
        info["organizacion"] = "Manchester Triage Group"
        return info


class ProtocoloCTAS:
    """
    Canadian Triage and Acuity Scale (CTAS)
    Canadian Association of Emergency Physicians (CAEP)
    
    Niveles similares a ESI pero con especificaciones de tiempo diferentes.
    """
    nombre = "CTAS (Canadian Triage and Acuity Scale)"
    version = "v5"
    organizacion = "CAEP"

    @staticmethod
    def clasificar(nivel_motor: int) -> dict:
        mapeo = {
            1: {"nivel_ctas": 1, "color": "Rojo", "resuscitation": True,
                "tiempo": "Inmediato", "descripcion": "Reanimacion"},
            2: {"nivel_ctas": 2, "color": "Naranja", "resuscitation": False,
                "tiempo": "<15 min", "descripcion": "Emergencia"},
            3: {"nivel_ctas": 3, "color": "Amarillo", "resuscitation": False,
                "tiempo": "<30 min", "descripcion": "Urgencia"},
            4: {"nivel_ctas": 4, "color": "Verde", "resuscitation": False,
                "tiempo": "<60 min", "descripcion": "Poco urgente"},
            5: {"nivel_ctas": 5, "color": "Azul", "resuscitation": False,
                "tiempo": "<120 min", "descripcion": "No urgente"},
        }
        info = mapeo.get(nivel_motor, mapeo[5])
        info["protocolo"] = "CTAS"
        info["organizacion"] = "Canadian Association of Emergency Physicians"
        return info


class ProtocoloATS:
    """
    Australasian Triage Scale (ATS)
    Australasian College for Emergency Medicine (ACEM)
    
    Utilizado en Australia y Nueva Zelanda.
    """
    nombre = "ATS (Australasian Triage Scale)"
    version = "2006"
    organizacion = "ACEM"

    @staticmethod
    def clasificar(nivel_motor: int) -> dict:
        mapeo = {
            1: {"nivel_ats": 1, "color": "Rojo", "tiempo": "Inmediato",
                "descripcion": "Resuscitation"},
            2: {"nivel_ats": 2, "color": "Naranja", "tiempo": "<10 min",
                "descripcion": "Emergency"},
            3: {"nivel_ats": 3, "color": "Amarillo", "tiempo": "<30 min",
                "descripcion": "Urgent"},
            4: {"nivel_ats": 4, "color": "Verde", "tiempo": "<60 min",
                "descripcion": "Semi-urgent"},
            5: {"nivel_ats": 5, "color": "Azul", "tiempo": "<120 min",
                "descripcion": "Non-urgent"},
        }
        info = mapeo.get(nivel_motor, mapeo[5])
        info["protocolo"] = "ATS"
        info["organizacion"] = "Australasian College for Emergency Medicine"
        return info


# =============================================================================
# MOTOR DE SOPORTE CLINICO
# =============================================================================

class MotorSoporteClinico:
    """
    Motor de decision clinica que integra:
    - Inferencia de diagnosticos diferenciales
    - Clasificacion en multiples protocolos
    - Score de riesgo multifactorizado
    """

    def __init__(self):
        self.diagnosticos: list[DiagnosticoDiferencial] = []

    def calcular_score_riesgo(self, datos: dict) -> dict:
        """
        Calcula score de riesgo multifactorizado (0-100).
        
        Factores:
        - Edad (neonatos y ancianos = mayor riesgo)
        - Numero de alteraciones vitales
        - Sintomas de alarma
        - Nivel de conciencia
        """
        sv = datos.get("signos_vitales", {})
        sx = datos.get("sintomas", {})
        edad = datos.get("edad", 30)
        conc = datos.get("nivel_conciencia", "Alerta")

        score = 0
        factores = []

        # Factor edad
        if edad < 1:
            score += 15
            factores.append(("Edad neonatal", 15))
        elif edad < 5:
            score += 10
            factores.append(("Edad pediatrica", 10))
        elif edad > 75:
            score += 12
            factores.append(("Edad avanzada", 12))
        elif edad > 60:
            score += 6
            factores.append(("Edad mayor", 6))

        # Factor conciencia
        conciencia_puntos = {"Alerta": 0, "Verbal": 20, "Dolor": 30, "Inconsciente": 50}
        puntos_conc = conciencia_puntos.get(conc, 0)
        if puntos_conc > 0:
            score += puntos_conc
            factores.append((f"Conciencia: {conc}", puntos_conc))

        # Factor FC
        fc = sv.get("frecuencia_cardiaca", 72)
        if fc < 40 or fc > 160:
            score += 20
            factores.append(("FC critica", 20))
        elif fc < 50 or fc > 120:
            score += 10
            factores.append(("FC alterada", 10))

        # Factor SpO2
        spo2 = sv.get("saturacion_oxigeno", 98)
        if spo2 < 85:
            score += 25
            factores.append(("SpO2 critica", 25))
        elif spo2 < 90:
            score += 18
            factores.append(("SpO2 severamente baja", 18))
        elif spo2 < 94:
            score += 8
            factores.append(("SpO2 reducida", 8))

        # Factor PAS
        pas = sv.get("presion_sistolica", 120)
        if pas < 70:
            score += 22
            factores.append(("PAS critica", 22))
        elif pas < 90:
            score += 12
            factores.append(("PAS baja", 12))
        elif pas > 200:
            score += 15
            factores.append(("PAS hipertensiva severa", 15))

        # Factor sintomas
        if sx.get("convulsiones"):
            score += 20
            factores.append(("Convulsiones", 20))
        if sx.get("dolor_toracico"):
            score += 15
            factores.append(("Dolor toracico", 15))
        if sx.get("dificultad_respiratoria"):
            score += 12
            factores.append(("Dificultad respiratoria", 12))
        if sx.get("sangrado_activo"):
            score += 18
            factores.append(("Sangrado activo", 18))
        if sx.get("alteracion_conducta"):
            score += 10
            factores.append(("Alteracion conducta", 10))

        # Factor temperatura
        temp = sv.get("temperatura", 36.5)
        if temp > 40:
            score += 12
            factores.append(("Fiebre hiperpira", 12))
        elif temp < 34:
            score += 15
            factores.append(("Hipotermia severa", 15))

        score = min(score, 100)

        # Clasificacion
        if score >= 80:
            nivel_riesgo = "Critico"
        elif score >= 55:
            nivel_riesgo = "Alto"
        elif score >= 30:
            nivel_riesgo = "Moderado"
        else:
            nivel_riesgo = "Bajo"

        return {
            "score": score,
            "nivel_riesgo": nivel_riesgo,
            "factores": sorted(factores, key=lambda x: x[1], reverse=True),
            "num_factores": len(factores)
        }

    def inferir_diagnosticos(self, datos: dict) -> list[DiagnosticoDiferencial]:
        """
        Infiere diagnosticos diferenciales basado en patron sintomatico.
        Usa matching de patrones con ponderacion.
        """
        sx = datos.get("sintomas", {})
        edad = datos.get("edad", 30)
        temp = datos.get("signos_vitales", {}).get("temperatura", 36.5)

        self.diagnosticos = []

        for patron in PATRONES_DIAGNOSTICOS:
            # Verificar requisitos minimos
            requiere = patron["requiere"]
            cumple = True

            for key, val in requiere.items():
                if key == "edad_min":
                    if edad < val:
                        cumple = False
                        break
                elif key == "edad_menor_5":
                    if not (edad < 5):
                        cumple = False
                        break
                elif key in sx:
                    if sx[key] != val:
                        cumple = False
                        break
                elif key == "fiebre":
                    if temp < 38.0:
                        cumple = False
                        break
                elif key == "crisis_hipertensiva":
                    pas = datos.get("signos_vitales", {}).get("presion_sistolica", 120)
                    pad = datos.get("signos_vitales", {}).get("presion_diastolica", 80)
                    if not (pas > 200 or pad > 120):
                        cumple = False
                        break

            if not cumple:
                continue

            # Verificar exclusiones
            excluye = patron.get("excluye", set())
            excluido = False
            for key in excluye:
                if key == "fiebre":
                    if temp >= 38.0:
                        excluido = True
                        break
                elif key == "crisis_hipertensiva":
                    pas_val = datos.get("signos_vitales", {}).get("presion_sistolica", 120)
                    pad_val = datos.get("signos_vitales", {}).get("presion_diastolica", 80)
                    if pas_val > 200 or pad_val > 120:
                        excluido = True
                        break
                elif key in sx and sx[key]:
                    excluido = True
                    break
            if excluido:
                continue

            # Calcular probabilidad con evidencia
            evidencia = []
            prob = patron["peso_base"]

            # Boost por asociaciones
            asocia = patron.get("asocia", [])
            for key in asocia:
                if key in sx and sx[key]:
                    evidencia.append(f"+ {key}")
                    prob += 0.1

            prob = min(prob, 0.95)

            self.diagnosticos.append(DiagnosticoDiferencial(
                codigo=patron["id"],
                nombre=patron["nombre"],
                especialidad=patron["especialidad"],
                probabilidad=round(prob, 2),
                evidencia=evidencia if evidencia else ["Patron basico compatible"],
                estudios_sugeridos=patron["estudios"],
                conducta=patron["conducta"]
            ))

        # Ordenar por probabilidad
        self.diagnosticos.sort(key=lambda d: d.probabilidad, reverse=True)
        return self.diagnosticos[:5]  # Top 5

    def clasificar_todos_los_protocolos(self, nivel_motor: int, sintomas: dict = None) -> dict:
        """
        Clasifica al paciente en todos los protocolos de triaje disponibles.
        """
        return {
            "esi": ProtocoloESI.clasificar(nivel_motor),
            "mts": ProtocoloMTS.clasificar(nivel_motor, sintomas),
            "ctas": ProtocoloCTAS.clasificar(nivel_motor),
            "ats": ProtocoloATS.clasificar(nivel_motor),
        }


# =============================================================================
# FUNCION PUBLICA
# =============================================================================

def obtener_soporte_clinico_completo(datos: dict, nivel_motor: int) -> dict:
    """
    Genera el soporte clinico completo para un paciente.
    
    Returns:
        - diagnosticos: lista de diagnosticos diferenciales
        - score_riesgo: score multifactorizado
        - protocolos: clasificacion en todos los protocolos
    """
    motor = MotorSoporteClinico()
    diagnosticos = motor.inferir_diagnosticos(datos)
    score = motor.calcular_score_riesgo(datos)
    protocolos = motor.clasificar_todos_los_protocolos(nivel_motor, datos.get("sintomas"))

    return {
        "diagnosticos": [
            {
                "codigo": d.codigo,
                "nombre": d.nombre,
                "especialidad": d.especialidad,
                "probabilidad": d.probabilidad,
                "evidencia": d.evidencia,
                "estudios_sugeridos": d.estudios_sugeridos,
                "conducta": d.conducta,
            }
            for d in diagnosticos
        ],
        "score_riesgo": score,
        "protocolos": protocolos,
    }
