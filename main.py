import json
import sys
from pathlib import Path

from coletor import Coletor


CAMINHO_CONFIG = Path(__file__).resolve().parent / "config.json"
CAMINHO_EXEMPLO = Path(__file__).resolve().parent / "config.json.example"
CAMPOS_OBRIGATORIOS = ["appium", "persistencia", "limite_consultas", "intervalo_segundos"]


def carregar_config():
    if not CAMINHO_CONFIG.exists():
        print(f"Arquivo config.json não encontrado em {CAMINHO_CONFIG}")
        print(f"Copie o exemplo: cp config.json.example config.json")
        sys.exit(1)

    try:
        with open(CAMINHO_CONFIG, encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Erro ao ler config.json: JSON inválido - {e}")
        sys.exit(1)

    campos_faltando = [c for c in CAMPOS_OBRIGATORIOS if c not in config]
    if campos_faltando:
        print(f"Campos obrigatórios faltando no config.json: {', '.join(campos_faltando)}")
        sys.exit(1)

    config_clima = config.get("openweather", {})
    api_key = config_clima.get("api_key", "")
    lat = config_clima.get("lat")
    lon = config_clima.get("lon")
    if not api_key or api_key == "SUA_CHAVE_AQUI":
        print("Aviso: Chave da API OpenWeather não configurada. Coleta de clima será desabilitada.")
    elif lat is None or lon is None:
        print("Aviso: Coordenadas (lat/lon) não configuradas no openweather. Coleta de clima será desabilitada.")

    return config


def main():
    config = carregar_config()
    coletor = Coletor(config, status_callback=print)
    coletor.executar()


if __name__ == "__main__":
    main()
