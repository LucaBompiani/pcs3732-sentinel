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

# Quadros capturados por amostra desejada antes de desistir do cadastro: rostos
# fora de quadro ou desfocados são descartados e recapturados.
FACE_CAPTURE_ATTEMPTS = 6


def pin_echo(hal, cfg, titulo, dica="termine com #"):
    """Devolve um callback que mostra a digitação do PIN no display, ou ``None``.

    Sem esse retorno visual não há como saber se o teclado registrou a tecla —
    a varredura matricial ignora repiques e pressões muito curtas, e o usuário
    fica digitando às cegas.

    O padrão mascara os dígitos (``SENTINEL_PIN_ECHO=mask``): quem olha a tela
    vê o comprimento, não o segredo. ``plain`` mostra os dígitos e serve para
    depurar a montagem; ``off`` desliga o retorno.

    Args:
        hal: Dispositivos (usa ``hal.display``).
        cfg: Configuração (``cfg.pin_echo``).
        titulo: Primeira linha do display, mantida durante a digitação.
        dica: Segunda linha enquanto nada foi digitado.
    """
    if cfg.pin_echo == "off":
        return None

    def mostrar(digitos):
        if not digitos:
            hal.display.show(titulo, dica)
            return
        texto = digitos if cfg.pin_echo == "plain" else "*" * len(digitos)
        hal.display.show(titulo, texto)

    return mostrar


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


def read_second_factor(hal, timeout, on_change=None):
    """Aguarda o segundo fator: PIN (teclado) OU cartão (RFID), o que vier antes.

    Faz *polling* alternado nos dois dispositivos dentro do orçamento de tempo.
    Cada dispositivo é consultado ao menos uma vez (mesmo com ``timeout`` zero),
    o que mantém os testes determinísticos com backend mock.

    Args:
        hal: Conjunto de dispositivos :class:`~sentinel.hal.hal_bundle.Hal`.
        timeout: Tempo máximo de espera, em segundos.
        on_change: Callback de eco da digitação (ver :func:`pin_echo`).

    Returns:
        Tupla ``(pin, card_uid)`` — cada elemento é o valor lido ou ``None``.
    """
    # Descarta dígitos que tenham sobrado de uma tentativa anterior: eles
    # entrariam no PIN desta, causando uma falha inexplicável para o usuário.
    hal.keypad.reset()

    deadline = time.monotonic() + timeout
    while True:
        card_uid = hal.rfid.read_uid(0)
        if card_uid is not None:
            return None, card_uid
        pin = hal.keypad.read_pin(0, on_change=on_change)
        if pin is not None:
            return pin, None
        if time.monotonic() >= deadline:
            return None, None
        time.sleep(0.05)


def identify_with_retries(conn, hal, cfg, recognizer):
    """Captura uma rajada de quadros e devolve o primeiro reconhecido.

    O detector Haar exige rosto frontal e nítido, então uma única captura falha
    com frequência por motivos banais — a pessoa piscou, virou de leve, o
    autofoco não acompanhou. Repetir alguns quadros derruba esse falso negativo
    sem tornar o sistema permissivo: o critério de aceitação de CADA quadro
    continua o mesmo, apenas há mais oportunidades de pegar um quadro bom.

    Encerra assim que alguém é identificado, então o caso normal (rosto
    reconhecido de primeira) não fica mais lento.

    Returns:
        O usuário identificado, ou ``None`` se todos os quadros falharem.
    """
    ultimo = cfg.face_attempts - 1
    for tentativa in range(cfg.face_attempts):
        candidate = recognizer.identify(conn, hal.camera.capture())
        if candidate is not None:
            return candidate
        if tentativa < ultimo:
            hal.display.show("Reconhecendo...", f"{tentativa + 1}/{cfg.face_attempts}")
            if cfg.face_interval:
                time.sleep(cfg.face_interval)
    return None


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
    # RF02/RF03 — rajada de quadros; o primeiro reconhecido encerra a busca.
    candidate = identify_with_retries(conn, hal, cfg, recognizer)

    if candidate is None:
        autorizado, f1, f2 = run_access_attempt(conn, cfg, None, None)
        hal.indicators.signal_denied()  # RF07
        hal.display.show("Acesso negado", "Face nao reconh.")
        return autorizado, f1, f2

    if lockout.is_locked(conn, candidate):  # RF10
        autorizado, f1, f2 = run_access_attempt(conn, cfg, candidate)
        hal.indicators.signal_denied()
        hal.display.show("Bloqueado", candidate)
        return autorizado, f1, f2

    hal.display.show("Fator 2", "PIN ou cartao")  # RF04
    pin, card_uid = read_second_factor(
        hal, cfg.factor2_timeout, on_change=pin_echo(hal, cfg, "Fator 2", "PIN ou cartao")
    )

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


