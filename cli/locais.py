import sys
import time

import structlog
from modelos.local_coleta import LocalColeta
from persistencia.repositorio_banco import RepositorioBanco
from servicos.geo import GeoServico, DescobridorLocais
from servicos.mapa import MapaServico

from rich.prompt import Prompt, Confirm
from rich import print

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


def gerar(cidade: str | None = None, uf: str | None = None) -> None:
    """Gera os 6 locais (C1, C2, E1, E2, M1, M2) para uma cidade."""

    if cidade is None or uf is None:
        cidade, uf = _solicitar_cidade_uf()

    repo = RepositorioBanco("mobilidade.db")
    repo.inicializar()

    locais = repo.listar_locais(cidade, uf)
    cache = {l.codigo: l for l in locais}

    if len(cache) == 6:
        print(f"📌 Todos os 6 locais já cadastrados para {cidade}/{uf}:")
        for l in locais:
            print(f"   {l.codigo} — {l.endereco} ({l.lat}, {l.lon})")
        repo.fechar()
        
        usar_existente = Confirm.ask("\nDeseja usar estas localizações existentes?", default=True)
        if usar_existente:
            print(f"\n💡 [bold green]Próximo passo:[/bold green] Escolha a opção [bold]2[/bold] (Gerar agendamentos) no Menu Principal.")
            return
        cache = {}
        repo = RepositorioBanco("mobilidade.db")
        repo.inicializar()

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
        c1 = descobridor.buscar_c1(min_lat, max_lat, min_lon, max_lon, centro_lat, centro_lon, cidade, uf)
        time.sleep(1)

    c2 = cache.get("C2")
    if not c2:
        c2 = descobridor.buscar_c2(min_lat, max_lat, min_lon, max_lon, centro_lat, centro_lon,
                                   c1.lat, c1.lon, cidade, uf, diametro_km)

    usadas = {(c1.lat, c1.lon), (c2.lat, c2.lon)}

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

    print(f"\n💡 [bold green]Próximo passo:[/bold green] Escolha a opção [bold]2[/bold] (Gerar agendamentos) no Menu Principal.")
