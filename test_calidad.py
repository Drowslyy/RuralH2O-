from validaciones import evaluar_nch409

def test_agua_perfecta():
    # pH 7.0, Cloro 1.5, Turbidez 2.0 (Todo dentro de norma)
    resultado = evaluar_nch409(7.0, 1.5, 2.0)
    assert resultado["apta"] == True
    assert len(resultado["alertas_generadas"]) == 0

def test_ph_critico_alto():
    # pH 10.0 (Fuera de norma, nivel crítico)
    resultado = evaluar_nch409(10.0, 1.0, 1.0)
    assert resultado["apta"] == False
    assert resultado["alertas_generadas"][0]["nivel"] == "crítico"