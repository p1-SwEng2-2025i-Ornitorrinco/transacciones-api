from pydantic import BaseModel, Field
from typing import Literal

class AsignacionCreditoRequest(BaseModel):
    usuario_id: str
    monto: float = Field(gt=0, description="Cantidad de créditos a asignar")
    justificacion: str = Field(..., min_length=10)