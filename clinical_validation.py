"""Compare local priorities with reference labels; never certify clinical safety.

Example: python clinical_validation.py --cases tests/fixtures/triage_regression.json
The report contains aggregate metrics, not patient data or identifiers.
"""
import argparse
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.exc import SQLAlchemyError
from knowledge_base import BaseConocimiento, ENGINE_VERSION
from models import DatosPaciente
from triage_engine import MotorTriaje


class ReferenceCase(BaseModel):
    model_config = ConfigDict(extra='forbid')
    paciente: DatosPaciente
    nivel_referencia: int = Field(ge=1, le=5, strict=True)


class ReferenceDataset(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tipo: Literal['sintetico', 'adjudicado']
    referencia: str = Field(min_length=1)
    revisor: str | None = None
    casos: list[ReferenceCase] = Field(min_length=1)

    @model_validator(mode='after')
    def require_provenance(self):
        if self.tipo == 'adjudicado' and not (self.revisor and self.revisor.strip()):
            raise ValueError('Los casos adjudicados requieren identificación del revisor')
        identifiers = [c.paciente.id_paciente for c in self.casos]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError('Identificadores de caso duplicados')
        return self


def evaluate_dataset(dataset: ReferenceDataset, knowledge_path=None, *, ampliaciones=None):
    base = BaseConocimiento(knowledge_path, ampliaciones=ampliaciones)
    motor = MotorTriaje(base)
    matrix = [[0] * 5 for _ in range(5)]
    for case in dataset.casos:
        predicted = motor.evaluar(case.paciente).nivel_prioridad
        matrix[case.nivel_referencia - 1][predicted - 1] += 1
    total = len(dataset.casos)
    correct = sum(matrix[i][i] for i in range(5))
    under = sum(matrix[i][j] for i in range(5) for j in range(i + 1, 5))
    over = sum(matrix[i][j] for i in range(5) for j in range(i))
    return {
        'version_motor': ENGINE_VERSION, 'tipo_datos': dataset.tipo, 'referencia': dataset.referencia,
        'revisor': dataset.revisor, 'version_conocimiento': base.config.version,
        'sha256_conocimiento': base.sha256, 'casos_ejecutados': total,
        'matriz_confusion': {'filas': 'nivel_referencia', 'columnas': 'nivel_local',
                            'niveles': [1, 2, 3, 4, 5], 'valores': matrix},
        'concordancia_exacta': correct / total,
        'subtriaje': {'casos': under, 'tasa': under / total},
        'sobretriaje': {'casos': over, 'tasa': over / total},
        'sensibilidad_por_nivel': {
            str(i + 1): matrix[i][i] / sum(matrix[i]) if sum(matrix[i]) else None for i in range(5)},
        'validacion_clinica': 'pendiente',
        'limitaciones': 'Concordancia con etiquetas aportadas; no certifica seguridad, calibración ni equivalencia con protocolos oficiales.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, required=True)
    parser.add_argument('--knowledge', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--include-extensions', action='store_true', help='Evaluar el conocimiento activo de MySQL junto al archivo base')
    args = parser.parse_args()
    # Do not include input values in validation error messages or reports.
    try:
        dataset = ReferenceDataset.model_validate_json(args.cases.read_text(encoding='utf-8'))
        if args.include_extensions:
            from database import SessionLocal
            from symptom_extensions import listar_ampliaciones
            with SessionLocal() as db:
                report = evaluate_dataset(dataset, args.knowledge, ampliaciones=listar_ampliaciones(db))
        else:
            report = evaluate_dataset(dataset, args.knowledge)
    except (ValueError, OSError, SQLAlchemyError):
        parser.exit(2, 'No se pudo validar el conjunto de referencia o la base de conocimiento.\n')
    output = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(output, encoding='utf-8')
    else:
        print(output, end='')


if __name__ == '__main__':
    main()
