from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from app.routers import transacciones, auth, admin
from app.models.transaccion import Transaccion 
from datetime import datetime, timedelta
from fastapi.openapi.models import APIKey, APIKeyIn, SecuritySchemeType
from fastapi.openapi.utils import get_openapi
from app.utils.jwt_handler import SECRET_KEY, ALGORITHM
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.db.mongo import transacciones_collection, usuarios_collection
from jose import JWTError, jwt
from bson import ObjectId
import uvicorn 
import traceback


app = FastAPI(title="API de Transacciones y Moneda Virtual")
security = HTTPBearer()

# 🔵 Añadir middleware de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instrumentación automática de métricas 
Instrumentator().instrument(app).expose(app)

# Rutas del API
app.include_router(auth.router, prefix="/api")
app.include_router(transacciones.router, prefix="/api")
app.include_router(admin.router)

@app.get("/")
def root():
    return {"mensaje": "API de gestión de créditos y transacciones"}

# Manejo de errores (igual que antes)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={"detail": exc.errors(), "body": exc.body},
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    print("🔴 Excepción no controlada:")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": f"Error interno del servidor: {str(exc)}"},
    )

if __name__ == "__main__":  # ← ¡Agrega esto!
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)

@app.post("/generar-token")
async def generar_token(usuario: str, rol: str = "user"):
    """Endpoint temporal para generar tokens de prueba"""
    expires = datetime.utcnow() + timedelta(hours=1)
    to_encode = {"sub": usuario, "rol": rol, "exp": expires}
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version="1.0.0",
        description="API de Transacciones y Moneda Virtual",
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }
    for path in openapi_schema["paths"]:
        for method in openapi_schema["paths"][path]:
            if "security" not in openapi_schema["paths"][path][method]:
                openapi_schema["paths"][path][method]["security"] = [{"BearerAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

