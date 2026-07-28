"""Acesso à tabela de usuários (cadastro e verificação do Fator 2)."""

from sentinel.infra.security import hash_pin


def create_user(conn, username, pin):
    conn.execute(
        "INSERT INTO users (username, pin_hash) VALUES (?, ?)",
        (username, hash_pin(pin)),
    )
    conn.commit()


def user_exists(conn, username):
    row = conn.execute(
        "SELECT 1 FROM users WHERE username = ?", (username,)
    ).fetchone()
    return row is not None


def verify_pin(conn, username, pin):
    row = conn.execute(
        "SELECT pin_hash FROM users WHERE username = ?", (username,)
    ).fetchone()
    if row is None:
        return False
    return row[0] == hash_pin(pin)
