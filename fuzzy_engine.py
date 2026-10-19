"""
fuzzy_engine.py - Motor de Logica Difusa para Triaje
=====================================================
Implementa un sistema de inferencia difusa (Fuzzy Inference System - FIS)
para clasificacion mas natural y matematicamente robusta.

Conceptos clave del paradigma difuso:
- Pertenecia (membership): grado en que un valor pertenece a un conjunto difuso
- Variables linguisticas: "baja", "normal", "alta", "muy alta"
- Reglas difusas: IF condicion THEN consecuencia
- Defuzzificacion: conversion de salida difusa a valor crisp

Referencia: Zadeh, L.A. (1965). "Fuzzy sets". Information and Control, 8(3), 338-353.
"""

import math
from dataclasses import dataclass, field


# =============================================================================
# FUNCIONES DE PERTENECIA (MEMBERSHIP FUNCTIONS)
# =============================================================================

def trimf(x: float, params: tuple[float, float, float]) -> float:
    """
    Funcion de pertenencia triangular.
    
    Parametros (a, b, c):
    - a: punto donde empieza a subir
    - b: punto maximo (pertenencia = 1)
    - c: punto donde baja a 0
    
    Retorna valor de pertenencia en [0, 1]
    """
    a, b, c = params
    if x <= a or x >= c:
        return 0.0
    if x == b:
        return 1.0
    if x < b:
        return (x - a) / (b - a) if b != a else 0.0
    return (c - x) / (c - b) if c != b else 0.0


def trapmf(x: float, params: tuple[float, float, float, float]) -> float:
    """
    Funcion de pertenencia trapezoidal.
    
    Parametros (a, b, c, d):
    - a, d: puntos donde la pertenencia es 0
    - b, c: puntos donde la pertenencia es 1
    """
    a, b, c, d = params
    if x <= a or x >= d:
        return 0.0
    if b <= x <= c:
        return 1.0
    if a < x < b:
        return (x - a) / (b - a) if b != a else 0.0
    return (d - x) / (d - c) if d != c else 0.0


def gaussmf(x: float, params: tuple[float, float]) -> float:
    """
    Funcion de pertenencia gaussiana.
    
    Parametros (media, desviacion_estandar)
    """
    media, sigma = params
    if sigma == 0:
        return 1.0 if x == media else 0.0
    return math.exp(-((x - media) ** 2) / (2 * sigma ** 2))


# =============================================================================
# VARIABLES LINGUISTICAS DIFUSAS
# =============================================================================

@dataclass
class VariableLinguistica:
    """
    Representa una variable linguistica difusa.
    Ejemplo: "Frecuencia Cardiaca" con conjuntos {Baja, Normal, Alta, MuyAlta}
    """
    nombre: str
    unit: str
    rango: tuple[float, float]
    conjuntos: dict[str, tuple] = field(default_factory=dict)

    def agregar_conjunto(self, nombre: str, params: tuple, tipo: str = "trimf"):
        self.conjuntos[nombre] = {"params": params, "tipo": tipo}

    def evaluar(self, valor: float) -> dict[str, float]:
        """Retorna el grado de pertenencia de un valor a cada conjunto."""
        resultado = {}
        for nombre, conf in self.conjuntos.items():
            if conf["tipo"] == "trimf":
                resultado[nombre] = trimf(valor, conf["params"])
            elif conf["tipo"] == "trapmf":
                resultado[nombre] = trapmf(valor, conf["params"])
            elif conf["tipo"] == "gaussmf":
                resultado[nombre] = gaussmf(valor, conf["params"])
            else:
                resultado[nombre] = 0.0
        return resultado


# =============================================================================
# BASE DE REGLAS DIFUSAS
# =============================================================================

@dataclass
class ReglaDifusa:
    """
    Regla IF-THEN difusa.
    
    antecedentes: lista de (variable, conjunto) con operador AND entre ellos
    consecuente: (variable_salida, conjunto_salida)
    peso: peso de la regla en [0, 1]
    """
    id: str
    descripcion: str
    antecedentes: list[tuple[str, str]]
    consecuente: tuple[str, str]
    peso: float = 1.0
    activa: bool = True


# =============================================================================
# MOTOR DE INFERENCIA DIFUSA (Mamdani)
# =============================================================================

