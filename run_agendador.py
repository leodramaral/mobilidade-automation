import json
from pathlib import Path

from agendador.servico import AgendadorService

CAMINHO_CONFIG = Path(__file__).resolve().parent / "config.json"
CAMINHO_AGENDAMENTOS = Path(__file__).resolve().parent / "agendamentos.json"


def main():
    config = json.loads(CAMINHO_CONFIG.read_text(encoding="utf-8"))
    agendamentos_data = json.loads(CAMINHO_AGENDAMENTOS.read_text(encoding="utf-8"))
    timezone = agendamentos_data.get("timezone", "America/Manaus")
    servico = AgendadorService(config, agendamentos_data["agendamentos"], timezone)
    servico.iniciar()


if __name__ == "__main__":
    main()