def _collect_face_samples(hal, cfg, recognizer, username):
    """Captura quadros até obter ``cfg.face_samples`` vetores faciais.

    Quadros sem rosto detectável são descartados e uma nova captura é feita, até
    o teto de tentativas — no backend real é comum o usuário piscar, virar o
    rosto ou sair de quadro durante a coleta, e abortar o cadastro por isso
    seria frustrante. O teto evita laço infinito quando não há ninguém.

    Returns:
        Lista de vetores em ``bytes``; vazia se nenhum rosto foi obtido.
    """
    amostras = []
    tentativas = 0
    limite = cfg.face_samples * FACE_CAPTURE_ATTEMPTS
    while len(amostras) < cfg.face_samples and tentativas < limite:
        tentativas += 1
        embedding = recognizer.encode(hal.camera.capture(), username)
        if embedding is None:
            hal.display.show("Rosto nao visto", "Olhe p/ camera")
            continue
        amostras.append(embedding)
        hal.display.show("Olhe p/ camera", f"Capturando {len(amostras)}/{cfg.face_samples}")
    return amostras


def run_enrollment(conn, hal, cfg, username, recognizer=None):
    """Cadastra (enrola) um novo usuário com os dois fatores (RF08).

    Exige o gatilho de cadastro (tecla ``A`` no hardware, pois a placa não tem
    botão livre) e o PIN mestre do operador, coleta ``cfg.face_samples``
    amostras faciais (Fator 1) e associa um segundo fator (PIN e/ou cartão).

    Args:
        conn: Conexão SQLite.
        hal: Dispositivos de hardware.
        cfg: Configuração (PIN mestre, número de amostras, timeouts).
        username: Nome do novo usuário.
        recognizer: Extrator de vetores faciais; ``None`` usa o do backend.

    Returns:
        ``True`` se o cadastro foi concluído; ``False`` se abortado (usuário já
        existente, PIN mestre incorreto ou nenhum segundo fator apresentado).
    """
    recognizer = recognizer or face_recognition.get_recognizer(cfg)

    if user_exists(conn, username):
        hal.display.show("Cadastro", "Usuario existe")
        return False

    hal.display.show("Novo cadastro", "Tecle A p/ inic")
    hal.enroll_button.wait_for_press(cfg.factor2_timeout)

    hal.display.show("PIN do operador", "termine com #")
    hal.keypad.reset()
    master = hal.keypad.read_pin(
        cfg.factor2_timeout, on_change=pin_echo(hal, cfg, "PIN do operador")
    )
    if master != cfg.master_pin:  # RF08 — autorização do operador
        hal.indicators.signal_denied()
        hal.display.show("Cadastro negado", "PIN mestre")
        log_event(
            conn, username=username, fator1_ok=False, fator2_ok=False,
            resultado="CADASTRO_NEGADO", tipo="CADASTRO",
        )
        return False

    hal.display.show("Olhe p/ camera", "Capturando 0/%d" % cfg.face_samples)
    hal.camera.start()
    coletadas = _collect_face_samples(hal, cfg, recognizer, username)
    if not coletadas:  # RF02 — nenhum rosto utilizável
        hal.indicators.signal_denied()
        hal.display.show("Cadastro negado", "Rosto nao visto")
        log_event(
            conn, username=username, fator1_ok=False, fator2_ok=False,
            resultado="CADASTRO_NEGADO", tipo="CADASTRO",
        )
        return False
    for embedding in coletadas:
        add_face_embedding(conn, username, embedding)

    # Os dois fatores são pedidos em sequência, cada um com sua tela: pedir
    # "PIN e/ou cartao" numa tela só deixava o usuário sem saber o que fazer
    # durante a leitura do cartão, que acontece depois do PIN de qualquer forma.
    hal.display.show("Defina seu PIN", "termine com #")
    hal.keypad.reset()
    pin = hal.keypad.read_pin(
        cfg.factor2_timeout, on_change=pin_echo(hal, cfg, "Defina seu PIN")
    )
    pin = pin or None  # "#" sem dígitos não é um PIN

    hal.display.show("Passe o cartao", "ou aguarde")
    card_uid = hal.rfid.read_uid(cfg.factor2_timeout)
    if pin is None and card_uid is None:
        hal.indicators.signal_denied()
        hal.display.show("Cadastro negado", "Sem PIN/cartao")
        return False

    hal.display.show("Aceita cadastro?", "Tecle A p/ sim")  # RNF04 (LGPD)
    hal.enroll_button.wait_for_press(cfg.factor2_timeout)

    create_user(conn, username, pin or "", card_uid=card_uid)
    log_event(
        conn, username=username, fator1_ok=True, fator2_ok=True,
        resultado="CADASTRO", tipo="CADASTRO",
    )
    hal.indicators.signal_granted()
    hal.display.show("Cadastro OK", username)
    return True
