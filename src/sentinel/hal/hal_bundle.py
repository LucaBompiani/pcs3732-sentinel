"""Agregado dos dispositivos do HAL."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Hal:
    """Conjunto imutável dos oito dispositivos do sistema.

    Cada atributo é um objeto que satisfaz o contrato correspondente descrito
    em :mod:`sentinel.hal.interfaces`, seja na versão ``mock`` ou ``real``.
    """

    presence: object
    camera: object
    keypad: object
    rfid: object
    display: object
    indicators: object
    lock: object
    enroll_button: object
