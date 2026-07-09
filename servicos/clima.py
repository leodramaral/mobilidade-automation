import sqlite3
from datetime import datetime, timedelta
from typing import Optional

import requests


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

    def consultar(self, lat: float, lon: float, api_key: str) -> str:
        chave_cache = f"{lat},{lon}"
        print(f"[Clima] Consultando clima para: lat={lat}, lon={lon}")
        cache = self._buscar_cache(chave_cache)
        if cache is not None:
            print(f"[Clima] Usando cache: {cache}")
            return cache

        print(f"[Clima] Cache expirado ou inexistente, chamando API...")
        resultado = self._buscar_api(lat, lon, api_key)
        if resultado is not None:
            self._salvar_cache(chave_cache, resultado["temperatura"], resultado["condicao"], resultado["condicao_texto"])
            print(f"[Clima] Sucesso: {resultado['condicao_texto']}")
            return resultado["condicao_texto"]

        print(f"[Clima] Falha ao consultar clima")
        return "Erro ao consultar clima"

    def _buscar_cache(self, chave: str) -> Optional[str]:
        cursor = self.conn.execute(
            "SELECT condicao_texto, consultado_em FROM clima_cache "
            "WHERE cidade = ? ORDER BY consultado_em DESC LIMIT 1",
            (chave,),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        texto, consultado_em_str = row
        consultado_em = datetime.fromisoformat(consultado_em_str)
        if datetime.now() - consultado_em < timedelta(minutes=self.CACHE_MINUTOS):
            return texto

        return None

    def _buscar_api(self, lat: float, lon: float, api_key: str) -> Optional[dict]:
        print(f"[Clima] Chamando API: lat={lat}, lon={lon}")
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
            print(f"[Clima] Resposta API: status={resp.status_code}")
            resp.raise_for_status()
            dados = resp.json()

            temperatura = round(dados["main"]["temp"], 1)
            condicao = dados["weather"][0]["description"]
            texto = f"{temperatura}°C - {condicao}"

            return {
                "temperatura": temperatura,
                "condicao": condicao,
                "condicao_texto": texto,
            }
        except requests.exceptions.HTTPError as e:
            print(f"[Clima] Erro HTTP: {e} (status {e.response.status_code if e.response else '?'})")
            if e.response is not None:
                print(f"[Clima] Corpo da resposta: {e.response.text[:500]}")
            return None
        except Exception as e:
            print(f"[Clima] Erro ao consultar API: {type(e).__name__}: {e}")
            return None

    def _salvar_cache(self, chave: str, temperatura: float, condicao: str, condicao_texto: str) -> None:
        self.conn.execute(
            "INSERT INTO clima_cache (cidade, temperatura, condicao, condicao_texto, consultado_em) "
            "VALUES (?, ?, ?, ?, ?)",
            (chave, temperatura, condicao, condicao_texto, datetime.now().isoformat()),
        )
        self.conn.commit()
