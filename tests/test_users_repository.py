import sqlite3

import pytest

from src.sentinel.infra.db import connect
from src.sentinel.infra.users_repository import create_user, user_exists, verify_pin


@pytest.fixture
def conn():
    return connect(":memory:")


def test_user_exists_falso_quando_nao_cadastrado(conn):
    assert user_exists(conn, "joao") is False


def test_create_user_e_user_exists(conn):
    create_user(conn, "joao", "1234")
    assert user_exists(conn, "joao") is True


def test_verify_pin_correto(conn):
    create_user(conn, "joao", "1234")
    assert verify_pin(conn, "joao", "1234") is True


def test_verify_pin_incorreto(conn):
    create_user(conn, "joao", "1234")
    assert verify_pin(conn, "joao", "0000") is False


def test_verify_pin_usuario_inexistente(conn):
    assert verify_pin(conn, "fantasma", "1234") is False


def test_create_user_duplicado_falha(conn):
    create_user(conn, "joao", "1234")
    with pytest.raises(sqlite3.IntegrityError):
        create_user(conn, "joao", "0000")
