# minesweeper_v5.py — Minesweeper for Pico + SSD1306 (portrait 64x128)
#
# Changes vs v4 (per request):
# - End (BOOM / YOU WIN) screen: moved everything UP so nothing is off-screen.
# - In-game hints: smaller font (scale=1) and centered.
#
# Controls:
#   UP/DN/L/R : move cursor
#   UP+DN tap : reveal cell at cursor
#   L+R  tap  : flag/unflag cell at cursor
#   UP+DN hold (~0.7s): restart
#   DOWN on title/end: return to menu (exit script)

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

W, H = 64, 128

def draw_pixel(x, y, c=1):
    if 0 <= x < 64 and 0 <= y < 128:
        oled.pixel(y, 63 - x, c)

def fill(c=0):
    oled.fill(c)

def show():
    oled.show()

def any_pressed():
    return (not btn_up.value()) or (not btn_down.value()) or (not btn_left.value()) or (not btn_right.value())

def wait_released():
    while any_pressed():
        time.sleep_ms(10)
    time.sleep_ms(60)

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

GLYPH = {
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
    "F":[0b111,0b100,0b111,0b100,0b100],
    "G":[0b111,0b100,0b101,0b101,0b111],
    "I":[0b111,0b010,0b010,0b010,0b111],
    "L":[0b100,0b100,0b100,0b100,0b111],
    "M":[0b101,0b111,0b111,0b101,0b101],
    "N":[0b101,0b111,0b111,0b111,0b101],
    "O":[0b111,0b101,0b101,0b101,0b111],
    "P":[0b110,0b101,0b110,0b100,0b100],
    "R":[0b110,0b101,0b110,0b101,0b101],
    "S":[0b111,0b100,0b111,0b001,0b111],
    "T":[0b111,0b010,0b010,0b010,0b010],
    "U":[0b101,0b101,0b101,0b101,0b111],
    "V":[0b101,0b101,0b101,0b101,0b010],
    "W":[0b101,0b101,0b101,0b111,0b111],
    "Y":[0b101,0b101,0b010,0b010,0b010],

    " ": [0,0,0,0,0],
    ":": [0b000,0b010,0b000,0b010,0b000],
    "-": [0b000,0b000,0b111,0b000,0b000],
    "+": [0b000,0b010,0b111,0b010,0b000],
}

def draw_glyph(ch, x, y, scale=1, c=1):
    rows = GLYPH.get(ch, GLYPH[" "])
    for ry in range(5):
        bits = rows[ry]
        for rx in range(3):
            if (bits >> (2-rx)) & 1:
                for sy in range(scale):
                    for sx in range(scale):
                        draw_pixel(x + rx*scale + sx, y + ry*scale + sy, c)

def text_width(s, scale=1, spacing=1):
    if not s:
        return 0
    return len(s) * (3*scale) + (len(s)-1) * (spacing*scale)

def draw_text(s, x, y, scale=1, spacing=1, c=1):
    cx = x
    step = 3*scale + spacing*scale
    for ch in s:
        draw_glyph(ch, cx, y, scale=scale, c=c)
        cx += step

def draw_text_center(s, y, scale=1):
    w = text_width(s, scale=scale, spacing=1)
    x = (W - w)//2
    draw_text(s, x, y, scale=scale)

def draw_rect(x, y, w, h, c=1):
    for i in range(w):
        draw_pixel(x+i, y, c)
        draw_pixel(x+i, y+h-1, c)
    for j in range(h):
        draw_pixel(x, y+j, c)
        draw_pixel(x+w-1, y+j, c)

def draw_flag(cx, cy):
    draw_pixel(cx, cy-2, 1)
    draw_pixel(cx, cy-1, 1)
    draw_pixel(cx, cy, 1)
    draw_pixel(cx, cy+1, 1)
    draw_pixel(cx+1, cy-2, 1)
    draw_pixel(cx+2, cy-1, 1)
    draw_pixel(cx+1, cy, 1)
    draw_pixel(cx-1, cy+2, 1)
    draw_pixel(cx,   cy+2, 1)
    draw_pixel(cx+1, cy+2, 1)

def draw_mine(cx, cy):
    draw_pixel(cx, cy, 1)
    for d in (-2, -1, 1, 2):
        draw_pixel(cx+d, cy, 1)
        draw_pixel(cx, cy+d, 1)
    draw_pixel(cx-1, cy-1, 1); draw_pixel(cx+1, cy-1, 1)
    draw_pixel(cx-1, cy+1, 1); draw_pixel(cx+1, cy+1, 1)

