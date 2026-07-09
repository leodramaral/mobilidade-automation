from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class Corrida:
    app: str
    categoria: str
    preco: float
    estimativa: int
    origem: str
    destino: str
    timestamp: datetime
    preco_base: Optional[float] = None
    preco_minimo: Optional[float] = None
    adicional_por_minuto: Optional[float] = None
    adicional_por_km: Optional[float] = None
    custo_fixo: Optional[float] = None
    adicional_espera: Optional[float] = None

    def para_dict(self) -> dict:
        d = {
            "categoria": self.categoria,
            "preco": self.preco,
            "estimativa_min": self.estimativa,
        }
        if self.preco_base is not None:
            d["preco_base"] = self.preco_base
        if self.preco_minimo is not None:
            d["preco_minimo"] = self.preco_minimo
        if self.adicional_por_minuto is not None:
            d["adicional_por_minuto"] = self.adicional_por_minuto
        if self.adicional_por_km is not None:
            d["adicional_por_km"] = self.adicional_por_km
        if self.custo_fixo is not None:
            d["custo_fixo"] = self.custo_fixo
        if self.adicional_espera is not None:
            d["adicional_espera"] = self.adicional_espera
        return d


@dataclass
class Snapshot:
    id: int
    timestamp: datetime
    device_model: str
    app: str
    origem: str
    destino: str
    temperatura: Optional[float]
    condicao_tempo: str
    payload: List[dict]
