#!/usr/bin/env python3
"""
Verificador de los fixes de RuralH2O.

Comprueba, archivo por archivo, que cada bug reportado quedó corregido.
No prueba el comportamiento en el navegador (eso depende del caché del
Service Worker); verifica que el CÓDIGO fuente contenga los arreglos.

Uso:
    python3 test_fixes.py [carpeta]

Si no se indica carpeta, usa el directorio actual.
Sale con código 0 si todo pasa, 1 si algo falla.
"""

import sys
import re
from pathlib import Path

base = Path(sys.argv[1] if len(sys.argv) > 1 else ".")

fallos = []
oks = []


def leer(nombre):
    f = base / nombre
    if not f.exists():
        fallos.append(f"[{nombre}] NO ENCONTRADO en {base}")
        return None
    return f.read_text(encoding="utf-8")


def check(nombre, descripcion, condicion):
    if condicion:
        oks.append(f"[{nombre}] OK — {descripcion}")
    else:
        fallos.append(f"[{nombre}] FALLA — {descripcion}")


# ── mediciones.html ──────────────────────────────────────────
med = leer("mediciones.html")
if med:
    check("mediciones.html", "campo 'Observaciones' (inp-obs) eliminado",
          "inp-obs" not in med)
    check("mediciones.html", "inputs lat/lng son type=text (punto decimal)",
          'id="inp-lat"' in med and re.search(r'type="text"\s+id="inp-lat"', med) is not None)
    check("mediciones.html", "marcador usa divIcon CSS (no PNG roto)",
          "iconoSel" in med and "fijarCoords" in med)
    check("mediciones.html", "bloque historial + descarga PDF al elegir punto",
          'id="info-punto"' in med and "btn-pdf-punto" in med)
    check("mediciones.html", "normaliza coma a punto en coordenadas",
          'replace(",", ".")' in med)
    check("mediciones.html", "visualizador redirigido (no registra)",
          'ROL === "visualizador"' in med)

# ── index.html ───────────────────────────────────────────────
idx = leer("index.html")
if idx:
    check("index.html", "clic en marcador detiene propagación",
          "stopPropagation(ev)" in idx)
    check("index.html", "centra/resalta el punto seleccionado",
          "seleccionarPunto" in idx)
    check("index.html", "botón PDF individual en panel de detalle",
          "btn-pdf-punto" in idx)

# ── campo.html ───────────────────────────────────────────────
campo = leer("campo.html")
if campo:
    check("campo.html", "guard de solo-lectura para visualizador",
          "SOLO_LECTURA" in campo)

# ── main.py ──────────────────────────────────────────────────
mainpy = leer("main.py")
if mainpy:
    check("main.py", "título Swagger en Iteración 5",
          "Iteración 5" in mainpy or "Iteracion 5" in mainpy)
    check("main.py", "crear_punto bloquea visualizador",
          'rol not in ("admin", "registrador")' in mainpy)

# ── sw.js ────────────────────────────────────────────────────
sw = leer("sw.js")
if sw:
    check("sw.js", "versión de caché actualizada (invalida caché viejo)",
          "ruralh2o-v6" in sw)
    check("sw.js", "estrategia network-first para /view/* (no HTML obsoleto)",
          "Network-first" in sw or "network-first" in sw)

# ── Resultado ────────────────────────────────────────────────
print("\n".join(oks))
if fallos:
    print("\n--- FALLOS ---")
    print("\n".join(fallos))
    print(f"\n{len(oks)} pasaron, {len(fallos)} fallaron.")
    sys.exit(1)
else:
    print(f"\nTodos los checks pasaron ({len(oks)}).")
    sys.exit(0)