"""Camada de Abstração de Hardware (HAL) do Sentinel.

Importar este pacote NUNCA deve carregar bibliotecas específicas do Raspberry
Pi (``gpiozero``, ``picamera2``, ``mfrc522`` etc.). Os drivers reais em
``sentinel.hal.real`` importam essas bibliotecas apenas dentro de suas funções
``make``/``__init__`` (import tardio), de modo que o pacote permaneça
importável e testável em um PC comum.
"""
