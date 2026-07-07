import json
import time

from automacoes.automacao_99 import Automacao99
from persistencia.repositorio_arquivo import RepositorioArquivo


def carregar_config(caminho="config.json"):
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def criar_automacao(config):
    if config['app'] == '99':
        return Automacao99(config['appium'])
    raise ValueError(f"App não suportado: {config['app']}")


def criar_repositorio(config):
    if config['persistencia']['tipo'] == 'arquivo':
        return RepositorioArquivo(
            config['persistencia']['caminho'],
            config['persistencia'].get('formato', 'markdown')
        )
    raise ValueError(f"Persistência não suportada: {config['persistencia']['tipo']}")


def main():
    config = carregar_config()
    automacao = criar_automacao(config)
    repositorio = criar_repositorio(config)

    repositorio.inicializar()
    automacao.conectar()

    try:
        for rodada in range(1, config['limite_consultas'] + 1):
            agora = time.strftime('%H:%M:%S')
            print(f"\n[{agora}] Iniciando rodada {rodada}/{config['limite_consultas']}...")

            corridas = automacao.coletar_precos(config['destino'])
            repositorio.salvar(corridas, rodada)

            automacao.voltar_tela_inicial()

            if rodada < config['limite_consultas']:
                print(f"Aguardando {config['intervalo_segundos']} segundos...")
                time.sleep(config['intervalo_segundos'])
    except KeyboardInterrupt:
        print("\nColeta interrompida.")
    finally:
        automacao.desconectar()


if __name__ == "__main__":
    main()
