import pytest

from src.sentinel.infra.db import connect
from src.sentinel.infra.users_repository import create_user
from src.sentinel.services import second_factor


@pytest.fixture
def conn():
    c = connect(":memory:")
    create_user(c, "joao", "1234")
    return c


def test_pin_correto_verifica_ok(conn):
    assert second_factor.verify(conn, "joao", "1234") is True


def test_pin_incorreto_falha(conn):
    assert second_factor.verify(conn, "joao", "9999") is False


def test_pin_de_usuario_inexistente_falha(conn):
    assert second_factor.verify(conn, "fantasma", "1234") is False
