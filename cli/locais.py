import sys
import time

import structlog
from modelos.local_coleta import LocalColeta
from persistencia.repositorio_banco import RepositorioBanco
from servicos.geo import GeoServico, DescobridorLocais
from servicos.mapa import MapaServico

from rich.prompt import Prompt, Confirm
from rich import print

import inquirer

logger = structlog.get_logger("cli.locais")

def _solicitar_cidade_uf() -> tuple[str, str]:
    """Pede cidade e UF ao usuário via Prompt, com validação."""
    cidade = Prompt.ask("[bold]Cidade[/bold]").strip()
    while not cidade:
        print("⚠️  Cidade não pode ser vazia.")
        cidade = Prompt.ask("[bold]Cidade[/bold]").strip()
        
    while True:
        uf = Prompt.ask("[bold]UF (sigla, 2 letras)[/bold]").strip().upper()
        if len(uf) == 2 and uf.isalpha():
            break
        print("⚠️  UF deve ter 2 letras (ex: AP, SP, RJ).")
    return cidade, uf


def gerar(cidade: str | None = None, uf: str | None = None, coordenadas_descartadas: set | None = None) -> None:
    """Gera os 6 locais (C1, C2, E1, E2, M1, M2) para uma cidade."""

    if cidade is None or uf is None:
        cidade, uf = _solicitar_cidade_uf()

    repo = RepositorioBanco("mobilidade.db")
    repo.inicializar()

    locais = repo.listar_locais(cidade, uf)
    cache = {l.codigo: l for l in locais}

    if coordenadas_descartadas is None:
        coordenadas_descartadas = set()

        if len(cache) > 0:
            print(f"📌 Encontrados {len(cache)} locais já cadastrados para {cidade}/{uf}:")
            for l in locais:
                print(f"   {l.codigo} — {l.endereco} ({l.lat}, {l.lon})")
            
            sobrescrever = Confirm.ask("\nDeseja sobrescrever ou regerar alguma destas localizações?", default=False)
            if sobrescrever:
                print("[bold yellow]Selecione os locais para SOBRESCREVER (Espaço para marcar, Enter para confirmar):[/bold yellow]")
                opcoes_validas = sorted(list(cache.keys()))
                pergunta = [
                    inquirer.Checkbox(
                        "codigos",
                        message="Locais",
                        choices=opcoes_validas,
                    )
                ]
                respostas = inquirer.prompt(pergunta)
                
                if respostas and respostas.get("codigos"):
                    codigos_para_deletar = respostas["codigos"]
                    
                    for cod in codigos_para_deletar:
                        l_antigo = cache.get(cod)
                        if l_antigo:
                            coordenadas_descartadas.add((l_antigo.lat, l_antigo.lon))
                    
                    repo.deletar_locais_especificos(cidade, uf, codigos_para_deletar)
                    print(f"♻️  Localizações removidas: {', '.join(codigos_para_deletar)}. Elas serão recalculadas evitando os endereços antigos.")
                    
                    for cod in codigos_para_deletar:
                        cache.pop(cod, None)
                else:
                    print("⚠️  Nenhuma localização selecionada para sobrescrever.")
            else:
                if len(cache) == 6:
                    print(f"\n💡 [bold green]Próximo passo:[/bold green] Escolha a opção [bold]Gerar agendamentos[/bold] no Menu Principal.")
                    repo.fechar()
                    return

    for codigo in ["C1", "C2", "E1", "E2", "M1", "M2"]:
        if codigo in cache:
            print(f"📌 {codigo} já cadastrado: {cache[codigo].endereco} "
                  f"({cache[codigo].lat}, {cache[codigo].lon})")

    geo = GeoServico()
    descobridor = DescobridorLocais(geo)

    bbox = geo.buscar_bounding_box(cidade, uf)
    min_lat, max_lat, min_lon, max_lon, centro_lat, centro_lon, diametro_km = bbox

    c1 = cache.get("C1")
    if not c1:
        c1 = descobridor.buscar_c1(min_lat, max_lat, min_lon, max_lon, centro_lat, centro_lon, cidade, uf, usadas=coordenadas_descartadas)
        time.sleep(1)

    c2 = cache.get("C2")
    if not c2:
        c2 = descobridor.buscar_c2(min_lat, max_lat, min_lon, max_lon, centro_lat, centro_lon,
                                   c1.lat, c1.lon, cidade, uf, diametro_km, usadas=coordenadas_descartadas)

    usadas = {(c1.lat, c1.lon), (c2.lat, c2.lon)} | coordenadas_descartadas

    e1 = cache.get("E1")
    e2 = cache.get("E2")
    if not e1 or not e2:
        time.sleep(3)
        e1_novo, e2_novo = descobridor.buscar_extremos(min_lat, max_lat, min_lon, max_lon,
                                                       centro_lat, centro_lon, cidade, uf, diametro_km, usadas)
        if not e1:
            e1 = e1_novo
        if not e2:
            e2 = e2_novo

    usadas |= {(e1.lat, e1.lon), (e2.lat, e2.lon)}

    m1 = cache.get("M1")
    m2 = cache.get("M2")
    if not m1 or not m2:
        m1_novo, m2_novo = descobridor.buscar_bairros(c1, c2, e1, e2, cidade, uf, diametro_km, usadas)
        if not m1:
            m1 = m1_novo
        if not m2:
            m2 = m2_novo

    todos = [c1, c2, e1, e2, m1, m2]

    coords_vistos = {}
    dups = []
    for l in todos:
        key = (l.lat, l.lon)
        if key in coords_vistos:
            dups.append(f"  {l.codigo} e {coords_vistos[key].codigo} ({l.lat}, {l.lon})")
        else:
            coords_vistos[key] = l

    if dups:
        raise RuntimeError(
            f"Pontos duplicados detectados para {cidade}/{uf}:\n" + "\n".join(dups)
            + "\nExecute novamente com 'buscar novas' para gerar pontos diferentes."
        )

    if len(cache) < 6:
        repo.salvar_locais(todos)
        print(f"💾 6 locais salvos no banco")

    repo.fechar()

    caminho_mapa = f"mapas/{cidade}_{uf}.png"
    MapaServico.gerar_png(todos, caminho_mapa)
    print(f"🗺️  Mapa salvo: {caminho_mapa}")

    print(f"\n💡 [bold green]Próximo passo:[/bold green] Escolha a opção [bold]Gerar agendamentos[/bold] no Menu Principal.")


