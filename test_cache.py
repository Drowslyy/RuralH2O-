"""
test_cache.py — Comparación de rendimiento: caché vacía vs caché llena

Mide el efecto de la optimización de la Iteración 6 (caché en memoria del
endpoint del mapa) de forma honesta y reproducible:

  - 1ª petición: la caché está vacía, la respuesta se calcula desde la BD.
  - Peticiones siguientes: la caché está llena, la respuesta es inmediata.

La diferencia entre ambas demuestra el efecto real de la caché, sin
necesidad de comparar contra una versión antigua del código.

USO CONTRA RENDER (recomendado):
    PowerShell:  $env:RURALH2O_URL="https://ruralh2o.onrender.com"
    pytest test_cache.py -v -s

El parámetro -s muestra los tiempos en pantalla.

NOTA: la caché tiene un tiempo de vida (TTL). Si entre peticiones pasa más
tiempo que el TTL, la caché se vuelve a llenar. Por eso las peticiones
cacheadas se hacen seguidas, sin pausa.
"""

import os
import time
import statistics

URL = os.getenv("RURALH2O_URL", "").rstrip("/")

if not URL:
    import pytest
    pytest.skip(
        "Define RURALH2O_URL para medir contra Render. "
        "Ej: $env:RURALH2O_URL='https://ruralh2o.onrender.com'",
        allow_module_level=True,
    )

import urllib.request


def _peticion():
    req = urllib.request.Request(
        URL + "/mapa/puntos-calidad",
        headers={"User-Agent": "ruralh2o-cache"},
    )
    inicio = time.perf_counter()
    with urllib.request.urlopen(req, timeout=90) as r:
        r.read()
    return time.perf_counter() - inicio


class TestCacheComparacion:

    def test_cache_vacia_vs_llena(self):
        # Despertar el servidor (no se cuenta)
        print("\n[Despertando el servidor si estaba inactivo...]")
        try:
            _peticion()
        except Exception:
            pass

        # Esperar a que expire la caché para forzar una petición "fría"
        print("[Esperando a que expire la caché para medir petición fría...]")
        time.sleep(35)  # mayor que el TTL de la caché (30 s)

        # 1ª petición: caché vacía (se calcula desde la BD)
        t_fria = _peticion()

        # Peticiones siguientes: caché llena (respuesta inmediata)
        cacheadas = [_peticion() for _ in range(5)]
        t_cacheada = statistics.mean(cacheadas)

        mejora = (1 - t_cacheada / t_fria) * 100 if t_fria > 0 else 0

        print(f"\n──────── EFECTO DE LA CACHÉ (Render) ────────")
        print(f"Endpoint: /mapa/puntos-calidad")
        print(f"Petición fría (caché vacía):  {t_fria:.3f} s")
        print(f"Peticiones cacheadas (prom.): {t_cacheada:.3f} s")
        print(f"   Mediciones cacheadas: {[round(t,3) for t in cacheadas]} s")
        print(f"Mejora con caché: {mejora:.1f}% más rápido")
        print(f"─────────────────────────────────────────────")

        # Ambas deben cumplir el RNF (<= 4 s)
        assert t_fria <= 4.0
        assert t_cacheada <= 4.0