#!/usr/bin/env python3
"""Testa cada periférico isoladamente, fora do fluxo de autenticação.

Quando algo "não funciona" no ciclo completo, a causa pode estar no driver, no
GPIO, na chave seletora da placa ou na própria lógica. Este script tira a
lógica do caminho: aciona um dispositivo de cada vez e pergunta o que você
observou.

Uso no Raspberry Pi:
    ./scripts/diag-hardware.py            # todos os testes
    ./scripts/diag-hardware.py buzzer     # só o buzzer
    ./scripts/diag-hardware.py buzzer led servo
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

os.environ.setdefault("SENTINEL_BACKEND", "real")
os.environ.setdefault("SENTINEL_LOCK_TYPE", "servo")

VERDE = "\033[32m"
AMARELO = "\033[33m"
VERMELHO = "\033[31m"
CIANO = "\033[1;36m"
FIM = "\033[0m"


def titulo(texto):
    print(f"\n{CIANO}==> {texto}{FIM}")


def pergunta(texto):
    resposta = input(f"    {texto} [s/N] ").strip().lower()
    return resposta in ("s", "sim", "y", "yes")


def resultado(nome, ok, dica=""):
    if ok:
        print(f"    {VERDE}[ ok ]{FIM} {nome}")
    else:
        print(f"    {VERMELHO}[FALHA]{FIM} {nome}")
        if dica:
            print(f"           {dica}")
    return ok


# --------------------------------------------------------------------- testes

def teste_buzzer():
    """Aciona o buzzer direto no GPIO, sem passar pelos padrões sonoros."""
    from gpiozero import Buzzer

    from sentinel.hal.real.indicators import BUZZER_PIN, beep_sequence

    titulo(f"Buzzer (GPIO {BUZZER_PIN})")
    print("    A placa tem CHAVES SELETORAS numeradas: se a do buzzer estiver")
    print("    desligada, o GPIO comuta certinho e nenhum som sai.")
    print("    Na Projects Board o buzzer ativo divide o GPIO 12 com o relé.")

    buzzer = Buzzer(BUZZER_PIN)

    print("\n    1) Ligando por 2 s, contínuo...")
    buzzer.on()
    time.sleep(2)
    buzzer.off()
    contínuo = pergunta("Ouviu um som contínuo?")

    if not contínuo:
        print(f"\n    {AMARELO}Nada saiu. Verifique, nesta ordem:{FIM}")
        print("      1. A chave seletora do buzzer na placa está LIGADA?")
        print("      2. Se há uma chave que escolhe entre BUZZER e RELÉ,")
        print("         ela está do lado do buzzer? (os dois usam o GPIO 12)")
        print("      3. É o buzzer ATIVO? O passivo (GPIO 4) não toca com")
        print("         nível fixo — precisa de PWM. Teste abaixo.")
        if pergunta("Testar o buzzer PASSIVO no GPIO 4 agora?"):
            return teste_buzzer_passivo()
        return resultado("buzzer", False, "provável chave seletora da placa")

    print("\n    2) Padrão de acesso concedido: um bipe curto ('pi')")
    for duracao in beep_sequence("ok"):
        buzzer.on(); time.sleep(duracao); buzzer.off()
    time.sleep(0.8)

    print("    3) Padrão de acesso negado: 'pi pi piiii'")
    duracoes = beep_sequence("fail")
    for i, duracao in enumerate(duracoes):
        buzzer.on(); time.sleep(duracao); buzzer.off()
        if i < len(duracoes) - 1:
            time.sleep(0.12)

    distintos = pergunta("Os dois padrões soaram DIFERENTES entre si?")
    return resultado("buzzer", distintos, "ajuste BEEP_PATTERNS em hal/real/indicators.py")


def teste_buzzer_passivo():
    """O buzzer passivo precisa de PWM; nível fixo não produz som."""
    from gpiozero import TonalBuzzer

    titulo("Buzzer passivo (GPIO 4)")
    buzzer = TonalBuzzer(4)
    buzzer.play(440)
    time.sleep(1.5)
    buzzer.stop()

    ok = pergunta("Ouviu um tom?")
    if ok:
        print(f"\n    {AMARELO}É o buzzer PASSIVO que está ligado.{FIM}")
        print("    Troque BUZZER_PIN para 4 e use TonalBuzzer em")
        print("    src/sentinel/hal/real/indicators.py")
    return resultado("buzzer passivo", ok)


def teste_led():
    from sentinel.hal.real.indicators import LED_PIN, RealIndicators

    titulo(f"LED (GPIO {LED_PIN})")
    ind = RealIndicators()

    print("    1) Aceso contínuo por 2 s (acesso concedido)...")
    ind.led_green(True)
    time.sleep(2)
    ind.led_green(False)

    print("    2) Piscando 3x (acesso negado)...")
    ind.led_red(True)
    ind.led_green(False)

    return resultado("LED", pergunta("Viu aceso e depois piscando?"),
                     "confira a chave seletora do LED na placa")


def teste_display():
    from sentinel.hal.real.display import I2C_ADDR, RealDisplay

    titulo(f"Display LCD1602 (I2C {hex(I2C_ADDR)})")
    disp = RealDisplay()
    disp.show("Sentinel", "teste de LCD")
    time.sleep(2)

    ok = pergunta("Apareceu 'Sentinel / teste de LCD'?")
    if not ok:
        print("    Se a tela acende mas nada aparece: gire o potenciômetro de")
        print("    contraste atrás do módulo. Se nem acende: rode 'i2cdetect -y 1'")
        print("    e ajuste I2C_ADDR em hal/real/display.py.")
    return resultado("display", ok)


def teste_servo():
    from sentinel.hal.real.servo_lock import SERVO_PIN, RealServoLock

    titulo(f"Servo (GPIO {SERVO_PIN})")
    servo = RealServoLock()
    print("    Destravando por 3 s e travando de novo...")
    servo.unlock(3)

    return resultado("servo", pergunta("O servo girou e voltou?"),
                     "servo precisa de alimentação externa e GND comum com o Pi")


def teste_teclado():
    from sentinel.hal.real.keypad import COL_PINS, ROW_PINS, RealKeypad

    titulo(f"Teclado 4x4 (linhas {ROW_PINS}, colunas {COL_PINS})")
    tec = RealKeypad()
    print("    Digite 1234 e termine com # (15 s)...")

    tec.reset()
    pin = tec.read_pin(15, on_change=lambda d: print(f"      digitado: {d}"))

    if pin is None:
        return resultado("teclado", False, "nenhuma tecla registrada — confira a chave da placa")
    if pin != "1234":
        print(f"    {AMARELO}Recebido '{pin}' em vez de '1234'.{FIM}")
        print("    Teclas trocadas => linhas/colunas invertidas em keypad.py")
        return resultado("teclado", False, "ver Tutorial cap. 21")
    return resultado("teclado", True)


def teste_rfid():
    from sentinel.hal.real.rfid import RealRfid

    titulo("Leitor RFID RC522 (SPI)")
    leitor = RealRfid()
    print("    Encoste um cartão no leitor (15 s)...")
    uid = leitor.read_uid(15)

    if uid is None:
        return resultado("RFID", False, "SPI habilitado? cartão Mifare 13,56 MHz?")
    print(f"    UID lido: {uid}")
    return resultado("RFID", True)


def teste_camera():
    from sentinel.hal.real.camera import RealCamera
    from sentinel.services.face_detector import HaarFaceDetector

    titulo("Câmera + detecção de rosto")
    cam = RealCamera()
    cam.start()
    time.sleep(1)  # tempo de o autoexposure estabilizar
    frame = cam.capture()
    cam.stop()
    print(f"    Quadro capturado: {getattr(frame, 'shape', '?')}")

    det = HaarFaceDetector()
    rosto, caixa = det.detect(frame)
    if rosto is None:
        return resultado("câmera", False,
                         "quadro capturado, mas nenhum rosto detectado — enquadramento/luz")
    print(f"    Rosto detectado em {caixa}")
    return resultado("câmera", True)


TESTES = {
    "buzzer": teste_buzzer,
    "led": teste_led,
    "display": teste_display,
    "servo": teste_servo,
    "teclado": teste_teclado,
    "rfid": teste_rfid,
    "camera": teste_camera,
}


def main():
    pedidos = sys.argv[1:] or list(TESTES)
    invalidos = [p for p in pedidos if p not in TESTES]
    if invalidos:
        print(f"Teste desconhecido: {', '.join(invalidos)}")
        print(f"Disponíveis: {', '.join(TESTES)}")
        return 2

    print(f"{CIANO}Sentinel — diagnóstico de hardware{FIM}")
    falhas = []
    for nome in pedidos:
        try:
            if not TESTES[nome]():
                falhas.append(nome)
        except KeyboardInterrupt:
            print("\n    interrompido")
            return 130
        except Exception as erro:
            print(f"    {VERMELHO}[ERRO]{FIM} {nome}: {type(erro).__name__}: {erro}")
            falhas.append(nome)

    titulo("Resumo")
    if falhas:
        print(f"    {VERMELHO}Falharam:{FIM} {', '.join(falhas)}")
        return 1
    print(f"    {VERDE}Todos os testes passaram.{FIM}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
