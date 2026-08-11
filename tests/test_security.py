from src.sentinel.infra.security import hash_pin


def test_hash_e_deterministico():
    assert hash_pin("1234") == hash_pin("1234")


def test_hash_pins_diferentes_geram_hashes_diferentes():
    assert hash_pin("1234") != hash_pin("4321")


def test_hash_nao_armazena_pin_em_claro():
    assert "1234" not in hash_pin("1234")
