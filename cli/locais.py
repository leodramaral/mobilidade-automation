import math
import sys
import time

import requests
import structlog
from persistencia.repositorio_banco import RepositorioBanco

logger = structlog.get_logger("cli.locais")

NOMES_GENERICOS = [
    "posto ipiranga", "posto shell", "posto br", "posto ale", "posto petrobras",
    "posto texaco", "posto raízen",
    "supermercados dia", "atacadão", "atacadao", "atacare", "assai", "carrefour",
    "atacad", "prezunic", "guanabara", "super bom", "extra",
    "mcdonald", "burger king", "subway", "bobs", "habib",
    "kfc", "giraffa", "spoleto", "girafas",
    "igreja universal", "assembleia de deus", "igreja mundial",
    "congregação cristã", "testemunha de jeová", "congregacao crista",
    "smart fit", "bluefit", "bodytech",
    "drogasil", "drogaraia", "pague menos", "são joão",
    "drogaria sp", "drogaria araujo", "extrafarma", "drogaria venancio",
    "cacau show", "o boticário", "boticario", "quem disse berenice", "havanna",
    "kopenhagen",
    "caixa econômica", "banco do brasil", "bradesco", "itaú", "itau",
    "santander", "banco safra",
    "magazine luiza", "casas bahia", "americanas", "renner", "riachuelo",
    "marisa", "ce&a", "cea", "pernambucanas",
    "am/pm", "shell select", "br mania", "localiza",
    "havaianas", "milwaukee", "lupo",
]


def _nome_generico(elemento):
    tags = elemento.get("tags", {})
    nome = (tags.get("name") or "").lower()
    brand = (tags.get("brand") or "").lower()
    if brand and len(brand) >= 3 and brand in nome:
        return True
    for padrao in NOMES_GENERICOS:
        if padrao in nome:
            return True
    return False


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
    """Retorna (min_lat, max_lat, min_lon, max_lon, centro_lat, centro_lon, diametro_km) para a cidade."""
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

    largura_km = haversine(centro_lat, min_lon, centro_lat, max_lon)
    altura_km = haversine(min_lat, centro_lon, max_lat, centro_lon)
    diametro_km = (largura_km + altura_km) / 2

    print(f"📍 {item.get('display_name', query)}")
    print(f"   Centro: ({centro_lat}, {centro_lon})")
    print(f"   BBox: [{min_lat}, {max_lat}, {min_lon}, {max_lon}]")
    print(f"   Diâmetro estimado: {diametro_km:.1f}km ({largura_km:.1f}×{altura_km:.1f})")

    return (min_lat, max_lat, min_lon, max_lon, centro_lat, centro_lon, diametro_km)


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
    """Descobre C1: POI nomeado e não-genérico mais próximo do centro da cidade."""
    from modelos.local_coleta import LocalColeta

    query = f"""
    [out:json];
    (
      node[amenity]({min_lat},{min_lon},{max_lat},{max_lon});
      node[shop]({min_lat},{min_lon},{max_lat},{max_lon});
      node[tourism]({min_lat},{min_lon},{max_lat},{max_lon});
      node[historic]({min_lat},{min_lon},{max_lat},{max_lon});
      node[leisure]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out center;
    """

    elementos = _overpass_query(query)
    validos = [e for e in elementos if e.get("tags", {}).get("name") and not _nome_generico(e)]

    if not validos:
        print("⚠️  Nenhum local não-genérico encontrado — usando centro da cidade como C1")
        nome = f"Centro, {cidade}"
        return LocalColeta(
            codigo="C1", endereco=f"Centro, {cidade}, {uf}",
            cidade=cidade, uf=uf, lat=centro_lat, lon=centro_lon, tipo="central",
        )

    mais_perto = min(
        validos,
        key=lambda e: haversine(centro_lat, centro_lon, e.get("lat", 0), e.get("lon", 0)),
    )
    lat = mais_perto.get("lat", centro_lat)
    lon = mais_perto.get("lon", centro_lon)
    nome = mais_perto.get("tags", {}).get("name", f"Centro, {cidade}")
    rua = _obter_rua(lat, lon)
    genericos_filtrados = len(elementos) - len(validos)
    total = len(elementos)
    print(f"🏙️  C1: {nome} ({lat}, {lon}) — {genericos_filtrados} genéricos filtrados de {total} POIs")
    return LocalColeta(codigo="C1", endereco=f"{nome}, {rua}, {cidade}, {uf}", cidade=cidade, uf=uf, lat=lat, lon=lon, tipo="central")


