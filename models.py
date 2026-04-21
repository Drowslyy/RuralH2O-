# =============================
#         Capa de Datos
# =============================

from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
import datetime


# ── Tabla: usuarios ──────────────────────────────────────
#Guardamos datos del usuarios
class Usuario(Base):
    __tablename__ = "usuarios" 

    id       = Column(Integer, primary_key=True, index=True)
    nombre   = Column(String(100))
    email    = Column(String(100), unique=True, index=True)
    password = Column(String(200))           # hash BCrypt
    rol      = Column(String(20))            # "registrador" o "visualizador"


# ── Tabla: puntos_monitoreo ───────────────────────────────
#Guardamos los puntos de monitoreo (Geograficamente)
class PuntoMonitoreo(Base):
    __tablename__ = "puntos_monitoreo"

    id          = Column(Integer, primary_key=True, index=True)
    nombre      = Column(String(100))
    tipo_fuente = Column(String(50))         # pozo, rio, vertiente
    latitud     = Column(Float)
    longitud    = Column(Float)

    mediciones  = relationship("Medicion", back_populates="punto")


# ── Tabla: mediciones ─────────────────────────────────────
#Registra los niveles del agua
class Medicion(Base):
    __tablename__ = "mediciones"

    id         = Column(Integer, primary_key=True, index=True)
    comunidad  = Column(String(100))
    ph         = Column(Float)
    cloro      = Column(Float)
    turbidez   = Column(Float)
    fecha      = Column(DateTime, default=datetime.datetime.utcnow)
    punto_id   = Column(Integer, ForeignKey("puntos_monitoreo.id"), nullable=True) # Indica que el dato pertenece a un punto especifico de monitoreo

    punto      = relationship("PuntoMonitoreo", back_populates="mediciones")
