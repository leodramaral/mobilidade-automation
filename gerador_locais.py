"""Gerador de localizações — descoberta de C1 e C2 via OpenStreetMap."""
import math
import time

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org"
HEADERS = {"User-Agent": "MobilidadeAutomation/1.0 (projeto@mobilidade.local)"}


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância entre dois pontos geográficos em km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def buscar_bounding_box(cidade: str, uf: str) -> tuple:
    """Retorna (min_lat, max_lat, min_lon, max_lon, centro_lat, centro_lon) para a cidade."""
    query = f"{cidade},{uf}"
    resp = requests.get(
        f"{NOMINATIM_URL}/search",
        params={"q": query, "format": "json", "limit": 5},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    dados = resp.json()
    if not dados:
        raise ValueError(f"Cidade não encontrada no Nominatim: {cidade}/{uf}")

    # Escolher o resultado com menor bounding box (evita fronteira estadual)
    def _area_bbox(item):
        bbox = item.get("boundingbox", [0, 0, 0, 0])
        return abs(float(bbox[1]) - float(bbox[0])) * abs(float(bbox[3]) - float(bbox[2]))

    dados.sort(key=_area_bbox)
    item = dados[0]
    bbox = item["boundingbox"]
    min_lat, max_lat = float(bbox[0]), float(bbox[1])
    min_lon, max_lon = float(bbox[2]), float(bbox[3])
    centro_lat = float(item["lat"])
    centro_lon = float(item["lon"])

    print(f"📍 {item.get('display_name', query)}")
    print(f"   Centro: ({centro_lat}, {centro_lon})")
    print(f"   BBox: [{min_lat}, {max_lat}, {min_lon}, {max_lon}]")

    return (min_lat, max_lat, min_lon, max_lon, centro_lat, centro_lon)


OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def _overpass_query(query: str) -> list:
    """Executa query Overpass com retry em caso de rate limit ou timeout."""
    for tentativa in range(5):
        if tentativa > 0:
            espera = 5 * (2 ** tentativa)
            print(f"   ⏳ Overpass indisponível — aguardando {espera}s...")
            time.sleep(espera)
        resp = requests.post(OVERPASS_URL, data={"data": query}, headers=HEADERS, timeout=30)
        if resp.status_code in (429, 504):
            continue
        resp.raise_for_status()
        return resp.json().get("elements", [])
    raise RuntimeError("Overpass indisponível após 5 tentativas")


def buscar_c1(min_lat: float, max_lat: float, min_lon: float, max_lon: float,
              centro_lat: float, centro_lon: float, cidade: str, uf: str):
    """Descobre C1: igreja ou praça mais próxima do centro da cidade."""
    from modelos.local_coleta import LocalColeta

    query = f"""
    [out:json];
    (
      node[amenity=place_of_worship][religion=christian]({min_lat},{min_lon},{max_lat},{max_lon});
      node[place=square]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out center;
    """

    elementos = _overpass_query(query)

    if not elementos:
        print("⚠️  Nenhuma igreja/praça encontrada — usando centro da cidade como C1")
        nome = f"Centro, {cidade}"
        return LocalColeta(
            codigo="C1", endereco=f"Centro, {cidade}, {uf}",
            cidade=cidade, uf=uf, lat=centro_lat, lon=centro_lon, tipo="central",
        )

    mais_perto = min(
        elementos,
        key=lambda e: haversine(centro_lat, centro_lon, e.get("lat", 0), e.get("lon", 0)),
    )
    lat = mais_perto.get("lat", centro_lat)
    lon = mais_perto.get("lon", centro_lon)
    nome = mais_perto.get("tags", {}).get("name", f"Centro, {cidade}")
    rua = _obter_rua(lat, lon)
    print(f"⛪ C1: {nome} ({lat}, {lon}) — {len(elementos)} igrejas/praças analisadas")
    return LocalColeta(codigo="C1", endereco=f"{nome}, {rua}, {cidade}, {uf}", cidade=cidade, uf=uf, lat=lat, lon=lon, tipo="central")


def buscar_c2(min_lat: float, max_lat: float, min_lon: float, max_lon: float,
              centro_lat: float, centro_lon: float, c1_lat: float, c1_lon: float,
              cidade: str, uf: str):
    """Descobre C2: ponto turístico ou histórico, a >100m de C1."""
    from modelos.local_coleta import LocalColeta

    def _selecionar(elementos):
        candidatos = [
            e for e in elementos
            if e.get("tags", {}).get("name")
            and haversine(c1_lat, c1_lon, e.get("lat", 0), e.get("lon", 0)) > 0.1
        ]
        if not candidatos:
            return None
        return min(
            candidatos,
            key=lambda e: haversine(centro_lat, centro_lon, e.get("lat", 0), e.get("lon", 0)),
        )

    # Primeira tentativa: tourism + historic
    query = f"""
    [out:json];
    (
      node[tourism]({min_lat},{min_lon},{max_lat},{max_lon});
      node[historic]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out center;
    """
    elementos = _overpass_query(query)
    selecionado = _selecionar(elementos)

    if selecionado is None:
        print("⚠️  Nenhum tourism/historic adequado — tentando amenidades genéricas")
        query_fallback = f"""
        [out:json];
        node[amenity]({min_lat},{min_lon},{max_lat},{max_lon});
        out center;
        """
        elementos = _overpass_query(query_fallback)
        selecionado = _selecionar(elementos)

    if selecionado is None:
        raise ValueError(f"Nenhum POI adequado encontrado para C2 em {cidade}/{uf}")

    lat = selecionado.get("lat", centro_lat)
    lon = selecionado.get("lon", centro_lon)
    nome = selecionado.get("tags", {}).get("name", f"POI, {cidade}")
    rua = _obter_rua(lat, lon)
    dist_m = haversine(c1_lat, c1_lon, lat, lon) * 1000
    print(f"🏛️  C2: {nome} ({lat}, {lon}) — {dist_m:.0f}m de C1")
    return LocalColeta(codigo="C2", endereco=f"{nome}, {rua}, {cidade}, {uf}", cidade=cidade, uf=uf, lat=lat, lon=lon, tipo="central")


def _obter_rua(lat: float, lon: float) -> str:
    """Obtém o nome da rua via Nominatim reverse geocode."""
    time.sleep(1)
    resp = requests.get(
        f"{NOMINATIM_URL}/reverse",
        params={"lat": lat, "lon": lon, "format": "json", "zoom": 18},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    address = resp.json().get("address", {})
    return address.get("road") or address.get("path") or ""


def _reverse_geocode(lat: float, lon: float, cidade: str) -> str:
    """Obtém o nome do bairro/local via Nominatim reverse geocode."""
    time.sleep(1)  # Rate limit
    resp = requests.get(
        f"{NOMINATIM_URL}/reverse",
        params={"lat": lat, "lon": lon, "format": "json", "zoom": 18},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    address = resp.json().get("address", {})

    nome_local = (
        address.get("neighbourhood")
        or address.get("hamlet")
        or address.get("suburb")
        or address.get("village")
        or address.get("road")
        or address.get("city_district")
        or "Bairro"
    )
    if nome_local.lower() == cidade.lower():
        nome_local = address.get("road") or nome_local

    return nome_local


def buscar_extremos(min_lat: float, max_lat: float, min_lon: float, max_lon: float,
                    centro_lat: float, centro_lon: float, cidade: str, uf: str):
    """Descobre E1 e E2: extremos opostos dentro do perímetro urbano."""
    from modelos.local_coleta import LocalColeta

    query = f"""
    [out:json];
    (
      node[amenity]({min_lat},{min_lon},{max_lat},{max_lon});
      node[shop]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out center;
    """
    elementos = _overpass_query(query)

    pois_todos = [
        e for e in elementos
        if e.get("tags", {}).get("name")
    ]

    # Raio urbano adaptativo: começa em 3km, dobra até ter ≥ 4 POIs
    raio_km = 3.0
    while True:
        pois = [
            e for e in pois_todos
            if haversine(centro_lat, centro_lon, e.get("lat", 0), e.get("lon", 0)) <= raio_km
        ]
        if len(pois) >= 4 or raio_km >= 30:
            break
        raio_km *= 2

    print(f"🎯 {len(pois)} POIs em raio urbano de {raio_km:.0f}km (total: {len(pois_todos)})")

    if len(pois) < 2:
        print(f"⚠️  Apenas {len(pois)} POIs no raio urbano — usando cantos da bounding box")
        e1_lat, e1_lon = max_lat, max_lon
        e2_lat, e2_lon = min_lat, min_lon
        nome_e1 = _reverse_geocode(e1_lat, e1_lon, cidade)
        nome_e2 = _reverse_geocode(e2_lat, e2_lon, cidade)
    else:
        # E1: POI na direção noroeste com maior distância do centro
        def _score_nw(e):
            elat = e.get("lat", centro_lat)
            elon = e.get("lon", centro_lon)
            return (elat - centro_lat) + (centro_lon - elon)

        e1 = max(pois, key=_score_nw)
        e1_lat = e1.get("lat", centro_lat)
        e1_lon = e1.get("lon", centro_lon)
        nome_e1 = e1.get("tags", {}).get("name", "Extremo 1")

        # E2: POI com maior projeção negativa no vetor centro→E1
        vec_lat = e1_lat - centro_lat
        vec_lon = e1_lon - centro_lon
        vec_len = math.sqrt(vec_lat**2 + vec_lon**2)

        def _proj_oposta(e):
            elat = e.get("lat", centro_lat)
            elon = e.get("lon", centro_lon)
            if elat == e1_lat and elon == e1_lon:
                return float("inf")
            dot = vec_lat * (elat - centro_lat) + vec_lon * (elon - centro_lon)
            return dot / vec_len

        e2 = min(pois, key=_proj_oposta)
        e2_lat = e2.get("lat", centro_lat)
        e2_lon = e2.get("lon", centro_lon)
        nome_e2 = e2.get("tags", {}).get("name", "Extremo 2")

    e1_dist = haversine(centro_lat, centro_lon, e1_lat, e1_lon)
    e2_dist = haversine(centro_lat, centro_lon, e2_lat, e2_lon)
    print(f"🏪 E1: {nome_e1} ({e1_lat}, {e1_lon}) — {e1_dist:.1f}km do centro")
    print(f"🏪 E2: {nome_e2} ({e2_lat}, {e2_lon}) — {e2_dist:.1f}km do centro")

    e1_local = LocalColeta(codigo="E1", endereco=f"{nome_e1}, {cidade}, {uf}", cidade=cidade, uf=uf, lat=e1_lat, lon=e1_lon, tipo="extremo")
    e2_local = LocalColeta(codigo="E2", endereco=f"{nome_e2}, {cidade}, {uf}", cidade=cidade, uf=uf, lat=e2_lat, lon=e2_lon, tipo="extremo")
    return e1_local, e2_local


def buscar_bairros(c1, c2, e1, e2, cidade: str, uf: str):
    """Descobre M1 e M2: pontos médios entre extremos e centros."""
    from modelos.local_coleta import LocalColeta

    m1_lat = round((e1.lat + c1.lat) / 2, 7)
    m1_lon = round((e1.lon + c1.lon) / 2, 7)
    nome_m1 = _reverse_geocode(m1_lat, m1_lon, cidade)
    print(f"🏘️  M1: {nome_m1} ({m1_lat}, {m1_lon}) — midpoint(E1, C1)")

    m2_lat = round((e2.lat + c2.lat) / 2, 7)
    m2_lon = round((e2.lon + c2.lon) / 2, 7)
    nome_m2 = _reverse_geocode(m2_lat, m2_lon, cidade)
    print(f"🏘️  M2: {nome_m2} ({m2_lat}, {m2_lon}) — midpoint(E2, C2)")

    m1 = LocalColeta(codigo="M1", endereco=f"{nome_m1}, {cidade}, {uf}", cidade=cidade, uf=uf, lat=m1_lat, lon=m1_lon, tipo="bairro")
    m2 = LocalColeta(codigo="M2", endereco=f"{nome_m2}, {cidade}, {uf}", cidade=cidade, uf=uf, lat=m2_lat, lon=m2_lon, tipo="bairro")
    return m1, m2


def gerar_agendamentos(cidade: str, uf: str) -> list:
    """Gera 18 agendamentos (9 rotas × 2 períodos) a partir dos pontos no banco."""
    import json
    import random
    from datetime import datetime, timedelta
    from persistencia.repositorio_banco import RepositorioBanco

    repo = RepositorioBanco("mobilidade.db")
    repo.inicializar()
    locais = repo.listar_locais(cidade, uf)
    repo.fechar()

    if len(locais) != 6:
        raise RuntimeError(f"São necessários 6 locais, mas há {len(locais)} no banco")

    pts = {l.codigo: l for l in locais}
    C1, C2 = pts["C1"], pts["C2"]
    E1, E2 = pts["E1"], pts["E2"]
    M1, M2 = pts["M1"], pts["M2"]

    # 9 rotas fixas
    rotas = [
        (C1, C2),   # 1
        (E1, C1),   # 2
        (E2, C1),   # 3
        (E1, E2),   # 4
        (M1, C1),   # 5
        (M2, C1),   # 6
        (M1, E1),   # 7
        (M1, M2),   # 8
        (M1, E2),   # 9
    ]

    agora = datetime.now().replace(second=0, microsecond=0)
    hoje = agora.date()

    # Janelas disponíveis: 5 dias a partir de hoje
    dias = [hoje + timedelta(days=i) for i in range(5)]

    agendamentos = []
    idx_manha = 0   # qual rota usar para o próximo agendamento da manhã
    idx_tarde = 0   # qual rota usar para o próximo agendamento da tarde

    for dia in dias:
        if idx_manha >= 9 and idx_tarde >= 9:
            break

        # ── Manhã 06:00–08:50 ──
        inicio_manha = datetime(dia.year, dia.month, dia.day, 6, 0)
        fim_manha = datetime(dia.year, dia.month, dia.day, 8, 50)

        # Pula manhã do dia 0 se já passou do fim_manha
        if dia == hoje and agora >= fim_manha:
            idx_manha = 9
        else:
            # No dia 0, ponto de partida é max(06:00, agora); nos demais, é 06:00.
            # O buffer de 5min aplica-se a partir do último agendamento do dia anterior,
            # mas como a manhã começa cedo, isso raramente interfere.
            if dia == hoje:
                ultimo_fim_manha = max(inicio_manha, agora) - timedelta(minutes=5)
            else:
                ultimo_fim_manha = inicio_manha - timedelta(minutes=5)

            while idx_manha < 9:
                origem_rota, destino_rota = rotas[idx_manha]
                limite = random.randint(3, 10)
                duracao = timedelta(seconds=(limite - 1) * 60)

                horario = ultimo_fim_manha + timedelta(minutes=5)
                if horario + duracao > fim_manha:
                    break  # não cabe mais, tenta próximo dia

                # Manhã: RES→POI direto, POI→POI ordem natural, RES→RES direto
                origem, destino = _direcao("manhã", origem_rota, destino_rota, C1, C2)

                agendamentos.append({
                    "quando": horario.strftime("%Y-%m-%d %H:%M"),
                    "config_override": {
                        "origem": origem.endereco,
                        "destino": destino.endereco,
                        "limite_consultas": limite,
                    },
                })
                ultimo_fim_manha = horario + duracao
                idx_manha += 1

        # ── Tarde 17:00–18:50 ──
        inicio_tarde = datetime(dia.year, dia.month, dia.day, 17, 0)
        fim_tarde = datetime(dia.year, dia.month, dia.day, 18, 50)

        # Pula tarde do dia 0 se já passou do fim_tarde
        if dia == hoje and agora >= fim_tarde:
            idx_tarde = 9
        else:
            if dia == hoje:
                ultimo_fim_tarde = max(inicio_tarde, agora) - timedelta(minutes=5)
            else:
                ultimo_fim_tarde = inicio_tarde - timedelta(minutes=5)

            while idx_tarde < 9:
                origem_rota, destino_rota = rotas[idx_tarde]
                limite = random.randint(3, 10)
                duracao = timedelta(seconds=(limite - 1) * 60)

                horario = ultimo_fim_tarde + timedelta(minutes=5)
                if horario + duracao > fim_tarde:
                    break  # não cabe mais

                # Tarde: POI→RES invertido, POI→POI invertido, RES→RES invertido
                origem, destino = _direcao("tarde", origem_rota, destino_rota, C1, C2)

                agendamentos.append({
                    "quando": horario.strftime("%Y-%m-%d %H:%M"),
                    "config_override": {
                        "origem": origem.endereco,
                        "destino": destino.endereco,
                        "limite_consultas": limite,
                    },
                })
                ultimo_fim_tarde = horario + duracao
                idx_tarde += 1

        if idx_manha >= 9 and idx_tarde >= 9:
            break

    # Escrever arquivo
    with open("agendamentos.json", "w", encoding="utf-8") as f:
        json.dump({"agendamentos": agendamentos}, f, ensure_ascii=False, indent=2)

    print(f"\n📋 {len(agendamentos)} agendamentos gerados em agendamentos.json")
    for a in agendamentos:
        o = a["config_override"]["origem"]
        d = a["config_override"]["destino"]
        print(f"   {a['quando']}  {o} → {d}")

    return agendamentos


def _direcao(periodo: str, origem, destino, C1, C2):
    """Determina origem/destino conforme período e tipo da rota."""
    pois = {C1.codigo, C2.codigo}
    if origem.codigo in pois and destino.codigo in pois:
        # POI → POI: manhã natural, tarde invertido
        return (C1, C2) if periodo == "manhã" else (C2, C1)
    if periodo == "manhã":
        return (origem, destino)
    else:
        return (destino, origem)


def _solicitar_cidade_uf() -> tuple[str, str]:
    """Pede cidade e UF ao usuário via input(), com validação."""
    while True:
        cidade = input("Cidade: ").strip()
        if cidade:
            break
        print("⚠️  Cidade não pode ser vazia.")
    while True:
        uf = input("UF (sigla, 2 letras): ").strip().upper()
        if len(uf) == 2 and uf.isalpha():
            break
        print("⚠️  UF deve ter 2 letras (ex: AP, SP, RJ).")
    return cidade, uf


def main(cidade: str, uf: str):
    """Descobre C1, C2, E1, E2, M1, M2 para a cidade informada, com cache no banco SQLite."""
    from persistencia.repositorio_banco import RepositorioBanco

    repo = RepositorioBanco("mobilidade.db")
    repo.inicializar()

    locais = repo.listar_locais(cidade, uf)
    cache = {l.codigo: l for l in locais}

    if len(cache) == 6:
        print(f"📌 Todos os 6 locais já cadastrados para {cidade}/{uf}:")
        for l in locais:
            print(f"   {l.codigo} — {l.endereco} ({l.lat}, {l.lon})")
        repo.fechar()
        resposta = input("\nDeseja usar estas localizações ou buscar novas? (1=usar / 2=buscar novas): ").strip()
        if resposta == "1":
            gerar_agendamentos(cidade, uf)
            return
        # 2 (ou qualquer outra coisa) → redescobrir
        cache = {}
        repo = RepositorioBanco("mobilidade.db")
        repo.inicializar()

    for codigo in ["C1", "C2", "E1", "E2", "M1", "M2"]:
        if codigo in cache:
            print(f"📌 {codigo} já cadastrado: {cache[codigo].endereco} ({cache[codigo].lat}, {cache[codigo].lon})")

    bbox = buscar_bounding_box(cidade, uf)
    min_lat, max_lat, min_lon, max_lon, centro_lat, centro_lon = bbox

    # C1
    c1 = cache.get("C1")
    if not c1:
        c1 = buscar_c1(min_lat, max_lat, min_lon, max_lon, centro_lat, centro_lon, cidade, uf)
        time.sleep(1)

    # C2
    c2 = cache.get("C2")
    if not c2:
        c2 = buscar_c2(min_lat, max_lat, min_lon, max_lon, centro_lat, centro_lon, c1.lat, c1.lon, cidade, uf)

    # E1, E2
    e1 = cache.get("E1")
    e2 = cache.get("E2")
    if not e1 or not e2:
        time.sleep(3)  # Rate limit Overpass
        e1_novo, e2_novo = buscar_extremos(min_lat, max_lat, min_lon, max_lon, centro_lat, centro_lon, cidade, uf)
        if not e1:
            e1 = e1_novo
        if not e2:
            e2 = e2_novo

    # M1, M2
    m1 = cache.get("M1")
    m2 = cache.get("M2")
    if not m1 or not m2:
        m1_novo, m2_novo = buscar_bairros(c1, c2, e1, e2, cidade, uf)
        if not m1:
            m1 = m1_novo
        if not m2:
            m2 = m2_novo

    todos = [c1, c2, e1, e2, m1, m2]
    if len(cache) < 6:
        repo.salvar_locais(todos)
        print(f"💾 6 locais salvos no banco")

    repo.fechar()

    gerar_agendamentos(cidade, uf)


if __name__ == "__main__":
    cidade, uf = _solicitar_cidade_uf()
    main(cidade, uf)
