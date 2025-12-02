import os
from datetime import datetime
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer

from app.db.mongo import client, transacciones_collection, usuarios_collection
from app.models.transaccion import ServicioTransaccion, Transaccion
from app.utils.jwt_handler import get_current_user

router = APIRouter()
security = HTTPBearer()

USUARIOS_API_BASE_URL = os.getenv(
    "USUARIOS_API_BASE_URL", "https://usuarios-api-2d5af8f6584a.herokuapp.com"
)


def _build_avatar_url(foto_url: Optional[str]) -> Optional[str]:
    """Devuelve la URL completa de la foto de perfil."""
    if not foto_url:
        return None
    if foto_url.startswith("http"):
        return foto_url
    if foto_url.startswith("/"):
        return f"{USUARIOS_API_BASE_URL}{foto_url}"
    return foto_url


async def _obtener_usuario(user_id: str, session=None):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="ID de usuario inválido")

    usuario = await usuarios_collection.find_one({"_id": ObjectId(user_id)}, session=session)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return usuario


async def _build_counterparty(user_id: str):
    try:
        usuario = await _obtener_usuario(user_id)
        nombre = f"{usuario.get('nombres', '')} {usuario.get('apellidos', '')}".strip()
        return {
            "id": user_id,
            "name": nombre or "Usuario",
            "avatar": _build_avatar_url(usuario.get("foto_url")) or "",
        }
    except HTTPException:
        # Si el usuario ya no existe, devolvemos datos mínimos
        return {"id": user_id, "name": "Usuario", "avatar": ""}


@router.get("/saldo/{user_id}")
async def obtener_saldo(user_id: str):
    usuario = await _obtener_usuario(user_id)
    return {"saldo": float(usuario.get("saldo_creditos", 0.0))}


@router.get("/transacciones/historial/{user_id}")
async def historial_transacciones(user_id: str):
    cursor = (
        transacciones_collection.find(
            {
                "$or": [
                    {"id_emisor": user_id},
                    {"id_receptor": user_id},
                ]
            }
        )
        .sort("fecha", -1)
    )

    historial = []
    async for transaccion in cursor:
        tipo_original = transaccion.get("tipo", "transferencia")

        if tipo_original == "asignacion" or transaccion.get("id_emisor") == "admin":
            tipo = "bonus"
        elif transaccion.get("id_receptor") == user_id:
            tipo = "received"
        else:
            tipo = "sent"

        if tipo == "bonus":
            contraparte_id = transaccion.get("id_emisor")
        elif tipo == "received":
            contraparte_id = transaccion.get("id_emisor")
        else:
            contraparte_id = transaccion.get("id_receptor")
        historial.append(
            {
                "id": str(transaccion.get("_id")),
                "type": tipo,
                "amount": float(transaccion.get("monto", 0)),
                "date": (
                    transaccion.get("fecha").isoformat()
                    if transaccion.get("fecha")
                    else datetime.utcnow().isoformat()
                ),
                "description": transaccion.get("justificacion") or tipo_original,
                "status": transaccion.get("estado", "completed"),
                "counterparty": await _build_counterparty(contraparte_id)
                if contraparte_id
                else None,
                "id_servicio": transaccion.get("id_servicio"),
            }
        )
    return historial


@router.get("/transacciones/servicios/{user_id}")
async def historial_servicios(user_id: str):
    cursor = (
        transacciones_collection.find(
            {
                "tipo": "servicio",
                "$or": [
                    {"id_emisor": user_id},
                    {"id_receptor": user_id},
                ],
            }
        )
        .sort("fecha", -1)
    )

    contratados = []
    prestados = []

    async for transaccion in cursor:
        es_contratado = transaccion.get("id_emisor") == user_id
        contraparte_id = (
            transaccion.get("id_receptor")
            if es_contratado
            else transaccion.get("id_emisor")
        )

        item = {
            "id": str(transaccion.get("_id")),
            "servicio_id": transaccion.get("id_servicio"),
            "titulo": transaccion.get("servicio_titulo")
            or transaccion.get("justificacion")
            or "Servicio",
            "fecha": (
                transaccion.get("fecha").isoformat()
                if transaccion.get("fecha")
                else datetime.utcnow().isoformat()
            ),
            "estado": transaccion.get("estado", "completed"),
            "monto": float(transaccion.get("monto", 0)),
            "contraparte": await _build_counterparty(contraparte_id)
            if contraparte_id
            else None,
        }

        if es_contratado:
            contratados.append(item)
        else:
            prestados.append(item)

    return {"contratados": contratados, "prestados": prestados}