class MotorDifuso:
    """
    Motor de inferencia difusa tipo Mamdani.
    
    Pasos:
    1. Fuzzificacion: convertir entradas crisp a grados de pertenencia
    2. Evaluacion de reglas: calcular fuerza de cada regla
    3. Agregacion: combinar salidas de todas las reglas
    4. Defuzzificacion: convertir salida difusa a valor crisp
    
    Utiliza metodo del centroide para defuzzificacion.
    """

    def __init__(self):
        self.variables_entrada: dict[str, VariableLinguistica] = {}
        self.variable_salida: VariableLinguistica | None = None
        self.reglas: list[ReglaDifusa] = []

    def agregar_variable_entrada(self, var: VariableLinguistica):
        self.variables_entrada[var.nombre] = var

    def agregar_variable_salida(self, var: VariableLinguistica):
        self.variable_salida = var

    def agregar_regla(self, regla: ReglaDifusa):
        self.reglas.append(regla)

    def fuzzificar(self, entradas: dict[str, float]) -> dict[str, dict[str, float]]:
        """Paso 1: Fuzzificar todas las entradas."""
        resultado = {}
        for nombre_var, valor in entradas.items():
            if nombre_var in self.variables_entrada:
                resultado[nombre_var] = self.variables_entrada[nombre_var].evaluar(valor)
        return resultado

    def evaluar_reglas(self, grados_pertenencia: dict[str, dict[str, float]]) -> list[tuple[ReglaDifusa, float]]:
        """
        Paso 2: Evaluar cada regla y calcular su fuerza.
        Operador AND = min de los antecedentes.
        """
        resultados = []
        for regla in self.reglas:
            if not regla.activa:
                continue

            fuerzas = []
            for var_name, conjunto in regla.antecedentes:
                if var_name in grados_pertenencia:
                    fuerza = grados_pertenencia[var_name].get(conjunto, 0.0)
                    fuerzas.append(fuerza)

            if fuerzas:
                fuerza_regla = min(fuerzas) * regla.peso
                resultados.append((regla, fuerza_regla))

        return resultados

    def defuzzificar(self, fuerzas_reglas: list[tuple[ReglaDifusa, float]]) -> float:
        """
        Paso 4: Defuzzificacion por metodo del centroide.
        """
        if not self.variable_salida or not fuerzas_reglas:
            return 0.0

        # Muestrear el rango de salida
        min_salida, max_salida = self.variable_salida.rango
        n_puntos = 200
        paso = (max_salida - min_salida) / n_puntos

        numerador = 0.0
        denominador = 0.0

        for i in range(n_puntos + 1):
            x = min_salida + i * paso

            # Agregar contribucion de cada regla
            valor_agregado = 0.0
            for regla, fuerza in fuerzas_reglas:
                var_sal, conj_sal = regla.consecuente
                if self.variable_salida and var_sal == self.variable_salida.nombre:
                    pertenencia = self.variable_salida.evaluar(x).get(conj_sal, 0.0)
                    valor_agregado = max(valor_agregado, min(pertenencia, fuerza))

            numerador += x * valor_agregado
            denominador += valor_agregado

        if denominador == 0:
            # Si no hay area, usar ponderacion simple
            suma_ponderada = sum(f * self.variable_salida.rango[0] for _, f in fuerzas_reglas)
            suma_pesos = sum(f for _, f in fuerzas_reglas)
            if suma_pesos > 0:
                return suma_ponderada / suma_pesos + (max_salida - min_salida) / 2
            return (min_salida + max_salida) / 2

        return numerador / denominador

    def inferir(self, entradas: dict[str, float]) -> tuple[float, dict]:
        """
        Metodo principal: ejecuta el pipeline completo de inferencia.
        
        Retorna:
        - valor_crisp: resultado defuzzificado
        - metadata: informacion detallada del proceso
        """
        # Paso 1: Fuzzificacion
        grados = self.fuzzificar(entradas)

        # Paso 2: Evaluacion de reglas
        fuerzas = self.evaluar_reglas(grados)

        # Paso 3: Defuzzificacion
        resultado = self.defuzzificar(fuerzas)

        metadata = {
            "grados_pertenencia": grados,
            "fuerzas_reglas": [(r.id, r.descripcion, f) for r, f in fuerzas],
            "num_reglas_activas": len([f for _, f in fuerzas if f > 0]),
        }

        return resultado, metadata


# =============================================================================
# CONSTRUCCION DEL SISTEMA DIFUSO DE TRIAJE
# =============================================================================

