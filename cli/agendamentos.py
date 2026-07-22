import json
import sys
from datetime import datetime, timedelta

from persistencia.repositorio_banco import RepositorioBanco
from rich.prompt import Prompt
from rich import print


PRESETS_PROGRAMADOS = {
    "pico": {
        "descricao": "horários de pico — 08:00 centro / 16:30 bairro",
        "momentos": [
            ("08:00", "centro"),
            ("16:30", "bairro"),
        ],
    },
}


def _direcao(sentido: str, origem, destino, C1, C2):
    """Determina origem/destino conforme o sentido do trajeto.

    sentido 'centro': saidas dos E e M rumo aos C (E/M -> C)
    sentido 'bairro': saidas dos C rumo aos E e M (C -> E/M)
    """
    pois = {C1.codigo, C2.codigo}
    if origem.codigo in pois and destino.codigo in pois:
        return (C1, C2) if sentido == "centro" else (C2, C1)
    if sentido == "centro":
        return (origem, destino)
    else:
        return (destino, origem)


def _gerar_rotas(locais):
    """Gera as 9 rotas fixas a partir dos 6 pontos."""
    pts = {l.codigo: l for l in locais}
    C1, C2 = pts["C1"], pts["C2"]
    E1, E2 = pts["E1"], pts["E2"]
    M1, M2 = pts["M1"], pts["M2"]

    return [
        (C1, C2),
        (E1, C1),
        (E2, C1),
        (E1, E2),
        (M1, C1),
        (M2, C1),
        (M1, E1),
        (M1, M2),
        (M1, E2),
    ]


def _criar_agendamento(rotas, sentido, quando, C1, C2):
    agendamentos = []
    for origem_rota, destino_rota in rotas:
        origem, destino = _direcao(sentido, origem_rota, destino_rota, C1, C2)
        agendamentos.append({
            "quando": quando,
            "config_override": {
                "origem": origem.endereco,
                "destino": destino.endereco,
                "openweather": {"lat": origem.lat, "lon": origem.lon},
            },
        })
    return agendamentos


import inquirer

def _escolher_cidade(cidades):
    opcoes = [f"{cidade}/{uf}" for cidade, uf in cidades]
    opcoes_map = {f"{cidade}/{uf}": (cidade, uf) for cidade, uf in cidades}
    
    pergunta = [
        inquirer.List(
            "cidade",
            message="Escolha a cidade para gerar agendamentos",
            choices=opcoes,
        )
    ]
    respostas = inquirer.prompt(pergunta)
    if not respostas:
        sys.exit(0)
    return opcoes_map[respostas["cidade"]]


def _escolher_modo():
    opcoes = ["Sequencial — execução imediata"]
    presets = list(PRESETS_PROGRAMADOS.keys())
    for key in presets:
        desc = PRESETS_PROGRAMADOS[key]["descricao"]
        opcoes.append(f"Programado — {desc}")
        
    pergunta = [
        inquirer.List(
            "modo",
            message="Escolha o modo de geração",
            choices=opcoes,
        )
    ]
    respostas = inquirer.prompt(pergunta)
    if not respostas:
        sys.exit(0)
        
    escolha = respostas["modo"]
    if escolha.startswith("Sequencial"):
        return ("sequencial", None)
    else:
        for key in presets:
            desc = PRESETS_PROGRAMADOS[key]["descricao"]
            if desc in escolha:
                return ("programado", key)
        return ("sequencial", None)


def _escolher_sentido():
    opcoes = {
        "todos (18 rotas)": ["centro", "bairro"],
        "só sentido centro (9 rotas, E/M→C)": ["centro"],
        "só sentido bairro (9 rotas, C→E/M)": ["bairro"]
    }
    
    pergunta = [
        inquirer.List(
            "sentido",
            message="Escolha o sentido dos trajetos",
            choices=list(opcoes.keys()),
        )
    ]
    respostas = inquirer.prompt(pergunta)
    if not respostas:
        sys.exit(0)
        
    return opcoes[respostas["sentido"]]



def gerar() -> None:
    repo = RepositorioBanco("mobilidade.db")
    repo.inicializar()
    cidades = repo.listar_cidades_completas()
    repo.fechar()

    if not cidades:
        print("❌ Nenhuma cidade com 6 locais cadastrados encontrada.")
        print("   Por favor, escolha a opção [bold]1[/bold] (Gerar localizações) no Menu Principal primeiro.")
        sys.exit(1)

    cidade, uf = _escolher_cidade(cidades) if len(cidades) > 1 else cidades[0]
    modo, preset_nome = _escolher_modo()

    repo = RepositorioBanco("mobilidade.db")
    repo.inicializar()
    locais = repo.listar_locais(cidade, uf)
    repo.fechar()

    if len(locais) != 6:
        print(f"❌ [bold red]São necessários[/bold red] 6 locais cadastrados para {cidade}/{uf}, mas há {len(locais)}.")
        print("   Por favor, escolha a opção [bold]1[/bold] (Gerar localizações) no Menu Principal primeiro.")
        sys.exit(1)

    if modo == "sequencial":
        sentidos = _escolher_sentido()
        labels = {"centro": "E/M→C", "bairro": "C→E/M"}
        sentido_str = " + ".join(labels[s] for s in sentidos)
        print(f"\n▶️  Modo [bold cyan]SEQUENCIAL[/bold cyan] — {sentido_str}")

        C1 = next(l for l in locais if l.codigo == "C1")
        C2 = next(l for l in locais if l.codigo == "C2")
        rotas = _gerar_rotas(locais)
        agendamentos = []
        for sentido in sentidos:
            agendamentos.extend(_criar_agendamento(rotas, sentido, "now", C1, C2))
    else:
        preset = PRESETS_PROGRAMADOS[preset_nome]
        print(f"\n📅 Modo PROGRAMADO — {preset['descricao']}")
        amanha = datetime.now().date() + timedelta(days=1)
        print(f"   Data: {amanha} (dia seguinte)")

        C1 = next(l for l in locais if l.codigo == "C1")
        C2 = next(l for l in locais if l.codigo == "C2")
        rotas = _gerar_rotas(locais)

        agendamentos = []
        for hora, sentido in preset["momentos"]:
            data = datetime(amanha.year, amanha.month, amanha.day)
            quando = data.strftime(f"%Y-%m-%d {hora}")
            agendamentos.extend(_criar_agendamento(rotas, sentido, quando, C1, C2))

    with open("agendamentos.json", "w", encoding="utf-8") as f:
        json.dump({"agendamentos": agendamentos}, f, ensure_ascii=False, indent=2)

    print(f"\n📋 [bold green]{len(agendamentos)} agendamentos gerados[/bold green] em [cyan]agendamentos.json[/cyan]")
    for a in agendamentos:
        o = a["config_override"]["origem"]
        d = a["config_override"]["destino"]
        print(f"   {a['quando']}  {o} → {d}")

    if modo == "sequencial":
        print(f"\n💡 [bold green]Próximo passo:[/bold green] Escolha a opção [bold]3[/bold] (Iniciar coleta (imediata)) no Menu Principal.")
    else:
        print(f"\n💡 [bold green]Próximo passo:[/bold green] Escolha a opção [bold]4[/bold] (Iniciar agendador (programado)) no Menu Principal.")
