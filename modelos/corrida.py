from dataclasses import dataclass
from datetime import datetime


@dataclass
class Corrida:
    app: str
    categoria: str
    preco: float
    estimativa: str
    destino: str
    timestamp: datetime
