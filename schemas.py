# =============================
#         Validación
# =============================

from pydantic import BaseModel, Field
from typing import Optional

#Datos que entran en la API y salen a la API


# ── Mediciones ────────────────────────────────────────────
class MedicionBase(BaseModel):
    comunidad : str
    ph        : float = Field(..., ge=0,  le=14,  description="pH entre 0 y 14")
    cloro     : float = Field(..., ge=0,  le=5,   description="Cloro residual NCh 409: 0–5 mg/L")
    turbidez  : float = Field(..., ge=0,          description="Turbidez no puede ser negativa")

class MedicionCreate(MedicionBase): #Que datos recibes por parte del usuario
    punto_id  : Optional[int] = None

class MedicionOut(MedicionBase): #Muestra los datos al usuarios 
    id        : int
    punto_id  : Optional[int]
    class Config:
        from_attributes = True


# ── Puntos de monitoreo ───────────────────────────────────
class PuntoCreate(BaseModel):
    nombre      : str
    tipo_fuente : str = Field(..., description="pozo, rio o vertiente")
    latitud     : float
    longitud    : float

class PuntoOut(PuntoCreate):
    id : int
    class Config:
        from_attributes = True


# ── Autenticación ─────────────────────────────────────────
class UsuarioCreate(BaseModel):
    nombre   : str
    email    : str
    password : str
    rol      : str = Field(..., description="registrador o visualizador")

class LoginIn(BaseModel):
    email    : str
    password : str

# Define la estructura del ticket de acceso (JWT) que se le entrega al usuario al loguearse.
class Token(BaseModel):
    access_token : str
    token_type   : str
