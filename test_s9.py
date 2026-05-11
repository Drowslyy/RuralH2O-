# ============================================================
#  RuralH2O — Test Suite Semana 9: Iteración 3
#  Cobertura: RF-02, RF-03, RF-05, RF-06, RF-07
#  Ejecutar: pytest test_s9.py -v --cov=. --cov-report=term-missing
# ============================================================

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ── Base de datos en memoria (aislada, no toca tu BD real) ──
TEST_DB_URL = "sqlite:///./test_s9_temp.db"
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


app.dependency_overrides[get_db] = override_get_db


# ── Fixture: BD limpia antes de cada test ───────────────────
@pytest.fixture(autouse=True)
def limpiar_bd():
    """Crea todas las tablas al inicio y las borra al finalizar cada test."""
    Base.metadata.create_all(bind=engine_test)
    yield
    Base.metadata.drop_all(bind=engine_test)


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


def subir_medicion(token, punto_id, ph=7.0, cloro=1.0, turbidez=2.0):
    return client.post("/mediciones/", json={
        "ph": ph, "cloro": cloro, "turbidez": turbidez, "punto_id": punto_id
    }, headers=headers(token))


# ============================================================
# BLOQUE 1 — RF-07: Autenticación y control de roles
# ============================================================

class TestAutenticacion:

    def test_login_exitoso(self):
        """Un usuario registrado puede obtener un token JWT válido."""
        registrar_usuario()
        r = client.post("/login", data={"username": "user@test.cl", "password": "pass1234"})
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_login_password_incorrecta(self):
        """Credenciales incorrectas retornan 401."""
        registrar_usuario()
        r = client.post("/login", data={"username": "user@test.cl", "password": "wrongpass"})
        assert r.status_code == 401

    def test_email_duplicado(self):
        """Registrar el mismo email dos veces retorna 400."""
        registrar_usuario()
        r = client.post("/usuarios/", json={"nombre": "Otro", "email": "user@test.cl", "password": "x", "rol": "registrador"})
        assert r.status_code == 400

    def test_endpoint_protegido_sin_token(self):
        """Acceder a /mediciones/ sin token retorna 401."""
        r = client.post("/mediciones/", json={"ph": 7, "cloro": 1, "turbidez": 2, "punto_id": 1})
        assert r.status_code == 401

    def test_visualizador_no_puede_subir_medicion(self):
        """Un visualizador recibe 403 al intentar subir una medición."""
        registrar_usuario("viz@test.cl", "viz1234", "visualizador")
        token = obtener_token("viz@test.cl", "viz1234")
        r = subir_medicion(token, punto_id=1)
        assert r.status_code == 403

    def test_no_admin_no_puede_crear_punto(self):
        """Un registrador recibe 403 al intentar crear un punto de monitoreo."""
        registrar_usuario()
        token = obtener_token()
        r = client.post("/puntos/", json={
            "nombre": "Pozo X", "tipo_fuente": "pozo",
            "comunidad": "X", "latitud": -45.0, "longitud": -72.0
        }, headers=headers(token))
        assert r.status_code == 403


# ============================================================
# BLOQUE 2 — RF-03: Validación NCh 409
# ============================================================

