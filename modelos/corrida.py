from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass
class Corrida:
    app: str
    categoria: str
    preco: float
    estimativa: int
    origem: str
    destino: str
    timestamp: datetime
    preco_texto: str = ""
    estimativa_texto: str = ""

    def para_dict(self) -> dict:
        return {
            "app": self.app,
            "categoria": self.categoria,
            "preco": self.preco,
            "estimativa_min": self.estimativa,
            "origem": self.origem,
            "destino": self.destino,
            "preco_texto": self.preco_texto,
            "estimativa_texto": self.estimativa_texto,
        }


@dataclass
class Snapshot:
    id: int
    timestamp: datetime
    device_model: str
    payload: List[dict]
