"""Conexão, schema e migração do banco SQLite local."""

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    pin_hash TEXT NOT NULL,
    salt TEXT NOT NULL DEFAULT '',
    card_uid_hash TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    username TEXT,
    fator1_ok INTEGER NOT NULL,
    fator2_ok INTEGER NOT NULL,
    resultado TEXT NOT NULL,
    tipo TEXT NOT NULL DEFAULT 'ACESSO'
);

CREATE TABLE IF NOT EXISTS face_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    embedding BLOB NOT NULL,
    FOREIGN KEY (username) REFERENCES users (username)
);
"""

# Colunas acrescentadas após a versão inicial do schema. Para bancos em
# arquivo criados por versões antigas, precisam ser adicionadas via ALTER.
_ADDED_COLUMNS = {
    "users": [
        ("salt", "TEXT NOT NULL DEFAULT ''"),
        ("card_uid_hash", "TEXT"),
    ],
    "events": [
        ("tipo", "TEXT NOT NULL DEFAULT 'ACESSO'"),
    ],
}


def _column_names(conn, table):
    """Retorna o conjunto de nomes de coluna de uma tabela existente."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def _migrate(conn):
    """Adiciona colunas ausentes a bancos legados de forma idempotente.

    Bancos recém-criados já contêm todas as colunas de ``SCHEMA`` (inclusive
    ``:memory:``), tornando esta função um no-op nesses casos. Para arquivos
    antigos, aplica ``ALTER TABLE ... ADD COLUMN`` apenas para as colunas que
    faltarem, preservando os dados existentes (RNF03).
    """
    for table, columns in _ADDED_COLUMNS.items():
        existing = _column_names(conn, table)
        for name, definition in columns:
            if name not in existing:
                conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN {name} {definition}"
                )
    conn.commit()


def connect(db_path):
    """Abre uma conexão SQLite garantindo schema e migração aplicados.

    Args:
        db_path: Caminho do arquivo do banco, ou ``":memory:"``.

    Returns:
        Conexão :class:`sqlite3.Connection` com o schema criado e migrado.
    """
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn
