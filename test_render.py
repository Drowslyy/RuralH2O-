"""
test_render.py — Diagnóstico de despliegue (Iteración 7)

Verifica que la API responde correctamente a todos los endpoints que
el frontend necesita. Útil para confirmar el despliegue en Render
antes de la presentación.

USO LOCAL:    pytest test_render.py -v
USO RENDER:   set RURALH2O_URL=https://tu-app.onrender.com  (PowerShell: $env:RURALH2O_URL="...")
              luego: pytest test_render.py -v

Si no se define RURALH2O_URL, usa el TestClient local (no toca Render).
"""

import os
import pytest

URL = os.getenv("RURALH2O_URL", "").rstrip("/")

if URL:
    # Modo Render: peticiones HTTP reales contra el servicio desplegado
    import urllib.request
    import json as _json

    def _get(path):
        req = urllib.request.Request(URL + path, headers={"User-Agent": "ruralh2o-test"})
        with urllib.request.urlopen(req, timeout=90) as r:  # 90s: Render free tarda en despertar
            return r.status, _json.loads(r.read().decode())

    class TestRenderVivo:
        def test_mapa_responde(self):
            status, data = _get("/mapa/puntos-calidad")
            assert status == 200
            assert isinstance(data, list)

        def test_resumen_responde(self):
            status, data = _get("/mapa/resumen")
            assert status == 200
            assert "total" in data

        def test_comunidades_responde(self):
            status, data = _get("/mapa/comunidades")
            assert status == 200
            assert isinstance(data, list)

        def test_avisos_responde(self):
            status, data = _get("/avisos/")
            assert status == 200
            assert isinstance(data, list)

        def test_puntos_responde(self):
            status, data = _get("/puntos/")
            assert status == 200
            assert isinstance(data, list)

else:
    # Modo local: usa el TestClient (sin tocar Render)
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)

    class TestApiLocal:
        def test_mapa_responde(self):
            r = client.get("/mapa/puntos-calidad")
            assert r.status_code == 200
            assert isinstance(r.json(), list)

        def test_resumen_responde(self):
            r = client.get("/mapa/resumen")
            assert r.status_code == 200
            assert "total" in r.json()

        def test_comunidades_responde(self):
            r = client.get("/mapa/comunidades")
            assert r.status_code == 200

        def test_avisos_responde(self):
            r = client.get("/avisos/")
            assert r.status_code == 200
            assert isinstance(r.json(), list)

        def test_puntos_responde(self):
            r = client.get("/puntos/")
            assert r.status_code == 200