import pytest
from fastapi.testclient import TestClient
from main import app, get_current_user # Importamos la dependencia
import models

client = TestClient(app)

# 1. Creamos "Usuarios Simulados" (Mocks)
class MockUser:
    def __init__(self, nombre, email, rol):
        self.nombre = nombre
        self.email = email
        self.rol = rol

# 2. Funciones que simulan el comportamiento de 'get_current_user'
# Esto evita que el sistema vaya a la base de datos real durante el test
def mock_get_current_registrador():
    return MockUser("Registrador Test", "registrador@ruralh2o.cl", "registrador")

def mock_get_current_visualizador():
    return MockUser("Pedro Test", "pedro@gmail.com", "visualizador")

# ==========================================================
# TESTS CON ROLES SIMULADOS
# ==========================================================

def test_registrador_puede_crear_punto():
    # Sobrescribimos la dependencia para que este test actúe como REGISTRADOR (terreno)
    app.dependency_overrides[get_current_user] = mock_get_current_registrador
    
    response = client.post(
        "/puntos/",
        json={
            "nombre": "Pozo Test Registrador",
            "tipo_fuente": "Subterránea",
            "comunidad": "Coyhaique",
            "latitud": -45.57,
            "longitud": -72.06
        }
    )
    # Deberia ser 200 porque el registrador sí puede crear puntos
    assert response.status_code == 200
    # Limpiamos la simulación
    app.dependency_overrides = {}

def test_registrador_puede_subir_medicion():
    app.dependency_overrides[get_current_user] = mock_get_current_registrador

    response = client.post(
        "/mediciones/",
        json={
            "ph": 7.0,
            "cloro": 1.0,
            "turbidez": 1.0,
            "punto_id": 1
        }
    )
    # 200 si el punto existe, 404 si no -- lo importante es que NO sea 403
    assert response.status_code != 403
    app.dependency_overrides = {}

def test_visualizador_no_puede_crear_punto():
    # Sobrescribimos para que este test actúe como VISUALIZADOR
    app.dependency_overrides[get_current_user] = mock_get_current_visualizador
    
    response = client.post(
        "/puntos/",
        json={
            "nombre": "Pozo Ilegal",
            "tipo_fuente": "Río",
            "comunidad": "Aysén",
            "latitud": -45.0,
            "longitud": -72.0
        }
    )
    # Debe ser 403 (Prohibido) porque el rol visualizador no tiene permiso
    assert response.status_code == 403
    app.dependency_overrides = {}

def test_visualizador_no_puede_subir_medicion():
    app.dependency_overrides[get_current_user] = mock_get_current_visualizador
    
    response = client.post(
        "/mediciones/",
        json={
            "ph": 7.0,
            "cloro": 1.0,
            "turbidez": 1.0,
            "punto_id": 1
        }
    )
    assert response.status_code == 403
    app.dependency_overrides = {}

def test_acceso_sin_token():
    # El sistema pedirá token real
    # y como no enviamos nada, debe dar 401
    response = client.post("/puntos/", json={})
    assert response.status_code == 401

    