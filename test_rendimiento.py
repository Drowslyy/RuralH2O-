"""
test_rendimiento.py — Métricas de rendimiento (RNF)

Mide el tiempo de carga del endpoint del mapa y verifica que cumple
el requisito no funcional de rendimiento (<= 4 segundos).

USO LOCAL (con TestClient, sin red):
    pytest test_rendimiento.py -v -s

USO CONTRA RENDER (mide el tiempo real en producción):
    PowerShell:  $env:RURALH2O_URL="https://ruralh2o.onrender.com"
    pytest test_rendimiento.py -v -s

El parámetro -s es importante: muestra los tiempos medidos en pantalla.
"""

import os
import time
import statistics

UMBRAL_SEG = 4.0          # RNF: el mapa debe cargar en <= 4 segundos
N_MEDICIONES = 5          # número de mediciones para promediar

URL = os.getenv("RURALH2O_URL", "").rstrip("/")


def _medir(funcion_peticion):
    """Ejecuta la petición N veces y devuelve (promedio, minimo, maximo)."""
    tiempos = []
    for i in range(N_MEDICIONES):
        inicio = time.perf_counter()
        funcion_peticion()
        fin = time.perf_counter()
        tiempos.append(fin - inicio)
    return (
        statistics.mean(tiempos),
        min(tiempos),
        max(tiempos),
        tiempos,
    )


if URL:
    # ── Modo Render: mide el tiempo real en producción ──
    import urllib.request

    def _peticion():
        req = urllib.request.Request(
            URL + "/mapa/puntos-calidad",
            headers={"User-Agent": "ruralh2o-perf"},
        )
        with urllib.request.urlopen(req, timeout=90) as r:
            r.read()

    class TestRendimientoRender:
        def test_tiempo_carga_mapa(self):
            # Primera petición (puede despertar el servidor) — no se cuenta
            print("\n[Despertando el servidor si estaba inactivo...]")
            try:
                _peticion()
            except Exception:
                pass

            prom, mn, mx, tiempos = _medir(_peticion)
            print(f"\n──────── RENDIMIENTO EN RENDER ────────")
            print(f"Endpoint: /mapa/puntos-calidad")
            print(f"Mediciones: {[round(t,3) for t in tiempos]} s")
            print(f"Promedio: {prom:.3f} s")
            print(f"Mínimo:   {mn:.3f} s")
            print(f"Máximo:   {mx:.3f} s")
            print(f"Umbral RNF: {UMBRAL_SEG} s")
            print(f"Resultado: {'✔ CUMPLE' if prom <= UMBRAL_SEG else '✘ NO CUMPLE'}")
            print(f"───────────────────────────────────────")
            assert prom <= UMBRAL_SEG, f"El mapa tardó {prom:.3f}s (umbral {UMBRAL_SEG}s)"

else:
    # ── Modo local: mide con TestClient (sin red) ──
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)

    def _peticion():
        r = client.get("/mapa/puntos-calidad")
        assert r.status_code == 200

    class TestRendimientoLocal:
        def test_tiempo_carga_mapa(self):
            # Primera petición para "calentar" la caché — no se cuenta
            _peticion()

            prom, mn, mx, tiempos = _medir(_peticion)
            print(f"\n──────── RENDIMIENTO LOCAL ────────")
            print(f"Endpoint: /mapa/puntos-calidad")
            print(f"Mediciones: {[round(t,4) for t in tiempos]} s")
            print(f"Promedio: {prom:.4f} s")
            print(f"Mínimo:   {mn:.4f} s")
            print(f"Máximo:   {mx:.4f} s")
            print(f"Umbral RNF: {UMBRAL_SEG} s")
            print(f"Resultado: {'✔ CUMPLE' if prom <= UMBRAL_SEG else '✘ NO CUMPLE'}")
            print(f"───────────────────────────────────")
            assert prom <= UMBRAL_SEG