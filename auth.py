# =============================
#      Seguridad / Auth
# =============================

from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext

#SECRET 
SECRET_KEY = "ruralh2o-secret-aysen-2026"
ALGORITHM  = "HS256"
TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def crear_token(data: dict) -> str:
    payload = data.copy()
    expira  = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    payload.update({"exp": expira})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verificar_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
