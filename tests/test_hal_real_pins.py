"""Pinagem do backend real conforme a Freenove Projects Board.

Os componentes vêm soldados na placa, entao os GPIOs nao sao ajustaveis: sao
os do Tutorial. Estes testes travam as constantes para que uma edicao acidental
nao volte a apontar para o pino errado — o tipo de erro que so aparece no
hardware, e ainda assim de forma silenciosa (acionar o pino errado costuma
"funcionar", mexendo em outro periferico).

Importar os modulos de driver e seguro no PC: as bibliotecas de hardware sao
importadas tardiamente, dentro de ``make``/``__init__``.
"""

import pytest

from src.sentinel.config import load_config
from src.sentinel.hal.factory import build_hal
from src.sentinel.hal.real import enroll_button, indicators, keypad, lock, presence, servo_lock


def test_keypad_pins_match_tutorial_chapter_21():
    # Linhas e colunas nao podem estar transpostas: o scan aciona linha e le
    # coluna, entao inverter devolve a tecla errada (apertar '2' retorna '4').
    assert keypad.ROW_PINS == [16, 20, 21, 26]
    assert keypad.COL_PINS == [19, 13, 6, 5]
    assert keypad.KEYS[0] == ["1", "2", "3", "A"]
    assert keypad.KEYS[3] == ["*", "0", "#", "D"]


def test_indicators_pins_match_tutorial():
    assert indicators.LED_PIN == 17  # cap. 1: unico LED da placa
    assert indicators.BUZZER_PIN == 12  # cap. 6: buzzer ativo


def test_presence_pin_is_not_the_passive_buzzer():
    # GPIO 4 e o buzzer passivo da placa (cap. 6); o PIR do cap. 22 usa 24.
    assert presence.PIR_PIN == 24


def test_actuator_pins_match_tutorial():
    assert servo_lock.SERVO_PIN == 18  # cap. 13 (PWM por hardware)
    assert lock.RELAY_PIN == 12  # cap. 12


def test_relay_and_buzzer_share_a_pin():
    # Tutorial, pag. 41, nota 3. Este teste documenta o conflito que motiva a
    # recusa da fabrica logo abaixo; se a placa mudar, ele avisa.
    assert lock.RELAY_PIN == indicators.BUZZER_PIN


def test_factory_refuses_solenoid_on_real_backend(monkeypatch):
    monkeypatch.setenv("SENTINEL_BACKEND", "real")
    monkeypatch.setenv("SENTINEL_LOCK_TYPE", "solenoid")
    with pytest.raises(ValueError, match="GPIO 12"):
        build_hal(load_config())


def test_enroll_trigger_delegates_to_keypad():
    class FakeKeypad:
        def __init__(self, answer):
            self.answer = answer
            self.calls = []

        def wait_for_key(self, accept, timeout=None):
            self.calls.append((set(accept), timeout))
            return self.answer

    pressed = FakeKeypad("A")
    btn = enroll_button.make(None, keypad=pressed)
    assert btn.wait_for_press(timeout=5) is True
    assert pressed.calls == [({"A"}, 5)]

    # Timeout do teclado (None) vira "nao pressionado", nao uma excecao.
    assert enroll_button.make(None, keypad=FakeKeypad(None)).wait_for_press(1) is False


def test_enroll_trigger_requires_a_keypad():
    # A placa nao tem GPIO livre para um botao dedicado: sem teclado nao ha
    # gatilho, e falhar cedo e melhor do que um AttributeError depois.
    with pytest.raises(ValueError, match="teclado"):
        enroll_button.make(None)


def test_mock_backend_still_builds_without_a_keypad_argument():
    # O mock ignora o argumento; a fabrica passa o mesmo para os dois backends.
    hal = build_hal(load_config())
    assert hal.enroll_button.wait_for_press(0) is True
