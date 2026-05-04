import pytest
from validaciones import evaluar_nch409

# Lista de casos de prueba: (ph, cloro, turbidez, resultado_esperado, total_alertas)
casos_prueba = [
    # 1. CASOS APTOS (Límites de la norma)
    (7.0, 1.5, 2.0, True, 0),   # Todo perfecto
    (6.5, 0.2, 0.0, True, 0),   # Límite inferior de pH y cloro
    (8.5, 2.0, 5.0, True, 0),   # Límite superior de pH, cloro y turbidez
    
    # 2. FALLOS POR PH
    (6.4, 1.0, 1.0, False, 1),  # pH justo abajo (advertencia)
    (5.9, 1.0, 1.0, False, 1),  # pH muy abajo (crítico)
    (8.6, 1.0, 1.0, False, 1),  # pH justo arriba (advertencia)
    (9.1, 1.0, 1.0, False, 1),  # pH muy arriba (crítico)
    
    # 3. FALLOS POR CLORO
    (7.0, 2.1, 1.0, False, 1),  # Cloro excedido (2.1)
    (7.0, 5.0, 1.0, False, 1),  # Cloro al máximo permitido por el schema
    
    # 4. FALLOS POR TURBIDEZ
    (7.0, 1.0, 5.1, False, 1),  # Turbidez apenas excedida
    (7.0, 1.0, 100.0, False, 1), # Turbidez extrema
    
    # 5. FALLOS MÚLTIPLES (Combo mortal)
    (10.0, 4.0, 20.0, False, 3), # pH, Cloro y Turbidez mal (3 alertas)
]

@pytest.mark.parametrize("ph, cloro, turbidez, esperado, num_alertas", casos_prueba)
def test_matriz_calidad(ph, cloro, turbidez, esperado, num_alertas):
    """
    Test parametrizado que recorre toda la lógica de la NCh 409
    """
    resultado = evaluar_nch409(ph, cloro, turbidez)
    
    # Verificamos si el agua es apta o no
    assert resultado["apta"] == esperado, f"Fallo en aptitud: pH={ph}, Cl={cloro}, Turb={turbidez}"
    
    # Verificamos que se generen la cantidad correcta de alertas
    assert len(resultado["alertas_generadas"]) == num_alertas
    
    # Si hay alertas, verificar que el mensaje no esté vacío
    if num_alertas > 0:
        assert len(resultado["observaciones"]) > 0

def test_niveles_de_alerta():
    """
    Verifica específicamente que los niveles pasen de advertencia a crítico
    """
    # Caso advertencia (pH 8.7 está entre 8.5 y 9.0)
    res_adv = evaluar_nch409(8.7, 1.0, 1.0)
    assert res_adv["alertas_generadas"][0]["nivel"] == "advertencia"
    
    # Caso crítico (pH 9.5 es > 9.0)
    res_crit = evaluar_nch409(9.5, 1.0, 1.0)
    assert res_crit["alertas_generadas"][0]["nivel"] == "crítico"