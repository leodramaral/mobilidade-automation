import json
import random
import sys
from datetime import datetime, timedelta

from persistencia.repositorio_banco import RepositorioBanco


INTERVALO_SEGUNDOS = 60
BUFFER_MINUTOS = 5


def _direcao(periodo: str, origem, destino, C1, C2):
    """Determina origem/destino conforme período e tipo da rota."""
    pois = {C1.codigo, C2.codigo}
    if origem.codigo in pois and destino.codigo in pois:
        return (C1, C2) if periodo == "manhã" else (C2, C1)
    if periodo == "manhã":
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


def gerar_modo_teste(locais, agora):
    """Gera 18 agendamentos sequenciais a partir de agora."""
    C1 = next(l for l in locais if l.codigo == "C1")
    C2 = next(l for l in locais if l.codigo == "C2")
    rotas = _gerar_rotas(locais)

    agendamentos = []
    proximo = agora + timedelta(minutes=1)

    for origem_rota, destino_rota in rotas:
        limite = random.randint(3, 9)
        duracao = timedelta(seconds=(limite - 1) * INTERVALO_SEGUNDOS)

        # Manhã
        origem, destino = _direcao("manhã", origem_rota, destino_rota, C1, C2)
        agendamentos.append({
            "quando": proximo.strftime("%Y-%m-%d %H:%M"),
            "config_override": {
                "origem": origem.endereco,
                "destino": destino.endereco,
                "limite_consultas": limite,
                "openweather": {"lat": origem.lat, "lon": origem.lon},
            },
        })
        proximo += duracao + timedelta(minutes=BUFFER_MINUTOS)

        # Tarde
        origem, destino = _direcao("tarde", origem_rota, destino_rota, C1, C2)
        agendamentos.append({
            "quando": proximo.strftime("%Y-%m-%d %H:%M"),
            "config_override": {
                "origem": origem.endereco,
                "destino": destino.endereco,
                "limite_consultas": limite,
                "openweather": {"lat": origem.lat, "lon": origem.lon},
            },
        })
        proximo += duracao + timedelta(minutes=BUFFER_MINUTOS)

    return agendamentos


def _data_ref_programado(agora):
    """Determina a data de referência para o modo programado."""
    hoje = agora.date()
    if agora.hour >= 19:
        amanha = hoje + timedelta(days=1)
        return datetime(amanha.year, amanha.month, amanha.day, 6, 0)
    elif agora.hour >= 9:
        return datetime(hoje.year, hoje.month, hoje.day, 17, 0)
    elif agora.hour < 6:
        return datetime(hoje.year, hoje.month, hoje.day, 6, 0)
    else:
        return agora


def _cabe_na_janela(horario, duracao, fim_janela):
    return horario + duracao <= fim_janela