class TestValidacionNCh409:

    def setup_method(self):
        """Crea admin, registrador y un punto antes de cada test."""
        self.token_admin = crear_admin()
        registrar_usuario()
        self.token_reg = obtener_token()
        self.punto_id = crear_punto(self.token_admin)

    def test_medicion_apta(self):
        """Parámetros dentro de norma → apta=True."""
        r = subir_medicion(self.token_reg, self.punto_id, ph=7.0, cloro=1.0, turbidez=2.0)
        assert r.status_code == 200
        assert r.json()["apta"] is True

    def test_ph_bajo_critico(self):
        """pH < 6.0 → apta=False."""
        r = subir_medicion(self.token_reg, self.punto_id, ph=5.0, cloro=1.0, turbidez=2.0)
        assert r.status_code == 200
        assert r.json()["apta"] is False

    def test_ph_alto_critico(self):
        """pH > 9.0 → apta=False."""
        r = subir_medicion(self.token_reg, self.punto_id, ph=9.5, cloro=1.0, turbidez=2.0)
        assert r.status_code == 200
        assert r.json()["apta"] is False

    def test_cloro_bajo_critico(self):
        """Cloro < 0.2 mg/L → apta=False."""
        r = subir_medicion(self.token_reg, self.punto_id, ph=7.0, cloro=0.1, turbidez=2.0)
        assert r.status_code == 200
        assert r.json()["apta"] is False

    def test_cloro_alto_critico(self):
        """Cloro > 3.0 mg/L → apta=False."""
        r = subir_medicion(self.token_reg, self.punto_id, ph=7.0, cloro=3.5, turbidez=2.0)
        assert r.status_code == 200
        assert r.json()["apta"] is False

    def test_turbidez_critica(self):
        """Turbidez > 10 NTU → apta=False."""
        r = subir_medicion(self.token_reg, self.punto_id, ph=7.0, cloro=1.0, turbidez=11.0)
        assert r.status_code == 200
        assert r.json()["apta"] is False

    def test_multiples_parametros_fuera_norma(self):
        """pH y turbidez fuera de norma → apta=False con observaciones."""
        r = subir_medicion(self.token_reg, self.punto_id, ph=5.0, cloro=1.0, turbidez=15.0)
        data = r.json()
        assert data["apta"] is False
        assert data["observaciones"] is not None

    def test_schema_rechaza_ph_negativo(self):
        """Pydantic rechaza pH < 0 antes de llegar a la lógica NCh 409."""
        r = subir_medicion(self.token_reg, self.punto_id, ph=-1.0, cloro=1.0, turbidez=2.0)
        assert r.status_code == 422

    def test_schema_rechaza_turbidez_negativa(self):
        """Pydantic rechaza turbidez < 0."""
        r = subir_medicion(self.token_reg, self.punto_id, ph=7.0, cloro=1.0, turbidez=-5.0)
        assert r.status_code == 422


# ============================================================
# BLOQUE 3 — RF-06: Alertas automáticas
# ============================================================

class TestAlertas:

    def setup_method(self):
        self.token_admin = crear_admin()
        registrar_usuario()
        self.token_reg = obtener_token()
        self.punto_id = crear_punto(self.token_admin)

    def test_medicion_no_apta_genera_alerta(self):
        """Una medición fuera de norma crea al menos una alerta en /alertas/."""
        subir_medicion(self.token_reg, self.punto_id, ph=5.0, cloro=1.0, turbidez=2.0)
        r = client.get("/alertas/")
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_medicion_apta_no_genera_alerta(self):
        """Una medición dentro de norma no genera alertas."""
        subir_medicion(self.token_reg, self.punto_id, ph=7.0, cloro=1.0, turbidez=2.0)
        r = client.get("/alertas/")
        assert len(r.json()) == 0

    def test_marcar_alerta_leida(self):
        """Una alerta puede marcarse como leída vía PATCH."""
        subir_medicion(self.token_reg, self.punto_id, ph=5.0, cloro=1.0, turbidez=2.0)
        alertas = client.get("/alertas/").json()
        alerta_id = alertas[0]["id"]
        r = client.patch(f"/alertas/{alerta_id}/leer", headers=headers(self.token_reg))
        assert r.status_code == 200
        assert r.json()["leida"] is True

    def test_filtro_alertas_no_leidas(self):
        """El filtro ?leida=false retorna solo alertas pendientes."""
        subir_medicion(self.token_reg, self.punto_id, ph=5.0, cloro=1.0, turbidez=2.0)
        r = client.get("/alertas/?leida=false")
        assert all(not a["leida"] for a in r.json())


# ============================================================
# BLOQUE 4 — RF-05: Mapa interactivo y colores NCh 409
# ============================================================

