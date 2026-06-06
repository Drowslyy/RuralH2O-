# ============================================================
#  RuralH2O — Test Suite Semana 10: Iteración 4
#  Cobertura: RF-04 (Exportación PDF) + deuda técnica
#  Ejecutar: pytest test_s10.py -v --cov=. --cov-report=term-missing
# ============================================================

import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ── Base de datos en memoria (aislada, no toca tu BD real) ──
# FIX: ruta cross-platform (Windows y Linux) usando tempfile.gettempdir()
_db_path = os.path.join(tempfile.gettempdir(), "test_s10_temp.db").replace("\\", "/")
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


# ── Fixture: BD limpia antes de cada test ───────────────────
# FIX: el override se establece DENTRO del fixture para que no pise
# el override de otros archivos de test cuando se corre la suite completa.
@pytest.fixture(autouse=True)
def limpiar_bd():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine_test)
    yield
    Base.metadata.drop_all(bind=engine_test)
    app.dependency_overrides.pop(get_db, None)


client = TestClient(app)


# ============================================================
# HELPERS (mismos que test_s9.py)
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


def subir_medicion(token, punto_id, ph=7.0, cloro=1.0, turbidez=2.0):
    return client.post("/mediciones/", json={
        "ph": ph, "cloro": cloro, "turbidez": turbidez, "punto_id": punto_id
    }, headers=headers(token))


# ============================================================
# BLOQUE 1 — RF-04: Exportación PDF
# ============================================================

class TestExportacionPDF:
    """Valida que el endpoint /puntos/{id}/reporte.pdf funcione correctamente."""

    def setup_method(self):
        self.token_admin = crear_admin()
        registrar_usuario()
        self.token_reg = obtener_token()
        self.punto_id = crear_punto(self.token_admin)

    def test_pdf_punto_inexistente_retorna_404(self):
        """Solicitar PDF de un punto que no existe retorna 404."""
        r = client.get("/puntos/9999/reporte.pdf")
        assert r.status_code == 404

    def test_pdf_punto_sin_mediciones_retorna_200(self):
        """Un punto sin mediciones igual genera PDF (resumen vacío)."""
        r = client.get(f"/puntos/{self.punto_id}/reporte.pdf")
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"

    def test_pdf_content_type_correcto(self):
        """La respuesta tiene el Content-Type application/pdf."""
        subir_medicion(self.token_reg, self.punto_id)
        r = client.get(f"/puntos/{self.punto_id}/reporte.pdf")
        assert "application/pdf" in r.headers["content-type"]

    def test_pdf_content_disposition_attachment(self):
        """La respuesta incluye Content-Disposition como attachment."""
        r = client.get(f"/puntos/{self.punto_id}/reporte.pdf")
        assert "attachment" in r.headers.get("content-disposition", "")

    def test_pdf_nombre_archivo_contiene_punto_id(self):
        """El nombre del archivo PDF incluye el ID del punto."""
        r = client.get(f"/puntos/{self.punto_id}/reporte.pdf")
        disposition = r.headers.get("content-disposition", "")
        assert str(self.punto_id) in disposition

    def test_pdf_es_binario_valido(self):
        """El contenido binario comienza con el magic bytes de PDF (%PDF-)."""
        subir_medicion(self.token_reg, self.punto_id, ph=7.0, cloro=1.0, turbidez=2.0)
        r = client.get(f"/puntos/{self.punto_id}/reporte.pdf")
        assert r.status_code == 200
        assert r.content[:5] == b"%PDF-"

    def test_pdf_con_mediciones_aptas_e_inaptas(self):
        """El PDF se genera correctamente con una mezcla de mediciones aptas y no aptas."""
        subir_medicion(self.token_reg, self.punto_id, ph=7.0, cloro=1.0, turbidez=2.0)   # apta
        subir_medicion(self.token_reg, self.punto_id, ph=5.0, cloro=1.0, turbidez=2.0)   # no apta
        subir_medicion(self.token_reg, self.punto_id, ph=6.2, cloro=1.0, turbidez=2.0)   # advertencia
        r = client.get(f"/puntos/{self.punto_id}/reporte.pdf")
        assert r.status_code == 200
        assert r.content[:5] == b"%PDF-"

    def test_pdf_parametro_n_limita_mediciones(self):
        """El parámetro ?n controla cuántas mediciones se incluyen."""
        for ph in [7.0, 6.5, 7.2, 6.8, 7.5]:
            subir_medicion(self.token_reg, self.punto_id, ph=ph)
        # n=2 debe funcionar igual (sólo el PDF se genera, no podemos inspeccionar contenido)
        r = client.get(f"/puntos/{self.punto_id}/reporte.pdf?n=2")
        assert r.status_code == 200

    def test_pdf_parametro_n_invalido_retorna_422(self):
        """n=0 no está permitido por la validación de Query (ge=1)."""
        r = client.get(f"/puntos/{self.punto_id}/reporte.pdf?n=0")
        assert r.status_code == 422

    def test_pdf_parametro_n_maximo(self):
        """n=100 es el límite máximo permitido; n=101 retorna 422."""
        r_ok  = client.get(f"/puntos/{self.punto_id}/reporte.pdf?n=100")
        r_err = client.get(f"/puntos/{self.punto_id}/reporte.pdf?n=101")
        assert r_ok.status_code  == 200
        assert r_err.status_code == 422


