import sqlite3
from datetime import datetime, timedelta
from typing import Optional

import structlog
import requests

logger = structlog.get_logger("clima")


class ClimaServico:
    CACHE_MINUTOS = 10
    API_URL = "https://api.openweathermap.org/data/2.5/weather"

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._criar_tabela()

    def _criar_tabela(self) -> None:
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS clima_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cidade TEXT NOT NULL,
                temperatura REAL NOT NULL,
                condicao TEXT NOT NULL,
                condicao_texto TEXT NOT NULL,
                consultado_em TEXT NOT NULL
            )
        """)
        self.conn.commit()

    def consultar(self, lat: float, lon: float, api_key: str) -> tuple[float, str]:
        chave_cache = f"{lat},{lon}"
        logger.info("Consultando clima", lat=lat, lon=lon)
        cache = self._buscar_cache(chave_cache)
        if cache is not None:
            logger.info("Usando cache", temperatura=cache[0], condicao=cache[1])
            return cache

        logger.info("Cache expirado, chamando API")
        resultado = self._buscar_api(lat, lon, api_key)
        if resultado is not None:
            self._salvar_cache(chave_cache, resultado["temperatura"], resultado["condicao"], resultado["condicao_texto"])
            return (resultado["temperatura"], resultado["condicao"])

        logger.error("Falha ao consultar clima")
        return (0.0, "Erro ao consultar clima")

    def _buscar_cache(self, chave: str) -> Optional[tuple[float, str]]:
        cursor = self.conn.execute(
            "SELECT temperatura, condicao, consultado_em FROM clima_cache "
            "WHERE cidade = ? ORDER BY consultado_em DESC LIMIT 1",
            (chave,),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        temperatura, condicao, consultado_em_str = row
        consultado_em = datetime.fromisoformat(consultado_em_str)
        if datetime.now() - consultado_em < timedelta(minutes=self.CACHE_MINUTOS):
            return (temperatura, condicao)

        return None

    def _buscar_api(self, lat: float, lon: float, api_key: str) -> Optional[dict]:
        logger.debug("Chamando API", lat=lat, lon=lon)
        try:
            resp = requests.get(
                self.API_URL,
                params={
                    "lat": lat,
                    "lon": lon,
                    "appid": api_key,
                    "units": "metric",
                    "lang": "pt_br",
                },
                timeout=10,
            )
            logger.debug("Resposta API", status=resp.status_code)
            resp.raise_for_status()
            dados = resp.json()

            temperatura = round(dados["main"]["temp"], 1)
            condicao = dados["weather"][0]["description"]

            return {
                "temperatura": temperatura,
                "condicao": condicao,
                "condicao_texto": f"{temperatura}°C - {condicao}",
            }
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else '?'
            logger.error("Erro HTTP", status=status, erro=str(e))
            if e.response is not None:
                logger.debug("Corpo da resposta", body=e.response.text[:500])
            return None
        except Exception as e:
            logger.error("Erro ao consultar API", erro_tipo=type(e).__name__, erro=str(e))
            return None

    def _salvar_cache(self, chave: str, temperatura: float, condicao: str, condicao_texto: str) -> None:
        self.conn.execute(
            "INSERT INTO clima_cache (cidade, temperatura, condicao, condicao_texto, consultado_em) "
            "VALUES (?, ?, ?, ?, ?)",
            (chave, temperatura, condicao, condicao_texto, datetime.now().isoformat()),
        )
        self.conn.commit()
