"""Минимальный драйвер LCD 1602A (HD44780) через I2C-переходник PCF8574.

Заменяет пакет rpi-lcd: тот тянет устаревший C-модуль smbus (нужно компилировать)
и по умолчанию рассчитан на экран 20x4 — пишет лишние символы с задержками
и тормозит сканирование клавиатуры. Здесь — smbus2 (чистый Python) и ровно 16x2.
"""

import time

from smbus2 import SMBus

LCD_WIDTH = 16
LINE_ADDR = {1: 0x80, 2: 0xC0}

BACKLIGHT = 0x08
ENABLE = 0x04
RS_DATA = 0x01


class LCD:
    def __init__(self, address=0x27, bus=1):
        """address: обычно 0x27, у некоторых модулей 0x3F (проверить: i2cdetect -y 1)."""
        self.address = address
        self.bus = SMBus(bus)
        time.sleep(0.05)
        # Инициализация в 4-битный режим (по даташиту HD44780)
        for cmd in (0x33, 0x32):
            self._command(cmd)
            time.sleep(0.005)
        self._command(0x28)  # 4 бита, 2 строки, шрифт 5x8
        self._command(0x0C)  # экран вкл, курсор выкл
        self._command(0x06)  # сдвиг курсора вправо
        self.clear()

    def _pulse(self, data):
        self.bus.write_byte(self.address, data | ENABLE | BACKLIGHT)
        self.bus.write_byte(self.address, (data & ~ENABLE) | BACKLIGHT)

    def _send(self, value, mode):
        self._pulse(mode | (value & 0xF0))
        self._pulse(mode | ((value << 4) & 0xF0))

    def _command(self, value):
        self._send(value, 0)

    def text(self, text, line):
        """Выводит строку (обрезается/дополняется до 16 символов) в строку 1 или 2."""
        self._command(LINE_ADDR.get(line, LINE_ADDR[1]))
        for ch in text[:LCD_WIDTH].ljust(LCD_WIDTH):
            code = ord(ch)
            self._send(code if code < 128 else ord("?"), RS_DATA)

    def clear(self):
        self._command(0x01)
        time.sleep(0.002)  # очистка экрана выполняется ~1.5 мс
