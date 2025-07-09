from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class Transaccion(BaseModel):
    id_servicio: Optional[str] = None
    id_emisor: Optional[str] = None
    id_receptor: Optional[str] = None
    monto: int
    fecha: datetime = Field(default_factory=datetime.utcnow)
    tipo: str  # "transferencia" o "asignacion"
    justificacion: Optional[str] = None

