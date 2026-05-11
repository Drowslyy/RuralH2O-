from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

import models
import schemas
from database import engine, get_db
from auth import hash_password, verify_password, crear_token, verificar_token
from validaciones import evaluar_nch409
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Inicialización
models.Base.metadata.create_all(bind=engine)

# FIX: título actualizado a Semana 9
app = FastAPI(title="Semana 9: Iteración 3 - Mapa interactivo")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Configurar CORS (para que el mapa pueda pedir datos a la API)
# NOTA: en producción cambiar "*" por la URL exacta de tu frontend en Render
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar la carpeta del frontend (guarda index.html y mapa.js aquí)
app.mount("/view", StaticFiles(directory="static", html=True), name="static")


# ==========================================================
# SEGURIDAD (Dependencia de Usuario Actual)
# ==========================================================
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = verificar_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    email: str = payload.get("sub")
    usuario = db.query(models.Usuario).filter(models.Usuario.email == email).first()

    if not usuario:
        raise HTTPException(status_code=401, detail="Usuario no autorizado")
    return usuario


# ==========================================================
# USUARIOS Y LOGIN (RF-07)
# ==========================================================
@app.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.email == form_data.username).first()

    if not usuario or not verify_password(form_data.password, usuario.password):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")

    token = crear_token({"sub": usuario.email, "rol": usuario.rol})
    return {"access_token": token, "token_type": "bearer"}


@app.post("/usuarios/", response_model=schemas.UsuarioOut)
def registrar_usuario(usuario: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    existe = db.query(models.Usuario).filter(models.Usuario.email == usuario.email).first()
    if existe:
        raise HTTPException(status_code=400, detail="Email ya registrado")

    nuevo = models.Usuario(
        nombre=usuario.nombre,
        email=usuario.email,
        password=hash_password(usuario.password),
        rol=usuario.rol
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


# ==========================================================
# PUNTOS DE MONITOREO (RF-01 + RF-05)
# ==========================================================
@app.post("/puntos/", response_model=schemas.PuntoOut)
def crear_punto(
    punto: schemas.PuntoCreate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    if current_user.rol != "admin":
        raise HTTPException(status_code=403, detail="Permisos insuficientes para crear puntos")

    nuevo = models.PuntoMonitoreo(**punto.model_dump())
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


@app.get("/puntos/", response_model=List[schemas.PuntoOut])
def listar_puntos(db: Session = Depends(get_db)):
    return db.query(models.PuntoMonitoreo).all()


# ----------------------------------------------------------
# RF-05: Endpoint para el mapa interactivo (Semana 9)
# ----------------------------------------------------------
# DEUDA TÉCNICA (Iteración 4): este endpoint hace N+1 queries
# (una por punto a Medicion + una por punto a Alerta).
# Con pocos puntos piloto no es problema; optimizar con JOIN en S11.
@app.get("/mapa/puntos-calidad")
def obtener_puntos_mapa(db: Session = Depends(get_db)):
    puntos = db.query(models.PuntoMonitoreo).all()
    resultado = []

    for p in puntos:
        # Obtener la última medición del punto
        ultima = (
            db.query(models.Medicion)
            .filter(models.Medicion.punto_id == p.id)
            .order_by(models.Medicion.fecha.desc())
            .first()
        )

        # FIX: lógica de tres colores correcta según NCh 409
        # gray   → sin mediciones registradas
        # green  → apta (todos los parámetros dentro de norma)
        # yellow → apta pero con al menos una advertencia (parámetro en zona límite)
        # red    → no apta (al menos un parámetro fuera de norma)
        color = "gray"
        if ultima:
            if ultima.apta:
                tiene_advertencia = (
                    db.query(models.Alerta)
                    .filter(
                        models.Alerta.medicion_id == ultima.id,
                        models.Alerta.nivel == "advertencia"
                    )
                    .first()
                )
                color = "yellow" if tiene_advertencia else "green"
            else:
                color = "red"

        resultado.append({
            "id":     p.id,
            "nombre": p.nombre,
            "lat":    p.latitud,
            "lng":    p.longitud,
            "color":  color,
        })

    return resultado


# ==========================================================
# MEDICIONES (RF-02 + RF-03)
# ==========================================================
@app.post("/mediciones/", response_model=schemas.MedicionOut)
def crear_medicion(
    medicion: schemas.MedicionCreate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    if current_user.rol == "visualizador":
        raise HTTPException(status_code=403, detail="Tu rol solo permite visualizar datos")

    punto = db.query(models.PuntoMonitoreo).filter(models.PuntoMonitoreo.id == medicion.punto_id).first()
    if not punto:
        raise HTTPException(status_code=404, detail="Punto no encontrado")

    res = evaluar_nch409(medicion.ph, medicion.cloro, medicion.turbidez)
    nueva = models.Medicion(
        ph=medicion.ph,
        cloro=medicion.cloro,
        turbidez=medicion.turbidez,
        punto_id=medicion.punto_id,
        apta=res["apta"],
        observaciones=res["observaciones"]
    )
    db.add(nueva)
    db.commit()
    db.refresh(nueva)

    # FIX: guardar alertas para críticos Y advertencias (amarillo necesita alertas aunque apta=True)
    if res["alertas_generadas"]:
        for a in res["alertas_generadas"]:
            db.add(models.Alerta(
                medicion_id=nueva.id,
                tipo=a["tipo"],
                nivel=a["nivel"],
                mensaje=a["mensaje"]
            ))
        db.commit()

    return nueva


@app.get("/mediciones/", response_model=List[schemas.MedicionOut])
def listar_mediciones(db: Session = Depends(get_db)):
    return db.query(models.Medicion).all()


# ==========================================================
# ALERTAS (RF-06)
# ==========================================================
@app.get("/alertas/", response_model=List[schemas.AlertaOut])
def listar_alertas(leida: Optional[bool] = None, db: Session = Depends(get_db)):
    query = db.query(models.Alerta)
    if leida is not None:
        query = query.filter(models.Alerta.leida == leida)
    return query.order_by(models.Alerta.fecha.desc()).all()


@app.patch("/alertas/{alerta_id}/leer", response_model=schemas.AlertaOut)
def marcar_alerta_leida(
    alerta_id: int,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    alerta = db.query(models.Alerta).filter(models.Alerta.id == alerta_id).first()
    if not alerta:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    alerta.leida = True
    db.commit()
    db.refresh(alerta)
    return alerta