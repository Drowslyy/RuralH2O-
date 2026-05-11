# ============================================================
#  Iteración 3: RF-05 Mapa interactivo — 4 colores NCh 409
#
#  Inserta 4 puntos de monitoreo con sus mediciones y alertas
#  para visualizar los 4 estados del mapa:
#    ⚫ GRIS   → punto sin mediciones
#    🟢 VERDE  → agua apta, todos los parámetros dentro de norma
#    🟡 AMARILLO → apta pero con parámetro en zona límite
#    🔴 ROJO   → no apta, parámetro fuera de norma crítico
#
# ============================================================

import sys
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# ============================================================
# CONFIGURACIÓN DE CONEXIÓN A LA BASE DE DATOS (XAMPP MySQL)
# ============================================================
DB_HOST     = "localhost"
DB_PORT     = 3306
DB_USER     = "root"
DB_PASSWORD = "root1234"   
DB_NAME     = "ruralh2o"
# ============================================================

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


# ── Importar modelos y validaciones del proyecto ─────────────
try:
    from models import Base, PuntoMonitoreo, Medicion, Alerta
    from validaciones import evaluar_nch409
except ImportError as e:
    print(f"\n❌ Error al importar módulos del proyecto: {e}")
    print("   Asegúrate de ejecutar este script desde la carpeta raíz del proyecto.")
    sys.exit(1)


# ── Datos de los 4 puntos de prueba ──────────────────────────
PUNTOS_PRUEBA = [
    {
        "punto": {
            "nombre":      "Pozo Gris — Sin Datos",
            "tipo_fuente": "pozo",
            "comunidad":   "Villa Aysén",
            "latitud":     -45.5700,
            "longitud":    -72.0600,
        },
        "medicion": None,  # Sin medición → color GRIS
        "color_esperado": "⚫ GRIS",
    },
    {
        "punto": {
            "nombre":      "Pozo Verde — Agua Óptima",
            "tipo_fuente": "pozo",
            "comunidad":   "Villa Aysén",
            "latitud":     -45.5750,
            "longitud":    -72.0650,
        },
        "medicion": {
            # Todos los parámetros perfectamente dentro de norma
            "ph":       7.0,   # Rango normal: 6.5–8.5
            "cloro":    1.0,   # Rango normal: 0.2–2.0 mg/L
            "turbidez": 2.0,   # Rango normal: ≤5 NTU
        },
        "color_esperado": "🟢 VERDE",
    },
    {
        "punto": {
            "nombre":      "Pozo Amarillo — pH Límite",
            "tipo_fuente": "vertiente",
            "comunidad":   "Sector Norte",
            "latitud":     -45.5800,
            "longitud":    -72.0700,
        },
        "medicion": {
            # pH en zona de advertencia (6.0–6.5): apta pero con alerta
            "ph":       6.2,   # ⚠ Zona límite: 6.0–6.5
            "cloro":    1.0,   # ✅ Normal
            "turbidez": 2.0,   # ✅ Normal
        },
        "color_esperado": "🟡 AMARILLO",
    },
    {
        "punto": {
            "nombre":      "Pozo Rojo — Turbidez Crítica",
            "tipo_fuente": "río",
            "comunidad":   "Sector Sur",
            "latitud":     -45.5850,
            "longitud":    -72.0750,
        },
        "medicion": {
            # Turbidez fuera del rango crítico (>10 NTU): NO apta
            "ph":       7.0,    # ✅ Normal
            "cloro":    1.0,    # ✅ Normal
            "turbidez": 15.0,   # ❌ Crítico: >10 NTU
        },
        "color_esperado": "🔴 ROJO",
    },
]


def poblar(db):
    """Inserta los 4 puntos con sus mediciones y alertas."""
    resumen = []

    for item in PUNTOS_PRUEBA:
        # 1. Crear el punto de monitoreo
        punto = PuntoMonitoreo(**item["punto"])
        db.add(punto)
        db.flush()  # Obtener el id generado sin hacer commit aún

        # 2. Si tiene medición, evaluarla y guardar
        if item["medicion"]:
            m = item["medicion"]
            res = evaluar_nch409(m["ph"], m["cloro"], m["turbidez"])

            medicion = Medicion(
                ph           = m["ph"],
                cloro        = m["cloro"],
                turbidez     = m["turbidez"],
                punto_id     = punto.id,
                apta         = res["apta"],
                observaciones= res["observaciones"],
                fecha        = datetime.utcnow(),
            )
            db.add(medicion)
            db.flush()

            # 3. Guardar alertas si hay (críticas o advertencias)
            for a in res["alertas_generadas"]:
                db.add(Alerta(
                    medicion_id = medicion.id,
                    tipo        = a["tipo"],
                    nivel       = a["nivel"],
                    mensaje     = a["mensaje"],
                    leida       = False,
                    fecha       = datetime.utcnow(),
                ))

            resumen.append({
                "punto":   punto.nombre,
                "color":   item["color_esperado"],
                "apta":    res["apta"],
                "obs":     res["observaciones"],
                "alertas": len(res["alertas_generadas"]),
            })
        else:
            resumen.append({
                "punto":   punto.nombre,
                "color":   item["color_esperado"],
                "apta":    "—",
                "obs":     "Sin mediciones",
                "alertas": 0,
            })

    db.commit()
    return resumen


def main():
    print("\n" + "="*60)
    print("  RuralH2O — Población de BD XAMPP (4 colores NCh 409)")
    print("="*60)

    # Conexión a MySQL
    try:
        engine = create_engine(DATABASE_URL, echo=False)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"✅ Conexión exitosa a MySQL ({DB_HOST}/{DB_NAME})\n")
    except Exception as e:
        print(f"\n❌ No se pudo conectar a MySQL: {e}")
        print("   Verifica que XAMPP esté corriendo y que la contraseña sea correcta.")
        sys.exit(1)

    # Crear tablas si no existen
    Base.metadata.create_all(bind=engine)
    print("✅ Tablas verificadas/creadas\n")

    # Sesión y población
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        resumen = poblar(db)
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error al insertar datos: {e}")
        db.close()
        sys.exit(1)
    finally:
        db.close()

    # Mostrar resumen
    print(f"{'Punto':<35} {'Color':<20} {'Apta':<8} {'Alertas':<8} Observaciones")
    print("-"*100)
    for r in resumen:
        print(f"{r['punto']:<35} {r['color']:<20} {str(r['apta']):<8} {r['alertas']:<8} {r['obs']}")

    print("\n✅ Datos insertados correctamente en la BD.")
    print("   Abre el mapa en tu app y verás los 4 marcadores con sus colores.\n")


if __name__ == "__main__":
    main()