ROWS = 8
COLS = 8
MINES = 10

CELL = 7
GAP = 1
GRID_W = COLS*CELL + (COLS-1)*GAP
GRID_H = ROWS*CELL + (ROWS-1)*GAP
GRID_X = (W - GRID_W)//2
GRID_Y = 22

COVERED = 0
REVEALED = 1

def in_bounds(r, c):
    return 0 <= r < ROWS and 0 <= c < COLS

def neighbors(r, c):
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            rr = r + dr
            cc = c + dc
            if in_bounds(rr, cc):
                yield rr, cc

def make_empty():
    mines = [[False]*COLS for _ in range(ROWS)]
    nums  = [[0]*COLS for _ in range(ROWS)]
    vis   = [[COVERED]*COLS for _ in range(ROWS)]
    flag  = [[False]*COLS for _ in range(ROWS)]
    return mines, nums, vis, flag

def place_mines(mines, nums, safe_r, safe_c):
    blocked = set()
    for rr in range(safe_r-1, safe_r+2):
        for cc in range(safe_c-1, safe_c+2):
            if in_bounds(rr, cc):
                blocked.add((rr, cc))

    spots = []
    for r in range(ROWS):
        for c in range(COLS):
            if (r, c) not in blocked:
                spots.append((r, c))

    mines_to_place = MINES
    while mines_to_place > 0 and spots:
        idx = random.getrandbits(16) % len(spots)
        r, c = spots.pop(idx)
        mines[r][c] = True
        mines_to_place -= 1

    for r in range(ROWS):
        for c in range(COLS):
            if mines[r][c]:
                nums[r][c] = -1
            else:
                cnt = 0
                for rr, cc in neighbors(r, c):
                    if mines[rr][cc]:
                        cnt += 1
                nums[r][c] = cnt

def flood_reveal(nums, vis, flag, start_r, start_c):
    q = [(start_r, start_c)]
    seen = set(q)
    while q:
        r, c = q.pop()
        if flag[r][c]:
            continue
        vis[r][c] = REVEALED
        if nums[r][c] != 0:
            continue
        for rr, cc in neighbors(r, c):
            if (rr, cc) in seen:
                continue
            if flag[rr][cc]:
                continue
            if vis[rr][cc] == REVEALED:
                continue
            seen.add((rr, cc))
            q.append((rr, cc))

def count_flags(flag):
    n = 0
    for r in range(ROWS):
        for c in range(COLS):
            if flag[r][c]:
                n += 1
    return n

def count_revealed(vis):
    n = 0
    for r in range(ROWS):
        for c in range(COLS):
            if vis[r][c] == REVEALED:
                n += 1
    return n

def is_win(vis):
    return count_revealed(vis) == (ROWS*COLS - MINES)

