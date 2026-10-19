"""
knowledge_base.py - Base de Conocimiento y Sistema de Explicaciones
====================================================================
Implementa los componentes fundamentales de un Sistema Experto:

1. BASE DE CONOCIMIENTO (KB):
   - Reglas de produccion IF-THEN con factores de confianza
   - Metareglas (reglas sobre reglas)
   - Hechos clínicos del paciente

2. SISTEMA DE EXPLICACIONES:
   - WHY: por qué se activó una regla
   - HOW: cómo se llegó a un结论
   - TRAZA: camino completo de inferencia

3. ARBOL DE DECISION:
   - Estructura visual del proceso de decision
   - Nodo de decision -> rama -> resultado

Conceptos de Sistemas Expertos (Feigenbaum, 1982):
- Separación del conocimiento del mecanismo de inferencia
- Capacidad de explicar su razonamiento
- Uso de hechos inciertos y reglas con confianza
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# =============================================================================
# HECHOS CLINICOS
# =============================================================================

@dataclass
class Hecho:
    """
    Representa un hecho clinico establecido sobre el paciente.
    
    Un hecho es una afirmación verdadera o falsa con un factor de confianza.
    Ejemplo: ("hipoxemia_severa", True, 0.95) = "El paciente tiene hipoxemia severa con 95% de confianza"
    """
    id: str
    descripcion: str
    valor: Any
    confianza: float = 1.0  # Factor de confianza [0, 1]
    fuente: str = "signos_vitales"  # De donde se obtuvo
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# =============================================================================
# REGLAS DE PRODUCCION
# =============================================================================

@dataclass
class ReglaProduccion:
    """
    Regla de produccion IF-THEN con factor de confianza.
    
    Estructura:
        IF <condiciones> THEN <conclusion> CF:<confianza>
    
    Ejemplo:
        IF saturacion_oxigeno < 90 THEN riesgo_vital_critico CF:0.98
    
    El factor de confianza (CF) representa cuan seguro esta el experto
    en que esta regla es correcta. CF=1.0 significa certeza total.
    """
    id: str
    nombre: str
    descripcion: str
    condiciones: list[dict]  # [{"hecho": "...", "operador": "<", "valor": 90}]
    conclusion: str
    nivel_asignado: int | None = None  # Nivel de triaje si la regla es decisiva
    confianza: float = 1.0
    prioridad: int = 0  # Mayor = se evalúa primero
    activa: bool = True
    categoria: str = "general"  # "critico", "emergencia", "urgente", etc.

    def evaluar(self, hechos: dict[str, Any]) -> tuple[bool, float, list[str]]:
        """
        Evalúa si la regla se activa con los hechos dados.
        
        Returns:
            - activa: True si todas las condiciones se cumplen
            - confianza_resultante: CF de la regla si se activa
            - condiciones_cumplidas: lista de descripciones de condiciones cumplidas
        """
        if not self.activa:
            return False, 0.0, []

        condiciones_cumplidas = []
        for cond in self.condiciones:
            hecho_id = cond["hecho"]
            operador = cond["operador"]
            valor_requerido = cond["valor"]

            if hecho_id not in hechos:
                return False, 0.0, []

            valor_actual = hechos[hecho_id]
            cumplida = False

            if operador == "<":
                cumplida = valor_actual < valor_requerido
            elif operador == "<=":
                cumplida = valor_actual <= valor_requerido
            elif operador == ">":
                cumplida = valor_actual > valor_requerido
            elif operador == ">=":
                cumplida = valor_actual >= valor_requerido
            elif operador == "==":
                cumplida = valor_actual == valor_requerido
            elif operador == "!=":
                cumplida = valor_actual != valor_requerido
            elif operador == "in":
                cumplida = valor_actual in valor_requerido

            if not cumplida:
                return False, 0.0, []

            desc = f"{hecho_id} {operador} {valor_requerido} (actual: {valor_actual})"
            condiciones_cumplidas.append(desc)

        return True, self.confianza, condiciones_cumplidas


# =============================================================================
# ARBOL DE DECISION
# =============================================================================

@dataclass
class NodoDecision:
    """
    Nodo en el arbol de decision del sistema de triaje.
    
    Tipos:
    - "condicion": nodo que evalua una condicion (ramas SI/NO)
    - "resultado": nodo hoja con nivel de triaje
    - "pregunta": nodo que necesita input adicional
    """
    id: str
    tipo: str  # "condicion", "resultado", "pregunta"
    texto: str
    valor: int | None = None  # Nivel de triaje si es nodo resultado
    color: str | None = None
    hijos: list["NodoDecision"] = field(default_factory=list)
    condition_evaluada: bool | None = None  # True/False despues de evaluar


# =============================================================================
# BASE DE CONOCIMIENTO
# =============================================================================

class BaseConocimiento:
    """
    Base de conocimiento del sistema experto de triaje.
    
    Contiene:
    - Reglas de produccion con factores de confianza
    - Arbol de decision para inferencia en cascada
    - Metodos de explicacion (WHY, HOW, TRACE)
    
    Patrón arquitectónico: Production System Architecture
    (Newell & Simon, 1972)
    """

    def __init__(self):
        self.reglas: list[ReglaProduccion] = []
        self.hechos_paciente: dict[str, Any] = {}
        self.traza_inferencia: list[dict] = []
        self.arbol: NodoDecision | None = None
        self._construir_reglas()
        self._construir_arbol()

    def _construir_reglas(self):
        """Construye la base de reglas de produccion."""
        
        # === REGLAS CRITICAS (Nivel 1) ===
        self.reglas.append(ReglaProduccion(
            "R001", "Inconsciencia",
            "Paciente sin respuesta a estimulos",
            [{"hecho": "conciencia_i", "operador": "==", "valor": True}],
            "Paciente inconsciente - riesgo vital inmediato",
            nivel_asignado=1, confianza=1.0, prioridad=100, categoria="critico"
        ))
        self.reglas.append(ReglaProduccion(
            "R002", "Convulsiones activas",
            "Convulsiones en curso o recientes",
            [{"hecho": "convulsiones", "operador": "==", "valor": True}],
            "Convulsiones activas - requiere intervencion inmediata",
            nivel_asignado=1, confianza=0.98, prioridad=100, categoria="critico"
        ))
        self.reglas.append(ReglaProduccion(
            "R003", "SpO2 critica",
            "Saturacion de oxigeno menor a 90%",
            [{"hecho": "spo2", "operador": "<", "valor": 90}],
            f"Hipoxemia severa (SpO2 < 90%) - riesgo vital",
            nivel_asignado=1, confianza=0.98, prioridad=99, categoria="critico"
        ))
        self.reglas.append(ReglaProduccion(
            "R004", "FC incompatible con vida",
            "Frecuencia cardiaca extremadamente baja",
            [{"hecho": "fc", "operador": "<=", "valor": 25}],
            "Frecuencia cardiaca incompatible con vida",
            nivel_asignado=1, confianza=0.99, prioridad=100, categoria="critico"
        ))
        self.reglas.append(ReglaProduccion(
            "R005", "Shock hipotensivo",
            "Presion sistolica critica con alteracion de conciencia",
            [
                {"hecho": "pas", "operador": "<", "valor": 80},
                {"hecho": "conciencia_alerta", "operador": "==", "valor": False}
            ],
            "Shock hipotensivo con compromiso neurológico",
            nivel_asignado=1, confianza=0.97, prioridad=99, categoria="critico"
        ))
        self.reglas.append(ReglaProduccion(
            "R006", "Sangrado + hipotension",
            "Sangrado activo con presion arterial baja",
            [
                {"hecho": "sangrado_activo", "operador": "==", "valor": True},
                {"hecho": "pas", "operador": "<", "valor": 90}
            ],
            "Hemorragia activa con inestabilidad hemodinamica",
            nivel_asignado=1, confianza=0.96, prioridad=98, categoria="critico"
        ))

        # === REGLAS DE EMERGENCIA (Nivel 2) ===
        self.reglas.append(ReglaProduccion(
            "R010", "Alteracion de conciencia",
            "Nivel de conciencia alterado (Verbal o Dolor)",
            [{"hecho": "conciencia_alerta", "operador": "==", "valor": False}],
            "Alteracion del nivel de conciencia",
            nivel_asignado=2, confianza=0.95, prioridad=90, categoria="emergencia"
        ))
        self.reglas.append(ReglaProduccion(
            "R011", "Dolor toracico",
            "Dolor o malestar en el pecho",
            [{"hecho": "dolor_toracico", "operador": "==", "valor": True}],
            "Dolor toracico - descartar etiologia cardiaca",
            nivel_asignado=2, confianza=0.92, prioridad=88, categoria="emergencia"
        ))
        self.reglas.append(ReglaProduccion(
            "R012", "Dificultad respiratoria severa",
            "Disnea con desaturacion significativa",
            [
                {"hecho": "dificultad_respiratoria", "operador": "==", "valor": True},
                {"hecho": "spo2", "operador": "<", "valor": 94}
            ],
            "Insuficiencia respiratoria aguda",
            nivel_asignado=2, confianza=0.94, prioridad=87, categoria="emergencia"
        ))
        self.reglas.append(ReglaProduccion(
            "R013", "Taquicardia severa",
            "FC mayor a 150 lpm sin causa aparente",
            [
                {"hecho": "fc", "operador": ">", "valor": 150},
                {"hecho": "dolor_toracico", "operador": "==", "valor": False}
            ],
            "Taquicardia severa - evaluar causa",
            nivel_asignado=2, confianza=0.88, prioridad=85, categoria="emergencia"
        ))
        self.reglas.append(ReglaProduccion(
            "R014", "Crisis hipertensiva",
            "PAS > 200 o PAD > 120 mmHg",
            [{"hecho": "crisis_hipertensiva", "operador": "==", "valor": True}],
            "Crisis hipertensiva - riesgo de ACV",
            nivel_asignado=2, confianza=0.9, prioridad=86, categoria="emergencia"
        ))
        self.reglas.append(ReglaProduccion(
            "R015", "Pediatrico critico",
            "Neonato/infante con fiebre o dificultad respiratoria",
            [
                {"hecho": "edad_menor_2", "operador": "==", "valor": True},
                {"hecho": "fiebre", "operador": "==", "valor": True}
            ],
            "Paciente pediatrico de alto riesgo",
            nivel_asignado=2, confianza=0.85, prioridad=84, categoria="emergencia"
        ))

        # === REGLAS DE URGENTE (Nivel 3) ===
        self.reglas.append(ReglaProduccion(
            "R020", "Multiples alteraciones vitales",
            "2 o mas constantes vitales fuera de rango",
            [{"hecho": "num_alteraciones_vitales", "operador": ">=", "valor": 2}],
            "Multiples alteraciones en signos vitales",
            nivel_asignado=3, confianza=0.88, prioridad=70, categoria="urgente"
        ))
        self.reglas.append(ReglaProduccion(
            "R021", "Dolor intenso estable",
            "Dolor severo (EVA>=7) sin inestabilidad hemodinamica",
            [
                {"hecho": "dolor_intenso", "operador": "==", "valor": True},
                {"hecho": "pas", "operador": ">=", "valor": 90}
            ],
            "Dolor intenso con signos vitales estables",
            nivel_asignado=3, confianza=0.82, prioridad=68, categoria="urgente"
        ))
        self.reglas.append(ReglaProduccion(
            "R022", "Sangrado estable",
            "Sangrado activo sin hipotension",
            [
                {"hecho": "sangrado_activo", "operador": "==", "valor": True},
                {"hecho": "pas", "operador": ">=", "valor": 90}
            ],
            "Hemorragia activa compensada",
            nivel_asignado=3, confianza=0.85, prioridad=67, categoria="urgente"
        ))
        self.reglas.append(ReglaProduccion(
            "R023", "Fiebre con alteracion conducta",
            "Fiebre asociada a cambio de comportamiento",
            [
                {"hecho": "fiebre", "operador": "==", "valor": True},
                {"hecho": "alteracion_conducta", "operador": "==", "valor": True}
            ],
            "Fiebre con compromiso neurológico - descartar meningitis",
            nivel_asignado=3, confianza=0.8, prioridad=66, categoria="urgente"
        ))

        # === REGLAS DE MENOS URGENTE (Nivel 4) ===
        self.reglas.append(ReglaProduccion(
            "R030", "Fiebre leve",
            "Temperatura entre 38 y 39.5 C",
            [{"hecho": "fiebre_leve", "operador": "==", "valor": True}],
            "Cuadro febril sin signos de alarma",
            nivel_asignado=4, confianza=0.75, prioridad=50, categoria="menos_urgente"
        ))
        self.reglas.append(ReglaProduccion(
            "R031", "Alteracion vital leve",
            "Una sola constante vital fuera de rango normal",
            [{"hecho": "num_alteraciones_vitales", "operador": "==", "valor": 1}],
            "Alteracion aislada de signos vitales",
            nivel_asignado=4, confianza=0.7, prioridad=48, categoria="menos_urgente"
        ))

        # === REGLAS DE NO URGENTE (Nivel 5) ===
        self.reglas.append(ReglaProduccion(
            "R040", "Paciente estable",
            "Sin alteraciones vitales ni sintomas de alarma",
            [
                {"hecho": "num_alteraciones_vitales", "operador": "==", "valor": 0},
                {"hecho": "tiene_sintomas_alarma", "operador": "==", "valor": False}
            ],
            "Paciente estable sin factores de riesgo",
            nivel_asignado=5, confianza=0.9, prioridad=10, categoria="no_urgente"
        ))

    def _construir_arbol(self):
        """Construye el arbol de decision para inferencia en cascada."""
        self.arbol = NodoDecision(
            "N00", "condicion", "Paciente inconsciente o convulsiones?",
            hijos=[
                NodoDecision("N01-SI", "resultado", "NIVEL 1 - Resucitacion",
                           valor=1, color="Rojo"),
                NodoDecision("N01-NO", "condicion", "SpO2 < 90% o FC <= 25?",
                    hijos=[
                        NodoDecision("N02-SI", "resultado", "NIVEL 1 - Resucitacion",
                                   valor=1, color="Rojo"),
                        NodoDecision("N02-NO", "condicion", "PAS < 80 + conciencia alterada?",
                            hijos=[
                                NodoDecision("N03-SI", "resultado", "NIVEL 1 - Resucitacion",
                                           valor=1, color="Rojo"),
                                NodoDecision("N03-NO", "condicion", "Dolor toracico o alteracion conciencia?",
                                    hijos=[
                                        NodoDecision("N04-SI", "resultado", "NIVEL 2 - Emergencia",
                                                   valor=2, color="Naranja"),
                                        NodoDecision("N04-NO", "condicion", "SpO2 < 94 + dificultad respiratoria?",
                                            hijos=[
                                                NodoDecision("N05-SI", "resultado", "NIVEL 2 - Emergencia",
                                                           valor=2, color="Naranja"),
                                                NodoDecision("N05-NO", "condicion", "FC > 150 o crisis hipertensiva?",
                                                    hijos=[
                                                        NodoDecision("N06-SI", "resultado", "NIVEL 2 - Emergencia",
                                                                   valor=2, color="Naranja"),
                                                        NodoDecision("N06-NO", "condicion", "2+ alteraciones vitales?",
                                                            hijos=[
                                                                NodoDecision("N07-SI", "resultado", "NIVEL 3 - Urgente",
                                                                           valor=3, color="Amarillo"),
                                                                NodoDecision("N07-NO", "condicion", "Dolor intenso o sangrado estable?",
                                                                    hijos=[
                                                                        NodoDecision("N08-SI", "resultado", "NIVEL 3 - Urgente",
                                                                                   valor=3, color="Amarillo"),
                                                                        NodoDecision("N08-NO", "condicion", "1 alteracion vital leve?",
                                                                            hijos=[
                                                                                NodoDecision("N09-SI", "resultado", "NIVEL 4 - Menos Urgente",
                                                                                           valor=4, color="Verde"),
                                                                                NodoDecision("N09-NO", "resultado", "NIVEL 5 - No Urgente",
                                                                                           valor=5, color="Azul")
                                                                            ])
                                                                    ])
                                                            ])
                                                    ])
                                            ])
                                    ])
                            ])
                    ])
            ])
    def establecer_hechos(self, paciente_data: dict):
        """
        Establece los hechos del paciente a partir de los datos crudos.
        Convierte valores numericos en hechos logicos.
        """
        sv = paciente_data.get("signos_vitales", {})
        sx = paciente_data.get("sintomas", {})
        conc = paciente_data.get("nivel_conciencia", "Alerta")
        edad = paciente_data.get("edad", 30)

        fc = sv.get("frecuencia_cardiaca", 72)
        spo2 = sv.get("saturacion_oxigeno", 98)
        pas = sv.get("presion_sistolica", 120)
        pad = sv.get("presion_diastolica", 80)
        temp = sv.get("temperatura", 36.5)

        # Hechos de signos vitales
        self.hechos_paciente["fc"] = fc
        self.hechos_paciente["spo2"] = spo2
        self.hechos_paciente["pas"] = pas
        self.hechos_paciente["pad"] = pad
        self.hechos_paciente["temp"] = temp
        self.hechos_paciente["edad"] = edad

        # Hechos logicos derivados
        self.hechos_paciente["conciencia_i"] = conc == "Inconsciente"
        self.hechos_paciente["conciencia_alerta"] = conc == "Alerta"
        self.hechos_paciente["convulsiones"] = sx.get("convulsiones", False)
        self.hechos_paciente["dolor_toracico"] = sx.get("dolor_toracico", False)
        self.hechos_paciente["dificultad_respiratoria"] = sx.get("dificultad_respiratoria", False)
        self.hechos_paciente["sangrado_activo"] = sx.get("sangrado_activo", False)
        self.hechos_paciente["alteracion_conducta"] = sx.get("alteracion_conducta", False)
        self.hechos_paciente["trauma_significativo"] = sx.get("trauma_significativo", False)
        self.hechos_paciente["dolor_intenso"] = sx.get("dolor_intenso", False)

        # Hechos derivados de umbrales
        self.hechos_paciente["fiebre"] = temp >= 38.0
        self.hechos_paciente["fiebre_leve"] = 38.0 <= temp <= 39.5
        self.hechos_paciente["fiebre_alta"] = temp >= 39.5
        self.hechos_paciente["crisis_hipertensiva"] = pas > 200 or pad > 120
        self.hechos_paciente["edad_menor_2"] = edad < 2

        # Contar alteraciones vitales
        num_alt = 0
        if fc < 50 or fc > 120: num_alt += 1
        if pas < 90 or pas > 180: num_alt += 1
        if spo2 < 94: num_alt += 1
        if temp < 36.0 or temp > 38.0: num_alt += 1
        self.hechos_paciente["num_alteraciones_vitales"] = num_alt

        # Tiene sintomas de alarma
        tiene_alarma = any([
            sx.get("dolor_toracico"), sx.get("dificultad_respiratoria"),
            sx.get("sangrado_activo"), sx.get("convulsiones"),
            sx.get("alteracion_conducta"), sx.get("trauma_significativo"),
            sx.get("dolor_intenso")
        ])
        self.hechos_paciente["tiene_sintomas_alarma"] = tiene_alarma

    def forward_chaining(self) -> tuple[int, list[dict], dict]:
        """
        Ejecuta encadenamiento hacia adelante (Forward Chaining).
        
        El forward chaining parte de los hechos y aplica reglas
        para llegar a conclusiones. Es el metodo principal de
        inferencia en sistemas expertos.
        
        Returns:
            - nivel: nivel de triaje asignado
            - traza: lista de pasos de inferencia
            - explicacion: diccionario con explicaciones
        """
        self.traza_inferencia = []
        nivel_encontrado = None
        max_confianza = 0

        # Ordenar reglas por prioridad
        reglas_ordenadas = sorted(self.reglas, key=lambda r: r.prioridad, reverse=True)

        for regla in reglas_ordenadas:
            if not regla.activa:
                continue

            activa, confianza, condiciones = regla.evaluar(self.hechos_paciente)

            paso = {
                "regla_id": regla.id,
                "regla_nombre": regla.nombre,
                "descripcion": regla.descripcion,
                "condiciones_evaluadas": condiciones,
                "activa": activa,
                "confianza": confianza if activa else 0,
                "conclusion": regla.conclusion if activa else None,
                "nivel": regla.nivel_asignado if activa else None,
            }
            self.traza_inferencia.append(paso)

            if activa and regla.nivel_asignado is not None:
                if nivel_encontrado is None or confianza > max_confianza:
                    nivel_encontrado = regla.nivel_asignado
                    max_confianza = confianza

        if nivel_encontrado is None:
            nivel_encontrado = 5

        explicacion = self._generar_explicacion(nivel_encontrado)
        return nivel_encontrado, self.traza_inferencia, explicacion

    def _generar_explicacion(self, nivel: int) -> dict:
        """
        Genera explicaciones para la decision tomada.
        Implementa los 3 tipos de explicacion de sistemas expertos:
        - WHY: por que se activo una regla
        - HOW: como se llego a la conclusion
        - TRACE: camino completo de inferencia
        """
        reglas_activadas = [p for p in self.traza_inferencia if p["activa"]]
        reglas_nivel = [p for p in reglas_activadas if p["nivel"] == nivel]

        # WHY: Por que se asigno este nivel?
        why = []
        for r in reglas_nivel:
            why.append({
                "regla": r["regla_id"],
                "nombre": r["regla_nombre"],
                "razon": r["conclusion"],
                "confianza": r["confianza"],
                "evidencia": r["condiciones_evaluadas"]
            })

        # HOW: Como llego a esta conclusion?
        how = {
            "metodo": "Forward Chaining (encadenamiento hacia adelante)",
            "reglas_evaluadas": len(self.traza_inferencia),
            "reglas_activadas": len(reglas_activadas),
            "nivel_asignado": nivel,
            "factor_confianza_max": max((r["confianza"] for r in reglas_nivel), default=0),
        }

        # TRACE: Camino completo
        trace = []
        for paso in self.traza_inferencia:
            trace.append({
                "paso": paso["regla_id"],
                "evaluacion": f"IF {paso['descripcion']}",
                "resultado": "CUMPLE" if paso["activa"] else "NO CUMPLE",
                "confianza": paso["confianza"] if paso["activa"] else 0,
                "nivel_propuesto": paso["nivel"]
            })

        return {"why": why, "how": how, "trace": trace}

    def consultar_regla(self, regla_id: str) -> ReglaProduccion | None:
        """Consulta una regla por su ID."""
        for r in self.reglas:
            if r.id == regla_id:
                return r
        return None

    def listar_reglas_activas(self) -> list[dict]:
        """Lista todas las reglas activas con su informacion."""
        return [
            {
                "id": r.id,
                "nombre": r.nombre,
                "descripcion": r.descripcion,
                "confianza": r.confianza,
                "nivel": r.nivel_asignado,
                "categoria": r.categoria,
                "activa": r.activa,
            }
            for r in self.reglas if r.activa
        ]
