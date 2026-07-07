import json
import time

from automacoes.automacao_99 import Automacao99
from persistencia.repositorio_arquivo import RepositorioArquivo
from persistencia.repositorio_banco import RepositorioBanco


def carregar_config(caminho="config.json"):
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def criar_automacao(config):
    if config['app'] == '99':
        return Automacao99(config['appium'])
    raise ValueError(f"App não suportado: {config['app']}")


def criar_repositorio(config):
    tipo = config['persistencia']['tipo']
    caminho = config['persistencia']['caminho']
    if tipo == 'arquivo':
        return RepositorioArquivo(caminho, config['persistencia'].get('formato', 'markdown'))
    if tipo == 'banco':
        return RepositorioBanco(caminho)
    raise ValueError(f"Persistência não suportada: {tipo}")


def main():
    config = carregar_config()
    automacao = criar_automacao(config)
    repositorio = criar_repositorio(config)

    repositorio.inicializar()
    automacao.conectar()
    device_model = automacao.device_model

    try:
        for rodada in range(1, config['limite_consultas'] + 1):
            agora = time.strftime('%H:%M:%S')
            print(f"\n[{agora}] Iniciando rodada {rodada}/{config['limite_consultas']}...")

            corridas = automacao.coletar_precos(config['destino'])
            repositorio.salvar(corridas, rodada, device_model)

            automacao.voltar_tela_inicial()

            if rodada < config['limite_consultas']:
                print(f"Aguardando {config['intervalo_segundos']} segundos...")
                time.sleep(config['intervalo_segundos'])
    except KeyboardInterrupt:
        print("\nColeta interrompida.")
    finally:
        automacao.desconectar()
        if hasattr(repositorio, 'fechar'):
            repositorio.fechar()


if __name__ == "__main__":
    main()
