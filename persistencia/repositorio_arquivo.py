from datetime import datetime
from typing import List

from persistencia.base import BaseRepositorio
from modelos.corrida import Corrida


class RepositorioArquivo(BaseRepositorio):
    def __init__(self, caminho: str, formato: str = "markdown"):
        self.caminho = caminho
        self.formato = formato

    def inicializar(self) -> None:
        with open(self.caminho, "w", encoding="utf-8") as f:
            f.write(f"# Relatório de Monitoramento\n")
            f.write(
                f"Início da coleta: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
            )

    def salvar(self, corridas: List[Corrida], rodada: int) -> None:
        agora = datetime.now().strftime('%H:%M:%S')
        with open(self.caminho, "a", encoding="utf-8") as f:
            f.write(f"### Consulta {rodada} - {agora}\n")
            f.write("| Categoria | Preco (R$) | Estimativa |\n")
            f.write("| :--- | :--- | :--- |\n")
            for c in corridas:
                f.write(f"| {c.categoria} | {c.preco} | {c.estimativa} |\n")
                print(f"  -> {c.categoria}: R${c.preco} ({c.estimativa})")
            f.write("\n---\n\n")
