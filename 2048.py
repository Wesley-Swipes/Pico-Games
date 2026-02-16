# 2048_v5.py — 2048 for Pico + SSD1306 (portrait 64x128)
#
# Change vs v4:
# - 4-digit tiles (1024/2048) now use a special ultra-narrow 2x5 digit font,
#   so they fit comfortably inside the 13x13 cell and remain readable.
#
# 1–2 digits: 3x5 font scale=2
# 3 digits : 3x5 font scale=1 (spacing=0)
# 4 digits : 2x5 narrow digits (spacing=0)
#
# Wiring / buttons:
#   OLED I2C0: SCL=21, SDA=20
#   UP=19, DOWN=18, RIGHT=16, LEFT=17 (active LOW, PULL_UP)

from machine import Pin, I2C
import ssd1306
import time
import random
import sys

time.sleep(0.15)

i2c = I2C(0, scl=Pin(21), sda=Pin(20))
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

btn_up    = Pin(19, Pin.IN, Pin.PULL_UP)
btn_down  = Pin(18, Pin.IN, Pin.PULL_UP)
btn_right = Pin(16, Pin.IN, Pin.PULL_UP)
btn_left  = Pin(17, Pin.IN, Pin.PULL_UP)

W, H = 64, 128  # logical portrait coords

def draw_pixel(x, y, c=1):
    if 0 <= x < 64 and 0 <= y < 128:
        oled.pixel(y, 63 - x, c)

def fill(c=0):
    oled.fill(c)

def show():
    oled.show()

class EdgeButtons:
    def __init__(self):
        self.u = 1; self.d = 1; self.l = 1; self.r = 1
    def update(self):
        nu = btn_up.value()
        nd = btn_down.value()
        nl = btn_left.value()
        nr = btn_right.value()
        pu = (self.u == 1 and nu == 0)
        pd = (self.d == 1 and nd == 0)
        pl = (self.l == 1 and nl == 0)
        pr = (self.r == 1 and nr == 0)
        self.u, self.d, self.l, self.r = nu, nd, nl, nr
        return pu, pd, pl, pr

def wait_released():
    while (not btn_up.value()) or (not btn_down.value()) or (not btn_left.value()) or (not btn_right.value()):
        time.sleep_ms(10)
    time.sleep_ms(70)

# ---- 3x5 font ----
GLYPH3x5 = {
    "0":[0b111,0b101,0b101,0b101,0b111],
    "1":[0b010,0b110,0b010,0b010,0b111],
    "2":[0b111,0b001,0b111,0b100,0b111],
    "3":[0b111,0b001,0b111,0b001,0b111],
    "4":[0b101,0b101,0b111,0b001,0b001],
    "5":[0b111,0b100,0b111,0b001,0b111],
    "6":[0b111,0b100,0b111,0b101,0b111],
    "7":[0b111,0b001,0b010,0b010,0b010],
    "8":[0b111,0b101,0b111,0b101,0b111],
    "9":[0b111,0b101,0b111,0b001,0b111],

    "A":[0b111,0b101,0b111,0b101,0b101],
    "B":[0b110,0b101,0b110,0b101,0b110],
    "C":[0b111,0b100,0b100,0b100,0b111],
    "D":[0b110,0b101,0b101,0b101,0b110],
    "E":[0b111,0b100,0b111,0b100,0b111],
    "G":[0b111,0b100,0b101,0b101,0b111],
    "I":[0b111,0b010,0b010,0b010,0b111],
    "M":[0b101,0b111,0b111,0b101,0b101],
    "N":[0b101,0b111,0b111,0b111,0b101],
    "O":[0b111,0b101,0b101,0b101,0b111],
    "P":[0b110,0b101,0b110,0b100,0b100],
    "Q":[0b111,0b101,0b101,0b111,0b001],
    "R":[0b110,0b101,0b110,0b101,0b101],
    "S":[0b111,0b100,0b111,0b001,0b111],
    "T":[0b111,0b010,0b010,0b010,0b010],
    "U":[0b101,0b101,0b101,0b101,0b111],
    "V":[0b101,0b101,0b101,0b101,0b010],
    "W":[0b101,0b101,0b101,0b111,0b111],

    " ": [0,0,0,0,0],
    ":": [0b000,0b010,0b000,0b010,0b000],
    "-": [0b000,0b000,0b111,0b000,0b000],
    "/": [0b001,0b010,0b010,0b100,0b100],
}

def draw_glyph3x5(ch, x, y, scale=1, c=1):
    rows = GLYPH3x5.get(ch, GLYPH3x5[" "])
    for ry in range(5):
        bits = rows[ry]
        for rx in range(3):
            if (bits >> (2-rx)) & 1:
                for sy in range(scale):
                    for sx in range(scale):
                        draw_pixel(x + rx*scale + sx, y + ry*scale + sy, c)

