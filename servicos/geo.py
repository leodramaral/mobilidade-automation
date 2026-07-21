import math
import time
import requests
import structlog
from typing import Tuple, List, Set, Optional

from modelos.local_coleta import LocalColeta

logger = structlog.get_logger("servicos.geo")

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

NOMINATIM_URL = "https://nominatim.openstreetmap.org"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
HEADERS = {"User-Agent": "MobilidadeAutomation/1.0 (projeto@mobilidade.local)"}


class GeoServico:
    """Serviços geoespaciais: Nominatim, Overpass, haversine, geocoding reverso."""

    @staticmethod
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

    @staticmethod
    def _nome_generico(elemento: dict) -> bool:
        tags = elemento.get("tags", {})
        nome = (tags.get("name") or "").lower()
        brand = (tags.get("brand") or "").lower()
        if brand and len(brand) >= 3 and brand in nome:
            return True
        for padrao in NOMES_GENERICOS:
            if padrao in nome:
                return True
        return False

    @classmethod
    def buscar_bounding_box(cls, cidade: str, uf: str) -> tuple:
        """Retorna (min_lat, max_lat, min_lon, max_lon, centro_lat, centro_lon, diametro_km)."""
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

        largura_km = cls.haversine(centro_lat, min_lon, centro_lat, max_lon)
        altura_km = cls.haversine(min_lat, centro_lon, max_lat, centro_lon)
        diametro_km = (largura_km + altura_km) / 2

        print(f"📍 {item.get('display_name', query)}")
        print(f"   Centro: ({centro_lat}, {centro_lon})")
        print(f"   BBox: [{min_lat}, {max_lat}, {min_lon}, {max_lon}]")
        print(f"   Diâmetro estimado: {diametro_km:.1f}km ({largura_km:.1f}×{altura_km:.1f})")

        return (min_lat, max_lat, min_lon, max_lon, centro_lat, centro_lon, diametro_km)

    @classmethod
    def _overpass_query(cls, query: str) -> list:
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

    @classmethod
    def gerar_query_bbox(cls, min_lat: float, min_lon: float, max_lat: float, max_lon: float) -> str:
        """Gera query padronizada do Overpass para buscar POIs numa bounding box."""
        return f"""
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

    @classmethod
    def gerar_query_around(cls, centro_lat: float, centro_lon: float, raio_m: int) -> str:
        """Gera query Overpass filtrando por raio circular em torno do ponto central da cidade."""
        return f"""
        [out:json];
        (
          node(around:{raio_m},{centro_lat},{centro_lon})[amenity];
          node(around:{raio_m},{centro_lat},{centro_lon})[shop];
          node(around:{raio_m},{centro_lat},{centro_lon})[tourism];
          node(around:{raio_m},{centro_lat},{centro_lon})[historic];
          node(around:{raio_m},{centro_lat},{centro_lon})[leisure];
        );
        out center;
        """

    @classmethod
    def reverse_geocode(cls, lat: float, lon: float) -> dict:
        """Geocoding reverso via Nominatim. Retorna o dict 'address' da resposta."""
        time.sleep(1) # Respeito ao rate limit
        resp = requests.get(
            f"{NOMINATIM_URL}/reverse",
            params={"lat": lat, "lon": lon, "format": "json", "zoom": 18},
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("address", {})

    @classmethod
    def obter_rua(cls, lat: float, lon: float) -> str:
        """Nome da rua via geocoding reverso."""
        address = cls.reverse_geocode(lat, lon)
        return address.get("road") or address.get("path") or ""

    @classmethod
    def obter_bairro(cls, lat: float, lon: float, cidade: str) -> str:
        """Nome do bairro/local via geocoding reverso."""
        address = cls.reverse_geocode(lat, lon)

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
            nome_local = address.get("road") or "Bairro"

        return nome_local


class DescobridorLocais:
    """Descobre os 6 locais de coleta (C1, C2, E1, E2, M1, M2) via Overpass + Nominatim."""

    def __init__(self, geo: type[GeoServico] | None = None):
        self.geo = geo or GeoServico

    def _warp_para_poi(self, lat_base: float, lon_base: float, usadas: set,
                       raio_m: int = 800) -> tuple:
        """Ancora um ponto base no POI não-genérico mais próximo em raio_m metros."""
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
        elementos = self.geo._overpass_query(query)
        nomes = [
            e for e in elementos
            if e.get("tags", {}).get("name")
            and not self.geo._nome_generico(e)
            and (round(e.get("lat", 0), 7), round(e.get("lon", 0), 7)) not in usadas
        ]
        if nomes:
            mais_perto = min(nomes, key=lambda e: self.geo.haversine(
                lat_base, lon_base, e.get("lat", 0), e.get("lon", 0)))
            return (mais_perto.get("lat", lat_base),
                    mais_perto.get("lon", lon_base),
                    mais_perto.get("tags", {}).get("name"))
        return (lat_base, lon_base, None)

    def buscar_c1(self, min_lat: float, max_lat: float, min_lon: float, max_lon: float,
                  centro_lat: float, centro_lon: float, cidade: str, uf: str,
                  diametro_km: float = 12.0) -> LocalColeta:
        """Descobre C1: POI nomeado e não-genérico mais próximo do centro da cidade."""
        raio_busca = min(max(diametro_km * 0.25, 3.0), 8.0)
        query = self.geo.gerar_query_around(centro_lat, centro_lon, int(raio_busca * 1000))
        elementos = self.geo._overpass_query(query)
        validos = [e for e in elementos if e.get("tags", {}).get("name") and not self.geo._nome_generico(e)]

        if not validos:
            print("⚠️  Nenhum local não-genérico encontrado — usando centro da cidade como C1")
            return LocalColeta(
                codigo="C1", endereco=f"Centro, {cidade}, {uf}",
                cidade=cidade, uf=uf, lat=centro_lat, lon=centro_lon, tipo="central",
            )

        mais_perto = min(
            validos,
            key=lambda e: self.geo.haversine(centro_lat, centro_lon, e.get("lat", 0), e.get("lon", 0)),
        )
        lat = mais_perto.get("lat", centro_lat)
        lon = mais_perto.get("lon", centro_lon)
        nome = mais_perto.get("tags", {}).get("name", f"Centro, {cidade}")
        rua = self.geo.obter_rua(lat, lon)
        genericos_filtrados = len(elementos) - len(validos)
        print(f"🏙️  C1: {nome} ({lat}, {lon}) — {genericos_filtrados} genéricos filtrados de {len(elementos)} POIs")
        return LocalColeta(codigo="C1", endereco=f"{nome}, {rua}, {cidade}, {uf}", cidade=cidade, uf=uf, lat=lat, lon=lon, tipo="central")

    def buscar_c2(self, min_lat: float, max_lat: float, min_lon: float, max_lon: float,
                  centro_lat: float, centro_lon: float, c1_lat: float, c1_lon: float,
                  cidade: str, uf: str, diametro_km: float = 12.0) -> LocalColeta:
        """Descobre C2: POI não-genérico com separação mínima de C1."""
        min_dist = max(diametro_km * 0.15, 1.0)
        print(f"   🔍 Buscando C2 a ≥{min_dist:.1f}km de C1...")

        raio_busca = min(max(diametro_km * 0.25, 3.0), 8.0)
        query = self.geo.gerar_query_around(centro_lat, centro_lon, int(raio_busca * 1000))
        elementos = self.geo._overpass_query(query)

        def _selecionar(dist_min):
            candidatos = [
                e for e in elementos
                if e.get("tags", {}).get("name")
                and not self.geo._nome_generico(e)
                and self.geo.haversine(c1_lat, c1_lon, e.get("lat", 0), e.get("lon", 0)) >= dist_min
            ]
            if not candidatos:
                return None
            return min(
                candidatos,
                key=lambda e: self.geo.haversine(centro_lat, centro_lon, e.get("lat", 0), e.get("lon", 0)),
            )

        selecionado = _selecionar(min_dist)

        if selecionado is None:
            min_dist_fallback = max(diametro_km * 0.05, 0.3)
            print(f"   ⚠️  Nenhum POI não-genérico a ≥{min_dist:.1f}km — relaxando para ≥{min_dist_fallback:.1f}km")
            selecionado = _selecionar(min_dist_fallback)

        if selecionado is None:
            # Fallback urbano simétrico se não achar POI C2
            lat = centro_lat + 0.015
            lon = centro_lon + 0.015
            nome = f"Centro Secundário, {cidade}"
            rua = self.geo.obter_rua(lat, lon)
            return LocalColeta(codigo="C2", endereco=f"{nome}, {rua}, {cidade}, {uf}", cidade=cidade, uf=uf, lat=lat, lon=lon, tipo="central")

        lat = selecionado.get("lat", centro_lat)
        lon = selecionado.get("lon", centro_lon)
        nome = selecionado.get("tags", {}).get("name", f"POI, {cidade}")
        rua = self.geo.obter_rua(lat, lon)
        dist_m = self.geo.haversine(c1_lat, c1_lon, lat, lon) * 1000
        print(f"🏛️  C2: {nome} ({lat}, {lon}) — {dist_m:.0f}m de C1")
        return LocalColeta(codigo="C2", endereco=f"{nome}, {rua}, {cidade}, {uf}", cidade=cidade, uf=uf, lat=lat, lon=lon, tipo="central")

    def buscar_extremos(self, min_lat: float, max_lat: float, min_lon: float, max_lon: float,
                        centro_lat: float, centro_lon: float, cidade: str, uf: str,
                        diametro_km: float = 12.0, usadas: Set[Tuple[float, float]] = None) -> Tuple[LocalColeta, LocalColeta]:
        """Descobre E1 e E2: o par de POIs com maior distância absoluta entre si no raio urbano."""
        usadas = usadas or set()

        raio_inicial = min(max(diametro_km * 0.25, 3.0), 8.0)
        raio_maximo = min(max(diametro_km * 0.40, 4.5), 12.0)
        passo_expansao = 1.5

        raio_km = raio_inicial
        pois_todos = []
        elementos = []

        while True:
            query = self.geo.gerar_query_around(centro_lat, centro_lon, int(raio_km * 1000))
            elementos = self.geo._overpass_query(query)
            pois_todos = [
                e for e in elementos
                if e.get("tags", {}).get("name")
                and not self.geo._nome_generico(e)
                and (round(e.get("lat", 0), 7), round(e.get("lon", 0), 7)) not in usadas
            ]
            if len(pois_todos) >= 6 or raio_km >= raio_maximo:
                break
            raio_km = min(raio_km + passo_expansao, raio_maximo)

        print(f"🎯 {len(pois_todos)} POIs não-genéricos válidos no raio urbano dinâmico de {raio_km:.1f}km (diâmetro da sede: {diametro_km:.1f}km)")

        if len(pois_todos) >= 2:
            maior_dist = -1.0
            e1_sel, e2_sel = pois_todos[0], pois_todos[1]
            for i in range(len(pois_todos)):
                for j in range(i + 1, len(pois_todos)):
                    p1, p2 = pois_todos[i], pois_todos[j]
                    d = self.geo.haversine(p1.get("lat", 0), p1.get("lon", 0), p2.get("lat", 0), p2.get("lon", 0))
                    if d > maior_dist:
                        maior_dist = d
                        e1_sel, e2_sel = p1, p2

            e1_lat = e1_sel.get("lat", centro_lat)
            e1_lon = e1_sel.get("lon", centro_lon)
            nome_e1 = e1_sel.get("tags", {}).get("name", "Extremo 1")

            e2_lat = e2_sel.get("lat", centro_lat)
            e2_lon = e2_sel.get("lon", centro_lon)
            nome_e2 = e2_sel.get("tags", {}).get("name", "Extremo 2")

        elif len(pois_todos) == 1:
            print("⚠️  Apenas 1 POI válido no raio urbano — projetando E2 oposto na mancha urbana")
            e1 = pois_todos[0]
            e1_lat = e1.get("lat", centro_lat)
            e1_lon = e1.get("lon", centro_lon)
            nome_e1 = e1.get("tags", {}).get("name", "Extremo 1")

            vec_lat = e1_lat - centro_lat
            vec_lon = e1_lon - centro_lon
            if math.sqrt(vec_lat**2 + vec_lon**2) > 0:
                e2_lat = centro_lat - vec_lat
                e2_lon = centro_lon - vec_lon
            else:
                delta = (raio_km / 111.1) * 0.707
                e2_lat = centro_lat - delta
                e2_lon = centro_lon + delta
            nome_e2 = self.geo.obter_bairro(e2_lat, e2_lon, cidade)

        else:
            print("⚠️  Nenhum POI válido no raio urbano — calculando bordas NW e SE do raio urbano")
            delta_lat = (raio_km / 111.1) * 0.707
            delta_lon = (raio_km / (111.1 * math.cos(math.radians(centro_lat)))) * 0.707
            e1_lat = centro_lat + delta_lat
            e1_lon = centro_lon - delta_lon
            e2_lat = centro_lat - delta_lat
            e2_lon = centro_lon + delta_lon
            nome_e1 = self.geo.obter_bairro(e1_lat, e1_lon, cidade)
            nome_e2 = self.geo.obter_bairro(e2_lat, e2_lon, cidade)

        e1_dist = self.geo.haversine(centro_lat, centro_lon, e1_lat, e1_lon)
        e2_dist = self.geo.haversine(centro_lat, centro_lon, e2_lat, e2_lon)
        genericos_filtrados = len(elementos) - len(pois_todos)
        print(f"🏪 E1: {nome_e1} ({e1_lat}, {e1_lon}) — {e1_dist:.1f}km do centro")
        print(f"🏪 E2: {nome_e2} ({e2_lat}, {e2_lon}) — {e2_dist:.1f}km do centro | {genericos_filtrados} genéricos filtrados")

        rua_e1 = self.geo.obter_rua(e1_lat, e1_lon)
        rua_e2 = self.geo.obter_rua(e2_lat, e2_lon)
        e1_local = LocalColeta(codigo="E1", endereco=f"{nome_e1}, {rua_e1}, {cidade}, {uf}", cidade=cidade, uf=uf, lat=e1_lat, lon=e1_lon, tipo="extremo")
        e2_local = LocalColeta(codigo="E2", endereco=f"{nome_e2}, {rua_e2}, {cidade}, {uf}", cidade=cidade, uf=uf, lat=e2_lat, lon=e2_lon, tipo="extremo")
        return e1_local, e2_local

    def buscar_bairros(self, c1: LocalColeta, c2: LocalColeta, e1: LocalColeta, e2: LocalColeta, 
                       cidade: str, uf: str, diametro_km: float = 12.0,
                       usadas: Set[Tuple[float, float]] = None) -> Tuple[LocalColeta, LocalColeta]:
        """Descobre M1 e M2 no eixo perpendicular aos extremos (E1-E2) para cobrir os 360° da cidade."""
        usadas = usadas or set()

        centro_lat = (c1.lat + c2.lat) / 2
        centro_lon = (c1.lon + c2.lon) / 2

        vec_lat = e2.lat - e1.lat
        vec_lon = e2.lon - e1.lon
        norm = math.sqrt(vec_lat**2 + vec_lon**2)

        if norm > 0:
            perp_lat = -vec_lon / norm
            perp_lon = vec_lat / norm
        else:
            perp_lat, perp_lon = 0.707, 0.707

        dist_e1 = self.geo.haversine(centro_lat, centro_lon, e1.lat, e1.lon)
        dist_e2 = self.geo.haversine(centro_lat, centro_lon, e2.lat, e2.lon)
        base_dist = (dist_e1 + dist_e2) / 2
        dist_offset_km = min(max(base_dist * 0.5, 2.0), 6.0)

        delta_lat = perp_lat * (dist_offset_km / 111.1)
        delta_lon = perp_lon * (dist_offset_km / (111.1 * math.cos(math.radians(centro_lat))))

        base_m1_lat = centro_lat + delta_lat
        base_m1_lon = centro_lon + delta_lon
        base_m2_lat = centro_lat - delta_lat
        base_m2_lon = centro_lon - delta_lon

        def _garantir_ponto_urbano(lat_ini: float, lon_ini: float) -> Tuple[float, float, str, str]:
            lat, lon = lat_ini, lon_ini
            for _ in range(5):
                rua = self.geo.obter_rua(lat, lon)
                bairro = self.geo.obter_bairro(lat, lon, cidade)
                if rua:
                    return lat, lon, bairro, rua
                # Traz 20% mais próximo do centro
                lat = lat + (centro_lat - lat) * 0.20
                lon = lon + (centro_lon - lon) * 0.20
            return lat, lon, bairro, rua

        # M1
        m1_lat, m1_lon, nome_poi_1 = self._warp_para_poi(base_m1_lat, base_m1_lon, usadas)
        if nome_poi_1:
            nome_m1 = nome_poi_1
            rua_m1 = self.geo.obter_rua(m1_lat, m1_lon)
        else:
            m1_lat, m1_lon, nome_m1, rua_m1 = _garantir_ponto_urbano(m1_lat, m1_lon)

        # M2
        usadas_m2 = usadas | {(m1_lat, m1_lon)}
        m2_lat, m2_lon, nome_poi_2 = self._warp_para_poi(base_m2_lat, base_m2_lon, usadas_m2)
        if nome_poi_2:
            nome_m2 = nome_poi_2
            rua_m2 = self.geo.obter_rua(m2_lat, m2_lon)
        else:
            m2_lat, m2_lon, nome_m2, rua_m2 = _garantir_ponto_urbano(m2_lat, m2_lon)

        # Se os endereços completos forem idênticos, aplica um leve nudge em M2
        if f"{nome_m1}, {rua_m1}".lower() == f"{nome_m2}, {rua_m2}".lower():
            print("⚠️  M1 e M2 no mesmo endereço. Ajustando M2 ligeiramente...")
            m2_lat -= 0.0045
            m2_lon -= 0.0045
            m2_lat, m2_lon, nome_m2, rua_m2 = _garantir_ponto_urbano(m2_lat, m2_lon)

        print(f"🏘️  M1: {nome_m1} ({m1_lat:.5f}, {m1_lon:.5f}) — {rua_m1 or 'Sem rua'}")
        print(f"🏘️  M2: {nome_m2} ({m2_lat:.5f}, {m2_lon:.5f}) — {rua_m2 or 'Sem rua'}")

        m1 = LocalColeta(codigo="M1", endereco=f"{nome_m1}, {rua_m1}, {cidade}, {uf}", cidade=cidade, uf=uf, lat=m1_lat, lon=m1_lon, tipo="bairro")
        m2 = LocalColeta(codigo="M2", endereco=f"{nome_m2}, {rua_m2}, {cidade}, {uf}", cidade=cidade, uf=uf, lat=m2_lat, lon=m2_lon, tipo="bairro")
        return m1, m2
