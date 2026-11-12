"""Integration tests using an isolated database; never touch patient data."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from database import Base, get_db
from models_db import (Paciente, EvaluacionTriaje, SignosVitalesHistorial,
                       AlertaGenerada, DiagnosticoSugerido)


@pytest.fixture
def api(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
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
    with TestClient(main.app) as client:
        yield client, factory
    main.app.dependency_overrides.clear()
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
