# ============================================================
#  RuralH2O — Test Suite Semana 11: Iteración 5
#  Cobertura: PWA (manifest, sw.js) + offline UX + regresión
#  Ejecutar: pytest test_s11.py -v --cov=. --cov-report=term-missing
# ============================================================

import os
import json
import tempfile
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ── Base de datos en memoria (aislada) ──────────────────────
_db_path = os.path.join(tempfile.gettempdir(), "test_s11_temp.db").replace("\\", "/")
TEST_DB_URL = "sqlite:///" + _db_path
os.environ["DATABASE_URL"] = TEST_DB_URL

from database import Base, get_db
from main import app

engine_test = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def limpiar_bd():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine_test)
    yield
    Base.metadata.drop_all(bind=engine_test)
    app.dependency_overrides.pop(get_db, None)


client = TestClient(app)


# ============================================================
# HELPERS
# ============================================================

def registrar_usuario(email="user@test.cl", password="pass1234", rol="registrador"):
    client.post("/usuarios/", json={"nombre": "Test", "email": email, "password": password, "rol": rol})


def obtener_token(email="user@test.cl", password="pass1234"):
    r = client.post("/login", data={"username": email, "password": password})
    return r.json().get("access_token")


def headers(token):
    return {"Authorization": f"Bearer {token}"}


def crear_admin():
    registrar_usuario("admin@test.cl", "admin1234", "admin")
    return obtener_token("admin@test.cl", "admin1234")


def crear_punto(token_admin, nombre="Pozo Norte", lat=-45.57, lng=-72.06):
    r = client.post("/puntos/", json={
        "nombre": nombre, "tipo_fuente": "pozo",
        "comunidad": "Villa Aysén", "latitud": lat, "longitud": lng
    }, headers=headers(token_admin))
    return r.json()["id"]


# ============================================================
# BLOQUE 1 — PWA: manifest.json y service worker
# ============================================================

class TestPWA:
    """Verifica que los artefactos PWA están disponibles y son válidos."""

    def test_manifest_retorna_200(self):
        """El archivo manifest.json es accesible via /view/manifest.json."""
        r = client.get("/view/manifest.json")
        assert r.status_code == 200

    def test_manifest_content_type_json(self):
        """manifest.json se sirve con content-type JSON."""
        r = client.get("/view/manifest.json")
        assert "json" in r.headers.get("content-type", "")

    def test_manifest_tiene_campos_requeridos(self):
        """manifest.json contiene name, start_url, display e icons."""
        r = client.get("/view/manifest.json")
        data = r.json()
        assert "name" in data
        assert "start_url" in data
        assert "display" in data
        assert "icons" in data
        assert len(data["icons"]) >= 1

    def test_manifest_display_standalone(self):
        """display debe ser standalone para instalación como app."""
        r = client.get("/view/manifest.json")
        assert r.json()["display"] == "standalone"

    def test_manifest_start_url_campo(self):
        """start_url apunta a campo.html (app movil de campo — PWA entry point)."""
        r = client.get("/view/manifest.json")
        assert "campo" in r.json()["start_url"]

    def test_sw_retorna_200(self):
        """El Service Worker sw.js es accesible via /view/sw.js."""
        r = client.get("/view/sw.js")
        assert r.status_code == 200

    def test_sw_content_type_javascript(self):
        """sw.js se sirve con content-type JavaScript."""
        r = client.get("/view/sw.js")
        ct = r.headers.get("content-type", "")
        assert "javascript" in ct or "text" in ct

    def test_sw_contiene_cache_name(self):
        """sw.js declara un CACHE_NAME (requerido para versionado)."""
        r = client.get("/view/sw.js")
        assert "CACHE_NAME" in r.text or "ruralh2o" in r.text.lower()

    def test_sw_contiene_fetch_handler(self):
        """sw.js registra un handler para el evento fetch (intercepcion offline)."""
        r = client.get("/view/sw.js")
        assert "fetch" in r.text

    def test_sw_contiene_install_y_activate(self):
        """sw.js tiene los handlers install y activate (ciclo de vida SW)."""
        r = client.get("/view/sw.js")
        assert "install" in r.text
        assert "activate" in r.text

    def test_icono_192_accesible(self):
        """El icono 192x192 esta disponible para instalacion en Android."""
        r = client.get("/view/icon-192.png")
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("image/")

    def test_icono_512_accesible(self):
        """El icono 512x512 esta disponible para pantalla de splash."""
        r = client.get("/view/icon-512.png")
        assert r.status_code == 200

    def test_campo_html_accesible(self):
        """campo.html (app movil de campo) es accesible via /view/campo.html."""
        r = client.get("/view/campo.html")
        assert r.status_code == 200

    def test_campo_html_tiene_manifest_link(self):
        """campo.html incluye link rel=manifest para activar PWA."""
        r = client.get("/view/campo.html")
        assert "manifest" in r.text

    def test_campo_html_registra_sw(self):
        """campo.html contiene codigo para registrar el Service Worker."""
        r = client.get("/view/campo.html")
        assert "serviceWorker" in r.text

    def test_campo_html_tiene_indexeddb(self):
        """campo.html contiene logica IndexedDB para modo offline."""
        r = client.get("/view/campo.html")
        assert "indexedDB" in r.text

    def test_campo_html_tiene_logica_offline(self):
        """campo.html detecta estado offline y guarda mediciones localmente."""
        r = client.get("/view/campo.html")
        assert "navigator.onLine" in r.text
        assert "idbAdd" in r.text or "ST_MED" in r.text

    def test_campo_html_tiene_sync(self):
        """campo.html tiene funcion de sincronizacion al volver online."""
        r = client.get("/view/campo.html")
        assert "sincronizarTodo" in r.text or "sincronizar" in r.text.lower()

    def test_campo_html_api_base_dinamico(self):
        """campo.html usa window.location.origin (compatible con ngrok y Render)."""
        r = client.get("/view/campo.html")
        assert "window.location.origin" in r.text
        assert 'API_BASE = "http://localhost' not in r.text

    def test_mediciones_html_desktop_accesible(self):
        """mediciones.html (app escritorio con Leaflet) sigue accesible."""
        r = client.get("/view/mediciones.html")
        assert r.status_code == 200
        assert "serviceWorker" in r.text
        assert "indexedDB" in r.text