def gerenciar_cidades() -> None:
    repo = RepositorioBanco("mobilidade.db")
    repo.inicializar()
    cidades = repo.listar_todas_cidades()
    repo.fechar()

    opcoes = ["Configurar nova cidade"]
    opcoes_map = {}
    for cidade, uf in cidades:
        label = f"{cidade} - {uf}"
        opcoes.append(label)
        opcoes_map[label] = (cidade, uf)

    pergunta = [
        inquirer.List(
            "cidade_opcao",
            message="Gerenciar Cidades",
            choices=opcoes,
        )
    ]
    respostas = inquirer.prompt(pergunta)
    if not respostas:
        return

    escolha = respostas["cidade_opcao"]
    if escolha == "Configurar nova cidade":
        cidade, uf = _solicitar_cidade_uf()
        repo = RepositorioBanco("mobilidade.db")
        repo.inicializar()
        locais = repo.listar_locais(cidade, uf)
        repo.fechar()
        if locais:
            _gerenciar_cidade_especifica(cidade, uf, locais)
        else:
            gerar(cidade, uf)
    else:
        cidade, uf = opcoes_map[escolha]
        repo = RepositorioBanco("mobilidade.db")
        repo.inicializar()
        locais = repo.listar_locais(cidade, uf)
        repo.fechar()
        _gerenciar_cidade_especifica(cidade, uf, locais)


def _gerenciar_cidade_especifica(cidade: str, uf: str, locais: list[LocalColeta]) -> None:
    opcoes = []
    opcoes_map = {}
    for l in locais:
        endereco_curto = l.endereco[:50] + "..." if len(l.endereco) > 50 else l.endereco
        label = f"{l.codigo} — {endereco_curto}"
        opcoes.append(label)
        opcoes_map[label] = l

    print(f"\n[bold yellow]Selecione as localizações de {cidade}/{uf} que deseja SOBRESCREVER (Espaço para marcar, Enter para confirmar):[/bold yellow]")
    pergunta = [
        inquirer.Checkbox(
            "locais_selecionados",
            message="Locais",
            choices=opcoes,
        )
    ]
    respostas = inquirer.prompt(pergunta)
    if not respostas:
        return

    selecionados = respostas.get("locais_selecionados", [])
    if selecionados:
        confirmar = Confirm.ask(f"\nDeseja realmente substituir as {len(selecionados)} localizações selecionadas?", default=False)
        if confirmar:
            codigos_para_deletar = [opcoes_map[item].codigo for item in selecionados]
            
            coordenadas_descartadas = set()
            for item in selecionados:
                local_obj = opcoes_map[item]
                coordenadas_descartadas.add((local_obj.lat, local_obj.lon))
            
            repo = RepositorioBanco("mobilidade.db")
            repo.inicializar()
            repo.deletar_locais_especificos(cidade, uf, codigos_para_deletar)
            repo.fechar()
            print(f"♻️  Localizações removidas: {', '.join(codigos_para_deletar)}. Elas serão recalculadas evitando os endereços antigos.")
            
            gerar(cidade, uf, coordenadas_descartadas)
        else:
            print("⚠️  Substituição cancelada.")
    else:
        print("⚠️  Nenhuma localização selecionada.")
        if len(locais) == 6:
            print(f"\n💡 [bold green]Próximo passo:[/bold green] Escolha a opção [bold]Gerar agendamentos[/bold] no Menu Principal.")

