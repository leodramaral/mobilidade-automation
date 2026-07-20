import json
import os
import sys

from dotenv import load_dotenv
from pathlib import Path

import structlog
from coletor import Coletor
from logging_config import configurar_logging


CAMINHO_CONFIG = Path(__file__).resolve().parent / "config.json"
CAMINHO_EXEMPLO = Path(__file__).resolve().parent / "config.json.example"
CAMPOS_OBRIGATORIOS = ["appium", "persistencia", "limite_consultas"]

logger = structlog.get_logger("main")


def carregar_config():
    load_dotenv()
    if not CAMINHO_CONFIG.exists():
        logger.critical("Arquivo config.json não encontrado", caminho=str(CAMINHO_CONFIG))
        logger.info("Copie o exemplo: cp config.json.example config.json")
        sys.exit(1)

    try:
        with open(CAMINHO_CONFIG, encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        logger.critical("Erro ao ler config.json: JSON inválido", erro=str(e))
        sys.exit(1)

    campos_faltando = [c for c in CAMPOS_OBRIGATORIOS if c not in config]
    if campos_faltando:
        logger.critical("Campos obrigatórios faltando no config.json", campos=campos_faltando)
        sys.exit(1)

    config_clima = config.get("openweather", {})
    lat = config_clima.get("lat")
    lon = config_clima.get("lon")
    api_key = os.environ.get("OPENWEATHER_API_KEY", "")
    if not api_key or api_key == "SUA_CHAVE_AQUI":
        logger.warning("Chave da API OpenWeather não configurada. Defina OPENWEATHER_API_KEY no .env")
    elif lat is None or lon is None:
        logger.warning("Coordenadas (lat/lon) não configuradas no openweather. Coleta de clima será desabilitada.")

    return config


def main():
    config = carregar_config()
    nivel_log = config.get("logging", {}).get("level", "INFO")
    configurar_logging(nivel=nivel_log)
    
    coletor = Coletor(config)
    coletor.executar()


if __name__ == "__main__":
    main()
