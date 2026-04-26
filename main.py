
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

import models
import schemas
from database import engine, get_db
from auth import hash_password, verify_password, crear_token
from validaciones import evaluar_nch409

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="RuralH2O MVP - Iteración 2")


# ==========================================================
# HOME
# ==========================================================
@app.get("/")
def home():
    return {"mensaje": "API RuralH2O operativa - Iteración 2"}


# ==========================================================
# USUARIOS (RF-07)
# ==========================================================
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


@app.post("/login", response_model=schemas.Token)
def login(datos: schemas.LoginRequest, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.email == datos.email).first()
    if not usuario or not verify_password(datos.password, usuario.password):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    token = crear_token({"sub": usuario.email, "rol": usuario.rol})
    return {"access_token": token, "token_type": "bearer"}


# ==========================================================
# PUNTOS DE MONITOREO (RF-01)
# ==========================================================
@app.post("/puntos/", response_model=schemas.PuntoOut)
def crear_punto(punto: schemas.PuntoCreate, db: Session = Depends(get_db)):
    nuevo = models.PuntoMonitoreo(**punto.model_dump())
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


@app.get("/puntos/", response_model=List[schemas.PuntoOut])
def listar_puntos(db: Session = Depends(get_db)):
    return db.query(models.PuntoMonitoreo).all()


# ==========================================================
# MEDICIONES (RF-02 + RF-03)
# ==========================================================
@app.post("/mediciones/", response_model=schemas.MedicionOut)
def crear_medicion(medicion: schemas.MedicionCreate, db: Session = Depends(get_db)):
    # 1. Verificar que el punto exista
    punto = db.query(models.PuntoMonitoreo).filter(
        models.PuntoMonitoreo.id == medicion.punto_id
    ).first()
    if not punto:
        raise HTTPException(status_code=404, detail="Punto de monitoreo no encontrado")

    # 2. Evaluar según norma NCh 409
    resultado = evaluar_nch409(medicion.ph, medicion.cloro, medicion.turbidez)

    # 3. Crear y guardar la medición (la comunidad se hereda del punto)
    nueva = models.Medicion(
        ph=medicion.ph,
        cloro=medicion.cloro,
        turbidez=medicion.turbidez,
        punto_id=medicion.punto_id,
        apta=resultado["apta"],
        observaciones=resultado["observaciones"]
    )
    db.add(nueva)
    db.commit()
    db.refresh(nueva)

    # 4. Si no es apta, generar alertas automáticas (RF-06)
    if not resultado["apta"]:
        for alerta_data in resultado["alertas_generadas"]:
            nueva_alerta = models.Alerta(
                medicion_id=nueva.id,
                tipo=alerta_data["tipo"],
                nivel=alerta_data["nivel"],
                mensaje=alerta_data["mensaje"]
            )
            db.add(nueva_alerta)
        db.commit()

    return nueva


@app.get("/mediciones/", response_model=List[schemas.MedicionOut])
def listar_mediciones(db: Session = Depends(get_db)):
    return db.query(models.Medicion).all()


# ==========================================================
# ALERTAS (RF-06)
# ==========================================================
@app.get("/alertas/", response_model=List[schemas.AlertaOut])
def listar_alertas(
    leida: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    query = db.query(models.Alerta)
    if leida is not None:
        query = query.filter(models.Alerta.leida == leida)
    return query.order_by(models.Alerta.fecha.desc()).all()


@app.patch("/alertas/{alerta_id}/leer", response_model=schemas.AlertaOut)
def marcar_alerta_leida(alerta_id: int, db: Session = Depends(get_db)):
    alerta = db.query(models.Alerta).filter(models.Alerta.id == alerta_id).first()
    if not alerta:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")

    alerta.leida = True
    db.commit()
    db.refresh(alerta)
    return alerta