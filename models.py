# models.py
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime, timezone


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    rol = Column(String(50), nullable=False)


class PuntoMonitoreo(Base):
    __tablename__ = "puntos_monitoreo"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    tipo_fuente = Column(String(50), nullable=False)
    comunidad = Column(String(100), nullable=False)  # Cambios 26/04
    latitud = Column(Float, nullable=False)
    longitud = Column(Float, nullable=False)
    fecha_creacion = Column(DateTime, default=lambda: datetime.now(timezone.utc))  # FIX Iter. 4: utcnow deprecado

    mediciones = relationship("Medicion", back_populates="punto")


class Medicion(Base):
    __tablename__ = "mediciones"

    id = Column(Integer, primary_key=True, index=True)
    # comunidad = Column(String(100), nullable=False) Eliminacion de comunidad 26/04
    ph = Column(Float, nullable=False)
    cloro = Column(Float, nullable=False)
    turbidez = Column(Float, nullable=False)
    fecha = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # --- NUEVAS COLUMNAS (Iteración 2) ---
    apta = Column(Boolean, nullable=False, default=True)
    observaciones = Column(String(255), nullable=True)

    punto_id = Column(Integer, ForeignKey("puntos_monitoreo.id"))

    punto = relationship("PuntoMonitoreo", back_populates="mediciones")
    alertas = relationship("Alerta", back_populates="medicion", cascade="all, delete")


# --- NUEVA TABLA (Iteración 2) ---
class Alerta(Base):
    __tablename__ = "alertas"

    id = Column(Integer, primary_key=True, index=True)
    medicion_id = Column(Integer, ForeignKey("mediciones.id"), nullable=False)
    tipo = Column(String(50), nullable=False)
    nivel = Column(String(20), nullable=False)  # "crítico" o "advertencia"
    mensaje = Column(String(255), nullable=False)
    leida = Column(Boolean, default=False)
    fecha = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    medicion = relationship("Medicion", back_populates="alertas")


# --- NUEVA TABLA (Iteración 7 - RF-08): Avisos comunitarios ---
class Aviso(Base):
    __tablename__ = "avisos"

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String(120), nullable=False)
    mensaje = Column(String(500), nullable=False)
    comunidad = Column(String(100), nullable=True)   # opcional: aviso dirigido a una comunidad
    autor = Column(String(100), nullable=False)       # email del visualizador que lo publica
    activo = Column(Boolean, default=True)            # archivar en vez de borrar (registro inmutable)
    fecha = Column(DateTime, default=lambda: datetime.now(timezone.utc))