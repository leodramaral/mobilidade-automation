import time
from typing import Callable, Optional

from automacoes.automacao_99 import Automacao99
from automacoes.automacao_uber import AutomacaoUber
from persistencia.repositorio_banco import RepositorioBanco
from servicos.clima import ClimaServico


def listar_apps_ativos(config: dict) -> list[str]:
    return [
        app for app, cfg in config['appium'].items()
        if isinstance(cfg, dict) and cfg.get('active', False)
    ]


def criar_automacao(app: str, config: dict):
    config_appium = config['appium'][app].copy()
    config_appium['server'] = config['appium']['server']

    if app == '99':
        return Automacao99(config_appium)
    if app == 'uber':
        return AutomacaoUber(config_appium)
    raise ValueError(f"App não suportado: {app}")


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
        apps_ativos = listar_apps_ativos(self.config)
        repositorio = criar_repositorio(self.config)
        repositorio.inicializar()

        clima_servico = None
        config_clima = self.config.get('openweather', {})
        lat = config_clima.get('lat')
        lon = config_clima.get('lon')
        api_key = config_clima.get('api_key', '')
        if lat is not None and lon is not None and api_key and api_key != 'SUA_CHAVE_AQUI':
            assert repositorio.conn is not None
            clima_servico = ClimaServico(repositorio.conn)

        device_model = None

        try:
            for rodada in range(1, self.config['limite_consultas'] + 1):
                if self._parar:
                    break

                self.rodada_atual = rodada
                agora = time.strftime('%H:%M:%S')
                self.status_callback(f"[{agora}] Rodada {rodada}/{self.total_rodadas}...")

                condicao_tempo = ''
                if clima_servico is not None:
                    condicao_tempo = clima_servico.consultar(lat, lon, api_key)
                    self.status_callback(f"Clima: {condicao_tempo}")

                for app in apps_ativos:
                    automacao = criar_automacao(app, self.config)
                    automacao.conectar()
                    if device_model is None:
                        device_model = automacao.device_model
                        self.status_callback(f"Conectado: {device_model}")

                    self.status_callback(f"Coletando preços do {app.upper()}...")
                    corridas = automacao.coletar_precos(
                        self.config['destino'],
                        origem=self.config.get('origem', ''),
                    )
                    repositorio.salvar(corridas, rodada, device_model, condicao_tempo)
                    automacao.desconectar()

                self.status_callback(f"Rodada {rodada} concluída.")

                if rodada < self.config['limite_consultas'] and not self._parar:
                    self.status_callback(f"Aguardando {self.config['intervalo_segundos']}s...")
                    time.sleep(self.config['intervalo_segundos'])
        except Exception as e:
            self.status_callback(f"Erro na coleta: {e}")
        finally:
            if hasattr(repositorio, 'fechar'):
                repositorio.fechar()
            self.status_callback("Coleta finalizada.")
