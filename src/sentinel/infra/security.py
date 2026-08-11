"""Helpers de segurança (hash e salt do segundo fator)."""

import hashlib
import secrets


def hash_pin(pin, salt=""):
    """Gera o hash SHA-256 de um segredo (PIN ou UID de cartão).

    Args:
        pin: Segredo em texto plano a ser resumido.
        salt: Salt por-usuário concatenado antes do hash. O valor padrão
            vazio reproduz byte a byte o hash legado (sem salt), preservando
            a compatibilidade com bases e testes anteriores.

    Returns:
        Hash hexadecimal SHA-256 de ``salt + pin``.
    """
    return hashlib.sha256((salt + pin).encode("utf-8")).hexdigest()


def gen_salt():
    """Gera um salt aleatório em hexadecimal para um novo usuário.

    Returns:
        String hexadecimal de 32 caracteres (16 bytes) obtida de forma
        criptograficamente segura.
    """
    return secrets.token_hex(16)
