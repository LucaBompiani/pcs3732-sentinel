"""Contratos (duck-typed) dos dispositivos do HAL.

Seguindo o estilo do projeto (funções e objetos simples, sem ABCs), este
módulo apenas documenta a superfície esperada de cada dispositivo. Tanto os
backends ``mock`` quanto ``real`` devem oferecer estes métodos.

Presence (PIR)
    ``wait_for_presence(timeout=None) -> bool``: bloqueia até detectar presença
    ou expirar o timeout; retorna ``True`` se detectou.
    ``is_present() -> bool``: leitura instantânea do sensor.

Camera
    ``start()`` / ``stop()``: ciclo de vida da captura.
    ``capture() -> Frame``: captura um quadro. O ``Frame`` expõe ``.label``
    (identidade, usada pelo reconhecedor mock) e/ou dados de imagem.

Keypad (teclado matricial 4x4)
    ``read_pin(timeout) -> str | None``: lê um PIN digitado, ou ``None`` no
    timeout.

Rfid (leitor MFRC522)
    ``read_uid(timeout) -> str | None``: lê o UID de um cartão, ou ``None`` no
    timeout.

Display (LCD1602 I2C)
    ``show(line1, line2="")``: exibe até duas linhas.
    ``clear()``: limpa o display.

Indicators (LEDs + buzzer)
    ``signal_granted()`` / ``signal_denied()``: feedback composto de sucesso/
    falha. ``led_green(on)`` / ``led_red(on)`` / ``beep(pattern)``: controle
    granular.

Lock (relé + fechadura solenoide, ou servomotor)
    ``unlock(seconds)``: libera a fechadura pelo tempo indicado e retorna ao
    estado seguro (fail-secure). ``lock()``: força travamento.
    ``is_locked() -> bool``: estado atual.
    Dois atuadores cumprem este contrato, escolhidos por ``cfg.lock_type``:
    ``solenoid`` (relé, fail-secure, atuador do requisito) e ``servo`` (apenas
    demonstração — um servo não volta sozinho ao estado travado em queda de
    energia).

EnrollButton (botão físico de cadastro)
    ``wait_for_press(timeout) -> bool``: aguarda o pressionar do botão.
"""
