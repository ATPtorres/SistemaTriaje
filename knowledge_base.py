"""Validated, versioned production rules and monotonic forward chaining.

Rules propose local triage priorities, not certified medical protocol decisions.
No expressions from the knowledge file are executed as Python.
"""
from __future__ import annotations

import hashlib
import json
import operator
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import (BaseModel, ConfigDict, Field, StrictBool, StrictFloat,
                      StrictInt, StrictStr, model_validator)
from models import DatosPaciente

ENGINE_VERSION = '4.0.0'
DEFAULT_KNOWLEDGE_PATH = Path(__file__).parent / 'knowledge' / 'triage_rules.json'
INPUT_TYPES = {**dict.fromkeys(('fc', 'spo2', 'pas', 'pad', 'temp', 'edad'), 'number'),
               'conciencia': 'string', **dict.fromkeys((
                   'convulsiones', 'dolor_toracico', 'dificultad_respiratoria',
                   'sangrado_activo', 'alteracion_conducta', 'trauma_significativo',
                   'dolor_intenso'), 'bool')}
OPERATORS = {'<': operator.lt, '<=': operator.le, '>': operator.gt,
             '>=': operator.ge, '==': operator.eq, '!=': operator.ne,
             'in': lambda actual, required: actual in required}


class KnowledgeConfigurationError(ValueError):
    """Missing or invalid rule configuration; never fall back silently."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)


class Condicion(StrictModel):
    hecho: str = Field(min_length=1)
    operador: Literal['<', '<=', '>', '>=', '==', '!=', 'in']
    valor: StrictBool | StrictInt | StrictFloat | StrictStr | list[StrictStr]


class ReglaProduccion(StrictModel):
    id: str = Field(pattern=r'^[A-Z][A-Z0-9_-]*$')
    nombre: str = Field(min_length=1)
    descripcion: str = Field(min_length=1)
    condiciones: list[Condicion]
    conclusion: str = Field(min_length=1)
    nivel_asignado: int | None = Field(default=None, ge=1, le=5)
    confianza: float = Field(default=1.0, ge=0, le=1)
    prioridad: int = 0
    activa: bool = True
    efectos: dict[str, StrictBool] = Field(default_factory=dict)
    alertas: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def monotonic_effects(self):
        if any(value is not True for value in self.efectos.values()):
            raise ValueError('Los efectos solo pueden afirmar hechos verdaderos')
        if not self.efectos and self.nivel_asignado is None:
            raise ValueError('Una regla debe producir hechos o proponer un nivel')
        return self

    def evaluar(self, hechos):
        evidence = []
        for condition in self.condiciones:
            present = condition.hecho in hechos
            actual = hechos.get(condition.hecho)
            passed = present and OPERATORS[condition.operador](actual, condition.valor)
            evidence.append({'hecho': condition.hecho, 'operador': condition.operador,
                             'esperado': condition.valor, 'actual': actual,
                             'presente': present, 'cumple': passed})
        return self.activa and all(e['cumple'] for e in evidence), self.confianza, evidence


class Salida(StrictModel):
    color: str = Field(min_length=1)
    recomendacion: str = Field(min_length=1)


class ConfiguracionConocimiento(StrictModel):
    version: str = Field(pattern=r'^\d+\.\d+\.\d+$')
    descripcion: str = Field(min_length=1)
    fuente: str = Field(min_length=1)
    validacion_clinica: Literal['pendiente']
    confianza_interpretacion: str = Field(min_length=1)
    agregaciones: dict[str, list[str]]
    salidas: dict[str, Salida]
    respaldo: ReglaProduccion
    reglas: list[ReglaProduccion] = Field(min_length=1)

    @model_validator(mode='after')
    def validate_graph(self):
        all_rules = [*self.reglas, self.respaldo]
        ids = [r.id for r in all_rules]
        if len(ids) != len(set(ids)):
            raise ValueError('Identificadores de reglas duplicados')
        if set(self.salidas) != set('12345'):
            raise ValueError('Se requieren las cinco salidas locales')
        if (self.respaldo.nivel_asignado != 5 or self.respaldo.condiciones or
                self.respaldo.efectos or not self.respaldo.activa):
            raise ValueError('El respaldo debe ser explícito, activo y de nivel 5')
        effects = {f for r in self.reglas for f in r.efectos}
        if effects & (set(INPUT_TYPES) | set(self.agregaciones)):
            raise ValueError('Los efectos no pueden sobrescribir entradas o agregaciones')
        if set(self.agregaciones) & set(INPUT_TYPES):
            raise ValueError('Las agregaciones no pueden sobrescribir entradas')
        for name, sources in self.agregaciones.items():
            if not sources or len(sources) != len(set(sources)) or not set(sources) <= effects:
                raise ValueError(f'Fuentes de agregación inválidas: {name}')
        types = {**INPUT_TYPES, **dict.fromkeys(effects, 'derived'),
                 **dict.fromkeys(self.agregaciones, 'count')}
        for rule in self.reglas:
            if not rule.condiciones:
                raise ValueError('Solo la regla de respaldo puede ser incondicional')
            for c in rule.condiciones:
                kind = types.get(c.hecho)
                if kind is None:
                    raise ValueError(f'Hecho desconocido: {c.hecho}')
                if kind in ('number', 'count'):
                    if type(c.valor) not in (int, float) or c.operador == 'in':
                        raise ValueError(f'Condición numérica inválida: {c.hecho}')
                    if kind == 'count' and (c.operador not in ('>=', '>') or c.valor < 0):
                        raise ValueError('Los conteos derivados requieren condiciones monótonas')
                elif kind in ('bool', 'derived'):
                    if type(c.valor) is not bool or c.operador not in ('==', '!='):
                        raise ValueError(f'Condición booleana inválida: {c.hecho}')
                    if kind == 'derived' and (c.operador != '==' or c.valor is not True):
                        raise ValueError('Los hechos derivados solo se consultan como verdaderos')
                elif (c.operador == 'in' and not isinstance(c.valor, list)) or (
                        c.operador != 'in' and (not isinstance(c.valor, str) or c.operador not in ('==', '!='))):
                    raise ValueError(f'Condición textual inválida: {c.hecho}')
        return self


@dataclass
class NodoDecision:
    """Rule catalog tree, generated from the actual loaded knowledge."""
    id: str
    tipo: str
    texto: str
    valor: int | None = None
    color: str | None = None
    hijos: list[NodoDecision] = field(default_factory=list)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Clave JSON duplicada: {key}')
        result[key] = value
    return result


class BaseConocimiento:
    def __init__(self, path: str | Path | None = None):
        location = Path(path or os.getenv('TRIAGE_KNOWLEDGE_PATH') or DEFAULT_KNOWLEDGE_PATH)
        try:
            raw = location.read_bytes()
            data = json.loads(raw, object_pairs_hook=_unique_object)
            self.config = ConfiguracionConocimiento.model_validate(data)
        except (OSError, ValueError) as exc:
            raise KnowledgeConfigurationError('Base de conocimiento ausente o inválida') from exc
        canonical = json.dumps(self.config.model_dump(mode='json'), sort_keys=True,
                               ensure_ascii=False, separators=(',', ':')).encode()
        self.sha256 = hashlib.sha256(canonical).hexdigest()
        self.reglas = self.config.reglas
        self.hechos_entrada = {}
        self.hechos_paciente = {}
        self.traza_inferencia = []
        self.arbol = NodoDecision('reglas', 'catalogo', 'Catálogo de reglas; no es un algoritmo de protocolo oficial')
        for level in range(1, 6):
            node = NodoDecision(f'nivel-{level}', 'grupo', f'Prioridad local {level}',
                                level, self.config.salidas[str(level)].color)
            node.hijos = [NodoDecision(r.id, 'regla', r.nombre, r.nivel_asignado)
                          for r in [*self.reglas, self.config.respaldo]
                          if r.activa and r.nivel_asignado == level]
            self.arbol.hijos.append(node)

    def establecer_hechos(self, paciente_data: dict):
        patient = DatosPaciente.model_validate(paciente_data).model_dump(mode='json')
        sv = patient['signos_vitales']
        self.hechos_entrada = dict(zip(('fc', 'spo2', 'pas', 'pad', 'temp'), (
            sv['frecuencia_cardiaca'], sv['saturacion_oxigeno'], sv['presion_sistolica'],
            sv['presion_diastolica'], sv['temperatura'])))
        self.hechos_entrada.update(edad=patient['edad'], conciencia=patient['nivel_conciencia'])
        self.hechos_entrada.update(patient['sintomas'])
        self.hechos_paciente = dict(self.hechos_entrada)

    def forward_chaining(self):
        if not self.hechos_entrada:
            raise ValueError('Se requieren los hechos completos del paciente')
        facts = dict(self.hechos_entrada)
        provenance = {key: {'reglas': [], 'confianza': 1.0} for key in facts}
        fired = {}
        rules = sorted((r for r in self.reglas if r.activa), key=lambda r: (-r.prioridad, r.id))
        # Each rule fires at most once and effects only add True facts. No oscillation.
        for iteration in range(1, len(rules) + 2):
            for name, sources in self.config.agregaciones.items():
                contributors = [s for s in sources if facts.get(s) is True]
                facts[name] = len(contributors)
                provenance[name] = {'hechos': contributors,
                                    'reglas': sorted({r for s in contributors for r in provenance[s]['reglas']}),
                                    'confianza': min((provenance[s]['confianza'] for s in contributors), default=1.0)}
            changed = False
            for rule in rules:
                if rule.id in fired:
                    continue
                active, weight, evidence = rule.evaluar(facts)
                if not active:
                    continue
                confidence = min([weight, *(provenance[c.hecho]['confianza'] for c in rule.condiciones)])
                for item in evidence:
                    item['origen'] = provenance[item['hecho']].copy()
                fired[rule.id] = {'regla_id': rule.id, 'regla_nombre': rule.nombre,
                    'descripcion': rule.descripcion, 'condiciones_evaluadas': evidence,
                    'activa': True, 'confianza': confidence, 'conclusion': rule.conclusion,
                    'nivel': rule.nivel_asignado, 'iteracion': iteration,
                    'hechos_producidos': dict(rule.efectos)}
                for name in rule.efectos:
                    if name not in facts:
                        facts[name] = True
                        provenance[name] = {'reglas': [rule.id], 'confianza': confidence}
                changed = True
            if not changed:
                break
        candidates = [r for r in rules if r.id in fired and r.nivel_asignado is not None]
        if candidates:
            level = min(r.nivel_asignado for r in candidates)
            decisive = [r for r in candidates if r.nivel_asignado == level]
        else:
            fallback = self.config.respaldo
            level, decisive = 5, [fallback]
            fired[fallback.id] = {'regla_id': fallback.id, 'regla_nombre': fallback.nombre,
                'descripcion': fallback.descripcion, 'condiciones_evaluadas': [], 'activa': True,
                'confianza': fallback.confianza, 'conclusion': fallback.conclusion,
                'nivel': 5, 'iteracion': iteration, 'hechos_producidos': {}}
        selected = {r.id for r in decisive}
        trace = []
        for rule in [*rules, self.config.respaldo]:
            if rule.id in fired:
                step = fired[rule.id].copy()
            else:
                _, _, evidence = rule.evaluar(facts)
                step = {'regla_id': rule.id, 'regla_nombre': rule.nombre,
                    'descripcion': rule.descripcion, 'condiciones_evaluadas': evidence,
                    'activa': False, 'confianza': 0, 'conclusion': None, 'nivel': None,
                    'iteracion': None, 'hechos_producidos': {}}
            step['decisiva'] = rule.id in selected
            trace.append(step)
        self.hechos_paciente, self.traza_inferencia = facts, trace
        knowledge = {'version': self.config.version, 'sha256': self.sha256,
                     'fuente': self.config.fuente, 'validacion_clinica': self.config.validacion_clinica,
                     'snapshot': self.config.model_dump(mode='json')}
        explanation = {
            'version_motor': ENGINE_VERSION,
            'why': [{'regla': s['regla_id'], 'nombre': s['regla_nombre'],
                     'razon': s['conclusion'], 'confianza': s['confianza'],
                     'evidencia': s['condiciones_evaluadas']} for s in trace if s['decisiva']],
            'how': {'metodo': 'Encadenamiento hacia adelante hasta punto fijo',
                    'nivel_asignado': level, 'reglas_decisivas': sorted(selected),
                    'reglas_evaluadas': len(trace), 'reglas_activadas': len(fired),
                    'iteraciones': iteration, 'politica_conflictos': 'Mayor urgencia (menor nivel); prioridad e ID ordenan la traza',
                    'confianza_interpretacion': self.config.confianza_interpretacion},
            'trace': trace, 'hechos_finales': facts, 'procedencia_hechos': provenance,
            'conocimiento': knowledge,
        }
        return level, trace, explanation

    def consultar_regla(self, regla_id):
        return next((r for r in [*self.reglas, self.config.respaldo] if r.id == regla_id), None)

    def listar_reglas_activas(self):
        return [r.model_dump(mode='json') for r in [*self.reglas, self.config.respaldo] if r.activa]