def buscar_c2(min_lat: float, max_lat: float, min_lon: float, max_lon: float,
              centro_lat: float, centro_lon: float, c1_lat: float, c1_lon: float,
              cidade: str, uf: str, diametro_km: float):
    """Descobre C2: POI não-genérico com separação mínima de C1."""
    from modelos.local_coleta import LocalColeta

    min_dist = max(diametro_km * 0.15, 1.0)
    print(f"   🔍 Buscando C2 a ≥{min_dist:.1f}km de C1...")

    query = f"""
    [out:json];
    (
      node[amenity]({min_lat},{min_lon},{max_lat},{max_lon});
      node[shop]({min_lat},{min_lon},{max_lat},{max_lon});
      node[tourism]({min_lat},{min_lon},{max_lat},{max_lon});
      node[historic]({min_lat},{min_lon},{max_lat},{max_lon});
      node[leisure]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out center;
    """
    elementos = _overpass_query(query)

    def _selecionar(min_dist):
        candidatos = [
            e for e in elementos
            if e.get("tags", {}).get("name")
            and not _nome_generico(e)
            and haversine(c1_lat, c1_lon, e.get("lat", 0), e.get("lon", 0)) >= min_dist
        ]
        if not candidatos:
            return None
        return min(
            candidatos,
            key=lambda e: haversine(centro_lat, centro_lon, e.get("lat", 0), e.get("lon", 0)),
        )

    selecionado = _selecionar(min_dist)

    if selecionado is None:
        min_dist_fallback = max(diametro_km * 0.05, 0.3)
        print(f"   ⚠️  Nenhum POI não-genérico a ≥{min_dist:.1f}km — relaxando para ≥{min_dist_fallback:.1f}km")
        selecionado = _selecionar(min_dist_fallback)

    if selecionado is None:
        raise ValueError(f"Nenhum POI não-genérico adequado para C2 em {cidade}/{uf}")

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
    time.sleep(1)
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
                    centro_lat: float, centro_lon: float, cidade: str, uf: str,
                    diametro_km: float, usadas: set = None):
    """Descobre E1 e E2: extremos opostos dentro do perímetro urbano."""
    from modelos.local_coleta import LocalColeta

    usadas = usadas or set()

    query = f"""
    [out:json];
    (
      node[amenity]({min_lat},{min_lon},{max_lat},{max_lon});
      node[shop]({min_lat},{min_lon},{max_lat},{max_lon});
      node[tourism]({min_lat},{min_lon},{max_lat},{max_lon});
      node[historic]({min_lat},{min_lon},{max_lat},{max_lon});
      node[leisure]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out center;
    """
    elementos = _overpass_query(query)

    pois_todos = [
        e for e in elementos
        if e.get("tags", {}).get("name")
        and not _nome_generico(e)
        and (round(e.get("lat", 0), 7), round(e.get("lon", 0), 7)) not in usadas
    ]

    raio_km = max(diametro_km * 0.45, 3.0)
    while True:
        pois = [
            e for e in pois_todos
            if haversine(centro_lat, centro_lon, e.get("lat", 0), e.get("lon", 0)) <= raio_km
        ]
        if len(pois) >= 6 or raio_km >= max(diametro_km * 0.8, 30):
            break
        raio_km *= 1.5

    print(f"🎯 {len(pois)} POIs em raio urbano de {raio_km:.0f}km (total: {len(pois_todos)})")

    if len(pois) < 2:
        print(f"⚠️  Apenas {len(pois)} POIs no raio urbano — usando cantos da bounding box")
        e1_lat, e1_lon = max_lat, max_lon
        e2_lat, e2_lon = min_lat, min_lon
        nome_e1 = _reverse_geocode(e1_lat, e1_lon, cidade)
        nome_e2 = _reverse_geocode(e2_lat, e2_lon, cidade)
    else:
        def _score_nw(e):
            elat = e.get("lat", centro_lat)
            elon = e.get("lon", centro_lon)
            return (elat - centro_lat) + (centro_lon - elon)

        e1 = max(pois, key=_score_nw)
        e1_lat = e1.get("lat", centro_lat)
        e1_lon = e1.get("lon", centro_lon)
        nome_e1 = e1.get("tags", {}).get("name", "Extremo 1")

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
    genericos_filtrados = len(elementos) - len(pois_todos)
    print(f"🏪 E1: {nome_e1} ({e1_lat}, {e1_lon}) — {e1_dist:.1f}km do centro")
    print(f"🏪 E2: {nome_e2} ({e2_lat}, {e2_lon}) — {e2_dist:.1f}km do centro | {genericos_filtrados} genéricos filtrados")

    rua_e1 = _obter_rua(e1_lat, e1_lon)
    rua_e2 = _obter_rua(e2_lat, e2_lon)
    e1_local = LocalColeta(codigo="E1", endereco=f"{nome_e1}, {rua_e1}, {cidade}, {uf}", cidade=cidade, uf=uf, lat=e1_lat, lon=e1_lon, tipo="extremo")
    e2_local = LocalColeta(codigo="E2", endereco=f"{nome_e2}, {rua_e2}, {cidade}, {uf}", cidade=cidade, uf=uf, lat=e2_lat, lon=e2_lon, tipo="extremo")
    return e1_local, e2_local


