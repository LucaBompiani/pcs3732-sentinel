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
        db_path: Caminho do banco SQLite.
        relay_seconds: Tempo de acionamento da fechadura em segundos (RF06).
        factor2_timeout: Tempo máximo de espera pelo segundo fator (RF04).
        presence_timeout: Tempo máximo aguardando presença; ``None`` bloqueia
            indefinidamente.
        total_timeout: Orçamento total do fluxo de autenticação (RNF05).
        face_samples: Número de amostras faciais coletadas no cadastro (RF08).
        master_pin: PIN mestre do operador exigido no enrolamento (RF08).
    """

    backend: str
    db_path: str
    relay_seconds: float
    factor2_timeout: float
    presence_timeout: "float | None"
    total_timeout: float
    face_samples: int
    master_pin: str


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
        db_path=os.environ.get("SENTINEL_DB_PATH", "sentinel.db"),
        relay_seconds=_get_float("SENTINEL_RELAY_SECONDS", 5.0),
        factor2_timeout=_get_float("SENTINEL_FACTOR2_TIMEOUT", 15.0),
        presence_timeout=_get_optional_float("SENTINEL_PRESENCE_TIMEOUT", None),
        total_timeout=_get_float("SENTINEL_TOTAL_TIMEOUT", 8.0),
        face_samples=int(_get_float("SENTINEL_FACE_SAMPLES", 5)),
        master_pin=os.environ.get("SENTINEL_MASTER_PIN", "0000"),
    )
