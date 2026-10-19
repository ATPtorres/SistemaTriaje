"""
test_triaje.py - Script de pruebas del Sistema de Triaje
========================================================
Ejecuta 6 escenarios clínicos completos validando cada nivel ESI.

Uso:
    python test_triaje.py
"""

import json
from models import DatosPaciente, SignosVitales, Sintomas, NivelConciencia
from triage_engine import evaluar_triaje


# =============================================================================
# UTILIDADES
# =============================================================================

def imprimir_resultado(caso: str, resultado):
    """Imprime formateado el resultado de triaje."""
    print(f"\n{'='*70}")
    print(f"CASO: {caso}")
    print(f"{'='*70}")
    print(f"  Paciente ID     : {resultado.id_paciente}")
    print(f"  Nivel Prioridad : {resultado.nivel_prioridad}")
    print(f"  Color           : {resultado.color}")
    print(f"  Motivo Clínico  : {resultado.motivo_clinico}")
    if resultado.signos_alerta:
        print(f"  Signos de Alarma: {', '.join(resultado.signos_alerta)}")
    print(f"  Recomendación   : {resultado.recomendacion}")
    print(f"{'='*70}")


def crear_paciente(**kwargs) -> DatosPaciente:
    """Factory para crear pacientes de prueba de forma concisa."""
    sv = kwargs.pop("signos_vitales")
    sx = kwargs.pop("sintomas", Sintomas())
    nc = kwargs.pop("nivel_conciencia", NivelConciencia.A)
    return DatosPaciente(
        signos_vitales=SignosVitales(**sv),
        sintomas=sx,
        nivel_conciencia=nc,
        **kwargs
    )


# =============================================================================
# CASOS DE PRUEBA
# =============================================================================

def test_nivel_1_resucitacion():
    """
    CASO CRÍTICO: Paciente inconsciente con SpO2 baja y dolor torácico.
    Esperado: Nivel 1 - ROJO
    """
    paciente = crear_paciente(
        id_paciente="PAC-N1-001",
        edad=62,
        signos_vitales={
            "frecuencia_cardiaca": 130,
            "presion_sistolica": 85,
            "presion_diastolica": 50,
            "temperatura": 36.2,
            "saturacion_oxigeno": 82
        },
        nivel_conciencia=NivelConciencia.I,
        sintomas=Sintomas(
            dolor_toracico=True,
            dificultad_respiratoria=True
        )
    )
    resultado = evaluar_triaje(paciente)
    imprimir_resultado("NIVEL 1 - RESUCITACIÓN (Paciente inconsciente, SpO2 82%)", resultado)
    assert resultado.nivel_prioridad == 1, f"Esperado nivel 1, obtenido {resultado.nivel_prioridad}"
    assert resultado.color == "Rojo"
    print("  [PASS] ASSERT PASSED: Nivel 1 asignado correctamente")
    return resultado


def test_nivel_2_emergencia():
    """
    CASO EMERGENCIA: Paciente consciente con dolor torácico y dificultad respiratoria.
    SpO2 en 91% (no critica pero alterada) con disnea y dolor torácico.
    Esperado: Nivel 2 - NARANJA
    """
    paciente = crear_paciente(
        id_paciente="PAC-N2-001",
        edad=55,
        signos_vitales={
            "frecuencia_cardiaca": 110,
            "presion_sistolica": 100,
            "presion_diastolica": 65,
            "temperatura": 36.8,
            "saturacion_oxigeno": 91
        },
        nivel_conciencia=NivelConciencia.A,
        sintomas=Sintomas(
            dolor_toracico=True,
            dificultad_respiratoria=True
        )
    )
    resultado = evaluar_triaje(paciente)
    imprimir_resultado("NIVEL 2 - EMERGENCIA (Dolor torácico + disnea + SpO2 88%)", resultado)
    assert resultado.nivel_prioridad == 2, f"Esperado nivel 2, obtenido {resultado.nivel_prioridad}"
    assert resultado.color == "Naranja"
    print("  [PASS] ASSERT PASSED: Nivel 2 asignado correctamente")
    return resultado


def test_nivel_2_emergencia_conciencia():
    """
    CASO EMERGENCIA: Paciente confundido (responde solo a verbal) con fiebre alta.
    Esperado: Nivel 2 - NARANJA
    """
    paciente = crear_paciente(
        id_paciente="PAC-N2-002",
        edad=78,
        signos_vitales={
            "frecuencia_cardiaca": 95,
            "presion_sistolica": 110,
            "presion_diastolica": 70,
            "temperatura": 40.1,
            "saturacion_oxigeno": 93
        },
        nivel_conciencia=NivelConciencia.V,
        sintomas=Sintomas(alteracion_conducta=True)
    )
    resultado = evaluar_triaje(paciente)
    imprimir_resultado("NIVEL 2 - EMERGENCIA (Paciente confundido + fiebre 40.1°C)", resultado)
    assert resultado.nivel_prioridad == 2, f"Esperado nivel 2, obtenido {resultado.nivel_prioridad}"
    assert resultado.color == "Naranja"
    print("  [PASS] ASSERT PASSED: Nivel 2 asignado correctamente")
    return resultado