def gerar_modo_programado(locais, agora):
    """Gera 18 agendamentos em janelas de pico (06:00-08:50 / 17:00-18:50), em até 18h."""
    C1 = next(l for l in locais if l.codigo == "C1")
    C2 = next(l for l in locais if l.codigo == "C2")
    rotas = _gerar_rotas(locais)

    data_ref = _data_ref_programado(agora)
    prazo_final = data_ref + timedelta(hours=18)

    agendamentos = []
    idx_manha = 0
    idx_tarde = 0
    dia_atual = data_ref.date()
    limite_padrao = True

    while idx_manha < 9 or idx_tarde < 9:
        inicio_manha = datetime(dia_atual.year, dia_atual.month, dia_atual.day, 6, 0)
        fim_manha = datetime(dia_atual.year, dia_atual.month, dia_atual.day, 8, 50)
        inicio_tarde = datetime(dia_atual.year, dia_atual.month, dia_atual.day, 17, 0)
        fim_tarde = datetime(dia_atual.year, dia_atual.month, dia_atual.day, 18, 50)

        # Manhã
        if idx_manha < 9:
            if dia_atual == data_ref.date():
                ultimo_fim_manha = max(inicio_manha, data_ref) - timedelta(minutes=BUFFER_MINUTOS)
            else:
                ultimo_fim_manha = inicio_manha - timedelta(minutes=BUFFER_MINUTOS)

            while idx_manha < 9:
                origem_rota, destino_rota = rotas[idx_manha]
                limite = 3 if not limite_padrao else random.randint(3, 9)
                duracao = timedelta(seconds=(limite - 1) * INTERVALO_SEGUNDOS)

                horario = ultimo_fim_manha + timedelta(minutes=BUFFER_MINUTOS)
                if not _cabe_na_janela(horario, duracao, fim_manha):
                    break
                if horario + duracao > prazo_final:
                    break

                origem, destino = _direcao("manhã", origem_rota, destino_rota, C1, C2)
                agendamentos.append({
                    "quando": horario.strftime("%Y-%m-%d %H:%M"),
                    "config_override": {
                        "origem": origem.endereco,
                        "destino": destino.endereco,
                        "limite_consultas": limite,
                        "openweather": {"lat": origem.lat, "lon": origem.lon},
                    },
                })
                ultimo_fim_manha = horario + duracao
                idx_manha += 1

        # Tarde
        if idx_tarde < 9:
            if dia_atual == data_ref.date():
                ultimo_fim_tarde = max(inicio_tarde, data_ref) - timedelta(minutes=BUFFER_MINUTOS)
            else:
                ultimo_fim_tarde = inicio_tarde - timedelta(minutes=BUFFER_MINUTOS)

            while idx_tarde < 9:
                origem_rota, destino_rota = rotas[idx_tarde]
                limite = 3 if not limite_padrao else random.randint(3, 9)
                duracao = timedelta(seconds=(limite - 1) * INTERVALO_SEGUNDOS)

                horario = ultimo_fim_tarde + timedelta(minutes=BUFFER_MINUTOS)
                if not _cabe_na_janela(horario, duracao, fim_tarde):
                    break
                if horario + duracao > prazo_final:
                    break

                origem, destino = _direcao("tarde", origem_rota, destino_rota, C1, C2)
                agendamentos.append({
                    "quando": horario.strftime("%Y-%m-%d %H:%M"),
                    "config_override": {
                        "origem": origem.endereco,
                        "destino": destino.endereco,
                        "limite_consultas": limite,
                        "openweather": {"lat": origem.lat, "lon": origem.lon},
                    },
                })
                ultimo_fim_tarde = horario + duracao
                idx_tarde += 1

        if idx_manha >= 9 and idx_tarde >= 9:
            break

        dia_atual += timedelta(days=1)

        # Se estourou o prazo de 18h e ainda faltam agendamentos, reduz limites
        if (idx_manha < 9 or idx_tarde < 9) and dia_atual >= prazo_final.date() and limite_padrao:
            print("⚠️  18 agendamentos não couberam em 18h — reduzindo limite_consultas para 3")
            agendamentos.clear()
            idx_manha = 0
            idx_tarde = 0
            dia_atual = data_ref.date()
            limite_padrao = False
            continue

        if dia_atual > prazo_final.date():
            break

    return sorted(agendamentos, key=lambda a: a["quando"])


def salvar_agendamentos(agendamentos):
    with open("agendamentos.json", "w", encoding="utf-8") as f:
        json.dump({"agendamentos": agendamentos}, f, ensure_ascii=False, indent=2)

    print(f"\n📋 {len(agendamentos)} agendamentos gerados em agendamentos.json")
    for a in agendamentos:
        o = a["config_override"]["origem"]
        d = a["config_override"]["destino"]
        print(f"   {a['quando']}  {o} → {d}")


def _escolher_cidade(cidades):
    """Exibe as cidades disponíveis e pede para o usuário escolher."""
    print("\n📌 Cidades com 6 locais cadastrados:")
    for i, (cidade, uf) in enumerate(cidades, 1):
        print(f"   {i}. {cidade}/{uf}")
    print()

    while True:
        try:
            escolha = input("Escolha o número da cidade: ").strip()
            idx = int(escolha) - 1
            if 0 <= idx < len(cidades):
                return cidades[idx]
            print(f"⚠️  Escolha um número entre 1 e {len(cidades)}.")
        except ValueError:
            print("⚠️  Digite um número válido.")


def _escolher_modo():
    """Pede o modo de geração ao usuário."""
    print("\nModo de geração:")
    print("   1. teste       — sequencial imediato a partir de agora")
    print("   2. programado  — horários de pico (06:00-08:50 / 17:00-18:50)")
    while True:
        escolha = input("Escolha o modo (1 ou 2): ").strip()
        if escolha == "1":
            return "teste"
        if escolha == "2":
            return "programado"
        print("⚠️  Digite 1 ou 2.")


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
    modo = _escolher_modo()

    repo = RepositorioBanco("mobilidade.db")
    repo.inicializar()
    locais = repo.listar_locais(cidade, uf)
    repo.fechar()

    if len(locais) != 6:
        print(f"❌ São necessários 6 locais cadastrados para {cidade}/{uf}, mas há {len(locais)}.")
        print(f"   Execute primeiro: python gerador_locais.py")
        sys.exit(1)

    agora = datetime.now().replace(second=0, microsecond=0)

    if modo == "teste":
        print(f"\n🧪 Modo TESTE — gerando agendamentos sequenciais a partir de {agora.strftime('%H:%M')}")
        agendamentos = gerar_modo_teste(locais, agora)
    else:
        print(f"\n📅 Modo PROGRAMADO — gerando agendamentos em horários de pico")
        agendamentos = gerar_modo_programado(locais, agora)

    if len(agendamentos) < 18:
        print(f"⚠️  Apenas {len(agendamentos)} de 18 agendamentos couberam no período")

    salvar_agendamentos(agendamentos)


if __name__ == "__main__":
    main()