# ============================================================
# BLOQUE 2 — Regresion: la API sigue funcionando
# ============================================================

class TestRegresion:
    """Asegura que la Iteracion 5 no rompio nada anterior."""

    def setup_method(self):
        self.token_admin = crear_admin()
        registrar_usuario()
        self.token_reg = obtener_token()
        self.punto_id = crear_punto(self.token_admin)

    def test_login_sigue_funcionando(self):
        r = client.post("/login", data={"username": "admin@test.cl", "password": "admin1234"})
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_medicion_apta_sigue_ok(self):
        r = client.post("/mediciones/", json={
            "ph": 7.0, "cloro": 1.0, "turbidez": 2.0, "punto_id": self.punto_id
        }, headers=headers(self.token_reg))
        assert r.status_code == 200
        assert r.json()["apta"] is True

    def test_medicion_inapta_genera_alerta(self):
        client.post("/mediciones/", json={
            "ph": 5.0, "cloro": 1.0, "turbidez": 2.0, "punto_id": self.punto_id
        }, headers=headers(self.token_reg))
        r = client.get("/alertas/")
        assert len(r.json()) >= 1

    def test_mapa_colores_ok(self):
        client.post("/mediciones/", json={
            "ph": 7.0, "cloro": 1.0, "turbidez": 2.0, "punto_id": self.punto_id
        }, headers=headers(self.token_reg))
        r = client.get("/mapa/puntos-calidad")
        assert r.status_code == 200
        assert any(p["color"] == "green" for p in r.json())

    def test_pdf_punto_sigue_generando(self):
        r = client.get(f"/puntos/{self.punto_id}/reporte.pdf")
        assert r.status_code == 200
        assert r.content[:5] == b"%PDF-"

    def test_reporte_mapa_sigue_ok(self):
        client.post("/mediciones/", json={
            "ph": 7.0, "cloro": 1.0, "turbidez": 2.0, "punto_id": self.punto_id
        }, headers=headers(self.token_reg))
        r = client.get("/reporte-mapa.pdf")
        assert r.status_code == 200
        assert r.content[:5] == b"%PDF-"