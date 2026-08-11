"""Orquestração do fluxo de autenticação multifator (MFA).

Contém dois níveis:

* :func:`run_access_attempt` — núcleo puro de decisão + log, sem hardware. É a
  fonte única de verdade da combinação dos fatores (usada por testes e pelas
  camadas superiores).
* :func:`run_access_cycle` / :func:`run_enrollment` — fluxos completos dirigidos
  pelo HAL (presença, câmera, teclado/RFID, LCD, LEDs/buzzer, fechadura).
"""

import time

from sentinel.infra.events_repository import log_event
from sentinel.infra.users_repository import (
    add_face_embedding,
    create_user,
    user_exists,
)
from sentinel.services import face_recognition, lockout, second_factor
from sentinel.services.decision import authorize


def run_access_attempt(conn, cfg, presented_name, pin=None, *, card_uid=None):
    """Núcleo puro: decide e registra uma tentativa de acesso.

    Executa Fator 1 (reconhecimento) → bloqueio por tentativas (RF10) →
    Fator 2 (PIN ou cartão, apenas se o Fator 1 identificou e o usuário não
    estiver bloqueado) → decisão (E lógico) → log de auditoria.

    Args:
        conn: Conexão SQLite.
        cfg: Configuração (limite de falhas e duração do bloqueio).
        presented_name: Identidade candidata do Fator 1.
        pin: PIN do segundo fator, ou ``None``.
        card_uid: UID de cartão do segundo fator, ou ``None``.

    Returns:
        Tupla ``(autorizado, fator1_ok, fator2_ok)``.
    """
    fator1_username = face_recognition.recognize(conn, presented_name)
    fator1_ok = fator1_username is not None

    if fator1_ok and lockout.is_locked(conn, fator1_username):
        # Fator 2 nem é avaliado: o fator correto também é recusado (RF10).
        log_event(
            conn,
            username=fator1_username,
            fator1_ok=True,
            fator2_ok=False,
            resultado="BLOQUEADO",
        )
        return False, True, False

    fator2_ok = False
    if fator1_ok:
        fator2_ok = second_factor.verify(
            conn, fator1_username, pin, card_uid=card_uid
        )
        if fator2_ok:
            lockout.reset_failures(conn, fator1_username)
        else:
            lockout.register_failure(conn, fator1_username, cfg)

    autorizado = authorize(fator1_username, fator2_ok)
    resultado = "AUTORIZADO" if autorizado else "NEGADO"

    log_event(
        conn,
        username=fator1_username,
        fator1_ok=fator1_ok,
        fator2_ok=fator2_ok,
        resultado=resultado,
    )

    return autorizado, fator1_ok, fator2_ok


def read_second_factor(hal, timeout):
    """Aguarda o segundo fator: PIN (teclado) OU cartão (RFID), o que vier antes.

    Faz *polling* alternado nos dois dispositivos dentro do orçamento de tempo.
    Cada dispositivo é consultado ao menos uma vez (mesmo com ``timeout`` zero),
    o que mantém os testes determinísticos com backend mock.

    Args:
        hal: Conjunto de dispositivos :class:`~sentinel.hal.hal_bundle.Hal`.
        timeout: Tempo máximo de espera, em segundos.

    Returns:
        Tupla ``(pin, card_uid)`` — cada elemento é o valor lido ou ``None``.
    """
    deadline = time.monotonic() + timeout
    while True:
        card_uid = hal.rfid.read_uid(0)
        if card_uid is not None:
            return None, card_uid
        pin = hal.keypad.read_pin(0)
        if pin is not None:
            return pin, None
        if time.monotonic() >= deadline:
            return None, None
        time.sleep(0.05)


