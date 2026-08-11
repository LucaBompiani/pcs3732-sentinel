import pytest

from src.sentinel.infra.db import connect
from src.sentinel.infra.users_repository import create_user
from src.sentinel.app.state_machine import run_access_attempt


@pytest.fixture
def conn():
    c = connect(":memory:")
    create_user(c, "joao", "1234")
    create_user(c, "maria", "5678")
    return c


def test_autoriza_com_face_e_pin_corretos(conn):
    autorizado, fator1_ok, fator2_ok = run_access_attempt(conn, "joao", "1234")
    assert (autorizado, fator1_ok, fator2_ok) == (True, True, True)


def test_nega_com_face_nao_reconhecida(conn):
    autorizado, fator1_ok, fator2_ok = run_access_attempt(conn, "fantasma", "1234")
    assert (autorizado, fator1_ok, fator2_ok) == (False, False, False)


def test_nega_com_pin_errado(conn):
    autorizado, fator1_ok, fator2_ok = run_access_attempt(conn, "joao", "0000")
    assert (autorizado, fator1_ok, fator2_ok) == (False, True, False)


def test_nega_pin_de_outro_usuario_cadastrado(conn):
    """RF05: o Fator 2 deve corresponder ao usuario identificado no Fator 1,
    nao a qualquer PIN valido da base."""
    autorizado, fator1_ok, fator2_ok = run_access_attempt(conn, "joao", "5678")
    assert (autorizado, fator1_ok, fator2_ok) == (False, True, False)


def test_tentativa_registra_evento_no_log(conn):
    run_access_attempt(conn, "joao", "1234")

    resultado = conn.execute("SELECT resultado FROM events").fetchone()[0]

    assert resultado == "AUTORIZADO"
