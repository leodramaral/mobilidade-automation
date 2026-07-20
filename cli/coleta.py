import sys

import structlog
from coletor import Coletor
from cli.comum import carregar_config_base, carregar_agendamentos, merge_config, e_sequencial
from cli.banner import mostrar as mostrar_banner
from logging_config import configurar_logging

logger = structlog.get_logger("cli.coleta")


def iniciar() -> None:
    config_base = carregar_config_base()
    agendamentos = carregar_agendamentos()

    sequenciais = [a for a in agendamentos if e_sequencial(a)]
    programados = [a for a in agendamentos if not e_sequencial(a)]

    nivel_log = config_base.get("logging", {}).get("level", "INFO")
    configurar_logging(nivel=nivel_log)

    if not sequenciais:
        logger.warning("Nenhum agendamento com 'quando: now' encontrado")
        return

    if programados:
        logger.info("Agendamentos programados ignorados", quantidade=len(programados),
                    dica="Use 'python main.py agendador iniciar' para agendamentos programados")

    logger.info("Iniciando coleta imediata", total=len(sequenciais))

    for idx, agendamento in enumerate(sequenciais):
        config = merge_config(config_base, agendamento.get("config_override", {}))
        origem = agendamento.get("config_override", {}).get("origem", "?")
        destino = agendamento.get("config_override", {}).get("destino", "?")
        logger.info("Coleta sequencial", indice=idx + 1, total=len(sequenciais),
                    origem=origem, destino=destino)
        coletor = Coletor(config)
        coletor.executar()

    logger.info("Coleta finalizada")
