"""Tempo de espera pelo segundo fator.

Um dos dois fatores basta, entao o fluxo nao pode ficar parado esperando o
outro. No cadastro, quem so define PIN esperava o timeout inteiro por um cartao
que nunca viria — parecia travado.
"""

import dataclasses
import time

import pytest

from src.sentinel.app.state_machine import run_access_cycle, run_enrollment
from src.sentinel.config import load_config
from src.sentinel.hal.factory import build_hal
from src.sentinel.infra.db import connect
from src.sentinel.infra.users_repository import create_user

CFG = dataclasses.replace(
    load_config(), factor2_timeout=6.0, second_factor_grace=1.0
)


class RfidQueNuncaLeCartao:
    """Leitor que registra o timeout pedido, como o driver real respeitaria."""

    def __init__(self):
        self.esperas = []

    def read_uid(self, timeout=None):
        espera = timeout or 0
        self.esperas.append(espera)
        # Dorme so um instante: o que importa e QUAL timeout foi pedido, e
        # esperar de verdade tornaria a suite lenta a toa.
        time.sleep(min(espera, 0.05))
        return None


@pytest.fixture
def conn():
    return connect(":memory:")


def _hal_com_rfid_mudo(cfg):
    leitor = RfidQueNuncaLeCartao()
    return dataclasses.replace(build_hal(cfg), rfid=leitor), leitor


def test_cadastro_com_pin_nao_espera_o_timeout_inteiro_pelo_cartao(conn):
    hal, leitor = _hal_com_rfid_mudo(CFG)
    hal.keypad.feed(CFG.master_pin, "1234")

    assert run_enrollment(conn, hal, CFG, "ana") is True

    # O PIN ja resolveu o segundo fator: o cartao vira extra, com janela curta.
    assert leitor.esperas == [CFG.second_factor_grace]
    assert CFG.second_factor_grace < CFG.factor2_timeout


def test_cadastro_sem_pin_da_o_tempo_cheio_ao_cartao(conn):
    hal, leitor = _hal_com_rfid_mudo(CFG)
    hal.keypad.feed(CFG.master_pin)  # so o PIN mestre; nenhum PIN do usuario

    assert run_enrollment(conn, hal, CFG, "bia") is False

    # Sem PIN, o cartao e a unica chance de segundo fator: merece o tempo todo.
    assert leitor.esperas == [CFG.factor2_timeout]


def test_cadastro_aceita_cartao_como_unico_segundo_fator(conn):
    hal = build_hal(CFG)
    hal.keypad.feed(CFG.master_pin)  # sem PIN do usuario
    hal.rfid.feed("CARD-BIA")

    assert run_enrollment(conn, hal, CFG, "bia") is True


def test_cadastro_registra_pin_e_cartao_quando_os_dois_vem(conn):
    # A janela curta encurta a espera, mas nao impede registrar os dois.
    from src.sentinel.infra.users_repository import verify_card, verify_pin

    hal = build_hal(CFG)
    hal.keypad.feed(CFG.master_pin, "1234")
    hal.rfid.feed("CARD-ANA")

    assert run_enrollment(conn, hal, CFG, "ana") is True
    assert verify_pin(conn, "ana", "1234") is True
    assert verify_card(conn, "ana", "CARD-ANA") is True


def test_acesso_com_pin_sai_na_hora(conn):
    create_user(conn, "joao", "1234")
    hal, _ = _hal_com_rfid_mudo(CFG)
    hal.camera.see("joao")
    hal.keypad.feed("1234")

    inicio = time.monotonic()
    autorizado, _, _ = run_access_cycle(conn, hal, CFG)
    decorrido = time.monotonic() - inicio

    assert autorizado is True
    # No acesso os dois fatores sao lidos em paralelo: o primeiro encerra.
    assert decorrido < CFG.factor2_timeout / 2


def test_acesso_com_cartao_sai_na_hora(conn):
    create_user(conn, "joao", "1234", card_uid="CARD-JOAO")
    hal = build_hal(CFG)
    hal.camera.see("joao")
    hal.rfid.feed("CARD-JOAO")

    inicio = time.monotonic()
    autorizado, _, _ = run_access_cycle(conn, hal, CFG)
    decorrido = time.monotonic() - inicio

    assert autorizado is True
    assert decorrido < CFG.factor2_timeout / 2


def test_config_le_a_janela_de_cortesia(monkeypatch):
    assert load_config().second_factor_grace == 3.0
    monkeypatch.setenv("SENTINEL_SECOND_FACTOR_GRACE", "0.5")
    assert load_config().second_factor_grace == 0.5
