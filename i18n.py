"""
i18n.py - Internacionalización ES / QU (Quechua Boliviano)
==========================================================
Traduce la salida del motor de triaje (color, motivo clinico,
recomendacion y signos de alarma) a quechua sureño de Bolivia.
El backend siempre guarda en español en MySQL; solo se traduce
la respuesta de la API cuando el cliente envia idioma="qu".
"""

from typing import Literal

Idioma = Literal["es", "qu"]

# =============================================================================
# DICCIONARIO ES -> QU (Quechua Boliviano, ortografia standard)
# =============================================================================

_COLORES = {
    "Rojo": "Puka",
    "Naranja": "Q'illi",
    "Amarillo": "Q'illu",
    "Verde": "Q'umis",
    "Azul": "Anqas",
}

_ALERTAS = {
    "Hipoxemia severa": "Sayk'a uraymi",
    "Bradicardia severa/muerte cardíaca": "Yuyaynin qalltaqmi",
    "Shock hipotensivo": "Sami uraymi",
    "Hemorragia activa con inestabilidad": "Wachuy awaq, sami tiksyasqa",
    "Alteración neurológica": "Yuyay tiksyasqa",
    "Dolor torácico": "K'uchi nan",
    "Insuficiencia respiratoria": "Samanay manchay",
    "Taquicardia compensatoria": "Yuyaynin utqallan",
    "Taquicardia severa": "Yuyaynin hatun utqallan",
    "Bradicardia": "Yuyaynin qalltaq",
    "Hipotensión": "Sami uray",
    "Fiebre con compromiso neurológico": "Q'uñiy yuyay tiksyasqa",
    "Crisis hipertensiva": "Sami hatunmi",
    "Paciente pediatrico de riesgo": "Ukuq paqarisqan",
    "Hemorragia activa compensada": "Wachuy awaq",
}

_RECOMENDACIONES = {
    "Intervención inmediata: activar código de trauma/paro cardíaco":
        "Mushukllan ruray: trauma/paro yuyaynin chakin",
    "Atención preferente: maximal 10 minutos, monitoreo continuo":
        "Ñawpaqman rikch'ay: 10 minutokunapi, awaq rikch'ay",
    "Evaluación médica: maximal 30 minutos, posible estancia":
        "Yachaq rikch'ay: 30 minutokunapi, tiyanakuy",
    "Consulta médica: maximal 60 minutos, alta probable":
        "Yachaq rimanakuy: 60 minutokunapi, apakuy",
    "Consulta de medicina general: maximal 120 minutos":
        "General yachaq rimanakuy: 120 minutokunapi",
}

# Frases fijas y templates del motor (reemplazo por fragmentos)
_FRASES = {
    "Paciente inconsciente (sin respuesta a estímulos)":
        "Ukuq manan yuyarqoq (manan yuyayta qhawarqoq)",
    "Convulsiones activas": "Q'uñiy awaqmi",
    "Frecuencia cardíaca incompatível con vida": "Yuyaynin manan ruwanchu",
    "Dolor torácico reportado": "K'uchi nan rimasqa",
    "Dificultad respiratoria con taquicardia": "Samanay tiksyasqa yuyaynin utqallanmi",
    "Paciente estable, sin alteraciones vitales ni síntomas de alarma.":
        "Ukuq samaraq, manan sami tiksyasqa, manan yupaq yarqaychu.",
    "Múltiples alteraciones vitales": "Hatun sami rikch'aykuna tiksyasqan",
    "Dolor intenso (EVA >= 7) con signos vitales estables":
        "Hatun nan (EVA >= 7) samaraq sami rikch'ayninwan",
    "Sangrado activo con presión arterial conservada":
        "Wachuy awaq, wachu sami samaraq",
    "Trauma significativo que requiere múltiples evaluaciones":
        "Hatun machuwanakuy, hatun rikch'aytachu",
    "Fiebre con alteración conductual": "Q'uñiy yuyay tiksyasqanwan",
    "Dificultad respiratoria leve con SpO2 conservada":
        "Samanay tiksyasqa leqtam, SpO2 samaraq",
    "Shock hipovolémico: PAS ": "Sami uraymi: PAS ",
    "con alteración de conciencia": "yuyay tiksyasqanwan",
    "Sangrado activo con hipotensión (PAS: ": "Wachuy awaq sami uraymi (PAS: ",
    "Nivel de conciencia alterado: ": "Yuyaynin tiksyasqan: ",
    "Dificultad respiratoria con SpO2 ": "Samanay tiksyasqa SpO2 ",
    "Saturación de oxígeno crítica: ": "Sayk'a uraymi: ",
    " (umbral: <": " (umbral: <",
    "Taquicardia severa: ": "Yuyaynin utqallanmi: ",
    " lpm": " lpm",
    "Bradicardia sintomática: ": "Yuyaynin qalltaqmi: ",
    "Hipotensión arterial: PAS ": "Wachu sami uraymi: PAS ",
    "Fiebre alta (": "Q'uñiy hatunmi (",
    ") con alteración de conciencia": ") yuyay tiksyasqanwan",
    "Crisis hipertensiva: ": "Sami hatunmi: ",
    "Paciente pediatrico (": "Ukuq paqarisqan (",
    " años) con síntomas sistémicos": " watayuq) yarqaykunawan",
    "FC alterada: ": "Yuyaynin tiksyasqan: ",
    "PAS alterada: ": "PAS tiksyasqan: ",
    "SpO2 reducida: ": "SpO2 uray: ",
    "Fiebre: ": "Q'uñiy: ",
    "Hipotermia: ": "Ch'iqay: ",
    " constantes vitales alteradas": " sami rikch'aykuna tiksyasqan",
    "umbral: >": "umbral: >",
}


def _traducir_alerta(texto: str, n: int | None = None) -> str:
    """Traduce un signo de alarma a quechua."""
    if n is not None:
        return f"{n} sami rikch'aykuna tiksyasqan"
    return _ALERTAS.get(texto, texto)


def _traducir_frase(texto: str) -> str:
    """Traduce motivo clinico aplicando reemplazos de frases ES->QU."""
    if not texto:
        return texto
    resultado = texto
    # Aplicar reemplazos de mas largos a mas cortos para evitar solapes
    for es, qu in sorted(_FRASES.items(), key=lambda x: -len(x[0])):
        if es in resultado:
            resultado = resultado.replace(es, qu)
    return resultado


def traducir_resultado(resultado, idioma: Idioma = "es"):
    """
    Traduce un ResultadoTriaje a quechua (in-place sobre copia de campos).
    No modifica el objeto original (se usa sobre una copia antes de la respuesta).
    """
    if idioma != "qu":
        return resultado

    resultado.color = _COLORES.get(resultado.color, resultado.color)
    resultado.recomendacion = _RECOMENDACIONES.get(
        resultado.recomendacion, resultado.recomendacion
    )
    resultado.motivo_clinico = _traducir_frase(resultado.motivo_clinico)

    alertas_trad = []
    for a in resultado.signos_alerta:
        # Manejar "{n} constantes vitales alteradas"
        if a.endswith(" constantes vitales alteradas"):
            try:
                n = int(a.split(" ")[0])
                alertas_trad.append(_traducir_alerta(a, n=n))
                continue
            except ValueError:
                pass
        alertas_trad.append(_traducir_alerta(a))
    resultado.signos_alerta = alertas_trad
    return resultado
