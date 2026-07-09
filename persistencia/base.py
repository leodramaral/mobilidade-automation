from abc import ABC, abstractmethod
from typing import List, Optional

from modelos.corrida import Corrida


class BaseRepositorio(ABC):
    @abstractmethod
    def inicializar(self) -> None: ...

    @abstractmethod
    def salvar(self, corridas: List[Corrida], rodada: int, device_model: str = '', temperatura: Optional[float] = None, condicao_tempo: str = '') -> None: ...
