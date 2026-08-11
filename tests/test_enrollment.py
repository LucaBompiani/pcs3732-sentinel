import pytest

from src.sentinel.app.state_machine import run_enrollment
from src.sentinel.config import load_config
from src.sentinel.hal.factory import build_hal
from src.sentinel.infra.db import connect
from src.sentinel.infra.users_repository import (
    get_embeddings,
    user_exists,
    verify_card,
    verify_pin,
)

CFG = load_config()  # master_pin padrao "0000", face_samples 5


@pytest.fixture
def conn():
    return connect(":memory:")


def _events(conn):
    return conn.execute("SELECT resultado, tipo FROM events").fetchall()


def test_enrollment_creates_user_with_pin_and_card(conn):
    hal = build_hal(CFG)
    hal.keypad.feed(CFG.master_pin, "1234")  # PIN mestre, depois PIN do usuario
    hal.rfid.feed("CARD-JOAO")

    ok = run_enrollment(conn, hal, CFG, "joao")

    assert ok is True
    assert user_exists(conn, "joao")
    assert verify_pin(conn, "joao", "1234") is True
    assert verify_card(conn, "joao", "CARD-JOAO") is True
    assert len(get_embeddings(conn)) == CFG.face_samples
    assert ("CADASTRO", "CADASTRO") in _events(conn)


def test_enrollment_wrong_master_pin_aborts(conn):
    hal = build_hal(CFG)
    hal.keypad.feed("9999", "1234")  # PIN mestre incorreto

    ok = run_enrollment(conn, hal, CFG, "joao")

    assert ok is False
    assert not user_exists(conn, "joao")
    assert ("CADASTRO_NEGADO", "CADASTRO") in _events(conn)


def test_enrollment_existing_user_aborts(conn):
    hal = build_hal(CFG)
    hal.keypad.feed(CFG.master_pin, "1234")
    hal.rfid.feed("CARD-JOAO")
    assert run_enrollment(conn, hal, CFG, "joao") is True

    hal2 = build_hal(CFG)
    hal2.keypad.feed(CFG.master_pin, "0000")
    assert run_enrollment(conn, hal2, CFG, "joao") is False


def test_enrollment_without_second_factor_aborts(conn):
    hal = build_hal(CFG)
    hal.keypad.feed(CFG.master_pin)  # so o PIN mestre; nenhum 2o fator do usuario

    ok = run_enrollment(conn, hal, CFG, "joao")

    assert ok is False
    assert not user_exists(conn, "joao")
