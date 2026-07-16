import os
import time
from typing import Optional

import structlog
from automacoes.automacao_99 import Automacao99
from automacoes.automacao_uber import AutomacaoUber
from persistencia.repositorio_banco import RepositorioBanco
from servicos.clima import ClimaServico

logger = structlog.get_logger("coletor")
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
    def __init__(self, config: dict):
        self.config = config
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
        api_key = os.environ.get("OPENWEATHER_API_KEY", "")
        if lat is not None and lon is not None and api_key and api_key != 'SUA_CHAVE_AQUI':
            assert repositorio.conn is not None
            clima_servico = ClimaServico(repositorio.conn)

        device_model = None

        try:
            for rodada in range(1, self.config['limite_consultas'] + 1):
                if self._parar:
                    break

                self.rodada_atual = rodada
                logger.info("Iniciando rodada", rodada=rodada, total=self.total_rodadas)

                temperatura = None
                condicao_tempo = ''
                if clima_servico is not None:
                    temperatura, condicao_tempo = clima_servico.consultar(lat, lon, api_key)
                    logger.info("Clima consultado", temperatura=temperatura, condicao=condicao_tempo)

                # Rastrear resultados por app para o resumo
                resultados_rodada = {}

                for app in apps_ativos:
                    logger.info("Iniciando coleta", app=app)
                    automacao = None
                    try:
                        automacao = criar_automacao(app, self.config)
                        automacao.conectar()
                        if device_model is None:
                            device_model = automacao.device_model
                            logger.info("Dispositivo conectado", device_model=device_model)

                        logger.info("Coletando preços", app=app)
                        corridas = automacao.coletar_precos(
                            self.config['destino'],
                            origem=self.config.get('origem', ''),
                        )

                        if not corridas:
                            logger.warning("Nenhum preço capturado", app=app)
                            resultados_rodada[app] = 0
                        else:
                            categorias = [c.categoria for c in corridas]
                            logger.info(
                                "Preços capturados",
                                app=app,
                                quantidade=len(corridas),
                                categorias=categorias
                            )
                            resultados_rodada[app] = len(corridas)

                        capturar_metricas = self.config["appium"][app].get("capturar_metricas", False)
                        if capturar_metricas:
                            logger.info("Capturando métricas detalhadas", app=app)
                            try:
                                corridas = automacao.coletar_metricas(corridas)
                            except Exception as e:
                                logger.warning(
                                    "Erro ao capturar métricas, salvando preços sem métricas",
                                    app=app,
                                    erro=str(e),
                                )

                        repositorio.salvar(corridas, rodada, device_model, temperatura, condicao_tempo)
                        logger.info("Dados salvos", app=app)
                    except Exception as e:
                        resultados_rodada[app] = 0
                        logger.error(
                            "Erro na coleta",
                            app=app,
                            erro_tipo=type(e).__name__,
                            erro=str(e),
                            exc_info=True
                        )
                    finally:
                        if automacao is not None:
                            try:
                                automacao.desconectar()
                            except Exception:
                                logger.debug("Falha ao desconectar", app=app)

                # Resumo da rodada
                resumo_parts = []
                for app, qtd in resultados_rodada.items():
                    resumo_parts.append(f"{app}={qtd}preco(s)")
                resumo = "  ".join(resumo_parts)
                logger.info("Rodada concluída", rodada=rodada, resumo=resumo)

                if rodada < self.config['limite_consultas'] and not self._parar:
                    intervalo = self.config['intervalo_segundos']
                    logger.info("Aguardando próxima rodada", segundos=intervalo)
                    time.sleep(intervalo)
        except Exception as e:
            logger.error(
                "Erro geral na coleta",
                erro_tipo=type(e).__name__,
                erro=str(e),
                exc_info=True
            )
        finally:
            if hasattr(repositorio, 'fechar'):
                repositorio.fechar()
            logger.info("Coleta finalizada")