def draw_header(mines_left, elapsed_ms):
    draw_text("MINES", 2, 2, scale=1)
    draw_text(str(mines_left), 2, 10, scale=1)
    draw_text("TIME", 40, 2, scale=1)
    draw_text(str(elapsed_ms//1000), 40, 10, scale=1)

def draw_grid(mines, nums, vis, flag, cur_r, cur_c, reveal_all_mines=False):
    for r in range(ROWS):
        for c in range(COLS):
            x = GRID_X + c*(CELL+GAP)
            y = GRID_Y + r*(CELL+GAP)

            draw_rect(x, y, CELL, CELL, 1)
            if r == cur_r and c == cur_c:
                draw_rect(x-1, y-1, CELL+2, CELL+2, 1)

            if vis[r][c] == COVERED:
                if flag[r][c]:
                    draw_flag(x + CELL//2, y + CELL//2)
                elif reveal_all_mines and mines[r][c]:
                    draw_mine(x + CELL//2, y + CELL//2)
            else:
                if mines[r][c]:
                    draw_mine(x + CELL//2, y + CELL//2)
                else:
                    n = nums[r][c]
                    if n > 0:
                        s = str(n)
                        tw = text_width(s, scale=1, spacing=0)
                        tx = x + (CELL - tw)//2
                        ty = y + (CELL - 5)//2
                        draw_text(s, tx, ty, scale=1, spacing=0)

def draw_hints():
    draw_text_center("UD REVEAL", 96, scale=1)
    draw_text_center("LR FLAG",   108, scale=1)

def render_game(mines, nums, vis, flag, cur_r, cur_c, mines_left, elapsed_ms, reveal_all_mines=False):
    fill(0)
    draw_header(mines_left, elapsed_ms)
    draw_grid(mines, nums, vis, flag, cur_r, cur_c, reveal_all_mines=reveal_all_mines)
    draw_hints()
    show()

def title_screen():
    fill(0)
    draw_text_center("MINE", 22, scale=3)
    draw_text_center("SWEEPER", 48, scale=2)
    draw_text_center("UP START", 82, scale=2)
    draw_text_center("DN MENU", 104, scale=2)
    show()
    wait_released()
    while True:
        if not btn_up.value():
            time.sleep_ms(180); return True
        if not btn_down.value():
            time.sleep_ms(180); return False
        time.sleep_ms(20)

def end_screen(win, elapsed_ms):
    fill(0)
    if win:
        draw_text_center("YOU WIN", 10, scale=2)
    else:
        draw_text_center("BOOM", 10, scale=3)

    draw_text_center("TIME", 44, scale=2)
    draw_text_center(str(elapsed_ms//1000), 62, scale=2)

    draw_text_center("UP AGAIN", 88, scale=2)
    draw_text_center("DN MENU", 108, scale=2)

    show()
    wait_released()
    while True:
        if not btn_up.value():
            time.sleep_ms(180); return True
        if not btn_down.value():
            time.sleep_ms(180); return False
        time.sleep_ms(20)

def chord_pressed():
    up = (btn_up.value() == 0)
    dn = (btn_down.value() == 0)
    lf = (btn_left.value() == 0)
    rt = (btn_right.value() == 0)
    return up, dn, lf, rt

def detect_action_chords(last_action_ms):
    up, dn, lf, rt = chord_pressed()
    now = time.ticks_ms()

    if up and dn:
        t0 = now
        while (btn_up.value() == 0) and (btn_down.value() == 0):
            if time.ticks_diff(time.ticks_ms(), t0) > 700:
                return "restart"
            time.sleep_ms(10)
        if time.ticks_diff(now, last_action_ms) > 160:
            return "reveal"

    if lf and rt:
        while (btn_left.value() == 0) and (btn_right.value() == 0):
            time.sleep_ms(10)
        if time.ticks_diff(now, last_action_ms) > 160:
            return "flag"

    return None

def main():
    eb = EdgeButtons()

    while True:
        if not title_screen():
            sys.exit()

        mines, nums, vis, flag = make_empty()
        cur_r, cur_c = 0, 0
        started = False
        start_ms = 0
        last_action_ms = 0

        wait_released()

        while True:
            now = time.ticks_ms()
            elapsed = 0 if not started else time.ticks_diff(now, start_ms)
            mines_left = MINES - count_flags(flag)

            render_game(mines, nums, vis, flag, cur_r, cur_c, mines_left, elapsed, reveal_all_mines=False)

            pu, pd, pl, pr = eb.update()
            if pu:
                cur_r = (cur_r - 1) % ROWS
            elif pd:
                cur_r = (cur_r + 1) % ROWS
            elif pl:
                cur_c = (cur_c - 1) % COLS
            elif pr:
                cur_c = (cur_c + 1) % COLS

            act = detect_action_chords(last_action_ms)
            if act:
                last_action_ms = time.ticks_ms()

            if act == "restart":
                break

            if act == "flag":
                if vis[cur_r][cur_c] == COVERED:
                    flag[cur_r][cur_c] = not flag[cur_r][cur_c]

            if act == "reveal":
                if vis[cur_r][cur_c] == COVERED and not flag[cur_r][cur_c]:
                    if not started:
                        place_mines(mines, nums, cur_r, cur_c)
                        started = True
                        start_ms = time.ticks_ms()
                        elapsed = 0

                    if mines[cur_r][cur_c]:
                        vis[cur_r][cur_c] = REVEALED
                        render_game(mines, nums, vis, flag, cur_r, cur_c, mines_left, elapsed, reveal_all_mines=True)
                        draw_text_center("BOOM", 92, scale=3)
                        show()
                        time.sleep_ms(900)
                        if not end_screen(False, elapsed):
                            sys.exit()
                        break
                    else:
                        if nums[cur_r][cur_c] == 0:
                            flood_reveal(nums, vis, flag, cur_r, cur_c)
                        else:
                            vis[cur_r][cur_c] = REVEALED

                        if is_win(vis):
                            render_game(mines, nums, vis, flag, cur_r, cur_c, mines_left, elapsed, reveal_all_mines=True)
                            draw_text_center("CLEARED", 92, scale=2)
                            show()
                            time.sleep_ms(900)
                            if not end_screen(True, elapsed):
                                sys.exit()
                            break

            time.sleep_ms(35)

main()
