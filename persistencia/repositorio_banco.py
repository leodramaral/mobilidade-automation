import json
import sqlite3
from datetime import datetime
from typing import List

from persistencia.base import BaseRepositorio
from modelos.corrida import Corrida


class RepositorioBanco(BaseRepositorio):
    def __init__(self, caminho: str):
        self.caminho = caminho
        self.conn = None

    def inicializar(self) -> None:
        self.conn = sqlite3.connect(self.caminho)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS corridas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                app TEXT NOT NULL,
                categoria TEXT NOT NULL,
                preco REAL NOT NULL,
                estimativa INTEGER NOT NULL,
                origem TEXT NOT NULL,
                destino TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_corridas_timestamp ON corridas(timestamp)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_corridas_destino ON corridas(destino)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_corridas_origem ON corridas(origem)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_corridas_categoria ON corridas(categoria)")
        self.conn.commit()

    def salvar(self, corridas: List[Corrida], rodada: int) -> None:
        dados = [
            (c.app, c.categoria, c.preco, c.estimativa, c.origem, c.destino, c.timestamp.isoformat())
            for c in corridas
        ]
        self.conn.executemany(
            "INSERT INTO corridas (app, categoria, preco, estimativa, origem, destino, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            dados
        )
        self.conn.commit()
        for c in corridas:
            print(f"  -> {c.categoria}: R${c.preco} ({c.estimativa} min)")

    def consultar_por_periodo(self, inicio: datetime, fim: datetime) -> List[Corrida]:
        cursor = self.conn.execute(
            "SELECT app, categoria, preco, estimativa, origem, destino, timestamp "
            "FROM corridas WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp",
            (inicio.isoformat(), fim.isoformat())
        )
        return [
            Corrida(
                app=row[0], categoria=row[1], preco=row[2],
                estimativa=row[3], origem=row[4], destino=row[5],
                timestamp=datetime.fromisoformat(row[6])
            )
            for row in cursor.fetchall()
        ]

    def exportar_json(self, inicio: datetime, fim: datetime, caminho: str) -> None:
        corridas = self.consultar_por_periodo(inicio, fim)
        dados = [
            {
                "app": c.app,
                "categoria": c.categoria,
                "preco": c.preco,
                "estimativa_min": c.estimativa,
                "origem": c.origem,
                "destino": c.destino,
                "timestamp": c.timestamp.isoformat()
            }
            for c in corridas
        ]
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        print(f"Exportados {len(dados)} registros para {caminho}")

    def fechar(self) -> None:
        if self.conn:
            self.conn.close()
