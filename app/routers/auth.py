from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
from app.models.auth import LoginRequest, LoginResponse
from app.db.mongo import usuarios_collection
from app.utils.jwt_handler import create_jwt_token
from passlib.context import CryptContext
from jose import jwt

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "secret"  # Usa la misma clave que en jwt_handler.py
ALGORITHM = "HS256"

@router.post("/auth/token")
async def generar_token(usuario: str, rol: str = "user"):
    expires = datetime.utcnow() + timedelta(hours=1)
    payload = {
        "sub": usuario,
        "rol": rol,
        "exp": expires
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login", response_model=LoginResponse)
async def login_user(credentials: LoginRequest):
    user = await usuarios_collection.find_one({"correo": credentials.correo})
    if not user:
        raise HTTPException(status_code=401, detail="Correo no encontrado")

    if not pwd_context.verify(credentials.contrasena, user.get("hashed_password", "")):
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")

    token = create_jwt_token(data={"sub": str(user["_id"])})
    return {"access_token": token, "token_type": "bearer"}