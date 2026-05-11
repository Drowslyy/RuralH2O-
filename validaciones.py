# =============================
#   Lógica NCh 409 - Validaciones
# =============================

def evaluar_nch409(ph: float, cloro: float, turbidez: float) -> dict:
    """
    Evalúa si los parámetros cumplen la norma chilena NCh 409.
    Retorna veredicto, observaciones y alertas generadas.

    Límites NCh 409:
      pH        : 6.5 – 8.5       (advertencia si 6.0–6.5 o 8.5–9.0)
      Cloro     : 0.2 – 2.0 mg/L  (advertencia si 2.0–3.0)
      Turbidez  : <= 5 NTU         (advertencia si 5–10)
    """
    apta = True
    observaciones_list = []
    alertas = []

    # ── pH ──────────────────────────────────────────────
    if ph < 6.0 or ph > 9.0:
        apta = False
        observaciones_list.append(f"pH {ph} fuera de rango crítico (6.0–9.0)")
        alertas.append({"tipo": "pH", "nivel": "crítico", "mensaje": f"pH={ph} fuera de norma NCh 409"})
    elif ph < 6.5 or ph > 8.5:
        # FIX: advertencia se registra aunque apta=True (zona límite)
        observaciones_list.append(f"pH {ph} en zona límite (advertencia)")
        alertas.append({"tipo": "pH", "nivel": "advertencia", "mensaje": f"pH={ph} en zona límite NCh 409"})

    # ── Cloro ────────────────────────────────────────────
    if cloro < 0.2 or cloro > 3.0:
        apta = False
        observaciones_list.append(f"Cloro {cloro} mg/L fuera de rango crítico (0.2–3.0)")
        alertas.append({"tipo": "cloro", "nivel": "crítico", "mensaje": f"Cloro={cloro} mg/L fuera de norma NCh 409"})
    elif cloro > 2.0:
        observaciones_list.append(f"Cloro {cloro} mg/L en zona límite (advertencia)")
        alertas.append({"tipo": "cloro", "nivel": "advertencia", "mensaje": f"Cloro={cloro} mg/L en zona límite NCh 409"})

    # ── Turbidez ─────────────────────────────────────────
    if turbidez > 10:
        apta = False
        observaciones_list.append(f"Turbidez {turbidez} NTU fuera de rango crítico (>10)")
        alertas.append({"tipo": "turbidez", "nivel": "crítico", "mensaje": f"Turbidez={turbidez} NTU fuera de norma NCh 409"})
    elif turbidez > 5:
        observaciones_list.append(f"Turbidez {turbidez} NTU en zona límite (advertencia)")
        alertas.append({"tipo": "turbidez", "nivel": "advertencia", "mensaje": f"Turbidez={turbidez} NTU en zona límite NCh 409"})

    return {
        "apta":              apta,
        "observaciones":     "; ".join(observaciones_list) if observaciones_list else "Cumple NCh 409",
        "alertas_generadas": alertas,
    }

    