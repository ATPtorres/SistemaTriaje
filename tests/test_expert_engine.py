"""Software regression and inference tests; these are not clinical validation."""
import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from clinical_validation import ReferenceDataset, evaluate_dataset
from knowledge_base import BaseConocimiento, DEFAULT_KNOWLEDGE_PATH, KnowledgeConfigurationError
from models import DatosPaciente
from triage_engine import MotorTriaje, evaluar_triaje

FIXTURE = json.loads((Path(__file__).parent / 'fixtures' / 'triage_regression.json').read_text())


def normal_patient(**changes):
    data = copy.deepcopy(FIXTURE['casos'][0]['paciente'])
    data.update(changes)
    return DatosPaciente(**data)


def write_config(tmp_path, change=lambda config: None):
    config = json.loads(DEFAULT_KNOWLEDGE_PATH.read_text())
    change(config)
    path = tmp_path / 'rules.json'
    path.write_text(json.dumps(config))
    return path


@pytest.mark.parametrize('case', FIXTURE['casos'], ids=lambda c: c['paciente']['id_paciente'])
def test_migrated_decisions_and_explanations_agree(case):
    result = evaluar_triaje(DatosPaciente(**case['paciente']))
    assert result.nivel_prioridad == case['nivel_referencia']
    metadata = result.metadata_motor
    explanation = metadata['explicaciones']
    assert explanation['how']['nivel_asignado'] == result.nivel_prioridad
    decisive = [s for s in metadata['traza_completa'] if s['decisiva']]
    assert decisive and all(s['activa'] and s['nivel'] == result.nivel_prioridad for s in decisive)
    assert result.motivo_clinico == ' | '.join(s['conclusion'] for s in decisive)
    assert [w['regla'] for w in explanation['why']] == [s['regla_id'] for s in decisive]


def test_multi_hop_inference_and_provenance_regardless_of_rule_order(tmp_path):
    def change(config):
        for rule in config['reglas']:
            if rule['id'] in ('H002', 'H014'):
                rule['prioridad'] = -100 if rule['id'] == 'H002' else -99
                rule['confianza'] = 0.5
    base = BaseConocimiento(write_config(tmp_path, change))
    patient = normal_patient(sintomas={'trauma_significativo': True})
    patient.signos_vitales.frecuencia_cardiaca = 130
    result = MotorTriaje(base).evaluar(patient)
    assert result.nivel_prioridad == 3
    explanation = result.metadata_motor['explicaciones']
    decisive = next(s for s in explanation['trace'] if s['regla_id'] == 'R033')
    assert decisive['activa'] and decisive['iteracion'] >= 3
    assert decisive['confianza'] == 0.5
    assert 'H014' in explanation['procedencia_hechos']['recursos_orientativos']['reglas']
    assert explanation['procedencia_hechos']['recurso_fc_alterada']['reglas'] == ['H014']
    assert explanation['procedencia_hechos']['fc_alterada']['reglas'] == ['H002']
    # Reusing a motor cannot leak derived facts into another patient.
    assert MotorTriaje(base).evaluar(normal_patient()).nivel_prioridad == 5
    assert 'fc_alterada' not in base.hechos_paciente


def test_urgency_wins_over_high_confidence_lower_priority(tmp_path):
    def change(config):
        next(r for r in config['reglas'] if r['id'] == 'R003')['confianza'] = 0.1
    patient = normal_patient()
    patient.signos_vitales.saturacion_oxigeno = 89
    patient.signos_vitales.temperatura = 38
    result = MotorTriaje(BaseConocimiento(write_config(tmp_path, change))).evaluar(patient)
    assert result.nivel_prioridad == 1
    assert result.metadata_motor['explicaciones']['why'][0]['regla'] == 'R003'


def test_editable_file_changes_decision_and_snapshot_reproduces_it(tmp_path, monkeypatch):
    path = write_config(tmp_path)
    monkeypatch.setenv('TRIAGE_KNOWLEDGE_PATH', str(path))
    patient = normal_patient()
    patient.signos_vitales.saturacion_oxigeno = 94
    old = evaluar_triaje(patient)
    config = json.loads(path.read_text())
    next(r for r in config['reglas'] if r['id'] == 'R003')['condiciones'][0]['valor'] = 95
    config['version'] = '4.0.1'
    path.write_text(json.dumps(config))
    new = evaluar_triaje(patient)
    assert old.nivel_prioridad == 5 and new.nivel_prioridad == 1
    assert old.metadata_motor['conocimiento']['sha256'] != new.metadata_motor['conocimiento']['sha256']
    snapshot = new.metadata_motor['explicaciones']['conocimiento']['snapshot']
    path.write_text(json.dumps(snapshot, indent=4))
    reproduced = evaluar_triaje(patient)
    assert reproduced.metadata_motor['conocimiento'] == new.metadata_motor['conocimiento']
    assert reproduced.nivel_prioridad == new.nivel_prioridad