def crear_sistema_difuso_triaje() -> MotorDifuso:
    """
    Construye y configura el motor difuso para evaluacion de triaje.
    
    Variables de entrada:
    - FC: Frecuencia cardiaca (20-200 lpm)
    - SpO2: Saturacion de oxigeno (70-100%)
    - PAS: Presion arterial sistolica (40-200 mmHg)
    - Temp: Temperatura (34-42 C)
    - Edad: Edad del paciente (0-120 anos)
    
    Variable de salida:
    - Riesgo: Score de riesgo (0-100)
    """
    motor = MotorDifuso()

    # --- FC ---
    fc = VariableLinguistica("FC", "lpm", (20, 200))
    fc.agregar_conjunto("MuyBaja", (20, 20, 35, 50), "trapmf")
    fc.agregar_conjunto("Baja", (35, 50, 65), "trimf")
    fc.agregar_conjunto("Normal", (55, 80, 105), "trimf")
    fc.agregar_conjunto("Alta", (95, 120, 145), "trimf")
    fc.agregar_conjunto("MuyAlta", (135, 160, 160, 200), "trapmf")
    motor.agregar_variable_entrada(fc)

    # --- SpO2 ---
    spo2 = VariableLinguistica("SpO2", "%", (70, 100))
    spo2.agregar_conjunto("Critica", (70, 70, 80, 90), "trapmf")
    spo2.agregar_conjunto("Baja", (80, 90, 95), "trimf")
    spo2.agregar_conjunto("Normal", (93, 97, 100), "trimf")
    spo2.agregar_conjunto("Optima", (97, 100, 100, 100), "trapmf")
    motor.agregar_variable_entrada(spo2)

    # --- PAS ---
    pas = VariableLinguistica("PAS", "mmHg", (40, 200))
    pas.agregar_conjunto("Critica", (40, 40, 60, 80), "trapmf")
    pas.agregar_conjunto("Baja", (70, 88, 98), "trimf")
    pas.agregar_conjunto("Normal", (90, 115, 140), "trimf")
    pas.agregar_conjunto("Alta", (135, 165, 185), "trimf")
    pas.agregar_conjunto("MuyAlta", (180, 200, 200, 200), "trapmf")
    motor.agregar_variable_entrada(pas)

    # --- Temp ---
    temp = VariableLinguistica("Temp", "C", (34, 42))
    temp.agregar_conjunto("Hipotermia", (34, 34, 34, 36), "trapmf")
    temp.agregar_conjunto("Baja", (35, 36, 36.5), "trimf")
    temp.agregar_conjunto("Normal", (36, 36.7, 37.5), "trimf")
    temp.agregar_conjunto("Fiebre", (37.2, 38.5, 39.5), "trimf")
    temp.agregar_conjunto("FiebreAlta", (39, 40.5, 42, 42), "trapmf")
    motor.agregar_variable_entrada(temp)

    # --- Edad ---
    edad = VariableLinguistica("Edad", "anos", (0, 120))
    edad.agregar_conjunto("Neonato", (0, 0, 0, 2), "trapmf")
    edad.agregar_conjunto("Infante", (0, 2, 5), "trimf")
    edad.agregar_conjunto("Nino", (3, 10, 15), "trimf")
    edad.agregar_conjunto("Adulto", (16, 40, 65), "trimf")
    edad.agregar_conjunto("Mayor", (60, 80, 120, 120), "trapmf")
    motor.agregar_variable_entrada(edad)

    # --- Salida: Riesgo ---
    riesgo = VariableLinguistica("Riesgo", "score", (0, 100))
    riesgo.agregar_conjunto("Bajo", (0, 0, 0, 35), "trapmf")
    riesgo.agregar_conjunto("Moderado", (20, 40, 60), "trimf")
    riesgo.agregar_conjunto("Alto", (50, 70, 85), "trimf")
    riesgo.agregar_conjunto("Critico", (80, 100, 100, 100), "trapmf")
    motor.agregar_variable_salida(riesgo)

    # --- Reglas difusas ---
    # Cada regla codifica conocimiento clinico experto

    # Riesgo critico
    motor.agregar_regla(ReglaDifusa(
        "R01", "FC muy alta + SpO2 critica -> Riesgo critico",
        [("FC", "MuyAlta"), ("SpO2", "Critica")], ("Riesgo", "Critico"), 1.0
    ))
    motor.agregar_regla(ReglaDifusa(
        "R02", "FC muy baja -> Riesgo critico",
        [("FC", "MuyBaja")], ("Riesgo", "Critico"), 1.0
    ))
    motor.agregar_regla(ReglaDifusa(
        "R03", "PAS critica -> Riesgo critico",
        [("PAS", "Critica")], ("Riesgo", "Critico"), 1.0
    ))
    motor.agregar_regla(ReglaDifusa(
        "R04", "SpO2 critica -> Riesgo critico",
        [("SpO2", "Critica")], ("Riesgo", "Critico"), 0.95
    ))
    motor.agregar_regla(ReglaDifusa(
        "R05", "Fiebre alta + edad mayor -> Riesgo critico",
        [("Temp", "FiebreAlta"), ("Edad", "Mayor")], ("Riesgo", "Critico"), 0.85
    ))

    # Riesgo alto
    motor.agregar_regla(ReglaDifusa(
        "R06", "FC alta + SpO2 baja -> Riesgo alto",
        [("FC", "Alta"), ("SpO2", "Baja")], ("Riesgo", "Alto"), 0.95
    ))
    motor.agregar_regla(ReglaDifusa(
        "R07", "FC alta + PAS baja -> Riesgo alto",
        [("FC", "Alta"), ("PAS", "Baja")], ("Riesgo", "Alto"), 0.9
    ))
    motor.agregar_regla(ReglaDifusa(
        "R08", "SpO2 baja + PAS baja -> Riesgo alto",
        [("SpO2", "Baja"), ("PAS", "Baja")], ("Riesgo", "Alto"), 0.95
    ))
    motor.agregar_regla(ReglaDifusa(
        "R09", "Fiebre alta + edad mayor -> Riesgo alto",
        [("Temp", "FiebreAlta"), ("Edad", "Mayor")], ("Riesgo", "Alto"), 0.8
    ))
    motor.agregar_regla(ReglaDifusa(
        "R10", "FC alta + temp fiebre -> Riesgo alto",
        [("FC", "Alta"), ("Temp", "Fiebre")], ("Riesgo", "Alto"), 0.7
    ))
    motor.agregar_regla(ReglaDifusa(
        "R11", "SpO2 baja + edad neonato -> Riesgo alto",
        [("SpO2", "Baja"), ("Edad", "Neonato")], ("Riesgo", "Alto"), 0.9
    ))
    motor.agregar_regla(ReglaDifusa(
        "R12", "PAS alta + edad mayor -> Riesgo alto",
        [("PAS", "Alta"), ("Edad", "Mayor")], ("Riesgo", "Alto"), 0.75
    ))

    # Riesgo moderado
    motor.agregar_regla(ReglaDifusa(
        "R13", "FC alta normal -> Riesgo moderado",
        [("FC", "Alta")], ("Riesgo", "Moderado"), 0.6
    ))
    motor.agregar_regla(ReglaDifusa(
        "R14", "FC baja normal -> Riesgo moderado",
        [("FC", "Baja")], ("Riesgo", "Moderado"), 0.5
    ))
    motor.agregar_regla(ReglaDifusa(
        "R15", "SpO2 baja -> Riesgo moderado",
        [("SpO2", "Baja")], ("Riesgo", "Moderado"), 0.7
    ))
    motor.agregar_regla(ReglaDifusa(
        "R16", "PAS baja -> Riesgo moderado",
        [("PAS", "Baja")], ("Riesgo", "Moderado"), 0.65
    ))
    motor.agregar_regla(ReglaDifusa(
        "R17", "Fiebre -> Riesgo moderado",
        [("Temp", "Fiebre")], ("Riesgo", "Moderado"), 0.5
    ))
    motor.agregar_regla(ReglaDifusa(
        "R18", "Edad mayor + FC normal -> Riesgo moderado",
        [("Edad", "Mayor"), ("FC", "Normal")], ("Riesgo", "Moderado"), 0.4
    ))
    motor.agregar_regla(ReglaDifusa(
        "R19", "PAS alta -> Riesgo moderado",
        [("PAS", "Alta")], ("Riesgo", "Moderado"), 0.55
    ))

    # Riesgo bajo (paciente estable)
    motor.agregar_regla(ReglaDifusa(
        "R20", "FC normal + SpO2 normal/optimas + PAS normal -> Riesgo bajo",
        [("FC", "Normal"), ("SpO2", "Normal"), ("PAS", "Normal")], ("Riesgo", "Bajo"), 0.9
    ))
    motor.agregar_regla(ReglaDifusa(
        "R21", "FC normal + SpO2 optimas + PAS normal + temp normal -> Riesgo bajo",
        [("FC", "Normal"), ("SpO2", "Optima"), ("PAS", "Normal"), ("Temp", "Normal")], ("Riesgo", "Bajo"), 0.95
    ))
    motor.agregar_regla(ReglaDifusa(
        "R22", "Todo normal + edad adulto -> Riesgo bajo",
        [("FC", "Normal"), ("SpO2", "Normal"), ("PAS", "Normal"), ("Temp", "Normal"), ("Edad", "Adulto")],
        ("Riesgo", "Bajo"), 1.0
    ))

    return motor


# =============================================================================
# FUNCION PUBLICA
# =============================================================================

def calcular_score_riesgo_difuso(fc: int, spo2: int, pas: int, temp: float, edad: int) -> tuple[float, dict]:
    """
    Calcula el score de riesgo difuso para un paciente.
    
    Args:
        fc: Frecuencia cardiaca (lpm)
        spo2: Saturacion de oxigeno (%)
        pas: Presion arterial sistolica (mmHg)
        temp: Temperatura (C)
        edad: Edad (anos)
    
    Returns:
        - score: valor de riesgo 0-100
        - metadata: grados de pertenencia y fuerzas de reglas
    """
    motor = crear_sistema_difuso_triaje()
    entradas = {
        "FC": float(fc),
        "SpO2": float(spo2),
        "PAS": float(pas),
        "Temp": temp,
        "Edad": float(edad),
    }
    return motor.inferir(entradas)