def text_width_3x5(s, scale=1, spacing=1):
    if not s:
        return 0
    return len(s) * (3*scale) + (len(s)-1) * (spacing*scale)

def draw_text_3x5(s, x, y, scale=1, spacing=1, c=1):
    cx = x
    step = 3*scale + spacing*scale
    for ch in s:
        draw_glyph3x5(ch, cx, y, scale=scale, c=c)
        cx += step

def draw_text_center(s, cy, scale=1):
    w = text_width_3x5(s, scale=scale, spacing=1)
    x = (W - w) // 2
    draw_text_3x5(s, x, cy, scale=scale)

# ---- ultra-narrow 2x5 digit font (for 4-digit tiles only) ----
# Each digit is 2 bits wide, 5 rows. Bits are MSB-first (bit1..bit0).
DIG2x5 = {
    "0":[0b11,0b10,0b10,0b10,0b11],
    "1":[0b01,0b11,0b01,0b01,0b11],
    "2":[0b11,0b01,0b11,0b10,0b11],
    "3":[0b11,0b01,0b11,0b01,0b11],
    "4":[0b10,0b10,0b11,0b01,0b01],
    "5":[0b11,0b10,0b11,0b01,0b11],
    "6":[0b11,0b10,0b11,0b10,0b11],
    "7":[0b11,0b01,0b01,0b10,0b10],
    "8":[0b11,0b10,0b11,0b10,0b11],
    "9":[0b11,0b10,0b11,0b01,0b11],
}

def draw_digit2(dch, x, y, c=1):
    rows = DIG2x5.get(dch)
    if not rows:
        return
    for ry in range(5):
        bits = rows[ry]
        if (bits >> 1) & 1: draw_pixel(x+0, y+ry, c)
        if (bits >> 0) & 1: draw_pixel(x+1, y+ry, c)

def text_width_2x5_digits(s, spacing=0):
    if not s:
        return 0
    return len(s)*2 + (len(s)-1)*spacing

def draw_digits_2x5(s, x, y, spacing=0):
    cx = x
    for ch in s:
        draw_digit2(ch, cx, y, 1)
        cx += 2 + spacing

# ---- UI primitives ----
def draw_rect(x, y, w, h, c=1):
    for i in range(w):
        draw_pixel(x+i, y, c)
        draw_pixel(x+i, y+h-1, c)
    for j in range(h):
        draw_pixel(x, y+j, c)
        draw_pixel(x+w-1, y+j, c)

# ---- 2048 logic ----
SIZE = 4

def new_board():
    b = [[0]*SIZE for _ in range(SIZE)]
    add_tile(b); add_tile(b)
    return b

def empty_cells(b):
    out = []
    for r in range(SIZE):
        for c in range(SIZE):
            if b[r][c] == 0:
                out.append((r,c))
    return out

def add_tile(b):
    cells = empty_cells(b)
    if not cells:
        return False
    r,c = cells[random.randint(0, len(cells)-1)]
    b[r][c] = 4 if random.random() < 0.10 else 2
    return True

def compress_line(line):
    out = [v for v in line if v != 0]
    out += [0]*(SIZE - len(out))
    return out

def merge_line(line):
    score_add = 0
    for i in range(SIZE-1):
        if line[i] != 0 and line[i] == line[i+1]:
            line[i] *= 2
            score_add += line[i]
            line[i+1] = 0
    return line, score_add

def move_left(b):
    moved = False; score_add = 0
    for r in range(SIZE):
        line = compress_line(b[r][:])
        line, s = merge_line(line)
        line = compress_line(line)
        if line != b[r]:
            moved = True
            b[r] = line
        score_add += s
    return moved, score_add

def move_right(b):
    moved = False; score_add = 0
    for r in range(SIZE):
        line = list(reversed(b[r]))
        line = compress_line(line)
        line, s = merge_line(line)
        line = compress_line(line)
        line = list(reversed(line))
        if line != b[r]:
            moved = True
            b[r] = line
        score_add += s
    return moved, score_add

def move_up(b):
    moved = False; score_add = 0
    for c in range(SIZE):
        col = [b[r][c] for r in range(SIZE)]
        col = compress_line(col)
        col, s = merge_line(col)
        col = compress_line(col)
        for r in range(SIZE):
            if b[r][c] != col[r]:
                moved = True
            b[r][c] = col[r]
        score_add += s
    return moved, score_add

def move_down(b):
    moved = False; score_add = 0
    for c in range(SIZE):
        col = [b[r][c] for r in range(SIZE)]
        col = list(reversed(col))
        col = compress_line(col)
        col, s = merge_line(col)
        col = compress_line(col)
        col = list(reversed(col))
        for r in range(SIZE):
            if b[r][c] != col[r]:
                moved = True
            b[r][c] = col[r]
        score_add += s
    return moved, score_add

