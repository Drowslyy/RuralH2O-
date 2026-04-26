# validaciones.py
# Módulo centralizado de validación según Norma NCh 409 (Agua Potable - Chile)

def evaluar_nch409(ph: float, cloro: float, turbidez: float) -> dict:
    """
    Evalúa una medición según la norma NCh 409.
    Retorna un diccionario con:
        - apta: True/False
        - observaciones: texto con los parámetros fuera de rango
        - alertas_generadas: lista de alertas a crear en la BD
    """
    observaciones = []
    alertas_generadas = []

    # --- Validación de pH ---
    if ph < 6.5 or ph > 8.5:
        # Nivel crítico si está muy fuera del rango
        if ph < 6.0 or ph > 9.0:
            nivel = "crítico"
        else:
            nivel = "advertencia"

        tipo = "pH bajo" if ph < 6.5 else "pH alto"
        mensaje = f"pH registrado: {ph}. Rango aceptable NCh 409: 6.5 - 8.5"

        observaciones.append(f"pH fuera de rango ({ph})")
        alertas_generadas.append({
            "tipo": tipo,
            "nivel": nivel,
            "mensaje": mensaje
        })

    # --- Validación de Cloro Residual ---
    if cloro > 2.0:
        observaciones.append(f"Cloro elevado ({cloro} mg/L)")
        alertas_generadas.append({
            "tipo": "Cloro alto",
            "nivel": "crítico",
            "mensaje": f"Cloro registrado: {cloro} mg/L. Máximo NCh 409: 2.0 mg/L"
        })

    # --- Validación de Turbidez ---
    if turbidez > 5.0:
        observaciones.append(f"Turbidez elevada ({turbidez} NTU)")
        alertas_generadas.append({
            "tipo": "Turbidez crítica",
            "nivel": "crítico",
            "mensaje": f"Turbidez registrada: {turbidez} NTU. Máximo NCh 409: 5.0 NTU"
        })

    # --- Resultado Final ---
    apta = len(observaciones) == 0

    return {
        "apta": apta,
        "observaciones": "; ".join(observaciones) if observaciones else None,
        "alertas_generadas": alertas_generadas
    }