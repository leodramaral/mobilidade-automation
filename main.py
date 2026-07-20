import copy
import json
import os
import sys

from dotenv import load_dotenv
from pathlib import Path

import structlog
from coletor import Coletor
from logging_config import configurar_logging


CAMINHO_CONFIG = Path(__file__).resolve().parent / "config.json"
CAMINHO_AGENDAMENTOS = Path(__file__).resolve().parent / "agendamentos.json"
CAMPOS_OBRIGATORIOS = ["appium", "persistencia"]

logger = structlog.get_logger("main")


def carregar_json(caminho: Path, nome: str) -> dict:
    if not caminho.exists():
        logger.critical("Arquivo %s nao encontrado", nome, caminho=str(caminho))
        sys.exit(1)
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.critical("Erro ao ler %s: JSON invalido", nome, erro=str(e))
        sys.exit(1)


def validar_config_base(config: dict) -> None:
    campos_faltando = [c for c in CAMPOS_OBRIGATORIOS if c not in config]
    if campos_faltando:
        logger.critical("Campos obrigatorios faltando no config.json", campos=campos_faltando)
        sys.exit(1)

    api_key = os.environ.get("OPENWEATHER_API_KEY", "")
    if not api_key or api_key == "SUA_CHAVE_AQUI":
        logger.warning("Chave da API OpenWeather nao configurada. Defina OPENWEATHER_API_KEY no .env")


def e_sequencial(agendamento: dict) -> bool:
    quando = agendamento.get("quando", "now")
    return quando == "now"


def merge_config(base: dict, override: dict) -> dict:
    config = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(config.get(k), dict):
            config[k].update(v)
        else:
            config[k] = v
    return config


def main():
    load_dotenv()

    config_base = carregar_json(CAMINHO_CONFIG, "config.json")
    validar_config_base(config_base)

    agendamentos_data = carregar_json(CAMINHO_AGENDAMENTOS, "agendamentos.json")
    agendamentos = agendamentos_data.get("agendamentos", [])

    if not agendamentos:
        logger.critical("Nenhum agendamento encontrado em agendamentos.json")
        sys.exit(1)

    sequenciais = [a for a in agendamentos if e_sequencial(a)]
    programados = [a for a in agendamentos if not e_sequencial(a)]

    nivel_log = config_base.get("logging", {}).get("level", "INFO")
    configurar_logging(nivel=nivel_log)

    logger.info(
        "Agendamentos carregados",
        sequenciais=len(sequenciais),
        programados=len(programados),
    )

    for idx, agendamento in enumerate(sequenciais):
        config = merge_config(config_base, agendamento.get("config_override", {}))
        origem = agendamento.get("config_override", {}).get("origem", "?")
        destino = agendamento.get("config_override", {}).get("destino", "?")
        logger.info(
            "Iniciando coleta sequencial",
            indice=idx + 1,
            total=len(sequenciais),
            origem=origem,
            destino=destino,
        )
        coletor = Coletor(config)
        coletor.executar()

    if programados:
        logger.info(
            "Agendamentos programados devem ser executados via run_agendador.py",
            quantidade=len(programados),
        )

    logger.info("Todas as coletas sequenciais concluidas")


if __name__ == "__main__":
    main()
