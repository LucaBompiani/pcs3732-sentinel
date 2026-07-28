import pytest

from src.sentinel.infra.db import connect
from src.sentinel.infra.events_repository import log_event


@pytest.fixture
def conn():
    return connect(":memory:")


def test_log_event_persiste_evento(conn):
    log_event(conn, username="joao", fator1_ok=True, fator2_ok=True, resultado="AUTORIZADO")

    row = conn.execute(
        "SELECT username, fator1_ok, fator2_ok, resultado FROM events"
    ).fetchone()

    assert row == ("joao", 1, 1, "AUTORIZADO")


def test_log_event_aceita_username_nulo(conn):
    log_event(conn, username=None, fator1_ok=False, fator2_ok=False, resultado="NEGADO")

    row = conn.execute("SELECT username, resultado FROM events").fetchone()

    assert row == (None, "NEGADO")


def test_log_event_registra_timestamp(conn):
    log_event(conn, username="joao", fator1_ok=True, fator2_ok=False, resultado="NEGADO")

    timestamp = conn.execute("SELECT timestamp FROM events").fetchone()[0]

    assert timestamp is not None and len(timestamp) > 0
