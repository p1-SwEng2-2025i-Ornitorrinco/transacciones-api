from fastapi import APIRouter, Depends, HTTPException
from app.models.credito import AsignacionCreditoRequest
from app.db.mongo import usuarios_collection, transacciones_collection
from app.utils.jwt_handler import get_current_user
from bson import ObjectId
from datetime import datetime

router = APIRouter(prefix="/admin")

@router.post("/admin/asignar_creditos")
async def asignar_creditos_admin(data: AsignacionCreditoRequest, user_id: str = Depends(get_current_user)):
    # Validar que el usuario autenticado sea un "admin"
    admin = await usuarios_collection.find_one({"_id": ObjectId(user_id)})
    if not admin or admin.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Solo los administradores pueden asignar créditos")

    # Validar que el usuario destino exista
    if not ObjectId.is_valid(data.usuario_id):
        raise HTTPException(status_code=400, detail="ID de usuario inválido")

    usuario = await usuarios_collection.find_one({"_id": ObjectId(data.usuario_id)})
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    saldo_actual = float(usuario.get("saldo_creditos", 0.0))
    nuevo_saldo = saldo_actual + data.monto

    await usuarios_collection.update_one(
        {"_id": ObjectId(data.usuario_id)},
        {
            "$set": {
                "saldo_creditos": nuevo_saldo,
                "moneda_virtual.ultima_actualizacion": datetime.utcnow()
            }
        }
    )
    nueva_transaccion = {
        "id_emisor": "admin",
        "id_receptor": data.usuario_id,
        "monto": data.monto,
        "fecha": datetime.utcnow(),
        "tipo": "asignacion",
        "justificacion": data.justificacion if hasattr(data, "justificacion") else "Asignación de créditos"
    }
    await transacciones_collection.insert_one(nueva_transaccion)

    return {
        "mensaje": f"{data.monto} créditos asignados a {usuario['nombres']} {usuario['apellidos']}",
        "nuevo_saldo": nuevo_saldo
    }

    
