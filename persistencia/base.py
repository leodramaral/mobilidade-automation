from abc import ABC, abstractmethod
from typing import List

from modelos.corrida import Corrida


class BaseRepositorio(ABC):
    @abstractmethod
    def inicializar(self) -> None: ...

    @abstractmethod
    def salvar(self, corridas: List[Corrida], rodada: int) -> None: ...
