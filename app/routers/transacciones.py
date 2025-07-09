from fastapi import APIRouter, Request, HTTPException, Depends, Header
from fastapi.security import HTTPBearer
from app.models.transaccion import Transaccion
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.db.mongo import transacciones_collection, usuarios_collection, client
from app.utils.jwt_handler import SECRET_KEY, ALGORITHM
from app.utils.jwt_handler import verificar_token, verificar_admin
from app.utils.jwt_handler import get_current_user
from app.models.transaccion import Transaccion 
from jose import jwt,JWTError
from bson import ObjectId
from datetime import datetime
from typing import Optional

router = APIRouter()
security = HTTPBearer()

async def verificar_admin(user_id: str = Depends(get_current_user)):
    usuario = await usuarios_collection.find_one({"_id": ObjectId(user_id)})
    if not usuario or usuario.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Acceso restringido a administradores")
    return user_id

async def ejecutar_transaccion(
    id_emisor: Optional[str],
    id_receptor: str,
    monto: float,
    tipo: str,
    justificacion: Optional[str] = None,
    id_servicio: Optional[str] = None,
    session=None
):
    """Función reusable para lógica transaccional"""
    # Validar usuarios
    if id_emisor:
        emisor = await usuarios_collection.find_one(
            {"_id": id_emisor},
            session=session
        )
        if not emisor:
            raise ValueError("Emisor no encontrado")
        if emisor.get("saldo", 0) < monto:
            raise ValueError("Saldo insuficiente")

    receptor = await usuarios_collection.find_one(
        {"_id": id_receptor},
        session=session
    )
    if not receptor:
        raise ValueError("Receptor no encontrado")

    # Actualizar saldos
    if id_emisor:
        await usuarios_collection.update_one(
            {"_id": id_emisor},
            {"$inc": {"saldo": -monto}},
            session=session
        )

    await usuarios_collection.update_one(
        {"_id": id_receptor},
        {"$inc": {"saldo": monto}},
        session=session
    )

    # Registrar transacción
    transaccion_data = {
        "id_emisor": id_emisor,
        "id_receptor": id_receptor,
        "monto": monto,
        "tipo": tipo,
        "fecha": datetime.utcnow(),
        "id_servicio": id_servicio,
        "justificacion": justificacion
    }

    result = await transacciones_collection.insert_one(
        transaccion_data,
        session=session
    )
    
    return str(result.inserted_id)

@router.get("/saldo/{user_id}")
async def obtener_saldo(user_id: str):
    usuario = await usuarios_collection.find_one({"_id": user_id})
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {"saldo": usuario.get("saldo", 0)}

@router.get("/transacciones/historial/{user_id}")
async def historial_transacciones(user_id: str):
    cursor = transacciones_collection.find({
        "$or": [
            {"id_emisor": user_id},
            {"id_receptor": user_id}
        ]
    }).sort("fecha", -1)
    historial = []
    async for transaccion in cursor:
        transaccion["_id"] = str(transaccion["_id"])
        historial.append(transaccion)
    return historial

@router.post("/transacciones/transferir", response_model=Transaccion)
async def transferir_creditos(datos: Transaccion, user_id: str = Depends(get_current_user)):
    # Validar que el usuario autenticado sea quien transfiere
    if user_id != datos.id_emisor:
        raise HTTPException(status_code=403, detail="No puedes transferir como otro usuario")

    # Validar IDs
    if not ObjectId.is_valid(datos.id_emisor) or not ObjectId.is_valid(datos.id_receptor):
        raise HTTPException(status_code=400, detail="ID inválido")

    emisor = await usuarios_collection.find_one({"_id": ObjectId(datos.id_emisor)})
    receptor = await usuarios_collection.find_one({"_id": ObjectId(datos.id_receptor)})

    if not emisor or not receptor:
        raise HTTPException(status_code=404, detail="Emisor o receptor no encontrado")

    # Obtener saldos actuales (inicializar si no existen)
    moneda_emisor = emisor.get("moneda_virtual", {})
    saldo_emisor = moneda_emisor.get("saldo", 0.0)

    moneda_receptor = receptor.get("moneda_virtual", {})
    saldo_receptor = moneda_receptor.get("saldo", 0.0)

    # Validar saldo suficiente
    if saldo_emisor < datos.monto:
        raise HTTPException(status_code=400, detail="Saldo insuficiente")

    # Registrar transacción
    transaccion_dict = datos.dict()
    transaccion_dict["fecha"] = datos.fecha or datetime.utcnow()

    await transacciones_collection.insert_one(transaccion_dict)

    # Actualizar saldo emisor
    await usuarios_collection.update_one(
        {"_id": ObjectId(datos.id_emisor)},
        {"$set": {
            "moneda_virtual.saldo": saldo_emisor - datos.monto,
            "moneda_virtual.ultima_actualizacion": datetime.utcnow()
        }}
    )

    # Actualizar saldo receptor
    await usuarios_collection.update_one(
        {"_id": ObjectId(datos.id_receptor)},
        {"$set": {
            "moneda_virtual.saldo": saldo_receptor + datos.monto,
            "moneda_virtual.ultima_actualizacion": datetime.utcnow()
        }}
    )

    return datos



@router.post("/admin/asignar_creditos")
async def asignar_creditos(datos: Transaccion, usuario=Depends(verificar_admin)):
    if not datos.justificacion or not datos.id_receptor:
        raise HTTPException(status_code=400, detail="Falta justificación o receptor")

    await usuarios_collection.update_one({"_id": datos.id_receptor}, {"$inc": {"saldo": datos.monto}})

    nueva_transaccion = datos.dict()
    nueva_transaccion["tipo"] = "asignacion"
    nueva_transaccion["fecha"] = datetime.utcnow()
    nueva_transaccion["id_emisor"] = "admin"

    await transacciones_collection.insert_one(nueva_transaccion)

    return {"mensaje": f"Se asignaron {datos.monto} créditos al usuario {datos.id_receptor}"}