class TestMapaColores:
    """
    Valida que /mapa/puntos-calidad devuelva el color correcto
    para cada estado: gray, green, yellow, red.
    """

    def setup_method(self):
        self.token_admin = crear_admin()
        registrar_usuario()
        self.token_reg = obtener_token()

    def _color_de(self, punto_id):
        puntos = client.get("/mapa/puntos-calidad").json()
        match = next((p for p in puntos if p["id"] == punto_id), None)
        assert match is not None, f"Punto {punto_id} no encontrado en el mapa"
        return match["color"]

    def test_color_gray_sin_mediciones(self):
        """Un punto sin mediciones aparece en gris en el mapa."""
        pid = crear_punto(self.token_admin, "Pozo Sin Datos", lat=-45.60, lng=-72.10)
        assert self._color_de(pid) == "gray"

    def test_color_green_todos_aptos(self):
        """Parámetros perfectamente dentro de norma → marcador verde."""
        pid = crear_punto(self.token_admin, "Pozo Verde", lat=-45.61, lng=-72.11)
        subir_medicion(self.token_reg, pid, ph=7.0, cloro=1.0, turbidez=2.0)
        assert self._color_de(pid) == "green"

    def test_color_yellow_advertencia_ph(self):
        """pH en zona límite (6.2) → marcador amarillo (apta pero con advertencia)."""
        pid = crear_punto(self.token_admin, "Pozo Amarillo pH", lat=-45.62, lng=-72.12)
        subir_medicion(self.token_reg, pid, ph=6.2, cloro=1.0, turbidez=2.0)
        assert self._color_de(pid) == "yellow"

    def test_color_yellow_advertencia_cloro(self):
        """Cloro en zona límite (2.5 mg/L) → marcador amarillo."""
        pid = crear_punto(self.token_admin, "Pozo Amarillo Cloro", lat=-45.63, lng=-72.13)
        subir_medicion(self.token_reg, pid, ph=7.0, cloro=2.5, turbidez=2.0)
        assert self._color_de(pid) == "yellow"

    def test_color_yellow_advertencia_turbidez(self):
        """Turbidez en zona límite (7 NTU) → marcador amarillo."""
        pid = crear_punto(self.token_admin, "Pozo Amarillo Turbidez", lat=-45.64, lng=-72.14)
        subir_medicion(self.token_reg, pid, ph=7.0, cloro=1.0, turbidez=7.0)
        assert self._color_de(pid) == "yellow"

    def test_color_red_ph_critico(self):
        """pH crítico (5.0) → marcador rojo."""
        pid = crear_punto(self.token_admin, "Pozo Rojo pH", lat=-45.65, lng=-72.15)
        subir_medicion(self.token_reg, pid, ph=5.0, cloro=1.0, turbidez=2.0)
        assert self._color_de(pid) == "red"

    def test_color_red_cloro_critico(self):
        """Cloro crítico (0.05 mg/L) → marcador rojo."""
        pid = crear_punto(self.token_admin, "Pozo Rojo Cloro", lat=-45.66, lng=-72.16)
        subir_medicion(self.token_reg, pid, ph=7.0, cloro=0.05, turbidez=2.0)
        assert self._color_de(pid) == "red"

    def test_color_red_turbidez_critica(self):
        """Turbidez crítica (15 NTU) → marcador rojo."""
        pid = crear_punto(self.token_admin, "Pozo Rojo Turbidez", lat=-45.67, lng=-72.17)
        subir_medicion(self.token_reg, pid, ph=7.0, cloro=1.0, turbidez=15.0)
        assert self._color_de(pid) == "red"

    def test_mapa_multiples_puntos_colores_distintos(self):
        """
        Escenario completo: 4 puntos con los 4 estados distintos.
        Verifica que el mapa retorna exactamente un punto de cada color.
        """
        # gray — sin mediciones
        p_gray   = crear_punto(self.token_admin, "Pozo Gris",     lat=-45.50, lng=-72.00)
        # green — todo ok
        p_green  = crear_punto(self.token_admin, "Pozo Verde",    lat=-45.51, lng=-72.01)
        subir_medicion(self.token_reg, p_green,  ph=7.0, cloro=1.0,  turbidez=2.0)
        # yellow — pH límite
        p_yellow = crear_punto(self.token_admin, "Pozo Amarillo", lat=-45.52, lng=-72.02)
        subir_medicion(self.token_reg, p_yellow, ph=6.2, cloro=1.0,  turbidez=2.0)
        # red — pH crítico
        p_red    = crear_punto(self.token_admin, "Pozo Rojo",     lat=-45.53, lng=-72.03)
        subir_medicion(self.token_reg, p_red,    ph=5.0, cloro=1.0,  turbidez=2.0)

        puntos = client.get("/mapa/puntos-calidad").json()
        colores = {p["id"]: p["color"] for p in puntos}

        assert colores[p_gray]   == "gray"
        assert colores[p_green]  == "green"
        assert colores[p_yellow] == "yellow"
        assert colores[p_red]    == "red"

    def test_mapa_usa_ultima_medicion(self):
        """
        El color refleja la ÚLTIMA medición, no la primera.
        Primera medición: mala (rojo). Segunda: buena (verde).
        """
        pid = crear_punto(self.token_admin, "Pozo Histórico", lat=-45.70, lng=-72.20)
        subir_medicion(self.token_reg, pid, ph=5.0, cloro=1.0, turbidez=2.0)  # rojo
        subir_medicion(self.token_reg, pid, ph=7.0, cloro=1.0, turbidez=2.0)  # verde
        assert self._color_de(pid) == "green"