def buscar_bairros(c1, c2, e1, e2, cidade: str, uf: str, diametro_km: float,
                   usadas: set = None):
    """Descobre M1 e M2: pontos médios entre extremos e centros, ancorados em POIs reais."""
    from modelos.local_coleta import LocalColeta

    usadas = usadas or set()

    def _warp_para_poi(lat_base, lon_base, raio_m=800):
        query = f"""
        [out:json];
        (
          node(around:{raio_m},{lat_base},{lon_base})[amenity];
          node(around:{raio_m},{lat_base},{lon_base})[shop];
          node(around:{raio_m},{lat_base},{lon_base})[tourism];
          node(around:{raio_m},{lat_base},{lon_base})[leisure];
        );
        out center;
        """
        elementos = _overpass_query(query)
        nomes = [e for e in elementos
                 if e.get("tags", {}).get("name")
                 and not _nome_generico(e)
                 and (round(e.get("lat", 0), 7), round(e.get("lon", 0), 7)) not in usadas]
        if nomes:
            mais_perto = min(nomes, key=lambda e: haversine(
                lat_base, lon_base, e.get("lat", 0), e.get("lon", 0)))
            return (mais_perto.get("lat", lat_base),
                    mais_perto.get("lon", lon_base),
                    mais_perto.get("tags", {}).get("name"))
        return (lat_base, lon_base, None)

    m1_lat, m1_lon, nome_poi = _warp_para_poi((e1.lat + c1.lat) / 2, (e1.lon + c1.lon) / 2)
    if nome_poi:
        nome_m1 = nome_poi
        print(f"🏘️  M1: {nome_m1} ({m1_lat}, {m1_lon}) — POI entre E1 e C1")
    else:
        nome_m1 = _reverse_geocode(m1_lat, m1_lon, cidade)
        print(f"🏘️  M1: {nome_m1} ({m1_lat}, {m1_lon}) — midpoint(E1, C1)")

    m2_lat, m2_lon, nome_poi = _warp_para_poi((e2.lat + c2.lat) / 2, (e2.lon + c2.lon) / 2)
    if nome_poi:
        nome_m2 = nome_poi
        print(f"🏘️  M2: {nome_m2} ({m2_lat}, {m2_lon}) — POI entre E2 e C2")
    else:
        nome_m2 = _reverse_geocode(m2_lat, m2_lon, cidade)
        print(f"🏘️  M2: {nome_m2} ({m2_lat}, {m2_lon}) — midpoint(E2, C2)")

    rua_m1 = _obter_rua(m1_lat, m1_lon)
    rua_m2 = _obter_rua(m2_lat, m2_lon)
    m1 = LocalColeta(codigo="M1", endereco=f"{nome_m1}, {rua_m1}, {cidade}, {uf}", cidade=cidade, uf=uf, lat=m1_lat, lon=m1_lon, tipo="bairro")
    m2 = LocalColeta(codigo="M2", endereco=f"{nome_m2}, {rua_m2}, {cidade}, {uf}", cidade=cidade, uf=uf, lat=m2_lat, lon=m2_lon, tipo="bairro")
    return m1, m2


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


