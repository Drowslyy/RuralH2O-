# =============================
#         Validación
# =============================

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

#Datos que entran en la API y salen a la API


# ── Mediciones ────────────────────────────────────────────
class MedicionBase(BaseModel):
    comunidad : str
    ph        : float = Field(..., ge=0,  le=14)
    cloro     : float = Field(..., ge=0,  le=5)
    turbidez  : float = Field(..., ge=0)
    punto_id  : int

class MedicionCreate(MedicionBase): #Que datos recibes por parte del usuario
    pass

class MedicionOut(MedicionBase): #Muestra los datos al usuarios 
    id        : int 
    fecha     : datetime
    apta      : bool  
    observaciones: Optional[str] = None

    class Config:
        from_attributes = True


# ── Puntos de monitoreo ───────────────────────────────────
class PuntoBase(BaseModel):
    nombre : str
    tipo_fuente : str
    latitud : float
    longitud : float


class PuntoCreate(PuntoBase):
    pass

class PuntoOut(PuntoBase):
    id : int
    class Config:
        from_attributes = True


# ── Usuario ─────────────────────────────────────────
class UsuarioBase(BaseModel):
    nombre   : str
    email    : str
    rol : str

class UsuarioCreate(UsuarioBase):
    password: str

class UsuarioOut(UsuarioBase):
    id : int
    class Config:
        from_attributes = True 

# ── Login ─────────────────────────────────────────

class LoginRequest(BaseModel):
    email    : str
    password : str

# Define la estructura del ticket de acceso (JWT) que se le entrega al usuario al loguearse.
class Token(BaseModel):
    access_token : str
    token_type   : str

# ── Alertas ─────────────────────────────────────────

class AlertaBase(BaseModel):
    tipo : str
    nivel : str 
    mensaje : str 

class AlertaCreate(AlertaBase):
    medicion_id : int

class AlertaOut(AlertaBase):
    id: int
    medicion_id : int
    leida : bool
    fecha : datetime

    class Config:
        from_attributes = True