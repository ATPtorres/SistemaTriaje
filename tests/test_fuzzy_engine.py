import pytest
from fuzzy_engine import crear_sistema_difuso_triaje, calcular_score_riesgo_difuso, trapmf, trimf


@pytest.mark.parametrize('value, expected', [(19, 0), (20, 1), (35, 1), (50, 0), (51, 0)])
def test_left_shoulder_boundaries(value, expected):
    assert trapmf(value, (20, 20, 35, 50)) == expected


def test_right_and_triangular_shoulders():
    assert trapmf(100, (90, 95, 100, 100)) == 1
    assert trimf(0, (0, 0, 10)) == 1
    assert trimf(10, (0, 10, 10)) == 1


def test_missing_antecedent_never_activates_fuzzy_rule():
    motor = crear_sistema_difuso_triaje()
    scores = {r.id: strength for r, strength in motor.evaluar_reglas({'FC': {'MuyAlta': 1}})}
    assert scores['R01'] == 0


@pytest.mark.parametrize('values', [(300, 98, 120, 36.5, 35), (75, 0, 120, 36.5, 35), (75, 98, 120, 45, 35)])
def test_out_of_range_is_not_an_invented_score(values):
    score, metadata = calcular_score_riesgo_difuso(*values)
    assert score is None
    assert metadata['estado'] == 'sin_resultado'
    assert metadata['motivo'] == 'fuera_de_rango'


def test_no_rules_or_missing_inputs_return_no_score():
    motor = crear_sistema_difuso_triaje()
    assert motor.defuzzificar([]) is None
    assert motor.defuzzificar([(motor.reglas[0], 0)]) is None
    assert motor.inferir({'FC': 180})[0] is None


def test_grouped_centroid_preserves_mamdani_result():
    motor = crear_sistema_difuso_triaje()
    forces = motor.evaluar_reglas(motor.fuzzificar({'FC': 120, 'SpO2': 92, 'PAS': 90, 'Temp': 38, 'Edad': 70}))
    numerator = denominator = 0
    for i in range(201):
        x = i / 2
        memberships = motor.variable_salida.evaluar(x)
        value = max(min(memberships.get(r.consecuente[1], 0), strength) for r, strength in forces)
        numerator += x * value
        denominator += value
    assert motor.defuzzificar(forces) == pytest.approx(numerator / denominator)
