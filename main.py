import json

from coletor import Coletor


def carregar_config(caminho="config.json"):
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def main():
    config = carregar_config()
    coletor = Coletor(config, status_callback=print)
    coletor.executar()


if __name__ == "__main__":
    main()
