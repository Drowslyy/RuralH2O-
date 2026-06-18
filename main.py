from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload, subqueryload
from sqlalchemy import func
from typing import List, Optional
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timezone
import io
import time
from fpdf import FPDF
from fastapi.responses import RedirectResponse

import models
import schemas
from database import engine, get_db
from auth import hash_password, verify_password, crear_token, verificar_token
from validaciones import evaluar_nch409
from notificaciones import enviar_aviso_por_correo
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Semana 13: Iteración 7 - RF-08 Avisos y consolidación")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def redirigir_al_login():
    return RedirectResponse(url="/view/login.html")

app.mount("/view", StaticFiles(directory="static", html=True), name="static")


# ==========================================================
# Iteración 6: Caché en memoria para el endpoint del mapa
# ==========================================================
# El mapa se consulta con frecuencia y sus datos cambian poco.
# Guardamos la respuesta unos segundos para no recalcularla en
# cada petición. Cualquier escritura (punto o medición nueva)
# invalida el caché para no servir datos obsoletos.
_cache_mapa: dict = {}
_CACHE_TTL = 30  # segundos


def _invalidar_cache_mapa():
    """Vacía el caché del mapa (se llama tras crear puntos o mediciones)."""
    _cache_mapa.clear()


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = verificar_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Token invalido o expirado")
    email: str = payload.get("sub")
    usuario = db.query(models.Usuario).filter(models.Usuario.email == email).first()
    if not usuario:
        raise HTTPException(status_code=401, detail="Usuario no autorizado")
    return usuario


@app.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.email == form_data.username).first()
    if not usuario or not verify_password(form_data.password, usuario.password):
        raise HTTPException(status_code=401, detail="Correo o contrasena incorrectos")
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


@app.post("/puntos/", response_model=schemas.PuntoOut)
def crear_punto(
    punto: schemas.PuntoCreate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    if current_user.rol != "registrador":
        raise HTTPException(status_code=403, detail="Tu rol solo permite visualizar datos")
    nuevo = models.PuntoMonitoreo(**punto.model_dump())
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    _invalidar_cache_mapa()
    return nuevo


@app.get("/puntos/", response_model=List[schemas.PuntoOut])
def listar_puntos(db: Session = Depends(get_db)):
    return db.query(models.PuntoMonitoreo).all()


@app.get("/mapa/puntos-calidad")
def obtener_puntos_mapa(
    color: Optional[str] = Query(None),
    tipo_fuente: Optional[str] = Query(None),
    comunidad: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    # ── Caché: clave según los filtros activos ───────────────
    clave = f"{color}|{tipo_fuente}|{comunidad}"
    ahora_ts = time.time()
    entrada = _cache_mapa.get(clave)
    if entrada and (ahora_ts - entrada["ts"] < _CACHE_TTL):
        return entrada["data"]

    # ── Filtros aplicados en SQL (no en Python) ──────────────
    query = db.query(models.PuntoMonitoreo).options(
        subqueryload(models.PuntoMonitoreo.mediciones)
        .subqueryload(models.Medicion.alertas)
    )
    if tipo_fuente:
        query = query.filter(func.lower(models.PuntoMonitoreo.tipo_fuente) == tipo_fuente.lower())
    if comunidad:
        query = query.filter(models.PuntoMonitoreo.comunidad.ilike(f"%{comunidad}%"))
    puntos = query.all()

    resultado = []
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)

    for p in puntos:
        ultima = max(p.mediciones, key=lambda m: m.fecha, default=None)
        color_punto = "gray"
        detalle_medicion = None

        if ultima:
            tiene_advertencia = any(a.nivel == "advertencia" for a in ultima.alertas)
            alertas_activas = [
                {"tipo": a.tipo, "nivel": a.nivel, "mensaje": a.mensaje}
                for a in ultima.alertas
            ]
            color_punto = ("yellow" if tiene_advertencia else "green") if ultima.apta else "red"
            dias_desde = (ahora - ultima.fecha).days
            detalle_medicion = {
                "fecha": ultima.fecha.strftime("%d/%m/%Y %H:%M"),
                "dias_desde": dias_desde,
                "ph": ultima.ph,
                "cloro": ultima.cloro,
                "turbidez": ultima.turbidez,
                "apta": ultima.apta,
                "observaciones": ultima.observaciones or "—",
                "alertas": alertas_activas,
            }

        if color and color_punto != color:
            continue

        resultado.append({
            "id": p.id,
            "nombre": p.nombre,
            "lat": p.latitud,
            "lng": p.longitud,
            "color": color_punto,
            "tipo_fuente": p.tipo_fuente,
            "comunidad": p.comunidad,
            "fecha_creacion": p.fecha_creacion.strftime("%d/%m/%Y") if p.fecha_creacion else "—",
            "medicion": detalle_medicion,
        })

    # Guardar en caché antes de responder
    _cache_mapa[clave] = {"ts": ahora_ts, "data": resultado}
    return resultado


@app.get("/mapa/comunidades")
def listar_comunidades(db: Session = Depends(get_db)):
    rows = db.query(models.PuntoMonitoreo.comunidad).distinct().all()
    return sorted(set(r[0] for r in rows))


@app.get("/mapa/resumen")
def resumen_mapa(db: Session = Depends(get_db)):
    """Resumen para el tablero de jefatura: conteo de puntos por estado NCh 409
    y cuántos llevan mucho tiempo sin una medición reciente."""
    puntos = (
        db.query(models.PuntoMonitoreo)
        .options(
            subqueryload(models.PuntoMonitoreo.mediciones)
            .subqueryload(models.Medicion.alertas)
        )
        .all()
    )
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)

    conteo = {"green": 0, "yellow": 0, "red": 0, "gray": 0}
    sin_medicion_reciente = 0  # > 30 días sin medir

    for p in puntos:
        ultima = max(p.mediciones, key=lambda m: m.fecha, default=None)
        if not ultima:
            conteo["gray"] += 1
            sin_medicion_reciente += 1
            continue
        tiene_advertencia = any(a.nivel == "advertencia" for a in ultima.alertas)
        color = ("yellow" if tiene_advertencia else "green") if ultima.apta else "red"
        conteo[color] += 1
        if (ahora - ultima.fecha).days > 30:
            sin_medicion_reciente += 1

    return {
        "total": len(puntos),
        "aptos": conteo["green"],
        "advertencia": conteo["yellow"],
        "no_aptos": conteo["red"],
        "sin_datos": conteo["gray"],
        "sin_medicion_reciente": sin_medicion_reciente,
    }


