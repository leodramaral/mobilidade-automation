import sqlite3
import structlog

logger = structlog.get_logger("migracoes")


def aplicar_migracao_0001_inicial(conn: sqlite3.Connection):
    conn.execute("""
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON snapshots(timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_device ON snapshots(device_model)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_app ON snapshots(app)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS locais_coleta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL,
            endereco TEXT NOT NULL,
            cidade TEXT NOT NULL,
            uf TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            tipo TEXT NOT NULL,
            criado_em TEXT DEFAULT (datetime('now')),
            UNIQUE(codigo, cidade, uf)
        )
    """)


def aplicar_migracao_0002_remover_nome_locais_coleta(conn: sqlite3.Connection):
    try:
        conn.execute("ALTER TABLE locais_coleta DROP COLUMN nome")
    except sqlite3.OperationalError:
        # Coluna já não existe ou tabela é nova
        pass


# Lista ordenada de migrações
MIGRACOES = [
    ("0001_inicial", aplicar_migracao_0001_inicial),
    ("0002_remover_nome_locais_coleta", aplicar_migracao_0002_remover_nome_locais_coleta),
]


def executar_migracoes(conn: sqlite3.Connection) -> None:
    # Garante que a tabela de migrações existe
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            versao TEXT PRIMARY KEY,
            aplicada_em TEXT DEFAULT (datetime('now'))
        )
    """)

    # Obtém migrações já executadas
    cursor = conn.execute("SELECT versao FROM schema_migrations")
    executadas = {row[0] for row in cursor.fetchall()}

    for versao, func in MIGRACOES:
        if versao not in executadas:
            logger.info("Aplicando migração", versao=versao)
            func(conn)
            conn.execute("INSERT INTO schema_migrations (versao) VALUES (?)", (versao,))
            conn.commit()
            logger.info("Migração aplicada com sucesso", versao=versao)