def any_moves(b):
    if empty_cells(b):
        return True
    for r in range(SIZE):
        for c in range(SIZE-1):
            if b[r][c] == b[r][c+1]:
                return True
    for c in range(SIZE):
        for r in range(SIZE-1):
            if b[r][c] == b[r+1][c]:
                return True
    return False

def max_tile(b):
    m = 0
    for r in b:
        for v in r:
            if v > m: m = v
    return m

# ---- screens ----
def title_screen():
    fill(0)
    draw_text_center("2048", 22, scale=4)
    draw_text_center("UP START", 78, scale=2)
    draw_text_center("DN QUIT", 98, scale=2)
    show()
    wait_released()
    while True:
        if not btn_up.value():
            time.sleep_ms(180); return True
        if not btn_down.value():
            time.sleep_ms(180); return False
        time.sleep_ms(20)

def game_over_screen(score, best):
    fill(0)
    draw_text_center("GAME", 16, scale=3)
    draw_text_center("OVER", 40, scale=3)

    draw_text_center("SCORE", 76, scale=2)
    draw_text_center(str(score), 96, scale=2)

    draw_text_center("UP AGAIN", 116, scale=2)
    show()
    wait_released()
    while True:
        if not btn_up.value():
            time.sleep_ms(180); return True
        if not btn_down.value():
            time.sleep_ms(180); return False
        time.sleep_ms(20)

def win_screen(score):
    fill(0)
    draw_text_center("YOU WIN", 16, scale=2)
    draw_text_center("2048", 40, scale=3)
    draw_text_center("UP CONT", 82, scale=2)
    draw_text_center("DN QUIT", 104, scale=2)
    draw_text_center("S"+str(score), 122, scale=1)
    show()
    wait_released()
    while True:
        if not btn_up.value():
            time.sleep_ms(180); return True
        if not btn_down.value():
            time.sleep_ms(180); return False
        time.sleep_ms(20)

# ---- tile number renderer ----
def draw_tile_number(v, x, y, cell):
    s = str(v)

    if len(s) <= 2:
        sc = 2
        spacing = 1
        tw = text_width_3x5(s, scale=sc, spacing=spacing)
        tx = x + (cell - tw)//2
        ty = y + (cell - (5*sc))//2
        draw_text_3x5(s, tx, ty, scale=sc, spacing=spacing)
        return

    if len(s) == 3:
        sc = 1
        spacing = 0
        tw = text_width_3x5(s, scale=sc, spacing=spacing)
        tx = x + (cell - tw)//2
        ty = y + (cell - (5*sc))//2
        draw_text_3x5(s, tx, ty, scale=sc, spacing=spacing)
        return

    # 4 digits (1024/2048): ultra-narrow 2x5 font
    tw = text_width_2x5_digits(s, spacing=0)
    tx = x + (cell - tw)//2
    ty = y + (cell - 5)//2
    draw_digits_2x5(s, tx, ty, spacing=0)

# ---- rendering ----
def draw_board(b, score, best):
    fill(0)

    draw_text_3x5("SCORE", 2, 2, scale=1)
    draw_text_3x5(str(score)[:10], 2, 10, scale=1)
    draw_text_3x5("BEST", 40, 2, scale=1)
    draw_text_3x5(str(best)[:10], 40, 10, scale=1)

    gap = 2
    cell = 13
    bw = SIZE*cell + (SIZE-1)*gap
    bh = SIZE*cell + (SIZE-1)*gap
    bx = (W - bw)//2
    by = 22

    draw_rect(bx-2, by-2, bw+4, bh+4, 1)

    for r in range(SIZE):
        for c in range(SIZE):
            v = b[r][c]
            x = bx + c*(cell+gap)
            y = by + r*(cell+gap)
            draw_rect(x, y, cell, cell, 1)
            if v:
                draw_tile_number(v, x, y, cell)

    draw_text_center("UP/DN/L/R", 112, scale=1)
    show()

# ---- main ----
def main():
    eb = EdgeButtons()
    best_score = 0

    while True:
        if not title_screen():
            sys.exit()

        board = new_board()
        score = 0
        won = False

        wait_released()
        draw_board(board, score, best_score)

        while True:
            pu, pd, pl, pr = eb.update()
            moved = False
            add = 0

            if pl:
                moved, add = move_left(board)
            elif pr:
                moved, add = move_right(board)
            elif pu:
                moved, add = move_up(board)
            elif pd:
                moved, add = move_down(board)

            if moved:
                score += add
                if score > best_score:
                    best_score = score
                add_tile(board)

                if (not won) and max_tile(board) >= 2048:
                    won = True
                    draw_board(board, score, best_score)
                    if not win_screen(score):
                        sys.exit()

                draw_board(board, score, best_score)

                if not any_moves(board):
                    if not game_over_screen(score, best_score):
                        sys.exit()
                    break

                time.sleep_ms(90)

            time.sleep_ms(20)

main()
