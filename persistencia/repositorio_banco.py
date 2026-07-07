import json
import sqlite3
from datetime import datetime
from typing import List

from persistencia.base import BaseRepositorio
from modelos.corrida import Corrida, Snapshot


class RepositorioBanco(BaseRepositorio):
    def __init__(self, caminho: str):
        self.caminho = caminho
        self.conn = None

    def inicializar(self) -> None:
        self.conn = sqlite3.connect(self.caminho)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                device_model TEXT,
                payload_json TEXT NOT NULL
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON snapshots(timestamp)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_device ON snapshots(device_model)")
        self.conn.commit()

    def salvar(self, corridas: List[Corrida], rodada: int, device_model: str = '') -> None:
        if not corridas:
            return

        timestamp = corridas[0].timestamp.isoformat()
        payload = json.dumps([c.para_dict() for c in corridas], ensure_ascii=False)

        self.conn.execute(
            "INSERT INTO snapshots (timestamp, device_model, payload_json) VALUES (?, ?, ?)",
            (timestamp, device_model, payload)
        )
        self.conn.commit()

        for c in corridas:
            print(f"  -> {c.categoria}: R${c.preco} ({c.estimativa} min)")

    def consultar_por_periodo(self, inicio: datetime, fim: datetime) -> List[Snapshot]:
        cursor = self.conn.execute(
            "SELECT id, timestamp, device_model, payload_json "
            "FROM snapshots WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp",
            (inicio.isoformat(), fim.isoformat())
        )
        return [
            Snapshot(
                id=row[0],
                timestamp=datetime.fromisoformat(row[1]),
                device_model=row[2] or '',
                payload=json.loads(row[3]),
            )
            for row in cursor.fetchall()
        ]

    def exportar_json(self, inicio: datetime, fim: datetime, caminho: str) -> None:
        snapshots = self.consultar_por_periodo(inicio, fim)
        dados = [
            {
                "id": s.id,
                "timestamp": s.timestamp.isoformat(),
                "resultados": s.payload,
            }
            for s in snapshots
        ]
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        print(f"Exportados {len(dados)} snapshots para {caminho}")

    def fechar(self) -> None:
        if self.conn:
            self.conn.close()
