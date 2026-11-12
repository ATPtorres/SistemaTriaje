"""Integration tests using an isolated database; never touch patient data."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from knowledge_access import password_hash
TEST_ADMIN_HASH = password_hash("test-admin-password")
from database import Base, get_db
from models_db import (Paciente, EvaluacionTriaje, SignosVitalesHistorial,
                       AlertaGenerada, DiagnosticoSugerido)


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("TRIAGE_ADMIN_PASSWORD_HASH", TEST_ADMIN_HASH)
    monkeypatch.setenv("TRIAGE_ADMIN_USER", "administrador")
    import os
    from sqlalchemy.engine import make_url
    mysql_url = os.getenv('TEST_MYSQL_URL')
    if mysql_url:
        if not (make_url(mysql_url).database or '').startswith('triaje_test_'):
            raise RuntimeError('Las pruebas MySQL requieren una base aislada triaje_test_*.')
        engine = create_engine(mysql_url)
        Base.metadata.drop_all(engine)
    else:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    def isolated_db():
        with factory() as db:
            try:
                yield db
            except Exception:
                db.rollback()
                raise

    monkeypatch.setattr(main, "init_db", lambda: None)
    main.app.dependency_overrides[get_db] = isolated_db
    with TestClient(main.app, base_url="http://localhost", client=("127.0.0.1", 50000)) as client:
        assert client.post("/conocimiento/sesion", json={"usuario":"administrador", "clave":"test-admin-password"}, headers={"X-Triaje-Gestion":"1"}).status_code == 200
        yield client, factory
    main.app.dependency_overrides.clear()
    if mysql_url:
        Base.metadata.drop_all(engine)
    engine.dispose()


def payload(identifier="TEST-001"):
    return {"id_paciente": identifier, "edad": 35, "nivel_conciencia": "Alerta",
            "signos_vitales": {"frecuencia_cardiaca": 75, "presion_sistolica": 120,
                               "presion_diastolica": 80, "temperatura": 36.5,
                               "saturacion_oxigeno": 98}}


def test_evaluation_is_persisted_and_reuses_patient(api):
    client, factory = api
    for _ in range(2):
        response = client.post("/triaje", json=payload())
        assert response.status_code == 200, response.text
        assert response.json()["metadata_motor"]["guardado_en_bd"] is True
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Paciente)) == 1
        assert db.scalar(select(func.count()).select_from(EvaluacionTriaje)) == 2
        assert db.scalar(select(func.count()).select_from(SignosVitalesHistorial)) == 2


def test_late_failure_rolls_back_entire_evaluation(api, monkeypatch):
    client, factory = api

    def fail(*args, **kwargs):
        raise SQLAlchemyError("internal-secret-connection-details")

    monkeypatch.setattr(main.crud, "crear_signos_vitales", fail)
    response = client.post("/triaje", json=payload())
    assert response.status_code == 503
    assert "internal-secret" not in response.text
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Paciente)) == 0
        assert db.scalar(select(func.count()).select_from(EvaluacionTriaje)) == 0


@pytest.mark.parametrize("identifier", ["", "   ", "X" * 51])
def test_rejects_invalid_identifiers(api, identifier):
    client, _ = api
    assert client.post("/triaje", json=payload(identifier)).status_code == 422
    assert client.post("/pacientes", json={"id_externo": identifier, "edad": 35}).status_code == 422


def test_duplicate_patient_and_paginated_search(api):
    client, _ = api
    for identifier in ["SEARCH-1", "SEARCH-2", "SEARCH-3"]:
        assert client.post("/pacientes", json={"id_externo": identifier, "edad": 35}).status_code == 200
    assert client.post("/pacientes", json={"id_externo": "SEARCH-1", "edad": 35}).status_code == 409
    page = client.get("/pacientes", params={"buscar": "SEARCH", "skip": 1, "limit": 1}).json()
    assert [p["id_externo"] for p in page["pacientes"]] == ["SEARCH-2"]


def test_evaluation_filters_are_combined(api):
    client, _ = api
    for identifier in ["FILTER-1", "FILTER-2"]:
        assert client.post("/triaje", json=payload(identifier)).status_code == 200
    patient = client.get("/pacientes", params={"buscar": "FILTER-1"}).json()["pacientes"][0]
    result = client.get("/evaluaciones", params={"paciente_id": patient["id"], "nivel": 5}).json()
    assert len(result["evaluaciones"]) == 1
    assert result["evaluaciones"][0]["paciente_id"] == patient["id"]


def test_health_reports_database_failure(api):
    client, _ = api
    assert client.get("/health").status_code == 200

    class BrokenSession:
        def execute(self, *args):
            raise SQLAlchemyError("private-details")

        def rollback(self):
            pass

    main.app.dependency_overrides[get_db] = lambda: BrokenSession()
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert "private-details" not in response.text


def test_critical_evaluation_saves_alerts_diagnoses_and_detail(api):
    client, factory = api
    data = payload("CRITICAL-1")
    data["nivel_conciencia"] = "Inconsciente"
    data["signos_vitales"]["saturacion_oxigeno"] = 82
    data["sintomas"] = {"dolor_toracico": True, "dificultad_respiratoria": True}
    response = client.post("/triaje", json=data)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["nivel_prioridad"] == 1
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(AlertaGenerada)) > 0
        assert db.scalar(select(func.count()).select_from(DiagnosticoSugerido)) > 0
    detail = client.get("/evaluaciones/" + result["metadata_motor"]["id_evaluacion"])
    assert detail.status_code == 200
    assert detail.json()["alertas"]
    assert detail.json()["signos_vitales"][0]["spo2"] == 82


def test_daily_statistics_refresh_without_dashboard_request(api):
    client, _ = api
    assert client.get("/estadisticas/diaria").json()["total_evaluaciones"] == 0
    assert client.post("/triaje", json=payload()).status_code == 200
    assert client.get("/estadisticas/diaria").json()["total_evaluaciones"] == 1


@pytest.mark.parametrize("path", ["/", "/knowledge-base", "/decision-tree", "/fuzzy-membership", "/protocols"])
def test_public_information_endpoints(api, path):
    client, _ = api
    assert client.get(path).status_code == 200


def test_decision_explanation_and_persisted_snapshot_are_consistent(api):
    client, factory = api
    data = payload('TRACE-1')
    data['signos_vitales']['frecuencia_cardiaca'] = 130
    data['sintomas'] = {'trauma_significativo': True}
    response = client.post('/triaje', json=data)
    assert response.status_code == 200, response.text
    result = response.json()
    explanation = result['metadata_motor']['explicaciones']
    assert result['nivel_prioridad'] == explanation['how']['nivel_asignado'] == 3
    assert result['metadata_motor']['conocimiento']['validacion_clinica'] == 'pendiente'
    detail = client.get('/evaluaciones/' + result['metadata_motor']['id_evaluacion']).json()['evaluacion']
    assert detail['explicaciones'] == explanation
    assert detail['traza_inferencia'] == result['metadata_motor']['traza_completa']
    assert len(detail['traza_inferencia']) > 20  # The old API truncated the audit trail.
    with factory() as db:
        saved = db.scalar(select(EvaluacionTriaje))
        assert saved.nivel_prioridad == 3
        assert saved.explicaciones['conocimiento']['sha256'] == result['metadata_motor']['conocimiento']['sha256']
        assert saved.explicaciones['conocimiento']['snapshot']['version'] == '4.0.0'
        assert saved.nivel_mts is saved.nivel_ctas is saved.nivel_ats is saved.nivel_esi is None


def test_official_protocols_are_not_fabricated(api):
    client, _ = api
    protocols = client.get('/protocols').json()
    assert protocols['validacion_clinica'] == 'pendiente'
    assert all(p['estado'] == 'no_implementado' for p in protocols['protocolos'] if p['id'] != 'LOCAL')
    result = client.post('/triaje', json=payload()).json()
    for name, field in [('esi', 'nivel'), ('mts', 'nivel_mts'), ('ctas', 'nivel_ctas'), ('ats', 'nivel_ats')]:
        protocol = result['soporte_clinico']['protocolos'][name]
        assert protocol[field] is None
        assert protocol['equivalencia_clinica'] is False
    assert result['soporte_clinico']['protocolos']['local']['nivel'] == result['nivel_prioridad']


def test_bad_knowledge_blocks_evaluation_without_saving_patient(api, monkeypatch, tmp_path):
    client, factory = api
    path = tmp_path / 'broken.json'
    path.write_text('{"reglas": "invalid"}')
    monkeypatch.setenv('TRIAGE_KNOWLEDGE_PATH', str(path))
    for endpoint in ['/knowledge-base', '/health']:
        assert client.get(endpoint).status_code == 503
    response = client.post('/triaje', json=payload())
    assert response.status_code == 503
    assert str(path) not in response.text
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Paciente)) == 0
        assert db.scalar(select(func.count()).select_from(EvaluacionTriaje)) == 0


def test_detail_uses_vitals_of_the_requested_evaluation(api):
    client, _ = api
    data = payload('AUDIT-SAME-PATIENT')
    first = client.post('/triaje', json=data).json()
    data['signos_vitales']['saturacion_oxigeno'] = 82
    second = client.post('/triaje', json=data).json()
    assert second['nivel_prioridad'] == 1
    detail = client.get('/evaluaciones/' + first['metadata_motor']['id_evaluacion']).json()
    assert detail['signos_vitales'][0]['spo2'] == 98
    assert detail['evaluacion']['explicaciones']['how']['nivel_asignado'] == 5


def test_startup_rejects_bad_rules_before_initializing_database(monkeypatch, tmp_path):
    from knowledge_base import KnowledgeConfigurationError
    monkeypatch.setenv('TRIAGE_KNOWLEDGE_PATH', str(tmp_path / 'missing.json'))
    def must_not_initialize():
        pytest.fail('Database initialization must not run with invalid rules')
    monkeypatch.setattr(main, 'init_db', must_not_initialize)
    with pytest.raises(KnowledgeConfigurationError):
        with TestClient(main.app):
            pass


GESTION_HEADERS = {"X-Triaje-Gestion": "1", "Origin": "http://localhost"}


def create_extra(client, **changes):
    data = {"nombre": "Síntoma de prueba", "descripcion": "Justificación sintética para pruebas de software", "nivel": 3}
    data.update(changes)
    response = client.post('/conocimiento/sintomas', json=data, headers=GESTION_HEADERS)
    if response.status_code == 201:
        assert client.post('/conocimiento/sintomas/'+response.json()['id']+'/ensayo', headers=GESTION_HEADERS).status_code == 200
        published = client.post('/conocimiento/sintomas/'+response.json()['id']+'/publicar', headers=GESTION_HEADERS)
        assert published.status_code == 200, published.text
    return response


def test_extra_symptom_end_to_end_and_base_protection(api, tmp_path):
    from knowledge_base import DEFAULT_KNOWLEDGE_PATH, BaseConocimiento
    from triage_engine import MotorTriaje
    from models import DatosPaciente
    import json
    client, factory = api
    original = DEFAULT_KNOWLEDGE_PATH.read_bytes()
    created = create_extra(client)
    assert created.status_code == 201, created.text
    symptom = created.json()
    patient = payload('EXTENSION-TEST')
    patient['sintomas_adicionales'] = {symptom['id']: True}
    simulation = client.post('/triaje/simular', json=patient)
    assert simulation.status_code == 200, simulation.text
    assert simulation.json()['nivel_prioridad'] == 3
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Paciente)) == 0
    response = client.post('/triaje', json=patient)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['nivel_prioridad'] == 3
    assert symptom['nombre'] in result['motivo_clinico']
    snapshot = result['metadata_motor']['explicaciones']['conocimiento']['snapshot']
    snapshot_path = tmp_path / 'snapshot.json'
    snapshot_path.write_text(json.dumps(snapshot), encoding='utf-8')
    assert MotorTriaje(BaseConocimiento(snapshot_path)).evaluar(DatosPaciente(**patient)).nivel_prioridad == 3
    assert DEFAULT_KNOWLEDGE_PATH.read_bytes() == original
    assert client.post('/conocimiento/sintomas/R003/desactivar', headers=GESTION_HEADERS).status_code == 404
    assert client.put('/knowledge-base', json={'reglas': []}).status_code == 405
    assert client.post('/conocimiento/sintomas/'+symptom['id']+'/desactivar', headers=GESTION_HEADERS).status_code == 200
    assert client.post('/triaje', json=patient).status_code == 409
    detail = client.get('/evaluaciones/'+result['metadata_motor']['id_evaluacion']).json()
    assert detail['evaluacion']['explicaciones']['conocimiento']['snapshot'] == snapshot
    assert DEFAULT_KNOWLEDGE_PATH.read_bytes() == original


def test_additions_cannot_reduce_base_urgency_or_activate_when_unknown(api):
    client, _ = api
    symptom = create_extra(client, nivel=4).json()
    patient = payload()
    for value in [None, False]:
        patient['sintomas_adicionales'] = {symptom['id']: value}
        assert client.post('/triaje/simular', json=patient).json()['nivel_prioridad'] == 5
    patient['sintomas_adicionales'] = {symptom['id']: True}
    patient['signos_vitales']['saturacion_oxigeno'] = 82
    assert client.post('/triaje/simular', json=patient).json()['nivel_prioridad'] == 1
    patient['sintomas_adicionales'] = {'sx_'+'0'*32: True}
    assert client.post('/triaje/simular', json=patient).status_code == 409


@pytest.mark.parametrize('changes', [ {'nivel': 1}, {'nivel': 5}, {'nivel': True},
    {'nivel': '2'}, {'reglas': []}, {'condiciones': []}, {'nombre': '  '}, {'descripcion': 'corta'}])
def test_extension_editor_rejects_arbitrary_rules_and_invalid_data(api, changes):
    client, _ = api
    assert create_extra(client, **changes).status_code == 422


def test_extension_management_requires_local_same_origin_request(api):
    client, _ = api
    data = {'nombre': 'Síntoma local', 'descripcion': 'Solo un caso sintético de prueba', 'nivel': 3}
    assert client.post('/conocimiento/sintomas', json=data).status_code == 403
    assert client.post('/conocimiento/sintomas', json=data, headers={'X-Triaje-Gestion': '1', 'Origin': 'https://evil.example'}).status_code == 403
    with TestClient(main.app, base_url='http://localhost', client=('192.0.2.1', 50000)) as remote:
        assert remote.post('/conocimiento/sintomas', json=data, headers=GESTION_HEADERS).status_code == 403


def test_duplicate_and_reserved_names_are_rejected(api):
    client, _ = api
    assert create_extra(client).status_code == 201
    assert create_extra(client, nombre='  SINTOMA   DE PRUEBA ').status_code == 409
    assert create_extra(client, nombre='Dolor torácico').status_code == 409


def test_fuzzy_no_result_does_not_prevent_persistence(api):
    client, _ = api
    data = payload()
    data['signos_vitales']['frecuencia_cardiaca'] = 250
    result = client.post('/triaje', json=data)
    assert result.status_code == 200, result.text
    assert result.json()['score_riesgo_difuso'] is None
    assert result.json()['metadata_motor']['logica_difusa']['estado'] == 'sin_resultado'


def test_idempotent_save_and_changed_payload_rejection(api):
    client, factory = api
    data = payload()
    data['id_solicitud'] = '12345678-1234-1234-1234-123456789012'
    first = client.post('/triaje', json=data)
    assert first.status_code == 200, first.text
    second = client.post('/triaje', json=data)
    assert second.json() == first.json()
    data['edad'] = 40
    assert client.post('/triaje', json=data).status_code == 409
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(EvaluacionTriaje)) == 1


def test_admin_drafts_and_publication(api):
    client, factory = api
    draft = client.post('/conocimiento/sintomas', headers=GESTION_HEADERS,
                        json={'nombre': 'Borrador nuevo', 'descripcion': 'Justificación sintética de prueba', 'nivel': 3})
    assert draft.status_code == 201, draft.text
    symptom = draft.json()
    assert symptom['estado'] == 'borrador' and symptom['activo'] is False
    assert client.post('/conocimiento/sintomas/'+symptom['id']+'/publicar', headers=GESTION_HEADERS).status_code == 409
    data = payload(); data['sintomas_adicionales'] = {symptom['id']: True}
    assert client.post('/triaje/simular', json=data).status_code == 409
    trial = client.post('/conocimiento/sintomas/'+symptom['id']+'/ensayo', headers=GESTION_HEADERS)
    assert trial.status_code == 200, trial.text
    assert [r['nivel'] for r in trial.json()['resultados']] == [5, 5, 3]
    published = client.post('/conocimiento/sintomas/'+symptom['id']+'/publicar', headers=GESTION_HEADERS)
    assert published.json()['publicado_por'] == 'administrador'
    assert client.post('/triaje/simular', json=data).json()['nivel_prioridad'] == 3
    client.delete('/conocimiento/sesion', headers=GESTION_HEADERS)
    assert client.post('/conocimiento/sintomas/'+symptom['id']+'/desactivar', headers=GESTION_HEADERS).status_code == 401
    assert client.get('/conocimiento/sesion').json()['rol'] == 'operador'


def test_trend_contains_actual_calendar_days_including_empty_days(api):
    client, _ = api
    response = client.get('/estadisticas/tendencia?dias=7')
    assert response.status_code == 200
    rows = response.json()['datos']
    assert len(rows) == 7
    from datetime import date, timedelta
    assert date.fromisoformat(rows[-1]['fecha']) - date.fromisoformat(rows[0]['fecha']) == timedelta(days=6)
    assert all(row['total'] == 0 for row in rows)


def test_day_boundaries_use_configured_timezone():
    import crud
    from datetime import date, datetime
    lower, upper = crud.limites_dia(date(2026, 11, 12))
    assert lower == datetime(2026, 11, 12, 4)
    assert upper == datetime(2026, 11, 13, 4)


def test_same_request_concurrently_is_saved_once_mysql(api):
    import os
    if not os.getenv('TEST_MYSQL_URL'):
        pytest.skip('Concurrencia de sesiones separadas requiere MySQL aislado')
    from concurrent.futures import ThreadPoolExecutor
    client,factory=api
    assert client.post('/pacientes',json={'id_externo':'CONCURRENT','edad':35}).status_code==200
    data=payload('CONCURRENT');data['id_solicitud']='99999999-1234-1234-1234-123456789012'
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses=list(executor.map(lambda _:client.post('/triaje',json=data),range(2)))
    assert [r.status_code for r in responses]==[200,200]
    assert responses[0].json()==responses[1].json()
    with factory() as db:assert db.scalar(select(func.count()).select_from(EvaluacionTriaje))==1


def test_additive_migration_is_repeatable_without_losing_data():
    from migrations import upgrade
    from sqlalchemy import text
    engine=create_engine('sqlite://')
    upgrade(engine)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO pacientes (id_externo,edad) VALUES ('PRESERVE',35)"))
    upgrade(engine)
    with engine.connect() as connection:
        assert connection.execute(text('SELECT COUNT(*) FROM pacientes')).scalar()==1
        assert connection.execute(text('SELECT COUNT(*) FROM schema_migrations')).scalar()==1
    engine.dispose()
