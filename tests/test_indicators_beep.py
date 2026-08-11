"""Padroes sonoros do buzzer.

O bipe e o unico retorno que a pessoa recebe sem olhar o LCD, entao concedido e
negado precisam ser distinguiveis de ouvido: um curto contra dois curtos e um
longo ("pi pi piiii").
"""

import pytest

from src.sentinel.app.state_machine import run_access_cycle
from src.sentinel.config import load_config
from src.sentinel.hal.factory import build_hal
from src.sentinel.hal.mock import indicators as mock_indicators
from src.sentinel.hal.real import indicators as real_indicators
from src.sentinel.infra.db import connect
from src.sentinel.infra.users_repository import create_user

CFG = load_config()


@pytest.fixture
def conn():
    return connect(":memory:")


# ------------------------------------------------------- padroes (driver real)

def test_aceito_e_um_bipe_curto():
    assert real_indicators.beep_sequence("ok") == (0.15,)


def test_negado_e_dois_curtos_e_um_longo():
    curto1, curto2, longo = real_indicators.beep_sequence("fail")
    assert curto1 == curto2
    assert longo > curto1 * 3  # o ultimo tem que soar claramente mais longo


def test_negado_tem_tres_bipes_e_aceito_um():
    assert len(real_indicators.beep_sequence("fail")) == 3
    assert len(real_indicators.beep_sequence("ok")) == 1


def test_padrao_desconhecido_cai_no_ok():
    assert real_indicators.beep_sequence("qualquer") == real_indicators.BEEP_PATTERNS["ok"]


def test_negado_dura_mais_que_aceito():
    # Diferenca perceptivel: o padrao de negacao precisa chamar atencao.
    def total(p):
        d = real_indicators.beep_sequence(p)
        return sum(d) + real_indicators.BEEP_GAP * (len(d) - 1)

    assert total("fail") > 2 * total("ok")


# --------------------------------------------------------- uso pelo sinalizador

def test_sinal_de_concedido_toca_ok_e_acende_o_led():
    ind = mock_indicators.make(CFG)
    ind.signal_granted()

    assert ("beep", "ok") in ind.events
    assert ("led_green", True) in ind.events
    assert ("beep", "fail") not in ind.events


def test_sinal_de_negado_toca_fail_e_pisca_o_led():
    ind = mock_indicators.make(CFG)
    ind.signal_denied()

    assert ("beep", "fail") in ind.events
    assert ("led_red", True) in ind.events
    assert ("beep", "ok") not in ind.events


# ----------------------------------------------------- integracao com o ciclo

def test_acesso_autorizado_apita_uma_vez(conn):
    create_user(conn, "joao", "1234")
    hal = build_hal(CFG)
    hal.camera.see("joao")
    hal.keypad.feed("1234")

    autorizado, _, _ = run_access_cycle(conn, hal, CFG)

    assert autorizado is True
    assert ("beep", "ok") in hal.indicators.events
    assert ("beep", "fail") not in hal.indicators.events


def test_acesso_negado_apita_o_padrao_longo(conn):
    create_user(conn, "joao", "1234")
    hal = build_hal(CFG)
    hal.camera.see("joao")
    hal.keypad.feed("9999")  # PIN errado

    autorizado, _, _ = run_access_cycle(conn, hal, CFG)

    assert autorizado is False
    assert ("beep", "fail") in hal.indicators.events
    assert ("beep", "ok") not in hal.indicators.events


def test_face_desconhecida_tambem_apita_negacao(conn):
    hal = build_hal(CFG)
    hal.camera.see("fantasma")

    run_access_cycle(conn, hal, CFG)

    assert ("beep", "fail") in hal.indicators.events
