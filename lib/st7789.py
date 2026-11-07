# Minimal ST7789 / ST7735S driver for SPI displays.
# The RP2040-LCD-0.96 uses an ST7735S; the commands used here are shared by both.

import time


class ST7789:
    def __init__(self, spi, width, height, dc, cs, rst, bl, xstart=0, ystart=0, rotation=0,
                 bgr=False, invert=False):
        self.spi = spi
        self.width = width
        self.height = height
        self.dc = dc
        self.cs = cs
        self.rst = rst
        self.bl = bl
        self.xstart = xstart
        self.ystart = ystart
        self.rotation = rotation
        self.bgr = bgr
        self.invert = invert
        self.cs.init(self.cs.OUT, value=1)
        self.dc.init(self.dc.OUT, value=0)
        self.rst.init(self.rst.OUT, value=1)
        self.bl.init(self.bl.OUT, value=1)
        self._init_display()

    def _write_cmd(self, cmd):
        self.dc(0)
        self.cs(0)
        self.spi.write(bytearray([cmd]))
        self.cs(1)

    def _write_data(self, data):
        self.dc(1)
        self.cs(0)
        self.spi.write(data)
        self.cs(1)

    def _init_display(self):
        self.rst(0)
        time.sleep_ms(50)
        self.rst(1)
        time.sleep_ms(50)

        self._write_cmd(0x01)  # SWRESET
        time.sleep_ms(150)
        self._write_cmd(0x11)  # SLPOUT
        time.sleep_ms(120)

        self._write_cmd(0x3A)  # COLMOD
        self._write_data(b"\x55")  # 16-bit

        madctl = 0x00
        if self.rotation == 1:
            madctl = 0x60
        elif self.rotation == 2:
            madctl = 0xC0
        elif self.rotation == 3:
            madctl = 0xA0
        if self.bgr:
            madctl |= 0x08

        self._write_cmd(0x36)  # MADCTL
        self._write_data(bytearray([madctl]))

        self._write_cmd(0x21 if self.invert else 0x20)  # INVON / INVOFF

        self._write_cmd(0x29)  # DISPON
        time.sleep_ms(50)

    def set_window(self, x0, y0, x1, y1):
        x0 += self.xstart
        x1 += self.xstart
        y0 += self.ystart
        y1 += self.ystart
        self._write_cmd(0x2A)
        self._write_data(bytearray([x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF]))
        self._write_cmd(0x2B)
        self._write_data(bytearray([y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF]))
        self._write_cmd(0x2C)

    def blit_buffer(self, buffer, x, y, w, h):
        self.set_window(x, y, x + w - 1, y + h - 1)
        self.dc(1)
        self.cs(0)
        self.spi.write(buffer)
        self.cs(1)

    def fill(self, row):
        # Fill the whole panel with one row of pixel data (width * 2 bytes), repeated
        self.set_window(0, 0, self.width - 1, self.height - 1)
        self.dc(1)
        self.cs(0)
        for _ in range(self.height):
            self.spi.write(row)
        self.cs(1)
