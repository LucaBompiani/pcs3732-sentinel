import pytest

from src.sentinel.infra.db import connect
from src.sentinel.infra.security import hash_pin
from src.sentinel.infra.users_repository import (
    create_user,
    set_card_uid,
    verify_card,
    verify_pin,
)


@pytest.fixture
def conn():
    return connect(":memory:")


def test_create_user_with_card(conn):
    create_user(conn, "joao", "1234", card_uid="CARD-JOAO")
    assert verify_card(conn, "joao", "CARD-JOAO") is True
    assert verify_pin(conn, "joao", "1234") is True


def test_set_card_uid_on_existing_user(conn):
    create_user(conn, "joao", "1234")
    assert verify_card(conn, "joao", "CARD-JOAO") is False
    assert set_card_uid(conn, "joao", "CARD-JOAO") is True
    assert verify_card(conn, "joao", "CARD-JOAO") is True


def test_set_card_uid_unknown_user(conn):
    assert set_card_uid(conn, "fantasma", "CARD-X") is False


def test_salt_is_used_and_stored(conn):
    create_user(conn, "joao", "1234")
    row = conn.execute(
        "SELECT pin_hash, salt FROM users WHERE username = ?", ("joao",)
    ).fetchone()
    pin_hash, salt = row
    assert salt != ""  # salt aleatorio por usuario
    assert pin_hash == hash_pin("1234", salt)
    # sem o salt, o hash nao bate -> salt de fato aplicado
    assert pin_hash != hash_pin("1234")


def test_legacy_row_without_salt_verifies(conn):
    # Simula linha legada gravada por versao antiga (salt vazio, hash sem salt)
    conn.execute(
        "INSERT INTO users (username, pin_hash, salt) VALUES (?, ?, '')",
        ("legado", hash_pin("1234")),
    )
    conn.commit()
    assert verify_pin(conn, "legado", "1234") is True
    assert verify_pin(conn, "legado", "0000") is False
