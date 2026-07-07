import time
from typing import Callable, Optional

from automacoes.automacao_99 import Automacao99
from persistencia.repositorio_banco import RepositorioBanco


def criar_automacao(config):
    if config['app'] == '99':
        return Automacao99(config['appium'])
    raise ValueError(f"App não suportado: {config['app']}")


def criar_repositorio(config):
    caminho = config['persistencia']['caminho']
    return RepositorioBanco(caminho)


class Coletor:
    def __init__(self, config: dict, status_callback: Optional[Callable[[str], None]] = None):
        self.config = config
        self.status_callback = status_callback or print
        self._parar = False
        self.rodada_atual = 0
        self.total_rodadas = config.get('limite_consultas', 1)

    def parar(self):
        self._parar = True

    def executar(self):
        automacao = criar_automacao(self.config)
        repositorio = criar_repositorio(self.config)

        repositorio.inicializar()
        self.status_callback("Conectando ao Appium...")
        automacao.conectar()
        device_model = automacao.device_model
        self.status_callback(f"Conectado: {device_model}")

        try:
            for rodada in range(1, self.config['limite_consultas'] + 1):
                if self._parar:
                    self.status_callback("Coleta interrompida pelo usuário.")
                    break

                self.rodada_atual = rodada
                agora = time.strftime('%H:%M:%S')
                self.status_callback(f"[{agora}] Rodada {rodada}/{self.total_rodadas}...")

                corridas = automacao.coletar_precos(self.config['destino'])
                repositorio.salvar(corridas, rodada, device_model)

                self.status_callback(f"Rodada {rodada} concluída: {len(corridas)} corridas coletadas.")

                automacao.voltar_tela_inicial()

                if rodada < self.config['limite_consultas'] and not self._parar:
                    self.status_callback(f"Aguardando {self.config['intervalo_segundos']}s...")
                    time.sleep(self.config['intervalo_segundos'])
        except Exception as e:
            self.status_callback(f"Erro na coleta: {e}")
        finally:
            automacao.desconectar()
            if hasattr(repositorio, 'fechar'):
                repositorio.fechar()
            self.status_callback("Coleta finalizada.")