def gerar(cidade: str | None = None, uf: str | None = None) -> None:
    """Gera os 6 locais (C1, C2, E1, E2, M1, M2) para uma cidade."""

    if cidade is None or uf is None:
        cidade, uf = _solicitar_cidade_uf()

    repo = RepositorioBanco("mobilidade.db")
    repo.inicializar()

    locais = repo.listar_locais(cidade, uf)
    cache = {l.codigo: l for l in locais}

    if len(cache) == 6:
        print(f"📌 Todos os 6 locais ja cadastrados para {cidade}/{uf}:")
        for l in locais:
            print(f"   {l.codigo} — {l.endereco} ({l.lat}, {l.lon})")
        repo.fechar()
        resposta = input("\nDeseja usar estas localizacoes ou buscar novas? (1=usar / 2=buscar novas): ").strip()
        if resposta == "1":
            print(f"\n💡 Agora gere os agendamentos com:\n   python main.py agendamentos gerar")
            return
        cache = {}
        repo = RepositorioBanco("mobilidade.db")
        repo.inicializar()

    for codigo in ["C1", "C2", "E1", "E2", "M1", "M2"]:
        if codigo in cache:
            print(f"📌 {codigo} ja cadastrado: {cache[codigo].endereco} "
                  f"({cache[codigo].lat}, {cache[codigo].lon})")

    bbox = buscar_bounding_box(cidade, uf)
    min_lat, max_lat, min_lon, max_lon, centro_lat, centro_lon, diametro_km = bbox

    c1 = cache.get("C1")
    if not c1:
        c1 = buscar_c1(min_lat, max_lat, min_lon, max_lon, centro_lat, centro_lon, cidade, uf)
        time.sleep(1)

    c2 = cache.get("C2")
    if not c2:
        c2 = buscar_c2(min_lat, max_lat, min_lon, max_lon, centro_lat, centro_lon,
                       c1.lat, c1.lon, cidade, uf, diametro_km)

    usadas = {(c1.lat, c1.lon), (c2.lat, c2.lon)}

    e1 = cache.get("E1")
    e2 = cache.get("E2")
    if not e1 or not e2:
        time.sleep(3)
        e1_novo, e2_novo = buscar_extremos(min_lat, max_lat, min_lon, max_lon,
                                           centro_lat, centro_lon, cidade, uf, diametro_km, usadas)
        if not e1:
            e1 = e1_novo
        if not e2:
            e2 = e2_novo

    usadas |= {(e1.lat, e1.lon), (e2.lat, e2.lon)}

    m1 = cache.get("M1")
    m2 = cache.get("M2")
    if not m1 or not m2:
        m1_novo, m2_novo = buscar_bairros(c1, c2, e1, e2, cidade, uf, diametro_km, usadas)
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
    print(f"\n💡 Agora gere os agendamentos com:\n   python main.py agendamentos gerar")
