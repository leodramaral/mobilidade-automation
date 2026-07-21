import math
import os
import structlog
from PIL import ImageDraw, ImageFont
from staticmap import StaticMap, CircleMarker

from modelos.local_coleta import LocalColeta

logger = structlog.get_logger("servicos.mapa")

CORES_TIPO = {
    "central": "#1f77b4",
    "extremo": "#d62728",
    "bairro": "#2ca02c",
}
RAIO_MARCADOR = 12
TAMANHO_FONTE = 13

_FONTES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def _lat_lon_para_pixel(lat, lon, zoom, x_centro, y_centro, largura, altura):
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x_mundo = (lon + 180.0) / 360.0 * n * 256
    y_mundo = (
        1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi
    ) / 2.0 * n * 256
    px = largura / 2 + (x_mundo - x_centro)
    py = altura / 2 + (y_mundo - y_centro)
    return px, py


def _carregar_fonte():
    for caminho in _FONTES:
        try:
            return ImageFont.truetype(caminho, TAMANHO_FONTE)
        except (OSError, IOError):
            continue
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", TAMANHO_FONTE)
    except (OSError, IOError):
        pass
    tamanho_padrao = ImageFont.load_default()
    if hasattr(tamanho_padrao, "font_variant"):
        return tamanho_padrao
    return ImageFont.load_default()


def _desenhar_texto_com_contorno(draw, x, y, texto, cor, fonte):
    try:
        draw.text((x, y), texto, fill=cor, font=fonte, stroke_width=3, stroke_fill="#ffffff")
    except TypeError:
        draw.text((x - 1, y - 1), texto, fill="#ffffff", font=fonte)
        draw.text((x + 1, y - 1), texto, fill="#ffffff", font=fonte)
        draw.text((x - 1, y + 1), texto, fill="#ffffff", font=fonte)
        draw.text((x + 1, y + 1), texto, fill="#ffffff", font=fonte)
        draw.text((x, y), texto, fill=cor, font=fonte)


class MapaServico:
    @staticmethod
    def gerar_png(locais: list[LocalColeta], caminho_saida: str) -> str:
        mapa = StaticMap(900, 700, padding_x=80, padding_y=80)

        for local in locais:
            cor = CORES_TIPO.get(local.tipo, "#000000")
            marker = CircleMarker((local.lon, local.lat), cor, RAIO_MARCADOR)
            mapa.add_marker(marker)

        imagem = mapa.render()
        draw = ImageDraw.Draw(imagem)
        fonte = _carregar_fonte()

        for local in locais:
            px, py = _lat_lon_para_pixel(
                local.lat, local.lon,
                mapa.zoom, mapa.x_center, mapa.y_center,
                mapa.width, mapa.height,
            )
            cor = CORES_TIPO.get(local.tipo, "#000000")

            px = max(6, min(px, mapa.width - 6))
            py = max(6, min(py, mapa.height - 6))

            _desenhar_texto_com_contorno(draw, px + 16, py - 16, local.codigo, cor, fonte)

        os.makedirs(os.path.dirname(caminho_saida) or ".", exist_ok=True)
        imagem.save(caminho_saida, "PNG")
        logger.info("mapa_gerado", caminho=caminho_saida, zoom=mapa.zoom,
                     centro=(mapa.x_center, mapa.y_center))
        return caminho_saida