@pytest.mark.parametrize('change', [
    lambda c: c['reglas'].append(copy.deepcopy(c['reglas'][0])),
    lambda c: c['reglas'][0]['condiciones'][0].update(operador='eval'),
    lambda c: c['reglas'][0]['condiciones'][0].update(hecho='no_existe'),
    lambda c: c['reglas'][0]['condiciones'][0].update(valor='50'),
    lambda c: c['reglas'][0].update(efectos={'fc': True}),
    lambda c: c['reglas'][0].update(efectos={'fc_alterada': False}),
    lambda c: c['reglas'][0].update(confianza=float('nan')),
    lambda c: c['salidas'].pop('1'),
    lambda c: c['reglas'][0].update(codigo='raise Exception()'),
    lambda c: c['reglas'][0].update(condiciones=[{'hecho': 'fc_alterada', 'operador': '==', 'valor': False}]),
    lambda c: c['reglas'][0].update(condiciones=[{'hecho': 'recursos_orientativos', 'operador': '<', 'valor': 2}]),
    lambda c: c['agregaciones'].update(recursos_orientativos=['missing']),
])
def test_invalid_knowledge_is_rejected(tmp_path, change):
    with pytest.raises(KnowledgeConfigurationError):
        BaseConocimiento(write_config(tmp_path, change))


def test_missing_or_malformed_file_never_uses_silent_defaults(tmp_path):
    path = tmp_path / 'missing.json'
    with pytest.raises(KnowledgeConfigurationError):
        BaseConocimiento(path)
    for raw in ['{', '{"version":"4.0.0","version":"5.0.0"}']:
        path.write_text(raw)
        with pytest.raises(KnowledgeConfigurationError):
            BaseConocimiento(path)


def test_synthetic_reference_report_does_not_claim_clinical_validation():
    report = evaluate_dataset(ReferenceDataset.model_validate(FIXTURE))
    assert report['casos_ejecutados'] == 62
    assert report['concordancia_exacta'] == 1
    assert report['validacion_clinica'] == 'pendiente'
    assert report['tipo_datos'] == 'sintetico'
    assert 'SYN-' not in json.dumps(report)


def test_reference_metrics_distinguish_under_and_overtriage():
    data = {'tipo': 'sintetico', 'referencia': 'Test métricas, no evidencia médica', 'casos': []}
    for identifier, reference in [('A', 1), ('B', 5)]:
        p = normal_patient(id_paciente=identifier, sintomas={'dolor_toracico': True})
        data['casos'].append({'paciente': p.model_dump(mode='json'), 'nivel_referencia': reference})
    report = evaluate_dataset(ReferenceDataset.model_validate(data))
    assert report['subtriaje'] == {'casos': 1, 'tasa': .5}
    assert report['sobretriaje'] == {'casos': 1, 'tasa': .5}
    assert report['sensibilidad_por_nivel']['3'] is None
    assert report['matriz_confusion']['valores'][0][1] == 1
    with pytest.raises(ValidationError):
        ReferenceDataset.model_validate({**data, 'tipo': 'adjudicado'})
    with pytest.raises(ValidationError):
        ReferenceDataset.model_validate({**data, 'casos': []})


@pytest.mark.parametrize('rule_id,vitals,symptoms,other', [
    ('R006', {'presion_sistolica': 89}, {'sangrado_activo': True}, {}),
    ('R012', {'saturacion_oxigeno': 93}, {'dificultad_respiratoria': True}, {}),
    ('R013', {'frecuencia_cardiaca': 121}, {'dificultad_respiratoria': True}, {}),
    ('R015', {'frecuencia_cardiaca': 49}, {}, {'nivel_conciencia': 'Verbal'}),
    ('R017', {'temperatura': 39.6}, {}, {'nivel_conciencia': 'Verbal'}),
    ('R021', {}, {'dificultad_respiratoria': True}, {'edad': 1}),
    ('R034', {'temperatura': 38.1}, {'alteracion_conducta': True}, {}),
])
def test_previously_uncovered_rules_fire(rule_id, vitals, symptoms, other):
    patient = normal_patient(sintomas=symptoms, **other)
    for name, value in vitals.items():
        setattr(patient.signos_vitales, name, value)
    result = evaluar_triaje(patient)
    step = next(s for s in result.metadata_motor['traza_completa'] if s['regla_id'] == rule_id)
    assert step['activa']
    assert all(c['cumple'] for c in step['condiciones_evaluadas'])


