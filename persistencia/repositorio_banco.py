import json
import sqlite3
from datetime import datetime
from typing import List, Optional

import structlog
from persistencia.base import BaseRepositorio
from modelos.corrida import Corrida, Snapshot

logger = structlog.get_logger("repositorio")


class RepositorioBanco(BaseRepositorio):
    def __init__(self, caminho: str):
        self.caminho = caminho
        self.conn: Optional[sqlite3.Connection] = None

    def inicializar(self) -> None:
        self.conn = sqlite3.connect(self.caminho)
        assert self.conn is not None
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                device_model TEXT,
                app TEXT NOT NULL DEFAULT '',
                origem TEXT NOT NULL DEFAULT '',
                destino TEXT NOT NULL DEFAULT '',
                temperatura REAL DEFAULT NULL,
                condicao_tempo TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON snapshots(timestamp)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_device ON snapshots(device_model)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_app ON snapshots(app)")
        self.conn.commit()

    def salvar(self, corridas: List[Corrida], rodada: int, device_model: str = '', temperatura: Optional[float] = None, condicao_tempo: str = '') -> None:
        if not corridas:
            return
        assert self.conn is not None

        timestamp = corridas[0].timestamp.isoformat()
        app = corridas[0].app
        origem = corridas[0].origem
        destino = corridas[0].destino
        payload = json.dumps([c.para_dict() for c in corridas], ensure_ascii=False)

        self.conn.execute(
            "INSERT INTO snapshots (timestamp, device_model, app, origem, destino, temperatura, condicao_tempo, payload_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (timestamp, device_model, app, origem, destino, temperatura, condicao_tempo, payload)
        )
        self.conn.commit()

        categorias = [c.categoria for c in corridas]
        logger.info("Corridas salvas", categorias=categorias)

    def listar_todos(self) -> List[Snapshot]:
        assert self.conn is not None
        cursor = self.conn.execute(
            "SELECT id, timestamp, device_model, app, origem, destino, temperatura, condicao_tempo, payload_json "
            "FROM snapshots ORDER BY timestamp"
        )
        return [
            Snapshot(
                id=row[0],
                timestamp=datetime.fromisoformat(row[1]),
                device_model=row[2] or '',
                app=row[3] or '',
                origem=row[4] or '',
                destino=row[5] or '',
                temperatura=row[6],
                condicao_tempo=row[7] or '',
                payload=json.loads(row[8]),
            )
            for row in cursor.fetchall()
        ]

    def fechar(self) -> None:
        if self.conn:
            self.conn.close()