# ============================================================
# BLOQUE 2 — Deuda técnica: sin utcnow, sin ext.declarative
# ============================================================

class TestDeudaTecnica:
    """Verifica que el código no usa patrones deprecados."""

    def test_models_no_usa_utcnow(self):
        """models.py no debe contener datetime.utcnow (deprecado en Python 3.12+)."""
        with open("models.py") as f:
            contenido = f.read()
        assert "datetime.utcnow" not in contenido, \
            "models.py aún usa datetime.utcnow — usar datetime.now(timezone.utc)"

    def test_main_no_usa_utcnow(self):
        """main.py no debe contener datetime.utcnow."""
        with open("main.py") as f:
            contenido = f.read()
        assert "datetime.utcnow" not in contenido, \
            "main.py aún usa datetime.utcnow — usar datetime.now(timezone.utc)"

    def test_database_no_usa_ext_declarative(self):
        """database.py debe importar declarative_base desde sqlalchemy.orm, no ext.declarative."""
        with open("database.py") as f:
            contenido = f.read()
        assert "ext.declarative" not in contenido, \
            "database.py aún importa desde sqlalchemy.ext.declarative (deprecado)"

    def test_schemas_no_usa_class_config(self):
        """schemas.py debe usar model_config = ConfigDict(...) en lugar de class Config."""
        with open("schemas.py") as f:
            contenido = f.read()
        assert "class Config:" not in contenido, \
            "schemas.py aún usa 'class Config:' — migrar a model_config = ConfigDict(...)"

    def test_schemas_usa_config_dict(self):
        """schemas.py debe usar ConfigDict importado de pydantic."""
        with open("schemas.py") as f:
            contenido = f.read()
        assert "ConfigDict" in contenido

    def test_titulo_app_actualizado(self):
        """El título de la app FastAPI debe reflejar la Iteración 4."""
        with open("main.py") as f:
            contenido = f.read()
        assert "Iteración 4" in contenido or "Iteracion 4" in contenido


# ============================================================
# BLOQUE 3 — Regresión: tests clave de iteraciones anteriores
# ============================================================

class TestRegresion:
    """Asegura que los arreglos de Iter. 4 no rompieron nada anterior."""

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
        r = subir_medicion(self.token_reg, self.punto_id, ph=7.0, cloro=1.0, turbidez=2.0)
        assert r.status_code == 200
        assert r.json()["apta"] is True

    def test_medicion_inapta_sigue_generando_alerta(self):
        subir_medicion(self.token_reg, self.punto_id, ph=5.0, cloro=1.0, turbidez=2.0)
        r = client.get("/alertas/")
        assert len(r.json()) >= 1

    def test_mapa_sigue_devolviendo_colores(self):
        subir_medicion(self.token_reg, self.punto_id, ph=7.0, cloro=1.0, turbidez=2.0)
        r = client.get("/mapa/puntos-calidad")
        assert r.status_code == 200
        puntos = r.json()
        assert any(p["color"] == "green" for p in puntos)

    def test_historial_punto_sigue_ok(self):
        subir_medicion(self.token_reg, self.punto_id, ph=7.0, cloro=1.0, turbidez=2.0)
        r = client.get(f"/mapa/historial/{self.punto_id}?n=5")
        assert r.status_code == 200
        assert len(r.json()) == 1