import json
from pathlib import Path

from dotenv import load_dotenv
import structlog
from agendador.servico import AgendadorService
from logging_config import configurar_logging

CAMINHO_CONFIG = Path(__file__).resolve().parent / "config.json"
CAMINHO_AGENDAMENTOS = Path(__file__).resolve().parent / "agendamentos.json"

logger = structlog.get_logger("run_agendador")


def main():
    load_dotenv()
    config = json.loads(CAMINHO_CONFIG.read_text(encoding="utf-8"))
    nivel_log = config.get("logging", {}).get("level", "INFO")
    configurar_logging(nivel=nivel_log)
    
    agendamentos_data = json.loads(CAMINHO_AGENDAMENTOS.read_text(encoding="utf-8"))
    servico = AgendadorService(config, agendamentos_data["agendamentos"])
    servico.iniciar()


if __name__ == "__main__":
    main()