def test_nivel_3_urgente():
    """
    CASO URGENTE: Paciente con múltiples signos vitales alterados.
    FC 115, PA 92/58, T 39.2, SpO2 92%, dolor intenso.
    Esperado: Nivel 3 - AMARILLO
    """
    paciente = crear_paciente(
        id_paciente="PAC-N3-001",
        edad=45,
        signos_vitales={
            "frecuencia_cardiaca": 115,
            "presion_sistolica": 92,
            "presion_diastolica": 58,
            "temperatura": 39.2,
            "saturacion_oxigeno": 92
        },
        nivel_conciencia=NivelConciencia.A,
        sintomas=Sintomas(dolor_intenso=True)
    )
    resultado = evaluar_triaje(paciente)
    imprimir_resultado("NIVEL 3 - URGENTE (FC 115 + PA 88/55 + T 39.2 + SpO2 92% + dolor)", resultado)
    assert resultado.nivel_prioridad == 3, f"Esperado nivel 3, obtenido {resultado.nivel_prioridad}"
    assert resultado.color == "Amarillo"
    print("  [PASS] ASSERT PASSED: Nivel 3 asignado correctamente")
    return resultado


def test_nivel_4_menos_urgente():
    """
    CASO MENOS URGENTE: Paciente con fiebre leve y taquicardia leve.
    Esperado: Nivel 4 - VERDE
    """
    paciente = crear_paciente(
        id_paciente="PAC-N4-001",
        edad=30,
        signos_vitales={
            "frecuencia_cardiaca": 105,
            "presion_sistolica": 115,
            "presion_diastolica": 75,
            "temperatura": 38.5,
            "saturacion_oxigeno": 97
        },
        nivel_conciencia=NivelConciencia.A,
        sintomas=Sintomas()
    )
    resultado = evaluar_triaje(paciente)
    imprimir_resultado("NIVEL 4 - MENOS URGENTE (FC 105 + T 38.5°C, estable)", resultado)
    assert resultado.nivel_prioridad == 4, f"Esperado nivel 4, obtenido {resultado.nivel_prioridad}"
    assert resultado.color == "Verde"
    print("  [PASS] ASSERT PASSED: Nivel 4 asignado correctamente")
    return resultado


def test_nivel_5_no_urgente():
    """
    CASO NO URGENTE: Esguince sin alteraciones vitales.
    Esperado: Nivel 5 - AZUL
    """
    paciente = crear_paciente(
        id_paciente="PAC-N5-001",
        edad=25,
        signos_vitales={
            "frecuencia_cardiaca": 72,
            "presion_sistolica": 120,
            "presion_diastolica": 80,
            "temperatura": 36.5,
            "saturacion_oxigeno": 99
        },
        nivel_conciencia=NivelConciencia.A,
        sintomas=Sintomas()
    )
    resultado = evaluar_triaje(paciente)
    imprimir_resultado("NIVEL 5 - NO URGENTE (Esguince, signos vitales normales)", resultado)
    assert resultado.nivel_prioridad == 5, f"Esperado nivel 5, obtenido {resultado.nivel_prioridad}"
    assert resultado.color == "Azul"
    print("  [PASS] ASSERT PASSED: Nivel 5 asignado correctamente")
    return resultado


# =============================================================================
# CASO EXTRA: Sangrado activo con hipotensión → Nivel 1
# =============================================================================

def test_nivel_1_sangrado():
    """
    CASO CRÍTICO: Sangrado activo con hipotensión.
    Esperado: Nivel 1 - ROJO
    """
    paciente = crear_paciente(
        id_paciente="PAC-N1-002",
        edad=40,
        signos_vitales={
            "frecuencia_cardiaca": 125,
            "presion_sistolica": 78,
            "presion_diastolica": 45,
            "temperatura": 35.8,
            "saturacion_oxigeno": 94
        },
        nivel_conciencia=NivelConciencia.D,
        sintomas=Sintomas(sangrado_activo=True)
    )
    resultado = evaluar_triaje(paciente)
    imprimir_resultado("NIVEL 1 - RESUCITACIÓN (Sangrado activo + shock hipotensivo)", resultado)
    assert resultado.nivel_prioridad == 1, f"Esperado nivel 1, obtenido {resultado.nivel_prioridad}"
    assert resultado.color == "Rojo"
    print("  [PASS] ASSERT PASSED: Nivel 1 asignado correctamente")
    return resultado


# =============================================================================
# EJECUCIÓN PRINCIPAL
# =============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("  SISTEMA EXPERTO DE TRIAJE - SUITE DE PRUEBAS")
    print("  Modelo: Emergency Severity Index (ESI) - 5 Niveles")
    print("="*70)

    pruebas = [
        ("Nivel 1 - Resucitación", test_nivel_1_resucitacion),
        ("Nivel 1 - Sangrado Crítico", test_nivel_1_sangrado),
        ("Nivel 2 - Emergencia", test_nivel_2_emergencia),
        ("Nivel 2 - Emergencia Neurológica", test_nivel_2_emergencia_conciencia),
        ("Nivel 3 - Urgente", test_nivel_3_urgente),
        ("Nivel 4 - Menos Urgente", test_nivel_4_menos_urgente),
        ("Nivel 5 - No Urgente", test_nivel_5_no_urgente),
    ]

    aprobadas = 0
    fallidas = 0

    for nombre, test_fn in pruebas:
        try:
            test_fn()
            aprobadas += 1
        except AssertionError as e:
            fallidas += 1
            print(f"  [FAIL] ASSERT FAILED: {e}")
        except Exception as e:
            fallidas += 1
            print(f"  [ERROR] ERROR: {e}")

    print(f"\n{'='*70}")
    print(f"  RESUMEN: {aprobadas} aprobadas / {fallidas} fallidas de {len(pruebas)} pruebas")
    print(f"{'='*70}\n")

    if fallidas > 0:
        exit(1)
