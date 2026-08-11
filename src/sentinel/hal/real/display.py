"""Driver real do display LCD1602 via I2C (RPLCD)."""

# Endereço I2C padrão do módulo PCF8574 (ajustar se necessário).
I2C_ADDR = 0x27


class RealDisplay:
    """LCD1602 via ``RPLCD.i2c.CharLCD`` (import tardio)."""

    def __init__(self, address=I2C_ADDR):
        from RPLCD.i2c import CharLCD

        self._lcd = CharLCD("PCF8574", address)

    def show(self, line1, line2=""):
        self._lcd.clear()
        self._lcd.write_string(line1[:16])
        if line2:
            self._lcd.crlf()
            self._lcd.write_string(line2[:16])

    def clear(self):
        self._lcd.clear()


def make(cfg):
    """Instancia o driver real do display."""
    return RealDisplay()
