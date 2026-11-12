"""Public triage facade: decision and explanations come from the same rule engine."""
from knowledge_base import BaseConocimiento, ENGINE_VERSION
from models import DatosPaciente, ResultadoTriaje


class MotorTriaje:
    def __init__(self, base_conocimiento: BaseConocimiento | None = None):
        self.base = base_conocimiento or BaseConocimiento()

    def evaluar(self, paciente: DatosPaciente) -> ResultadoTriaje:
        self.base.establecer_hechos(paciente.model_dump(mode='json'))
        level, trace, explanation = self.base.forward_chaining()
        selected = [step for step in trace if step['decisiva']]
        output = self.base.config.salidas[str(level)]
        rules = [self.base.consultar_regla(step['regla_id']) for step in selected]
        return ResultadoTriaje(
            id_paciente=paciente.id_paciente, nivel_prioridad=level, color=output.color,
            motivo_clinico=' | '.join(step['conclusion'] for step in selected),
            signos_alerta=list(dict.fromkeys(alert for rule in rules for alert in rule.alertas)),
            recomendacion=output.recomendacion,
            metadata_motor={
                'sintomas_no_evaluados': sorted(
                    [name for name, value in paciente.sintomas.model_dump().items() if value is None] +
                    [name for name in self.base.config.entradas_adicionales if paciente.sintomas_adicionales.get(name) is None]),
                'metodo_inferencia': 'Forward Chaining (reglas locales)',
                'reglas_evaluadas': len(trace), 'reglas_activadas': sum(s['activa'] for s in trace),
                'explicaciones': explanation, 'traza_completa': trace,
                'conocimiento': {k: v for k, v in explanation['conocimiento'].items() if k != 'snapshot'},
                'validacion_clinica': 'pendiente', 'version_motor': ENGINE_VERSION,
            })


def evaluar_triaje(paciente: DatosPaciente) -> ResultadoTriaje:
    return MotorTriaje().evaluar(paciente)
