"""
notificaciones.py — Iteración 7 (RF-08)

Notificación por correo a la jefatura, en modo "preparado y seguro":

- Si hay credenciales SMTP configuradas en variables de entorno
  (SMTP_HOST, SMTP_USER, SMTP_PASS), envía un correo real.
- Si NO hay credenciales, NO falla: registra la notificación en consola
  (modo simulado). Así la app funciona siempre, online u offline, y la
  demostración nunca se rompe por un problema de servidor de correo.

Esto respeta la arquitectura offline-first del proyecto: el correo es un
complemento, no una dependencia crítica.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.utils import formatdate


def _config_smtp():
    """Lee la configuración SMTP desde variables de entorno (si existe)."""
    host = os.getenv("SMTP_HOST")
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")
    if host and user and password:
        return {
            "host": host,
            "port": int(os.getenv("SMTP_PORT", "587")),
            "user": user,
            "password": password,
        }
    return None


def enviar_aviso_por_correo(destinatarios, titulo, mensaje):
    """
    Envía (o simula) un aviso por correo a la jefatura.

    Devuelve un dict con el resultado, sin lanzar excepciones que rompan
    la petición HTTP. El módulo de avisos sigue funcionando aunque el
    correo falle.
    """
    cfg = _config_smtp()

    # Modo simulado: sin SMTP configurado, registramos y seguimos.
    if cfg is None:
        print(f"[NOTIFICACION SIMULADA] Para: {destinatarios} | "
              f"Asunto: {titulo} | Mensaje: {mensaje}")
        return {"enviado": False, "modo": "simulado",
                "detalle": "SMTP no configurado; aviso registrado en la app."}

    # Modo real: intentamos enviar, capturando cualquier error.
    try:
        cuerpo = MIMEText(mensaje, "plain", "utf-8")
        cuerpo["Subject"] = f"[RuralH2O] {titulo}"
        cuerpo["From"] = cfg["user"]
        cuerpo["To"] = ", ".join(destinatarios)
        cuerpo["Date"] = formatdate(localtime=True)

        with smtplib.SMTP(cfg["host"], cfg["port"]) as server:
            server.starttls()
            server.login(cfg["user"], cfg["password"])
            server.sendmail(cfg["user"], destinatarios, cuerpo.as_string())

        return {"enviado": True, "modo": "smtp",
                "detalle": f"Correo enviado a {len(destinatarios)} destinatario(s)."}
    except Exception as e:
        # Nunca rompemos la petición por un fallo de correo.
        print(f"[NOTIFICACION ERROR] No se pudo enviar el correo: {e}")
        return {"enviado": False, "modo": "error",
                "detalle": f"Fallo SMTP: {e}. El aviso se guardó igualmente en la app."}