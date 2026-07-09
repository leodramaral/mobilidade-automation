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
    preco_label: str = ""
    estimativa_label: str = ""

    def para_dict(self) -> dict:
        return {
            "categoria": self.categoria,
            "preco": self.preco,
            "estimativa_min": self.estimativa,
            "preco_label": self.preco_label,
            "estimativa_label": self.estimativa_label,
        }


@dataclass
class Snapshot:
    id: int
    timestamp: datetime
    device_model: str
    app: str
    origem: str
    destino: str
    condicao_tempo: str
    payload: List[dict]
