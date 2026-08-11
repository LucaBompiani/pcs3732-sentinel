"""Fábrica que monta o :class:`Hal` a partir da configuração."""

from sentinel.hal.hal_bundle import Hal


def build_hal(cfg):
    """Constrói o conjunto de dispositivos conforme ``cfg.backend``.

    Os imports dos submódulos ocorrem DENTRO da função para que o backend
    ``real`` (e suas bibliotecas de hardware) só seja tocado quando de fato
    selecionado — mantendo o import do pacote seguro em um PC.

    Args:
        cfg: Instância de :class:`sentinel.config.Config`.

    Returns:
        Um :class:`Hal` com os oito dispositivos instanciados.
    """
    if cfg.backend == "real":
        from sentinel.hal.real import (
            camera,
            display,
            enroll_button,
            indicators,
            keypad,
            lock,
            presence,
            rfid,
        )
    else:
        from sentinel.hal.mock import (
            camera,
            display,
            enroll_button,
            indicators,
            keypad,
            lock,
            presence,
            rfid,
        )

    return Hal(
        presence=presence.make(cfg),
        camera=camera.make(cfg),
        keypad=keypad.make(cfg),
        rfid=rfid.make(cfg),
        display=display.make(cfg),
        indicators=indicators.make(cfg),
        lock=lock.make(cfg),
        enroll_button=enroll_button.make(cfg),
    )
