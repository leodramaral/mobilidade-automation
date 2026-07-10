from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class MetricasCorrida:
    preco_base: Optional[float] = None
    preco_minimo: Optional[float] = None
    adicional_por_minuto: Optional[float] = None
    adicional_por_km: Optional[float] = None
    custo_fixo: Optional[float] = None


@dataclass
class Corrida:
    app: str
    categoria: str
    preco: float
    estimativa: int
    origem: str
    destino: str
    timestamp: datetime
    metricas: Optional[MetricasCorrida] = None

    def para_dict(self) -> dict:
        d = {
            "categoria": self.categoria,
            "preco": self.preco,
            "estimativa_min": self.estimativa,
        }
        if self.metricas:
            d["metricas"] = {
                "preco_base": self.metricas.preco_base,
                "preco_minimo": self.metricas.preco_minimo,
                "adicional_por_minuto": self.metricas.adicional_por_minuto,
                "adicional_por_km": self.metricas.adicional_por_km,
                "custo_fixo": self.metricas.custo_fixo,
            }
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
