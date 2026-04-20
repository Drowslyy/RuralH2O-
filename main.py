# =============================
#            Servidor
# =============================

from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models, schemas, auth
from database import engine, get_db

# Crea todas las tablas al iniciar
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="RuralH2O MVP — Iteración 1")


# ── Check───────────────────────────────────────────
@app.get("/")
def home():
    return {"mensaje": "Bienvenido al Sistema RuralH2O de Aysén"}


# ── RF-07: Registro de usuario (de prueba) ──
@app.post("/usuarios/", response_model=schemas.Token)
def registrar_usuario(datos: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    existente = db.query(models.Usuario).filter(models.Usuario.email == datos.email).first()
    if existente:
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    nuevo = models.Usuario(
        nombre   = datos.nombre,
        email    = datos.email,
        password = auth.hash_password(datos.password),
        rol      = datos.rol
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)

    token = auth.crear_token({"sub": nuevo.email, "rol": nuevo.rol})
    return {"access_token": token, "token_type": "bearer"}


# ── RF-07: Login ──────────────────────────────────────────
@app.post("/login", response_model=schemas.Token)
def login(datos: schemas.LoginIn, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.email == datos.email).first()

    if not usuario or not auth.verify_password(datos.password, usuario.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas"
        )

    token = auth.crear_token({"sub": usuario.email, "rol": usuario.rol})
    return {"access_token": token, "token_type": "bearer"}


# ── RF-01: Crear punto de monitoreo ───────────────────────
@app.post("/puntos/", response_model=schemas.PuntoOut)
def crear_punto(datos: schemas.PuntoCreate, db: Session = Depends(get_db)):
    nuevo = models.PuntoMonitoreo(**datos.model_dump())
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


# ── RF-01: Listar puntos ──────────────────────────────────
@app.get("/puntos/")
def listar_puntos(db: Session = Depends(get_db)):
    return db.query(models.PuntoMonitoreo).all()


# ── RF-02: Registrar medición (guarda en BD) ──────────────
@app.post("/mediciones/", response_model=schemas.MedicionOut)
def crear_medicion(datos: schemas.MedicionCreate, db: Session = Depends(get_db)):
    nueva = models.Medicion(**datos.model_dump())
    db.add(nueva)
    db.commit()
    db.refresh(nueva)

    # Evaluación NCh 409
    apta = (6.5 <= nueva.ph <= 8.5) and (nueva.cloro <= 2.0) and (nueva.turbidez <= 5.0)

    return nueva


# ── RF-02: Listar mediciones ──────────────────────────────
@app.get("/mediciones/")
def listar_mediciones(db: Session = Depends(get_db)):
    mediciones = db.query(models.Medicion).all()
    resultado  = []
    for m in mediciones:
        apta = (6.5 <= m.ph <= 8.5) and (m.cloro <= 2.0) and (m.turbidez <= 5.0)
        resultado.append({
            "id"               : m.id,
            "comunidad"        : m.comunidad,
            "ph"               : m.ph,
            "cloro"            : m.cloro,
            "turbidez"         : m.turbidez,
            "fecha"            : m.fecha,
            "evaluacion_nch409": "✅ Apta" if apta else "❌ No apta"
        })
    return resultado
