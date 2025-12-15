from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Transaccion(BaseModel):
    """Representa una transacción genérica de créditos."""

    id_servicio: Optional[str] = None
    id_emisor: Optional[str] = None
    id_receptor: Optional[str] = None
    monto: float = Field(gt=0)
    fecha: datetime = Field(default_factory=datetime.utcnow)
    tipo: str  # "transferencia", "asignacion", "servicio"
    estado: Optional[str] = "completed"
    justificacion: Optional[str] = None


class ServicioTransaccion(BaseModel):
    """Payload específico para pagos de servicios."""

    servicio_id: str
    comprador_id: str
    proveedor_id: str
    monto: float = Field(gt=0)
    descripcion: Optional[str] = None
    estado: Optional[str] = "completed"