@router.post("/transacciones/servicio")
async def pagar_servicio(payload: ServicioTransaccion):
    comprador = await _obtener_usuario(payload.comprador_id)
    proveedor = await _obtener_usuario(payload.proveedor_id)

    if payload.comprador_id == payload.proveedor_id:
        raise HTTPException(
            status_code=400, detail="No puedes pagar un servicio a tu propio usuario"
        )

    saldo_actual = float(comprador.get("saldo_creditos", 0.0))
    if saldo_actual < payload.monto:
        raise HTTPException(status_code=400, detail="Saldo insuficiente")

    transaccion_doc = {
        "id_emisor": payload.comprador_id,
        "id_receptor": payload.proveedor_id,
        "monto": payload.monto,
        "tipo": "servicio",
        "id_servicio": payload.servicio_id,
        "servicio_titulo": payload.descripcion,
        "justificacion": payload.descripcion or "Pago de servicio",
        "estado": payload.estado or "completed",
        "fecha": datetime.utcnow(),
    }

    async with await client.start_session() as session:
        async with session.start_transaction():
            await usuarios_collection.update_one(
                {"_id": ObjectId(payload.comprador_id)},
                {"$inc": {"saldo_creditos": -payload.monto}},
                session=session,
            )
            await usuarios_collection.update_one(
                {"_id": ObjectId(payload.proveedor_id)},
                {"$inc": {"saldo_creditos": payload.monto}},
                session=session,
            )
            result = await transacciones_collection.insert_one(
                transaccion_doc, session=session
            )
            transaccion_doc["_id"] = str(result.inserted_id)

    return {
        "id": transaccion_doc["_id"],
        "nuevo_saldo": saldo_actual - payload.monto,
        "transaccion": transaccion_doc,
    }


@router.post("/transacciones/transferir")
async def transferir_creditos(datos: Transaccion, user_id: str = Depends(get_current_user)):
    if user_id != datos.id_emisor:
        raise HTTPException(status_code=403, detail="No puedes transferir como otro usuario")

    emisor = await _obtener_usuario(datos.id_emisor)
    receptor = await _obtener_usuario(datos.id_receptor)

    saldo_emisor = float(emisor.get("saldo_creditos", 0.0))
    if saldo_emisor < datos.monto:
        raise HTTPException(status_code=400, detail="Saldo insuficiente")

    transaccion_doc = {
        "id_emisor": datos.id_emisor,
        "id_receptor": datos.id_receptor,
        "monto": datos.monto,
        "tipo": datos.tipo or "transferencia",
        "estado": datos.estado or "completed",
        "justificacion": datos.justificacion,
        "fecha": datos.fecha or datetime.utcnow(),
    }

    async with await client.start_session() as session:
        async with session.start_transaction():
            await usuarios_collection.update_one(
                {"_id": ObjectId(datos.id_emisor)},
                {"$inc": {"saldo_creditos": -datos.monto}},
                session=session,
            )
            await usuarios_collection.update_one(
                {"_id": ObjectId(datos.id_receptor)},
                {"$inc": {"saldo_creditos": datos.monto}},
                session=session,
            )
            result = await transacciones_collection.insert_one(
                transaccion_doc, session=session
            )
            transaccion_doc["_id"] = str(result.inserted_id)

    return transaccion_doc


@router.post("/admin/asignar_creditos")
async def asignar_creditos(datos: Transaccion, user_id: str = Depends(get_current_user)):
    admin = await _obtener_usuario(user_id)
    if admin.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Acceso restringido a administradores")

    if not datos.id_receptor:
        raise HTTPException(status_code=400, detail="Falta receptor")

    await _obtener_usuario(datos.id_receptor)  # valida existencia

    nueva_transaccion = {
        "id_emisor": "admin",
        "id_receptor": datos.id_receptor,
        "monto": datos.monto,
        "tipo": "asignacion",
        "estado": datos.estado or "completed",
        "fecha": datetime.utcnow(),
        "justificacion": datos.justificacion or "Asignación de créditos",
    }

    async with await client.start_session() as session:
        async with session.start_transaction():
            await usuarios_collection.update_one(
                {"_id": ObjectId(datos.id_receptor)},
                {"$inc": {"saldo_creditos": datos.monto}},
                session=session,
            )
            result = await transacciones_collection.insert_one(
                nueva_transaccion, session=session
            )

    return {
        "mensaje": f"Se asignaron {datos.monto} créditos al usuario {datos.id_receptor}",
        "transaccion": {**nueva_transaccion, "_id": str(result.inserted_id)},
    }
