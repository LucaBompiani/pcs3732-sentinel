"""Retorno visual da digitacao do PIN e leitura em polling do teclado real.

Cobre tres correcoes que so apareceriam no hardware:

1. o driver real deve varrer o teclado ao menos uma vez mesmo com timeout=0,
   que e como o ciclo de acesso o consulta;
2. digitos parciais devem sobreviver entre chamadas do polling;
3. o display deve mostrar o progresso da digitacao.
"""

import dataclasses

import pytest

from src.sentinel.app.state_machine import pin_echo, read_second_factor
from src.sentinel.config import load_config
from src.sentinel.hal.factory import build_hal
from src.sentinel.hal.real import keypad as real_keypad


class TecladoFalso(real_keypad.RealKeypad):
    """RealKeypad com a varredura de GPIO substituida por uma fila de teclas."""

    def __init__(self, *teclas):
        self.teclas = list(teclas)
        self._buffer = []

    def _scan_key(self):
        return self.teclas.pop(0) if self.teclas else None


class DisplayFalso:
    def __init__(self):
        self.linhas = []

    def show(self, line1, line2=""):
        self.linhas.append((line1, line2))

    def clear(self):
        self.linhas.append(("", ""))


def _cfg(**kw):
    return dataclasses.replace(load_config(), **kw)


# ------------------------------------------- driver real: leitura em polling

def test_le_pin_completo_numa_chamada():
    tec = TecladoFalso("1", "2", "3", "4", "#")
    assert tec.read_pin(timeout=5) == "1234"


def test_asterisco_apaga_o_ultimo_digito():
    tec = TecladoFalso("1", "2", "*", "3", "#")
    assert tec.read_pin(timeout=5) == "13"


def test_teclas_de_funcao_nao_entram_no_pin():
    # 'A' dispara o cadastro; nao pode virar digito do PIN.
    tec = TecladoFalso("1", "A", "2", "B", "#")
    assert tec.read_pin(timeout=5) == "12"


def test_timeout_zero_ainda_varre_uma_vez():
    # O ciclo de acesso chama read_pin(0) em polling: se o laco nao executar
    # nenhuma varredura, o teclado nunca e lido no hardware.
    tec = TecladoFalso("#")
    assert tec.read_pin(timeout=0) == ""


def test_digitos_sobrevivem_entre_chamadas_do_polling():
    # Cada chamada com timeout=0 le uma tecla; o PIN so sai no '#'.
    tec = TecladoFalso("1", "2", "3", "4", "#")
    for _ in range(4):
        assert tec.read_pin(timeout=0) is None
    assert tec.read_pin(timeout=0) == "1234"


def test_reset_descarta_digitos_pendentes():
    tec = TecladoFalso("9", "9")
    tec.read_pin(timeout=0)
    tec.read_pin(timeout=0)
    tec.reset()
    tec.teclas = ["1", "#"]
    assert tec.read_pin(timeout=5) == "1"


def test_confirmar_limpa_o_buffer_para_a_leitura_seguinte():
    tec = TecladoFalso("1", "#", "2", "#")
    assert tec.read_pin(timeout=5) == "1"
    assert tec.read_pin(timeout=5) == "2"


# ------------------------------------------------------------- eco no display

def test_eco_mascarado_por_padrao():
    hal = dataclasses.replace(build_hal(load_config()), display=DisplayFalso())
    cfg = _cfg(pin_echo="mask")
    mostrar = pin_echo(hal, cfg, "Defina seu PIN")

    mostrar("12")
    mostrar("1234")

    assert hal.display.linhas == [("Defina seu PIN", "**"), ("Defina seu PIN", "****")]


def test_eco_em_claro_mostra_os_digitos():
    hal = dataclasses.replace(build_hal(load_config()), display=DisplayFalso())
    mostrar = pin_echo(hal, _cfg(pin_echo="plain"), "Defina seu PIN")

    mostrar("1234")

    assert hal.display.linhas == [("Defina seu PIN", "1234")]


def test_eco_vazio_volta_para_a_dica():
    hal = dataclasses.replace(build_hal(load_config()), display=DisplayFalso())
    mostrar = pin_echo(hal, _cfg(pin_echo="mask"), "Fator 2", "PIN ou cartao")

    mostrar("")

    assert hal.display.linhas == [("Fator 2", "PIN ou cartao")]


def test_eco_desligado_nao_devolve_callback():
    hal = build_hal(load_config())
    assert pin_echo(hal, _cfg(pin_echo="off"), "Fator 2") is None


def test_config_le_o_modo_de_eco(monkeypatch):
    assert load_config().pin_echo == "mask"  # padrao seguro
    monkeypatch.setenv("SENTINEL_PIN_ECHO", "PLAIN")
    assert load_config().pin_echo == "plain"  # normalizado


# --------------------------------------------- integracao com o segundo fator

def test_segundo_fator_ecoa_a_digitacao():
    cfg = _cfg(pin_echo="mask")
    hal = dataclasses.replace(build_hal(cfg), display=DisplayFalso())
    hal.keypad.feed("1234")

    pin, card = read_second_factor(
        hal, 1.0, on_change=pin_echo(hal, cfg, "Fator 2", "PIN ou cartao")
    )

    assert (pin, card) == ("1234", None)
    assert hal.keypad.echoes == ["1", "12", "123", "1234"]
    assert ("Fator 2", "*") in hal.display.linhas
    assert ("Fator 2", "****") in hal.display.linhas


def test_segundo_fator_limpa_o_buffer_antes_de_ler():
    # Sem o reset, digitos de uma tentativa anterior entrariam nesta e
    # causariam uma recusa inexplicavel.
    cfg = load_config()
    hal = build_hal(cfg)

    chamadas = []
    hal.keypad.reset = lambda: chamadas.append("reset")
    hal.keypad.feed("1234")

    read_second_factor(hal, 1.0)

    assert chamadas == ["reset"]


@pytest.mark.parametrize("modo", ["mask", "plain", "off"])
def test_todos_os_modos_de_eco_completam_a_leitura(modo):
    cfg = _cfg(pin_echo=modo)
    hal = dataclasses.replace(build_hal(cfg), display=DisplayFalso())
    hal.keypad.feed("4321")

    pin, _ = read_second_factor(
        hal, 1.0, on_change=pin_echo(hal, cfg, "Fator 2", "PIN ou cartao")
    )

    assert pin == "4321"
