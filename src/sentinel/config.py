"""Configuração do sistema lida de variáveis de ambiente.

Centraliza a seleção do backend de hardware (``mock`` ou ``real``) e os
parâmetros ajustáveis do fluxo de autenticação. Usa apenas a biblioteca
padrão; ``load_config`` é uma função pura de ``os.environ``, o que a torna
trivialmente testável.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Parâmetros imutáveis de execução do Sentinel.

    Attributes:
        backend: Backend de hardware, ``"mock"`` (padrão, roda no PC) ou
            ``"real"`` (drivers do Raspberry Pi).
        lock_type: Atuador do acesso, ``"solenoid"`` (padrão, relé + fechadura
            solenoide) ou ``"servo"`` (modo de demonstração).
        db_path: Caminho do banco SQLite.
        relay_seconds: Tempo de acionamento da fechadura em segundos (RF06).
        factor2_timeout: Tempo máximo de espera pelo segundo fator (RF04).
        presence_timeout: Tempo máximo aguardando presença; ``None`` bloqueia
            indefinidamente.
        total_timeout: Orçamento total do fluxo de autenticação (RNF05).
        pin_echo: Como o PIN digitado aparece no display: ``"mask"`` (padrão,
            um ``*`` por dígito), ``"plain"`` (mostra os dígitos — use apenas em
            depuração/demonstração, pois expõe o segredo a quem olhar a tela) ou
            ``"off"`` (nenhum retorno visual).
        face_preview: Exibição da captura: ``"web"`` (painel em
            ``http://<pi>:<web_port>``, recomendado), ``"window"`` (janela do
            OpenCV), ``"file"`` (grava JPEG em disco — DEPURAÇÃO, viola o RNF04
            enquanto ligado), ``"ascii"`` (recorte no terminal) ou ``"off"``.
        web_port: Porta do painel web.
        face_attempts: Quadros capturados por tentativa de acesso. O primeiro
            que identificar alguém encerra a rajada; só é negado quando todos
            falham. Combate o falso negativo do detector, que perde o rosto por
            piscada, micro-movimento ou desfoque momentâneo.
        face_interval: Intervalo entre os quadros da rajada, em segundos.
        face_samples: Número de amostras faciais coletadas no cadastro (RF08).
        face_threshold: Distância qui-quadrado máxima entre o rosto capturado e
            a amostra mais próxima para aceitar a identidade (RF03). Menor =
            mais rigoroso (mais falsos negativos); maior = mais permissivo
            (mais falsos positivos). Precisa de calibração empírica no Pi.
        master_pin: PIN mestre do operador exigido no enrolamento (RF08).
        max_failures: Falhas seguidas do Fator 2 que bloqueiam o usuário (RF10).
        lockout_seconds: Duração do bloqueio temporário em segundos (RF10).
    """

    backend: str
    lock_type: str
    db_path: str
    relay_seconds: float
    factor2_timeout: float
    presence_timeout: "float | None"
    total_timeout: float
    pin_echo: str
    face_preview: str
    web_port: int
    face_attempts: int
    face_interval: float
    face_samples: int
    face_threshold: float
    master_pin: str
    max_failures: int
    lockout_seconds: float


def _get_float(name, default):
    """Lê uma variável de ambiente como float, com fallback ao padrão."""
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return float(value)


def _get_optional_float(name, default):
    """Lê um float opcional; ``"none"``/``""`` viram ``None``."""
    value = os.environ.get(name)
    if value is None:
        return default
    if value == "" or value.lower() == "none":
        return None
    return float(value)


def load_config():
    """Constrói uma :class:`Config` a partir de ``os.environ``.

    Todas as variáveis são opcionais; ausentes assumem os padrões documentados
    em :class:`Config`.

    Returns:
        Instância imutável de :class:`Config`.
    """
    return Config(
        backend=os.environ.get("SENTINEL_BACKEND", "mock"),
        lock_type=os.environ.get("SENTINEL_LOCK_TYPE", "solenoid"),
        db_path=os.environ.get("SENTINEL_DB_PATH", "sentinel.db"),
        relay_seconds=_get_float("SENTINEL_RELAY_SECONDS", 5.0),
        factor2_timeout=_get_float("SENTINEL_FACTOR2_TIMEOUT", 15.0),
        presence_timeout=_get_optional_float("SENTINEL_PRESENCE_TIMEOUT", None),
        total_timeout=_get_float("SENTINEL_TOTAL_TIMEOUT", 8.0),
        pin_echo=os.environ.get("SENTINEL_PIN_ECHO", "mask").lower(),
        face_preview=os.environ.get("SENTINEL_FACE_PREVIEW", "web").lower(),
        web_port=int(_get_float("SENTINEL_WEB_PORT", 8080)),
        face_attempts=int(_get_float("SENTINEL_FACE_ATTEMPTS", 10)),
        face_interval=_get_float("SENTINEL_FACE_INTERVAL", 0.3),
        face_samples=int(_get_float("SENTINEL_FACE_SAMPLES", 5)),
        face_threshold=_get_float("SENTINEL_FACE_THRESHOLD", 0.55),
        master_pin=os.environ.get("SENTINEL_MASTER_PIN", "0000"),
        max_failures=int(_get_float("SENTINEL_MAX_FAILURES", 3)),
        lockout_seconds=_get_float("SENTINEL_LOCKOUT_SECONDS", 60.0),
    )
