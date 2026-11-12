"""Restricted additive knowledge. The HTTP API never edits the base rule file."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, StrictInt
from typing import Annotated
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models_db import SintomaAdicional, RevisionAmpliacion
from models import DatosPaciente, ResultadoTriaje
from pathlib import Path

router = APIRouter(tags=["Síntomas ampliables"])
TextName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=100)]


class NuevoSintoma(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: TextName
    descripcion: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=500)]
    nivel: StrictInt = Field(ge=2, le=4)


def validar_origen_local(request: Request):
    """Local deployment boundary + same-origin custom header to prevent CSRF."""
    if not request.client or request.client.host not in {"127.0.0.1", "::1"}:
        raise HTTPException(403, "La gestión de síntomas está habilitada solo en esta PC.")
    if request.headers.get("X-Triaje-Gestion") != "1":
        raise HTTPException(403, "Solicitud de gestión no válida.")
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "Origen de gestión no permitido.")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "Origen de gestión no permitido.")
    # Reject DNS rebinding to a local server exposed through an untrusted host.
    if urlsplit(str(request.base_url)).hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise HTTPException(403, "Servidor local no reconocido.")


def gestion_local(request: Request):
    validar_origen_local(request)
    from knowledge_access import exigir_administrador
    return exigir_administrador(request)


def listar_ampliaciones(db: Session, incluir_inactivos=False):
    query = db.query(SintomaAdicional).options(joinedload(SintomaAdicional.revision))
    if not incluir_inactivos:
        query = query.filter(SintomaAdicional.activo.is_(True))
    return query.order_by(SintomaAdicional.creado_en, SintomaAdicional.id).all()


def serializar(row):
    return {"id": row.id, "nombre": row.nombre, "descripcion": row.descripcion,
            "nivel": row.nivel, "activo": row.activo,
            "estado": row.revision.estado if row.revision else ('publicado' if row.activo else 'desactivado'),
            "creado_por": row.revision.creado_por if row.revision else 'registro_anterior',
            "publicado_por": row.revision.publicado_por if row.revision else None,
            "ensayado": bool(row.revision and row.revision.ensayado_en),
            "creado_en": row.creado_en.isoformat() if row.creado_en else None}


def integrar_ampliaciones(data, rows):
    """Compile a constrained presence rule; cannot override facts or lower urgency."""
    result = deepcopy(data)
    entries = result.setdefault("entradas_adicionales", [])
    for row in rows:
        if not row.activo:
            continue
        # Revalidate persisted content, including records changed outside the UI.
        validated = NuevoSintoma(nombre=row.nombre, descripcion=row.descripcion, nivel=row.nivel)
        entries.append(row.id)
        result["reglas"].append({
            "id": "USR_" + row.id[3:].upper(), "nombre": validated.nombre,
            "descripcion": validated.descripcion,
            "condiciones": [{"hecho": row.id, "operador": "==", "valor": True}],
            "conclusion": f"Síntoma adicional presente: {validated.nombre}. {validated.descripcion}",
            "nivel_asignado": validated.nivel, "confianza": 0.0, "prioridad": -10,
            "activa": True, "efectos": {}, "alertas": [f"Síntoma adicional: {validated.nombre}"]})
    return result


@router.get("/conocimiento", response_class=HTMLResponse)
def pagina_gestion():
    return HTMLResponse(Path(__file__).with_name("static").joinpath("conocimiento.html").read_text(encoding="utf-8"))


@router.get("/conocimiento/sintomas")
def catalogo(db: Session = Depends(get_db)):
    return {"sintomas": [serializar(s) for s in listar_ampliaciones(db, True)],
            "limites": {"niveles_permitidos": [2, 3, 4], "reglas_base_editables": False,
                        "tipo_regla": "síntoma presente", "gestion": "solo_local"}}


@router.post("/triaje/simular", response_model=ResultadoTriaje)
def simular(paciente: DatosPaciente, db: Session = Depends(get_db)):
    """Run current knowledge without writing patient or evaluation records."""
    from knowledge_base import BaseConocimiento
    from triage_engine import MotorTriaje
    additions = listar_ampliaciones(db)
    if not set(paciente.sintomas_adicionales) <= {s.id for s in additions}:
        raise HTTPException(409, "El catálogo de síntomas cambió. Actualice la página.")
    result = MotorTriaje(BaseConocimiento(ampliaciones=additions)).evaluar(paciente)
    result.metadata_motor["simulacion"] = True
    result.metadata_motor["guardado_en_bd"] = False
    return result


@router.post("/conocimiento/sintomas", status_code=201, dependencies=[Depends(gestion_local)])
def crear(datos: NuevoSintoma, request: Request, db: Session = Depends(get_db)):
    name = " ".join(datos.nombre.split())
    normalized = name.casefold()
    # Prevent confusing copies of the fixed symptoms, even with different accents.
    import unicodedata
    plain = "".join(c for c in unicodedata.normalize("NFD", normalized) if unicodedata.category(c) != "Mn")
    base_names = {"dolor toracico", "dificultad respiratoria", "sangrado activo", "convulsiones",
                  "alteracion de conducta", "alteracion conducta", "trauma significativo", "dolor intenso"}
    if plain in base_names:
        raise HTTPException(409, "Este síntoma ya pertenece al conocimiento base protegido.")
    if db.query(SintomaAdicional).count() >= 100:
        raise HTTPException(409, "Se alcanzó el límite de 100 ampliaciones.")
    row = SintomaAdicional(id="sx_" + uuid4().hex, nombre=name, nombre_normalizado=plain,
                          descripcion=datos.descripcion, nivel=datos.nivel, activo=False)
    from knowledge_access import exigir_administrador
    row.revision = RevisionAmpliacion(estado='borrador', creado_por=exigir_administrador(request)['usuario'])
    try:
        db.add(row)
        db.flush()
        # Validate complete graph before publication; the base file stays intact.
        from knowledge_base import BaseConocimiento
        BaseConocimiento(ampliaciones=listar_ampliaciones(db))
        db.commit()
        db.refresh(row)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Ya existe un síntoma con ese nombre, incluso si está desactivado.")
    except Exception:
        db.rollback()
        raise
    return serializar(row)


@router.post("/conocimiento/sintomas/{sintoma_id}/desactivar", dependencies=[Depends(gestion_local)])
def desactivar(sintoma_id: str, db: Session = Depends(get_db)):
    row = db.get(SintomaAdicional, sintoma_id)
    if row is None:
        raise HTTPException(404, "Ampliación no encontrada. Las reglas base no se pueden modificar.")
    row.activo = False
    if row.revision:
        row.revision.estado = 'desactivado'
    row.desactivado_en = datetime.now(timezone.utc)
    db.commit()
    return serializar(row)


@router.post('/conocimiento/sintomas/{sintoma_id}/publicar', dependencies=[Depends(gestion_local)])
def publicar(sintoma_id: str, request: Request, db: Session = Depends(get_db)):
    row = db.get(SintomaAdicional, sintoma_id)
    if not row or not row.revision or row.revision.estado != 'borrador':
        raise HTTPException(409, 'Solo se pueden publicar borradores nuevos.')
    if row.revision.ensayado_en is None:
        raise HTTPException(409, 'Primero ejecute el ensayo del borrador.')
    from knowledge_access import exigir_administrador
    from knowledge_base import BaseConocimiento
    row.activo = True
    row.revision.estado = 'publicado'
    row.revision.publicado_por = exigir_administrador(request)['usuario']
    row.revision.publicado_en = datetime.now(timezone.utc)
    try:
        db.flush()
        BaseConocimiento(ampliaciones=listar_ampliaciones(db))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return serializar(row)


@router.post('/conocimiento/sintomas/{sintoma_id}/ensayo', dependencies=[Depends(gestion_local)])
def ensayar_borrador(sintoma_id: str, db: Session = Depends(get_db)):
    from types import SimpleNamespace
    from knowledge_base import BaseConocimiento
    from triage_engine import MotorTriaje
    row = db.get(SintomaAdicional, sintoma_id)
    if not row or not row.revision or row.revision.estado != 'borrador':
        raise HTTPException(409, 'Seleccione un borrador pendiente.')
    candidate = SimpleNamespace(id=row.id, nombre=row.nombre, descripcion=row.descripcion, nivel=row.nivel, activo=True)
    base = BaseConocimiento(ampliaciones=[*listar_ampliaciones(db), candidate])
    results = []
    for value in (None, False, True):
        patient = DatosPaciente(id_paciente='ENSAYO-SINTETICO', edad=35, nivel_conciencia='Alerta',
                                signos_vitales={'frecuencia_cardiaca': 75, 'saturacion_oxigeno': 98,
                                                'presion_sistolica': 120, 'presion_diastolica': 80, 'temperatura': 36.5},
                                sintomas_adicionales={row.id: value})
        result = MotorTriaje(base).evaluar(patient)
        results.append({'presencia': value, 'nivel': result.nivel_prioridad, 'motivo': result.motivo_clinico})
    row.revision.ensayado_en = datetime.now(timezone.utc)
    db.commit()
    return {'tipo': 'ensayo_sintetico', 'validacion_clinica': 'pendiente', 'resultados': results}
