"""Backend ``real`` do HAL: drivers do Raspberry Pi.

IMPORTANTE: nenhum import de biblioteca de hardware deve ocorrer no nível de
módulo — nem aqui nem nos submódulos. Cada driver importa sua dependência
(``gpiozero``, ``picamera2``, ``mfrc522``, ``RPLCD`` ...) dentro de ``make`` ou
do ``__init__`` da classe, para que o pacote continue importável em um PC.
"""
