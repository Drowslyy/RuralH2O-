# =============================
#       Conexión a la BD
# =============================

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine

# Esto carga las variables del archivo .env
load_dotenv()

# Ahora la URL se lee del sistema, no está escrita aquí directamente
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL) #Motor de conexion usando las credenciales

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) # Fabrica de sesiones (Consuta de API --> BD)

Base = declarative_base()

# Dependencia para obtener sesión de BD en cada endpoint
def get_db(): # Asegura la conexion se abra para poder hacer peticiones y se cierra automaticamente al terminar (Evita fuga de memoria)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
