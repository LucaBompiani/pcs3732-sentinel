import pytest

from src.sentinel.infra.db import connect
from src.sentinel.infra.users_repository import create_user
from src.sentinel.services import second_factor


@pytest.fixture
def conn():
    c = connect(":memory:")
    create_user(c, "joao", "1234", card_uid="CARD-JOAO")
    create_user(c, "maria", "5678", card_uid="CARD-MARIA")
    return c


def test_card_matches_owner(conn):
    assert second_factor.verify(conn, "joao", card_uid="CARD-JOAO") is True


def test_card_of_another_user_fails(conn):
    # RF05: cartao da maria nao pode autorizar joao
    assert second_factor.verify(conn, "joao", card_uid="CARD-MARIA") is False


def test_wrong_card_fails(conn):
    assert second_factor.verify(conn, "joao", card_uid="CARD-X") is False


def test_pin_or_card_both_accepted(conn):
    assert second_factor.verify(conn, "joao", "1234") is True
    assert second_factor.verify(conn, "joao", card_uid="CARD-JOAO") is True
    # PIN errado mas cartao certo -> aceito (alternativos)
    assert second_factor.verify(conn, "joao", "0000", card_uid="CARD-JOAO") is True


def test_user_without_card_rejects_card(conn):
    create_user(conn, "ana", "9999")  # sem cartao
    assert second_factor.verify(conn, "ana", card_uid="CARD-JOAO") is False
    assert second_factor.verify(conn, "ana", "9999") is True
