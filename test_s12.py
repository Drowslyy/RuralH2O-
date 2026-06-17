"""
test_s12.py — Iteración 6: Optimización y estabilización

Cubre:
  - Integración: flujo completo (login -> crear punto -> medición -> mapa).
  - Rendimiento: el endpoint del mapa responde bajo un umbral de tiempo.
  - Caché: respuestas repetidas del mapa son consistentes y rápidas.
  - Regresión: los endpoints clave siguen respondiendo correctamente.

Ejecutar:  pytest test_s12.py -v
"""

import time
import pytest
from fastapi.testclient import TestClient

from main import app, get_current_user


# ── Usuario simulado (registrador) para los flujos de escritura ──
class MockUser:
    def __init__(self, nombre, email, rol):
        self.nombre = nombre
        self.email = email
        self.rol = rol


def mock_registrador():
    return MockUser("Registrador Test", "registrador@ruralh2o.cl", "registrador")


client = TestClient(app)


# ==========================================================
#  RENDIMIENTO
# ==========================================================
class TestRendimiento:

    def test_mapa_responde_bajo_umbral(self):
        """El mapa debe responder en menos de 4 segundos (criterio S12)."""
        inicio = time.perf_counter()
        r = client.get("/mapa/puntos-calidad")
        elapsed = time.perf_counter() - inicio
        assert r.status_code == 200
        assert elapsed < 4.0, f"El mapa tardó {elapsed:.2f}s (umbral 4s)"

    def test_mapa_segunda_llamada_usa_cache(self):
        """La 2da llamada (cacheada) no debe ser más lenta que la 1ra."""
        t1 = time.perf_counter()
        client.get("/mapa/puntos-calidad")
        d1 = time.perf_counter() - t1

        t2 = time.perf_counter()
        r2 = client.get("/mapa/puntos-calidad")
        d2 = time.perf_counter() - t2

        assert r2.status_code == 200
        # La cacheada debe ser igual o más rápida (con margen de tolerancia)
        assert d2 <= d1 + 0.5


# ==========================================================
#  CACHÉ — consistencia de datos
# ==========================================================
class TestCache:

    def test_mapa_respuestas_consistentes(self):
        """Dos llamadas seguidas devuelven exactamente los mismos datos."""
        r1 = client.get("/mapa/puntos-calidad")
        r2 = client.get("/mapa/puntos-calidad")
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json() == r2.json()

    def test_filtros_devuelven_subconjuntos_distintos(self):
        """Filtrar por color cambia (o reduce) el conjunto de resultados."""
        todos = client.get("/mapa/puntos-calidad").json()
        solo_rojos = client.get("/mapa/puntos-calidad?color=red").json()
        assert isinstance(todos, list) and isinstance(solo_rojos, list)
        assert len(solo_rojos) <= len(todos)
        # Todos los devueltos con filtro deben ser efectivamente rojos
        assert all(p["color"] == "red" for p in solo_rojos)


# ==========================================================
#  INTEGRACIÓN — flujo completo end-to-end
# ==========================================================
class TestIntegracion:

    def test_flujo_completo_punto_y_medicion(self):
        """Crear punto -> registrar medición -> verla reflejada en el mapa."""
        app.dependency_overrides[get_current_user] = mock_registrador
        try:
            # 1) Crear un punto nuevo
            rp = client.post("/puntos/", json={
                "nombre": "Punto Integración S12",
                "tipo_fuente": "vertiente",
                "comunidad": "Test Integracion",
                "latitud": -45.60,
                "longitud": -72.00,
            })
            assert rp.status_code == 200
            punto_id = rp.json()["id"]

            # 2) Registrar una medición NO apta (pH crítico)
            rm = client.post("/mediciones/", json={
                "ph": 1.0, "cloro": 1.0, "turbidez": 1.0, "punto_id": punto_id
            })
            assert rm.status_code == 200
            assert rm.json()["apta"] is False  # pH=1 está fuera de norma

            # 3) El punto debe aparecer en el mapa marcado en rojo
            mapa = client.get("/mapa/puntos-calidad").json()
            encontrado = next((p for p in mapa if p["id"] == punto_id), None)
            assert encontrado is not None, "El punto no aparece en el mapa"
            assert encontrado["color"] == "red"
        finally:
            app.dependency_overrides = {}

    def test_medicion_apta_se_refleja_verde(self):
        """Una medición dentro de norma deja el punto en verde."""
        app.dependency_overrides[get_current_user] = mock_registrador
        try:
            rp = client.post("/puntos/", json={
                "nombre": "Punto Apto S12",
                "tipo_fuente": "pozo",
                "comunidad": "Test Apto",
                "latitud": -45.61,
                "longitud": -72.01,
            })
            punto_id = rp.json()["id"]
            client.post("/mediciones/", json={
                "ph": 7.0, "cloro": 1.0, "turbidez": 1.0, "punto_id": punto_id
            })
            mapa = client.get("/mapa/puntos-calidad").json()
            encontrado = next((p for p in mapa if p["id"] == punto_id), None)
            assert encontrado is not None
            assert encontrado["color"] == "green"
        finally:
            app.dependency_overrides = {}


# ==========================================================
#  REGRESIÓN — endpoints clave siguen operativos
# ==========================================================
class TestRegresion:

    def test_listar_puntos(self):
        r = client.get("/puntos/")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_resumen_mapa(self):
        r = client.get("/mapa/resumen")
        assert r.status_code == 200
        body = r.json()
        for clave in ["total", "aptos", "advertencia", "no_aptos", "sin_datos"]:
            assert clave in body

    def test_comunidades(self):
        r = client.get("/mapa/comunidades")
        assert r.status_code == 200
        assert isinstance(r.json(), list)