"""Helpers de segurança (hash do segundo fator)."""

import hashlib


def hash_pin(pin):
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()
