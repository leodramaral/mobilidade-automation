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


def _escolher_cidade(cidades):
    print("\n📌 [bold]Cidades com 6 locais cadastrados:[/bold]")
    for i, (cidade, uf) in enumerate(cidades, 1):
        print(f"   [cyan]{i}[/cyan]. {cidade}/{uf}")
    print()

    choices = [str(i) for i in range(1, len(cidades) + 1)]
    escolha = Prompt.ask("Escolha o número da cidade", choices=choices)
    idx = int(escolha) - 1
    return cidades[idx]


def _escolher_modo():
    print("\n[bold]Modo de geração:[/bold]")
    print("   [cyan]1[/cyan]. Sequencial — execução imediata")
    
    presets = list(PRESETS_PROGRAMADOS.keys())
    for idx, key in enumerate(presets, 2):
        desc = PRESETS_PROGRAMADOS[key]["descricao"]
        print(f"   [cyan]{idx}[/cyan]. Programado — {desc}")
        
    choices = [str(i) for i in range(1, len(presets) + 2)]
    escolha = Prompt.ask("Escolha o modo", choices=choices)
    
    if escolha == "1":
        return ("sequencial", None)
    else:
        preset_idx = int(escolha) - 2
        preset_nome = presets[preset_idx]
        return ("programado", preset_nome)


def _escolher_sentido():
    print("\n[bold]Sentido dos trajetos:[/bold]")
    print("   [cyan]1[/cyan]. todos (18 rotas)")
    print("   [cyan]2[/cyan]. só sentido centro (9 rotas, E/M→C)")
    print("   [cyan]3[/cyan]. só sentido bairro (9 rotas, C→E/M)")
    
    escolha = Prompt.ask("Escolha o sentido", choices=["1", "2", "3"])
    if escolha == "1":
        return ["centro", "bairro"]
    if escolha == "2":
        return ["centro"]
    return ["bairro"]


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
