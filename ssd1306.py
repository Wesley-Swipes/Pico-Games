# ssd1306.py
# Clone-friendly SSD1306 I2C driver for 128x64 OLEDs with 132-column RAM mapping.
# Fixes "random dots/lines" that appear after showing an image by:
# - Writing full 132 bytes per page every frame
# - Offsetting the visible 128 columns by COL_OFFSET=4
# - Forcing hidden columns to zero every time
# - Sending data as ONE I2C transaction (required by many clone panels)

import framebuf

RAM_COLS   = 132
COL_OFFSET = 2  # your proven-good offset


class SSD1306:
    def __init__(self, width, height, external_vcc=False):
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.pages = self.height // 8

        # Standard 128x64 framebuffer
        self.buffer = bytearray(self.width * self.pages)
        self.framebuf = framebuf.FrameBuffer(self.buffer, self.width, self.height, framebuf.MONO_VLSB)

        # One reusable line buffer for page writes (132 bytes)
        self._line = bytearray(RAM_COLS)

        self.poweron()
        self.init_display()

    def poweron(self):
        pass

    def init_display(self):
        # MicroPython-standard SSD1306 init; PAGE addressing mode
        for cmd in (
            0xAE,             # display off
            0xD5, 0x80,       # clock divide
            0xA8, 0x3F,       # multiplex 1/64
            0xD3, 0x00,       # display offset
            0x40,             # start line
            0x8D, 0x14,       # charge pump
            0x20, 0x02,       # memory mode = Page Addressing Mode
            0xA1,             # seg remap
            0xC8,             # COM scan dir
            0xDA, 0x12,       # com pins
            0x81, 0xCF,       # contrast
            0xD9, 0xF1,       # precharge
            0xDB, 0x40,       # vcom detect
            0xA4,             # display follows RAM
            0xA6,             # normal
            0xAF              # display on
        ):
            self.write_cmd(cmd)

        # Hard scrub the controller RAM so the first image can't leave residue
        self._clear_controller_ram()

        self.fill(0)
        self.show()

    def _clear_controller_ram(self):
        # Force all pages, all 132 columns to 0 once at boot.
        # This prevents "appears after logo" ghost junk.
        zeros = b"\x00" * RAM_COLS
        for page in range(self.pages):
            self.write_cmd(0xB0 + page)
            self.write_cmd(0x00)  # col low = 0
            self.write_cmd(0x10)  # col high = 0
            self.write_data(zeros)

    def poweroff(self):
        self.write_cmd(0xAE)

    def contrast(self, contrast):
        self.write_cmd(0x81)
        self.write_cmd(contrast & 0xFF)

    def invert(self, invert):
        self.write_cmd(0xA7 if invert else 0xA6)

    # --- drawing proxies ---
    def fill(self, col): self.framebuf.fill(col)
    def pixel(self, x, y, col): self.framebuf.pixel(x, y, col)
    def scroll(self, dx, dy): self.framebuf.scroll(dx, dy)
    def text(self, s, x, y, col=1): self.framebuf.text(s, x, y, col)
    def rect(self, x, y, w, h, col): self.framebuf.rect(x, y, w, h, col)
    def fill_rect(self, x, y, w, h, col): self.framebuf.fill_rect(x, y, w, h, col)
    def blit(self, fbuf, x, y): self.framebuf.blit(fbuf, x, y)

    def show(self):
        # For each page:
        # - Set column to 0
        # - Build a 132-byte line of zeros
        # - Copy the 128 framebuffer bytes into columns 4..131
        # - Send the 132 bytes in ONE I2C transaction
        for page in range(self.pages):
            self.write_cmd(0xB0 + page)
            self.write_cmd(0x00)  # col low = 0
            self.write_cmd(0x10)  # col high = 0

            start = self.width * page
            end = start + self.width

            line = self._line
            # zero hidden + visible columns
            for i in range(RAM_COLS):
                line[i] = 0

            line[COL_OFFSET:COL_OFFSET + self.width] = self.buffer[start:end]
            self.write_data(line)

    def write_cmd(self, cmd):
        raise NotImplementedError

    def write_data(self, buf):
        raise NotImplementedError


class SSD1306_I2C(SSD1306):
    def __init__(self, width, height, i2c, addr=0x3C, external_vcc=False):
        self.i2c = i2c
        self.addr = addr
        self._tmp = bytearray(2)
        super().__init__(width, height, external_vcc)

    def write_cmd(self, cmd):
        self._tmp[0] = 0x80
        self._tmp[1] = cmd & 0xFF
        self.i2c.writeto(self.addr, self._tmp)

    def write_data(self, buf):
        # ONE transaction; required by many clone panels
        self.i2c.writeto(self.addr, b"\x40" + buf)
