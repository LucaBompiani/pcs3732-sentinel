"""Acesso à tabela de eventos (log de auditoria)."""

from datetime import datetime, timezone


def log_event(conn, username, fator1_ok, fator2_ok, resultado, tipo="ACESSO"):
    """Registra um evento persistente com data/hora (RF09).

    Args:
        conn: Conexão SQLite.
        username: Usuário associado ao evento, ou ``None``.
        fator1_ok: Se o Fator 1 (facial) foi validado.
        fator2_ok: Se o Fator 2 (PIN/RFID) foi validado.
        resultado: Rótulo do desfecho (ex.: ``"AUTORIZADO"``, ``"NEGADO"``,
            ``"CADASTRO"``).
        tipo: Categoria do evento (``"ACESSO"`` por padrão, ``"CADASTRO"`` no
            fluxo de enrolamento).
    """
    conn.execute(
        "INSERT INTO events "
        "(timestamp, username, fator1_ok, fator2_ok, resultado, tipo) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            datetime.now(timezone.utc).isoformat(),
            username,
            int(fator1_ok),
            int(fator2_ok),
            resultado,
            tipo,
        ),
    )
    conn.commit()
