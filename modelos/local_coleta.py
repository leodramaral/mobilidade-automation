from dataclasses import dataclass


@dataclass
class LocalColeta:
    codigo: str  # C1, C2, E1, E2, M1, M2
    endereco: str
    cidade: str
    uf: str
    lat: float
    lon: float
    tipo: str  # 'central', 'extremo', 'bairro'

    def __post_init__(self):
        self.lat = round(self.lat, 7)
        self.lon = round(self.lon, 7)
