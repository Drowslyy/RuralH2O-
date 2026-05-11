# =============================
#       Conexión a la BD
# =============================

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Carga las variables del archivo .env
load_dotenv()

# La URL se lee del sistema, no está escrita aquí directamente
DATABASE_URL = os.getenv("DATABASE_URL")

# FIX: eliminado import duplicado de create_engine que existía en la línea 12
engine = create_engine(DATABASE_URL)  # Motor de conexión usando las credenciales

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)  # Fábrica de sesiones

Base = declarative_base()


# Dependencia para obtener sesión de BD en cada endpoint.
# Asegura que la conexión se abra para poder hacer peticiones
# y se cierra automáticamente al terminar (evita fuga de memoria).
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()