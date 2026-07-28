"""Acesso à tabela de eventos (log de auditoria)."""

from datetime import datetime, timezone


def log_event(conn, username, fator1_ok, fator2_ok, resultado):
    conn.execute(
        "INSERT INTO events (timestamp, username, fator1_ok, fator2_ok, resultado) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            datetime.now(timezone.utc).isoformat(),
            username,
            int(fator1_ok),
            int(fator2_ok),
            resultado,
        ),
    )
    conn.commit()