def test_unknown_symptoms_are_not_recorded_as_absent():
    patient = normal_patient(sintomas={'dolor_toracico': None})
    result = evaluar_triaje(patient)
    facts = result.metadata_motor['explicaciones']['hechos_finales']
    assert 'dolor_toracico' not in facts


def test_unseeded_cycle_is_rejected(tmp_path):
    def change(config):
        for name, dependency in [('A', 'B'), ('B', 'A')]:
            config['reglas'].append({'id': 'LOOP_' + name, 'nombre': name, 'descripcion': name,
                'condiciones': [{'hecho': 'loop_' + dependency, 'operador': '==', 'valor': True}],
                'conclusion': name, 'efectos': {'loop_' + name: True}})
    with pytest.raises(KnowledgeConfigurationError):
        BaseConocimiento(write_config(tmp_path, change))


def test_all_producers_are_preserved(tmp_path):
    def change(config):
        for number in [1, 2]:
            config['reglas'].append({'id': f'PRODUCER_{number}', 'nombre': 'Productor', 'descripcion': 'Prueba',
                'condiciones': [{'hecho': 'edad', 'operador': '>=', 'valor': 0}],
                'conclusion': 'Hecho compartido', 'efectos': {'compartido': True}})
    result = MotorTriaje(BaseConocimiento(write_config(tmp_path, change))).evaluar(normal_patient())
    assert result.metadata_motor['explicaciones']['procedencia_hechos']['compartido']['reglas'] == ['PRODUCER_1', 'PRODUCER_2']


@pytest.mark.parametrize('rule_id,vitals,symptoms,other', [
 ('R006',{'presion_sistolica':90},{'sangrado_activo':True},{}),
 ('R012',{'saturacion_oxigeno':94},{'dificultad_respiratoria':True},{}),
 ('R013',{'frecuencia_cardiaca':120},{'dificultad_respiratoria':True},{}),
 ('R015',{'frecuencia_cardiaca':50},{},{'nivel_conciencia':'Verbal'}),
 ('R017',{'temperatura':39.5},{},{'nivel_conciencia':'Verbal'}),
 ('R021',{}, {'dificultad_respiratoria':True},{'edad':2}),
 ('R034',{'temperatura':38},{'alteracion_conducta':True},{})])
def test_rule_boundary_does_not_fire(rule_id,vitals,symptoms,other):
    patient=normal_patient(sintomas=symptoms,**other)
    for key,value in vitals.items():setattr(patient.signos_vitales,key,value)
    result=evaluar_triaje(patient)
    assert not next(s for s in result.metadata_motor['traza_completa'] if s['regla_id']==rule_id)['activa']


def test_impossible_numeric_conditions_rejected(tmp_path):
    def change(config):
        config['reglas'][0]['condiciones'] = [
            {'hecho': 'fc', 'operador': '>', 'valor': 150},
            {'hecho': 'fc', 'operador': '<', 'valor': 50}]
    with pytest.raises(KnowledgeConfigurationError):
        BaseConocimiento(write_config(tmp_path, change))


def test_reference_report_uses_combined_knowledge():
    from types import SimpleNamespace
    candidate = SimpleNamespace(id='sx_' + '1' * 32, nombre='Síntoma sintético',
                                descripcion='Justificación sintética para pruebas', nivel=3, activo=True)
    patient = normal_patient(sintomas_adicionales={candidate.id: True})
    dataset = ReferenceDataset.model_validate({'tipo': 'sintetico', 'referencia': 'Prueba de ampliaciones',
        'casos': [{'paciente': patient.model_dump(mode='json'), 'nivel_referencia': 3}]})
    report = evaluate_dataset(dataset, ampliaciones=[candidate])
    assert report['concordancia_exacta'] == 1
    assert report['sha256_conocimiento'] != BaseConocimiento().sha256
