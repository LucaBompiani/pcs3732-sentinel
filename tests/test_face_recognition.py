import pytest

from src.sentinel.infra.db import connect
from src.sentinel.infra.users_repository import create_user
from src.sentinel.services import face_recognition


@pytest.fixture
def conn():
    c = connect(":memory:")
    create_user(c, "joao", "1234")
    return c


def test_reconhece_usuario_cadastrado(conn):
    assert face_recognition.recognize(conn, "joao") == "joao"


def test_nao_reconhece_usuario_desconhecido(conn):
    assert face_recognition.recognize(conn, "fantasma") is None


def test_nao_reconhece_quando_ninguem_presente(conn):
    assert face_recognition.recognize(conn, None) is None
