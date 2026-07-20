import structlog
from agendador.servico import AgendadorService
from cli.comum import carregar_config_base, carregar_agendamentos
from logging_config import configurar_logging

logger = structlog.get_logger("cli.agendador")


def iniciar() -> None:
    config_base = carregar_config_base()
    agendamentos = carregar_agendamentos()

    programados = [a for a in agendamentos if a.get("quando", "now") != "now"]

    if not programados:
        logger.warning("Nenhum agendamento programado encontrado (apenas 'quando: now' presente)")
        logger.info("Use 'python main.py coleta iniciar' para coleta imediata")
        return

    nivel_log = config_base.get("logging", {}).get("level", "INFO")
    configurar_logging(nivel=nivel_log)

    servico = AgendadorService(config_base, programados)
    servico.iniciar()
