import copy
import json
import os
import sys
from pathlib import Path

import structlog

logger = structlog.get_logger("cli")

CAMINHO_CONFIG = Path(__file__).resolve().parent.parent / "config.json"
CAMINHO_AGENDAMENTOS = Path(__file__).resolve().parent.parent / "agendamentos.json"
CAMPOS_OBRIGATORIOS = ["appium", "persistencia"]


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


def carregar_config_base() -> dict:
    config = carregar_json(CAMINHO_CONFIG, "config.json")
    campos_faltando = [c for c in CAMPOS_OBRIGATORIOS if c not in config]
    if campos_faltando:
        logger.critical("Campos obrigatorios faltando no config.json", campos=campos_faltando)
        sys.exit(1)
    api_key = os.environ.get("OPENWEATHER_API_KEY", "")
    if not api_key or api_key == "SUA_CHAVE_AQUI":
        logger.warning("Chave da API OpenWeather nao configurada. Defina OPENWEATHER_API_KEY no .env")
    return config


def carregar_agendamentos() -> list[dict]:
    data = carregar_json(CAMINHO_AGENDAMENTOS, "agendamentos.json")
    agendamentos = data.get("agendamentos", [])
    if not agendamentos:
        logger.critical("Nenhum agendamento encontrado em agendamentos.json")
        sys.exit(1)
    return agendamentos


def merge_config(base: dict, override: dict) -> dict:
    config = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(config.get(k), dict):
            config[k].update(v)
        else:
            config[k] = v
    return config


def e_sequencial(agendamento: dict) -> bool:
    return agendamento.get("quando", "now") == "now"