def run_access_cycle(conn, hal, cfg, recognizer=None):
    """Fluxo físico completo de uma tentativa de acesso.

    Sequência: aguarda presença (RF01) → captura e reconhece (RF02/RF03) →
    solicita o segundo fator com timeout apenas se o Fator 1 identificou e o
    usuário não estiver bloqueado (RF04/RF10) → decide e registra (RF05/RF09)
    → aciona fechadura + LED verde (RF06) ou sinaliza negação mantendo travado
    (RF07).

    Args:
        conn: Conexão SQLite.
        hal: Dispositivos de hardware.
        cfg: Configuração (timeouts, tempo de relé).
        recognizer: Reconhecedor a usar; se ``None``, obtido de ``cfg``.

    Returns:
        Tupla ``(autorizado, fator1_ok, fator2_ok)``.
    """
    recognizer = recognizer or face_recognition.get_recognizer(cfg)

    hal.display.show("Aproxime-se")
    hal.presence.wait_for_presence(cfg.presence_timeout)  # RF01

    hal.camera.start()
    frame = hal.camera.capture()  # RF02
    candidate = recognizer.identify(conn, frame)  # RF03

    if candidate is None:
        autorizado, f1, f2 = run_access_attempt(conn, cfg, None, None)
        hal.indicators.signal_denied()  # RF07
        hal.display.show("Acesso negado", "Face nao reconh.")
        return autorizado, f1, f2

    if lockout.is_locked(conn, candidate):  # RF10
        autorizado, f1, f2 = run_access_attempt(conn, cfg, candidate)
        hal.indicators.signal_denied()
        hal.display.show("Usuario bloqueado", candidate)
        return autorizado, f1, f2

    hal.display.show("Fator 2", "PIN ou cartao")  # RF04
    pin, card_uid = read_second_factor(hal, cfg.factor2_timeout)

    autorizado, f1, f2 = run_access_attempt(  # RF05
        conn, cfg, candidate, pin, card_uid=card_uid
    )

    if autorizado:
        hal.indicators.signal_granted()  # RF06
        hal.lock.unlock(cfg.relay_seconds)
        hal.display.show("Bem-vindo", candidate)
    else:
        hal.indicators.signal_denied()  # RF07 (fechadura permanece travada)
        hal.display.show("Acesso negado", "Fator 2 invalido")

    return autorizado, f1, f2


def run_enrollment(conn, hal, cfg, username):
    """Cadastra (enrola) um novo usuário com os dois fatores (RF08).

    Exige o gatilho de cadastro (tecla ``A`` no hardware, pois a placa não tem
    botão livre) e o PIN mestre do operador, coleta ``cfg.face_samples``
    amostras faciais (Fator 1) e associa um segundo fator (PIN e/ou cartão).

    Args:
        conn: Conexão SQLite.
        hal: Dispositivos de hardware.
        cfg: Configuração (PIN mestre, número de amostras, timeouts).
        username: Nome do novo usuário.

    Returns:
        ``True`` se o cadastro foi concluído; ``False`` se abortado (usuário já
        existente, PIN mestre incorreto ou nenhum segundo fator apresentado).
    """
    if user_exists(conn, username):
        hal.display.show("Cadastro", "Usuario existe")
        return False

    hal.display.show("Cadastro", "Tecle A")
    hal.enroll_button.wait_for_press(cfg.factor2_timeout)

    hal.display.show("PIN mestre", "do operador")
    master = hal.keypad.read_pin(cfg.factor2_timeout)
    if master != cfg.master_pin:  # RF08 — autorização do operador
        hal.indicators.signal_denied()
        hal.display.show("Cadastro negado", "PIN mestre")
        log_event(
            conn, username=username, fator1_ok=False, fator2_ok=False,
            resultado="CADASTRO_NEGADO", tipo="CADASTRO",
        )
        return False

    hal.display.show("Capturando face", username)
    hal.camera.start()
    for _ in range(cfg.face_samples):  # RF02/RF08 — N amostras faciais
        frame = hal.camera.capture()
        embedding = (getattr(frame, "label", None) or username).encode("utf-8")
        add_face_embedding(conn, username, embedding)

    hal.display.show("Fator 2", "PIN e/ou cartao")
    pin = hal.keypad.read_pin(cfg.factor2_timeout)
    card_uid = hal.rfid.read_uid(cfg.factor2_timeout)
    if pin is None and card_uid is None:
        hal.indicators.signal_denied()
        hal.display.show("Cadastro negado", "Sem 2o fator")
        return False

    hal.display.show("Consentimento?", "Confirme: A")  # RNF04 (LGPD)
    hal.enroll_button.wait_for_press(cfg.factor2_timeout)

    create_user(conn, username, pin or "", card_uid=card_uid)
    log_event(
        conn, username=username, fator1_ok=True, fator2_ok=True,
        resultado="CADASTRO", tipo="CADASTRO",
    )
    hal.indicators.signal_granted()
    hal.display.show("Cadastro OK", username)
    return True
