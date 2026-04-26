# models.py
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime


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

    mediciones = relationship("Medicion", back_populates="punto")


class Medicion(Base):
    __tablename__ = "mediciones"

    id = Column(Integer, primary_key=True, index=True)
    # comunidad = Column(String(100), nullable=False) Eliminacion de comunidad 26/04
    ph = Column(Float, nullable=False)
    cloro = Column(Float, nullable=False)
    turbidez = Column(Float, nullable=False)
    fecha = Column(DateTime, default=datetime.utcnow)

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
    fecha = Column(DateTime, default=datetime.utcnow)

    medicion = relationship("Medicion", back_populates="alertas")