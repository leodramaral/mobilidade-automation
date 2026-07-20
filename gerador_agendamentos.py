import json
import sys
from datetime import datetime, timedelta

from persistencia.repositorio_banco import RepositorioBanco


PRESETS_PROGRAMADOS = {
    "pico": {
        "descricao": "horarios de pico — 08:00 centro / 16:30 bairro",
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


def gerar_modo_sequencial(locais, sentidos):
    """Gera agendamentos sequenciais com 'quando' = 'now'.

    sentidos: lista com 'centro' e/ou 'bairro'
    """
    C1 = next(l for l in locais if l.codigo == "C1")
    C2 = next(l for l in locais if l.codigo == "C2")
    rotas = _gerar_rotas(locais)

    agendamentos = []
    for sentido in sentidos:
        agendamentos.extend(_criar_agendamento(rotas, sentido, "now", C1, C2))

    return agendamentos


def gerar_modo_programado(locais, preset):
    """Gera agendamentos programados para o dia seguinte, 9 por momento."""
    C1 = next(l for l in locais if l.codigo == "C1")
    C2 = next(l for l in locais if l.codigo == "C2")
    rotas = _gerar_rotas(locais)

    amanha = datetime.now().date() + timedelta(days=1)

    agendamentos = []
    for hora, sentido in preset["momentos"]:
        data = datetime(amanha.year, amanha.month, amanha.day)
        quando = data.strftime(f"%Y-%m-%d {hora}")
        agendamentos.extend(_criar_agendamento(rotas, sentido, quando, C1, C2))

    return agendamentos


def salvar_agendamentos(agendamentos):
    with open("agendamentos.json", "w", encoding="utf-8") as f:
        json.dump({"agendamentos": agendamentos}, f, ensure_ascii=False, indent=2)

    print(f"\n📋 {len(agendamentos)} agendamentos gerados em agendamentos.json")
    for a in agendamentos:
        o = a["config_override"]["origem"]
        d = a["config_override"]["destino"]
        print(f"   {a['quando']}  {o} → {d}")


def _escolher_cidade(cidades):
    """Exibe as cidades disponiveis e pede para o usuario escolher."""
    print("\n📌 Cidades com 6 locais cadastrados:")
    for i, (cidade, uf) in enumerate(cidades, 1):
        print(f"   {i}. {cidade}/{uf}")
    print()

    while True:
        try:
            escolha = input("Escolha o numero da cidade: ").strip()
            idx = int(escolha) - 1
            if 0 <= idx < len(cidades):
                return cidades[idx]
            print(f"⚠️  Escolha um numero entre 1 e {len(cidades)}.")
        except ValueError:
            print("⚠️  Digite um numero valido.")


def _escolher_modo():
    """Pede o modo de geracao ao usuario."""
    print("\nModo de geracao:")
    print("   1. sequencial  — execucao imediata (python main.py)")
    for nome, info in PRESETS_PROGRAMADOS.items():
        print(f"   p.{nome}  — {info['descricao']}")
    while True:
        escolha = input("Escolha (1 ou nome do preset): ").strip().lower()
        if escolha == "1":
            return ("sequencial", None)
        if escolha in PRESETS_PROGRAMADOS:
            return ("programado", escolha)
        print(f"⚠️  Opcao invalida. Digite 1 ou um dos presets: {', '.join(PRESETS_PROGRAMADOS)}.")


def _escolher_sentido():
    """Pergunta quais sentidos incluir no modo sequencial."""
    print("\nSentido dos trajetos:")
    print("   1. todos (18 rotas)")
    print("   2. so sentido centro (9 rotas)")
    print("   3. so sentido bairro (9 rotas)")
    while True:
        escolha = input("Escolha (1, 2 ou 3): ").strip()
        if escolha == "1":
            return ["centro", "bairro"]
        if escolha == "2":
            return ["centro"]
        if escolha == "3":
            return ["bairro"]
        print("⚠️  Digite 1, 2 ou 3.")


def main():
    repo = RepositorioBanco("mobilidade.db")
    repo.inicializar()
    cidades = repo.listar_cidades_completas()
    repo.fechar()

    if not cidades:
        print("❌ Nenhuma cidade com 6 locais cadastrados encontrada.")
        print("   Execute primeiro: python gerador_locais.py")
        sys.exit(1)

    cidade, uf = _escolher_cidade(cidades) if len(cidades) > 1 else cidades[0]
    modo, preset_nome = _escolher_modo()

    repo = RepositorioBanco("mobilidade.db")
    repo.inicializar()
    locais = repo.listar_locais(cidade, uf)
    repo.fechar()

    if len(locais) != 6:
        print(f"❌ Sao necessarios 6 locais cadastrados para {cidade}/{uf}, mas ha {len(locais)}.")
        print(f"   Execute primeiro: python gerador_locais.py")
        sys.exit(1)

    if modo == "sequencial":
        sentidos = _escolher_sentido()
        labels = {"centro": "E/M→C", "bairro": "C→E/M"}
        sentido_str = " + ".join(labels[s] for s in sentidos)
        print(f"\n▶️  Modo SEQUENCIAL — {sentido_str}")
        agendamentos = gerar_modo_sequencial(locais, sentidos)
    else:
        preset = PRESETS_PROGRAMADOS[preset_nome]
        print(f"\n📅 Modo PROGRAMADO — {preset['descricao']}")
        print(f"   Data: {datetime.now().date() + timedelta(days=1)} (dia seguinte)")
        agendamentos = gerar_modo_programado(locais, preset)

    salvar_agendamentos(agendamentos)


if __name__ == "__main__":
    main()
