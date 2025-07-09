from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING
import os

MONGO_URI = "mongodb://localhost:27017"
DATABASE_NAME = "intercambio_servicios"  # Misma DB para mantener relaciones

client = AsyncIOMotorClient(MONGO_URI)
db = client[DATABASE_NAME]

# Colecciones
usuarios_collection = db["usuarios"]
transacciones_collection = db["transacciones_moneda"]  # Nueva colección

# Índices (ejecutar una vez)
async def create_indexes():
    await transacciones_collection.create_index([("id_emisor", ASCENDING)])
    await transacciones_collection.create_index([("id_receptor", ASCENDING)])
    await transacciones_collection.create_index([("fecha", ASCENDING)])
    print("Índices creados")