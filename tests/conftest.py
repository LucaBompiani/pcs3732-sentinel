import os
import sys

SRC = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

# Padroes de teste: uma unica captura por tentativa e sem espera entre elas.
# Em producao a rajada (10 quadros a 0,3 s) combate o falso negativo do
# detector; nos testes o quadro mock e sempre o mesmo, entao repetir so tornaria
# a suite lenta sem cobrir nada de novo. Os testes da rajada configuram os
# proprios valores explicitamente.
os.environ.setdefault("SENTINEL_FACE_ATTEMPTS", "1")
os.environ.setdefault("SENTINEL_FACE_INTERVAL", "0")
