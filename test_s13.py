"""
test_s13.py — Iteración 7: RF-08 Módulo de avisos comunitarios

Cubre permisos por rol, listado, archivado (no borrado) y notificación
por correo en modo simulado.

Ejecutar:  pytest test_s13.py -v
"""

import pytest
from fastapi.testclient import TestClient

from main import app, get_current_user


class MockUser:
    def __init__(self, nombre, email, rol):
        self.nombre = nombre
        self.email = email
        self.rol = rol


def mock_visualizador():
    return MockUser("Jefatura Test", "jefatura@ruralh2o.cl", "visualizador")


def mock_registrador():
    return MockUser("Registrador Test", "registrador@ruralh2o.cl", "registrador")


client = TestClient(app)


class TestPermisosAvisos:

    def test_visualizador_puede_crear_aviso(self):
        app.dependency_overrides[get_current_user] = mock_visualizador
        try:
            r = client.post("/avisos/", json={
                "titulo": "Corte de suministro",
                "mensaje": "Corte programado en Villa Manihuales por mantenimiento el 20/06.",
                "comunidad": "Villa Manihuales",
            })
            assert r.status_code == 200
            data = r.json()
            assert data["titulo"] == "Corte de suministro"
            assert data["autor"] == "jefatura@ruralh2o.cl"
            assert data["activo"] is True
        finally:
            app.dependency_overrides = {}

    def test_registrador_no_puede_crear_aviso(self):
        app.dependency_overrides[get_current_user] = mock_registrador
        try:
            r = client.post("/avisos/", json={
                "titulo": "Intento no autorizado",
                "mensaje": "Esto no deberia permitirse desde un registrador.",
            })
            assert r.status_code == 403
        finally:
            app.dependency_overrides = {}


class TestListadoAvisos:

    def test_listar_avisos_es_publico_autenticado(self):
        r = client.get("/avisos/")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_aviso_creado_aparece_en_listado(self):
        app.dependency_overrides[get_current_user] = mock_visualizador
        try:
            client.post("/avisos/", json={
                "titulo": "Aviso visible",
                "mensaje": "Este aviso debe aparecer en el listado activo.",
            })
        finally:
            app.dependency_overrides = {}
        r = client.get("/avisos/")
        titulos = [a["titulo"] for a in r.json()]
        assert "Aviso visible" in titulos


class TestArchivarAviso:

    def test_archivar_aviso_lo_desactiva(self):
        app.dependency_overrides[get_current_user] = mock_visualizador
        try:
            r = client.post("/avisos/", json={
                "titulo": "Aviso a archivar",
                "mensaje": "Se archivara en este test.",
            })
            aviso_id = r.json()["id"]
            ra = client.patch(f"/avisos/{aviso_id}/archivar")
            assert ra.status_code == 200
            assert ra.json()["activo"] is False
            activos = client.get("/avisos/").json()
            assert all(a["id"] != aviso_id for a in activos)
            todos = client.get("/avisos/?incluir_archivados=true").json()
            assert any(a["id"] == aviso_id for a in todos)
        finally:
            app.dependency_overrides = {}

    def test_registrador_no_puede_archivar(self):
        app.dependency_overrides[get_current_user] = mock_visualizador
        try:
            r = client.post("/avisos/", json={
                "titulo": "Protegido",
                "mensaje": "Solo la jefatura puede archivar esto.",
            })
            aviso_id = r.json()["id"]
        finally:
            app.dependency_overrides = {}
        app.dependency_overrides[get_current_user] = mock_registrador
        try:
            ra = client.patch(f"/avisos/{aviso_id}/archivar")
            assert ra.status_code == 403
        finally:
            app.dependency_overrides = {}


class TestNotificacion:

    def test_notificacion_no_rompe_creacion(self):
        app.dependency_overrides[get_current_user] = mock_visualizador
        try:
            r = client.post("/avisos/", json={
                "titulo": "Con notificacion",
                "mensaje": "Debe crearse aunque el correo este en modo simulado.",
            })
            assert r.status_code == 200
        finally:
            app.dependency_overrides = {}

    def test_modulo_notificaciones_modo_simulado(self):
        from notificaciones import enviar_aviso_por_correo
        res = enviar_aviso_por_correo(
            ["registrador@ruralh2o.cl"], "Prueba", "Mensaje de prueba"
        )
        assert res["enviado"] is False
        assert res["modo"] == "simulado"


class TestValidacionAvisos:

    def test_titulo_muy_corto_rechazado(self):
        app.dependency_overrides[get_current_user] = mock_visualizador
        try:
            r = client.post("/avisos/", json={"titulo": "ab", "mensaje": "mensaje valido aqui"})
            assert r.status_code == 422
        finally:
            app.dependency_overrides = {}