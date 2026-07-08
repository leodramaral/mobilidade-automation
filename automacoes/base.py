from abc import ABC, abstractmethod
from typing import List

from modelos.corrida import Corrida


class BaseAutomacao(ABC):
    @abstractmethod
    def conectar(self) -> None: ...

    @abstractmethod
    def coletar_precos(self, destino: str, origem: str = "") -> List[Corrida]: ...

    @abstractmethod
    def voltar_tela_inicial(self) -> None: ...

    @abstractmethod
    def desconectar(self) -> None: ...