@app.get("/mapa/historial/{punto_id}")
def historial_punto(
    punto_id: int,
    n: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    punto = db.query(models.PuntoMonitoreo).filter(models.PuntoMonitoreo.id == punto_id).first()
    if not punto:
        raise HTTPException(status_code=404, detail="Punto no encontrado")
    mediciones = (
        db.query(models.Medicion)
        .filter(models.Medicion.punto_id == punto_id)
        .order_by(models.Medicion.fecha.asc())
        .limit(n)
        .all()
    )
    return [
        {"fecha": m.fecha.strftime("%d/%m"), "ph": m.ph, "cloro": m.cloro,
         "turbidez": m.turbidez, "apta": m.apta}
        for m in mediciones
    ]


@app.post("/mediciones/", response_model=schemas.MedicionOut)
def crear_medicion(
    medicion: schemas.MedicionCreate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    if current_user.rol != "registrador":
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
    if res["alertas_generadas"]:
        for a in res["alertas_generadas"]:
            db.add(models.Alerta(
                medicion_id=nueva.id,
                tipo=a["tipo"],
                nivel=a["nivel"],
                mensaje=a["mensaje"]
            ))
        db.commit()
    _invalidar_cache_mapa()
    return nueva


@app.get("/mediciones/", response_model=List[schemas.MedicionOut])
def listar_mediciones(db: Session = Depends(get_db)):
    return db.query(models.Medicion).all()


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


# ==========================================================
# RF-08: MÓDULO DE AVISOS COMUNITARIOS (Iteración 7)
# ==========================================================
# La jefatura (visualizador) publica avisos cortos para terreno.
# El registrador los consulta desde su app. Los avisos no se borran:
# se archivan (activo=False), respetando el registro inmutable.

@app.post("/avisos/", response_model=schemas.AvisoOut)
def crear_aviso(
    aviso: schemas.AvisoCreate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    # Solo la jefatura (visualizador) publica avisos.
    if current_user.rol != "visualizador":
        raise HTTPException(
            status_code=403,
            detail="Solo la jefatura (visualizador) puede publicar avisos"
        )
    nuevo = models.Aviso(
        titulo=aviso.titulo,
        mensaje=aviso.mensaje,
        comunidad=aviso.comunidad,
        autor=current_user.email,
        activo=True,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)

    # Notificación por correo a los registradores (modo preparado/seguro).
    registradores = db.query(models.Usuario).filter(
        models.Usuario.rol == "registrador"
    ).all()
    destinatarios = [u.email for u in registradores]
    if destinatarios:
        enviar_aviso_por_correo(destinatarios, aviso.titulo, aviso.mensaje)

    return nuevo


@app.get("/avisos/", response_model=List[schemas.AvisoOut])
def listar_avisos(
    incluir_archivados: bool = Query(False),
    db: Session = Depends(get_db)
):
    """Lista los avisos activos (o todos si incluir_archivados=True).
    Accesible para cualquier usuario autenticado del sistema."""
    query = db.query(models.Aviso)
    if not incluir_archivados:
        query = query.filter(models.Aviso.activo == True)
    return query.order_by(models.Aviso.fecha.desc()).all()


@app.patch("/avisos/{aviso_id}/archivar", response_model=schemas.AvisoOut)
def archivar_aviso(
    aviso_id: int,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    """Archiva un aviso (no lo borra). Solo la jefatura puede archivar."""
    if current_user.rol != "visualizador":
        raise HTTPException(
            status_code=403,
            detail="Solo la jefatura (visualizador) puede archivar avisos"
        )
    aviso = db.query(models.Aviso).filter(models.Aviso.id == aviso_id).first()
    if not aviso:
        raise HTTPException(status_code=404, detail="Aviso no encontrado")
    aviso.activo = False
    db.commit()
    db.refresh(aviso)
    return aviso


# ==========================================================
# RF-04: EXPORTACION PDF (Iteracion 4)
# ==========================================================
@app.get("/puntos/{punto_id}/reporte.pdf")
def exportar_reporte_pdf(
    punto_id: int,
    n: int = Query(20, ge=1, le=100, description="Numero de mediciones a incluir"),
    db: Session = Depends(get_db)
):
    """Genera y descarga un reporte PDF con las ultimas N mediciones de un punto."""
    punto = db.query(models.PuntoMonitoreo).filter(models.PuntoMonitoreo.id == punto_id).first()
    if not punto:
        raise HTTPException(status_code=404, detail="Punto no encontrado")

    mediciones = (
        db.query(models.Medicion)
        .filter(models.Medicion.punto_id == punto_id)
        .order_by(models.Medicion.fecha.desc())
        .limit(n)
        .all()
    )

    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(15, 15, 15)

    pdf.set_fill_color(0, 70, 127)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, "RuralH2O - Reporte de Calidad de Agua", fill=True, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(3)

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, f"Punto: {punto.nombre}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Tipo de fuente: {punto.tipo_fuente}   |   Comunidad: {punto.comunidad}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Coordenadas: {punto.latitud:.5f}, {punto.longitud:.5f}", new_x="LMARGIN", new_y="NEXT")
    gen_ts = datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')
    pdf.cell(0, 6, f"Generado: {gen_ts} UTC", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "Norma: NCh 409 (pH 6.5-8.5 | Cloro <= 2.0 mg/L | Turbidez <= 5.0 NTU)", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(230, 240, 250)
    col_w = [28, 18, 18, 22, 20, 74]
    headers = ["Fecha", "pH", "Cloro", "Turbidez", "Estado", "Observaciones"]
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 7, h, border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font("Helvetica", "", 8)
    for idx, m in enumerate(mediciones):
        fill = idx % 2 == 0
        pdf.set_fill_color(245, 250, 255) if fill else pdf.set_fill_color(255, 255, 255)
        estado = "APTA" if m.apta else "NO APTA"
        pdf.set_text_color(0, 120, 0) if m.apta else pdf.set_text_color(180, 0, 0)
        fecha_str = m.fecha.strftime("%d/%m/%Y %H:%M") if m.fecha else "-"
        obs = (m.observaciones or "Sin observaciones").replace("\u2014","--").replace("\u2013","-").replace("\u2014","-").encode("latin-1","replace").decode("latin-1")[:45]
        row = [fecha_str, f"{m.ph:.2f}", f"{m.cloro:.2f}", f"{m.turbidez:.2f}", estado, obs]
        for i, val in enumerate(row):
            pdf.cell(col_w[i], 6, val, border=1, fill=fill, align="C" if i < 5 else "L")
        pdf.set_text_color(0, 0, 0)
        pdf.ln()

    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 7, "Resumen estadistico", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    total = len(mediciones)
    aptas = sum(1 for m in mediciones if m.apta)
    if total > 0:
        ph_vals = [m.ph for m in mediciones]
        cl_vals = [m.cloro for m in mediciones]
        tu_vals = [m.turbidez for m in mediciones]
        pdf.cell(0, 6, f"Total: {total} | Aptas: {aptas} ({aptas*100//total}%) | No aptas: {total-aptas}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 6, f"pH prom: {sum(ph_vals)/total:.2f} | min: {min(ph_vals):.2f} | max: {max(ph_vals):.2f}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 6, f"Cloro prom: {sum(cl_vals)/total:.2f} | min: {min(cl_vals):.2f} | max: {max(cl_vals):.2f}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 6, f"Turbidez prom: {sum(tu_vals)/total:.2f} | min: {min(tu_vals):.2f} | max: {max(tu_vals):.2f}", new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(-20)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 5, "Sistema RuralH2O - Universidad de Aysen - Norma NCh 409", align="C", new_x="LMARGIN", new_y="NEXT")

    buf = io.BytesIO(pdf.output())
    nombre_safe = punto.nombre.replace(' ', '_')
    nombre_archivo = f"reporte_{nombre_safe}_{punto_id}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"}
    )


# ==========================================================
# RF-08: AVISOS COMUNITARIOS (Iteracion 7)
# ==========================================================
# La jefatura (visualizador) publica avisos cortos visibles para
# todos los usuarios. Solo el visualizador puede crear o eliminar.
@app.post("/avisos/", response_model=schemas.AvisoOut)
def crear_aviso(
    aviso: schemas.AvisoCreate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    if current_user.rol != "visualizador":
        raise HTTPException(
            status_code=403,
            detail="Solo la jefatura (visualizador) puede publicar avisos"
        )
    nuevo = models.Aviso(
        titulo=aviso.titulo,
        mensaje=aviso.mensaje,
        comunidad=aviso.comunidad,
        autor=current_user.email,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


@app.get("/avisos/", response_model=List[schemas.AvisoOut])
def listar_avisos(
    comunidad: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Lista los avisos (más recientes primero). Visible para todos los usuarios."""
    query = db.query(models.Aviso)
    if comunidad:
        query = query.filter(models.Aviso.comunidad.ilike(f"%{comunidad}%"))
    return query.order_by(models.Aviso.fecha.desc()).all()


@app.delete("/avisos/{aviso_id}")
def eliminar_aviso(
    aviso_id: int,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(get_current_user)
):
    if current_user.rol != "visualizador":
        raise HTTPException(
            status_code=403,
            detail="Solo la jefatura (visualizador) puede eliminar avisos"
        )
    aviso = db.query(models.Aviso).filter(models.Aviso.id == aviso_id).first()
    if not aviso:
        raise HTTPException(status_code=404, detail="Aviso no encontrado")
    db.delete(aviso)
    db.commit()
    return {"detail": "Aviso eliminado", "id": aviso_id}


# ==========================================================
# RF-04 EXTRA: PDF FILTRADO DEL MAPA (Iteracion 4)
# ==========================================================
@app.get("/reporte-mapa.pdf")
def exportar_reporte_mapa_pdf(
    color: Optional[str] = Query(None, description="Filtrar por color: gray, green, yellow, red"),
    tipo_fuente: Optional[str] = Query(None, description="Filtrar por tipo de fuente"),
    comunidad: Optional[str] = Query(None, description="Filtrar por comunidad"),
    db: Session = Depends(get_db)
):
    """Genera un PDF con todos los puntos visibles segun los filtros activos del mapa."""
    puntos = (
        db.query(models.PuntoMonitoreo)
        .options(subqueryload(models.PuntoMonitoreo.mediciones))
        .all()
    )

    ahora = datetime.now(timezone.utc).replace(tzinfo=None)
    COLOR_LABELS = {"green": "APTA", "yellow": "ADVERTENCIA", "red": "NO APTA", "gray": "SIN DATOS"}

    # Aplicar filtros igual que /mapa/puntos-calidad
    resultado = []
    for p in puntos:
        if tipo_fuente and p.tipo_fuente.lower() != tipo_fuente.lower():
            continue
        if comunidad and comunidad.lower() not in p.comunidad.lower():
            continue
        ultima = max(p.mediciones, key=lambda m: m.fecha, default=None) if p.mediciones else None
        if ultima:
            from validaciones import evaluar_nch409
            tiene_advertencia = False
            # Recalcular color basado en la ultima medicion
            if not ultima.apta:
                color_punto = "red"
            else:
                # Verificar si tiene alertas de advertencia (simplificado)
                ph_ok = 6.5 <= ultima.ph <= 8.5
                cl_ok = 0.2 <= ultima.cloro <= 2.0
                tu_ok = ultima.turbidez <= 5.0
                if ph_ok and cl_ok and tu_ok:
                    color_punto = "green"
                else:
                    color_punto = "yellow"
        else:
            color_punto = "gray"

        if color and color_punto != color:
            continue

        resultado.append({
            "id": p.id,
            "nombre": p.nombre,
            "tipo_fuente": p.tipo_fuente,
            "comunidad": p.comunidad,
            "lat": p.latitud,
            "lng": p.longitud,
            "color": color_punto,
            "medicion": ultima,
        })

    if not resultado:
        raise HTTPException(status_code=404, detail="No hay puntos con los filtros aplicados")

    # Descripcion del filtro activo
    filtro_desc = []
    if color:      filtro_desc.append("Estado: " + COLOR_LABELS.get(color, color))
    if tipo_fuente: filtro_desc.append("Tipo: " + tipo_fuente)
    if comunidad:  filtro_desc.append("Comunidad: " + comunidad)
    filtro_str = " | ".join(filtro_desc) if filtro_desc else "Todos los puntos"

    # Construir PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(15, 15, 15)

    # Encabezado
    pdf.set_fill_color(0, 70, 127)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 12, "RuralH2O - Reporte Filtrado del Mapa", fill=True, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(2)

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 9)
    gen_ts = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")
    pdf.cell(0, 5, "Generado: " + gen_ts + " UTC   |   Filtro: " + filtro_str + "   |   Puntos: " + str(len(resultado)), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, "Norma NCh 409: pH 6.5-8.5 | Cloro 0.2-2.0 mg/L | Turbidez <= 5.0 NTU", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Cabecera de tabla
    # FIX: anchos ajustados para sumar exactamente 180mm (A4 - margenes 15+15)
    # col_w anterior sumaba 200mm → desbordaba y generaba pagina 2 en blanco
    COLOR_FILL = {"green": (20,83,45), "yellow": (113,63,18), "red": (127,29,29), "gray": (55,65,81)}
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(230, 240, 250)
    col_w = [8, 42, 20, 30, 24, 11, 13, 15, 17]  # suma = 180mm exacto
    headers = ["ID", "Nombre", "Tipo", "Comunidad", "Estado", "pH", "Cloro", "NTU", "Fecha"]
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 7, h, border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font("Helvetica", "", 7)
    for idx, p in enumerate(resultado):
        fill_bg = idx % 2 == 0
        pdf.set_fill_color(245, 250, 255) if fill_bg else pdf.set_fill_color(255, 255, 255)
        m = p["medicion"]
        estado = COLOR_LABELS.get(p["color"], p["color"])
        r,g,b = COLOR_FILL.get(p["color"], (55,65,81))
        ph_str = f"{m.ph:.1f}" if m else "-"
        cl_str = f"{m.cloro:.1f}" if m else "-"
        tu_str = f"{m.turbidez:.1f}" if m else "-"
        fecha_str = m.fecha.strftime("%d/%m/%y") if m and m.fecha else "-"
        # FIX: limites de truncacion aumentados para coincidir con anchos de columna reales
        nombre_safe = p["nombre"].encode("latin-1", "replace").decode("latin-1")[:22]
        com_safe = p["comunidad"].encode("latin-1", "replace").decode("latin-1")[:16]
        tipo_safe = p["tipo_fuente"].encode("latin-1", "replace").decode("latin-1")[:11]
        row = [str(p["id"]), nombre_safe, tipo_safe, com_safe, estado, ph_str, cl_str, tu_str, fecha_str]
        for i, val in enumerate(row):
            if i == 4:  # Estado con color
                pdf.set_text_color(r, g, b)
            else:
                pdf.set_text_color(0, 0, 0)
            pdf.cell(col_w[i], 6, val, border=1, fill=fill_bg, align="C")
        pdf.set_text_color(0, 0, 0)
        pdf.ln()

    # Resumen
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 6, "Resumen", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 8)
    conteo = {c: sum(1 for p in resultado if p["color"] == c) for c in ["green","yellow","red","gray"]}
    pdf.cell(0, 5,
        f"Aptos: {conteo['green']}  |  Advertencia: {conteo['yellow']}  |  No aptos: {conteo['red']}  |  Sin datos: {conteo['gray']}",
        new_x="LMARGIN", new_y="NEXT")

    # FIX: footer inline en vez de set_y(-15) para evitar pagina 2 en blanco
    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 5, "RuralH2O - Universidad de Aysen - Norma NCh 409", align="C",
             new_x="LMARGIN", new_y="NEXT")

    buf = io.BytesIO(pdf.output())
    nombre_safe2 = "reporte_mapa_" + (color or "todos") + "_" + datetime.now(timezone.utc).strftime("%Y%m%d") + ".pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=" + nombre_safe2}
    )