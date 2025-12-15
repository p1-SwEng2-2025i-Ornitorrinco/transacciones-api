from pydantic import BaseModel
from typing import Optional

class UsuarioBase(BaseModel):
    id: str
    nombres: str
    apellidos: str

class UsuarioMonedaVirtual(BaseModel):
    saldo: float = 0.0
    ultima_actualizacion: Optional[str] = None

class Usuario(UsuarioBase):  # Hereda de tu modelo existente
    moneda_virtual: Optional[UsuarioMonedaVirtual] = None

