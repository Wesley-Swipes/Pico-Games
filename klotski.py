# klotski_v2.py — Klotski (Hua Rong Dao) for Pico + SSD1306 (portrait 64x128)
#
# v2 changes:
# - Adds 5 total puzzles (the original + 4 more).
# - Title screen lets you pick puzzle with LEFT/RIGHT.
# - Win screen offers "UP AGAIN" (replay same) or RIGHT "NEXT" (advance).
#
# Controls
#   Title:
#     LEFT/RIGHT : choose puzzle
#     UP         : start
#     DOWN       : menu (exit)
#
#   In game:
#     D-pad            : move cursor (when not grabbing)
#     UP+DOWN (tap)    : GRAB / RELEASE the piece under cursor
#     D-pad (grabbed)  : move grabbed piece (1 cell per press if valid)
#     UP+DOWN (hold)   : RESET current puzzle
#
# Win condition:
#   2x2 "Cao Cao" block reaches the bottom middle exit.

from machine import Pin, I2C
import ssd1306
import time
import sys

time.sleep(0.15)

# ---- Hardware ----
i2c = I2C(0, scl=Pin(21), sda=Pin(20))
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

btn_up    = Pin(19, Pin.IN, Pin.PULL_UP)
btn_down  = Pin(18, Pin.IN, Pin.PULL_UP)
btn_right = Pin(16, Pin.IN, Pin.PULL_UP)
btn_left  = Pin(17, Pin.IN, Pin.PULL_UP)

# Logical portrait space
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

# ---- Tiny 3x5 font ----
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
    "G":[0b111,0b100,0b101,0b101,0b111],
    "I":[0b111,0b010,0b010,0b010,0b111],
    "K":[0b101,0b110,0b100,0b110,0b101],
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
    "X":[0b101,0b101,0b010,0b101,0b101],
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

# ---- Drawing helpers ----
def draw_rect(x, y, w, h, c=1):
    for i in range(w):
        draw_pixel(x+i, y, c)
        draw_pixel(x+i, y+h-1, c)
    for j in range(h):
        draw_pixel(x, y+j, c)
        draw_pixel(x+w-1, y+j, c)

def pattern_fill(x, y, w, h, pid):
    for j in range(1, h-1):
        for i in range(1, w-1):
            v = 0
            if pid == 1:
                v = ((i + j) % 2 == 0)
            elif pid in (2, 3):
                v = (i % 2 == 0)
            elif pid == 4:
                v = ((i % 3 == 0) and (j % 2 == 0))
            elif pid in (5, 6):
                v = (j % 2 == 0)
            else:
                v = ((i + pid) % 3 == 0) and ((j + pid) % 2 == 0)
            if v:
                draw_pixel(x+i, y+j, 1)

# ---- Klotski board ----
BR, BC = 5, 4

PIECES = {
    1: (2, 2),  # Cao Cao
    2: (1, 2),
    3: (1, 2),
    4: (2, 1),
    5: (1, 2),
    6: (1, 2),
    7: (1, 1),
    8: (1, 1),
    9: (1, 1),
    10:(1, 1),
}

# Puzzles: all use the same piece set, just rearranged.
# 0 is empty.
PUZZLES = [
    # Puzzle 1 (classic start)
    [
        [2, 1, 1, 5],
        [2, 1, 1, 5],
        [3, 4, 4, 6],
        [3, 7, 8, 6],
        [9, 0, 0,10],
    ],
    # Puzzle 2 (easier-ish: more freedom near bottom)
    [
        [2, 1, 1, 5],
        [2, 1, 1, 5],
        [3, 4, 4, 6],
        [3, 7, 0, 6],
        [9, 8, 0,10],
    ],
    # Puzzle 3 (mid: soldiers clustered, need reshuffle)
    [
        [2, 1, 1, 5],
        [2, 1, 1, 5],
        [3, 7, 8, 6],
        [3, 4, 4, 6],
        [9, 0, 0,10],
    ],
    # Puzzle 4 (mid+: Guan Yu higher, requires more staging)
    [
        [2, 1, 1, 5],
        [2, 1, 1, 5],
        [3, 7, 8, 6],
        [3, 9,10, 6],
        [0, 4, 4, 0],
    ],
    # Puzzle 5 (harder: empties split at bottom corners)
    [
        [2, 1, 1, 5],
        [2, 1, 1, 5],
        [3, 4, 4, 6],
        [3, 7, 8, 6],
        [0, 9,10, 0],
    ],
]

def clone_board(b):
    return [row[:] for row in b]

def find_piece_cells(board, pid):
    cells = []
    for r in range(BR):
        for c in range(BC):
            if board[r][c] == pid:
                cells.append((r, c))
    return cells

def piece_top_left(board, pid):
    cells = find_piece_cells(board, pid)
    if not cells:
        return None
    r0 = min(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    return r0, c0

def validate_board(board):
    # Basic sanity: counts per piece match expected area
    counts = {}
    for r in range(BR):
        for c in range(BC):
            pid = board[r][c]
            if pid == 0:
                continue
            counts[pid] = counts.get(pid, 0) + 1
    for pid, (w, h) in PIECES.items():
        if counts.get(pid, 0) != w*h:
            return False
    empties = 0
    for r in range(BR):
        for c in range(BC):
            if board[r][c] == 0:
                empties += 1
    return empties == 2

def can_move(board, pid, dr, dc):
    tl = piece_top_left(board, pid)
    if tl is None:
        return False
    pr, pc = tl
    pw, ph = PIECES[pid]
    nr, nc = pr + dr, pc + dc
    if nr < 0 or nc < 0 or nr + ph > BR or nc + pw > BC:
        return False
    for r in range(nr, nr + ph):
        for c in range(nc, nc + pw):
            v = board[r][c]
            if v != 0 and v != pid:
                return False
    return True

def move_piece(board, pid, dr, dc):
    if not can_move(board, pid, dr, dc):
        return False
    pr, pc = piece_top_left(board, pid)
    pw, ph = PIECES[pid]
    for r in range(pr, pr + ph):
        for c in range(pc, pc + pw):
            board[r][c] = 0
    nr, nc = pr + dr, pc + dc
    for r in range(nr, nr + ph):
        for c in range(nc, nc + pw):
            board[r][c] = pid
    return True

def is_win(board):
    return piece_top_left(board, 1) == (3, 1)

# ---- Layout / render ----
CELL = 14
GAP = 2
GRID_W = BC*CELL + (BC-1)*GAP
GRID_H = BR*CELL + (BR-1)*GAP
GRID_X = (W - GRID_W)//2
GRID_Y = 24

def render(board, cur_r, cur_c, grabbed_pid, moves, pidx):
    fill(0)

    draw_text("KLOT", 2, 2, scale=1)
    draw_text("P", 38, 2, scale=1)
    draw_text(str(pidx+1), 46, 2, scale=1)
    draw_text("M", 38, 10, scale=1)
    draw_text(str(moves), 46, 10, scale=1)

    # exit door
    exit_x = GRID_X + 1*(CELL+GAP)
    exit_y = GRID_Y + GRID_H + 2
    draw_rect(exit_x, exit_y, 2*CELL + GAP, 6, 1)

    drawn = set()
    for r in range(BR):
        for c in range(BC):
            pid = board[r][c]
            if pid == 0 or pid in drawn:
                continue
            drawn.add(pid)
            tl = piece_top_left(board, pid)
            if tl is None:
                continue
            pr, pc = tl
            pw, ph = PIECES[pid]
            x = GRID_X + pc*(CELL+GAP)
            y = GRID_Y + pr*(CELL+GAP)
            w = pw*CELL + (pw-1)*GAP
            h = ph*CELL + (ph-1)*GAP
            draw_rect(x, y, w, h, 1)
            pattern_fill(x, y, w, h, pid)
            if grabbed_pid == pid:
                draw_rect(x-1, y-1, w+2, h+2, 1)

    cx = GRID_X + cur_c*(CELL+GAP)
    cy = GRID_Y + cur_r*(CELL+GAP)
    draw_rect(cx-1, cy-1, CELL+2, CELL+2, 1)

    draw_text_center("UD GRAB", 112, scale=1)
    draw_text_center("HOLD UD RESET", 122, scale=1)

    show()

def title_screen(pidx):
    fill(0)
    draw_text_center("KLOTSKI", 16, scale=2)
    draw_text_center(str(pidx+1), 64, scale=2)
    draw_text_center("LR PICK", 92, scale=2)
    draw_text_center("UP START", 110, scale=2)
    draw_text_center("DN MENU", 124, scale=2)
    show()

def win_screen(moves, pidx):
    fill(0)
    draw_text_center("CLEARED", 10, scale=2)
    draw_text_center("PUZZLE", 34, scale=2)
    draw_text_center(str(pidx+1), 52, scale=3)
    draw_text_center("MOVES", 78, scale=2)
    draw_text_center(str(moves), 96, scale=2)
    draw_text_center("UP AGAIN", 114, scale=2)
    draw_text_center("RT NEXT", 126, scale=2)
    show()

def chord_pressed():
    up = (btn_up.value() == 0)
    dn = (btn_down.value() == 0)
    lf = (btn_left.value() == 0)
    rt = (btn_right.value() == 0)
    return up, dn, lf, rt

def detect_ud_action(last_action_ms):
    up, dn, _, _ = chord_pressed()
    now = time.ticks_ms()
    if up and dn:
        t0 = now
        while (btn_up.value() == 0) and (btn_down.value() == 0):
            if time.ticks_diff(time.ticks_ms(), t0) > 700:
                return "reset"
            time.sleep_ms(10)
        if time.ticks_diff(now, last_action_ms) > 160:
            return "grab"
    return None

def pid_under_cursor(board, r, c):
    pid = board[r][c]
    return pid if pid != 0 else None

def pick_puzzle():
    eb = EdgeButtons()
    pidx = 0
    wait_released()
    while True:
        title_screen(pidx)
        pu, pd, pl, pr = eb.update()

        if pl:
            pidx = (pidx - 1) % len(PUZZLES)
            time.sleep_ms(120)
        elif pr:
            pidx = (pidx + 1) % len(PUZZLES)
            time.sleep_ms(120)
        elif pu:
            time.sleep_ms(160)
            return ("start", pidx)
        elif pd:
            time.sleep_ms(160)
            return ("exit", pidx)

        time.sleep_ms(20)

def win_menu(moves, pidx):
    eb = EdgeButtons()
    wait_released()
    while True:
        win_screen(moves, pidx)
        pu, pd, pl, pr = eb.update()
        if pu:
            time.sleep_ms(160); return ("again", pidx)
        if pr:
            time.sleep_ms(160); return ("next", (pidx + 1) % len(PUZZLES))
        if pd:
            time.sleep_ms(160); return ("exit", pidx)
        time.sleep_ms(20)

def main():
    # sanity validate puzzles (if you edit/add later)
    for b in PUZZLES:
        if not validate_board(b):
            # fail hard rather than weird behavior
            fill(0)
            draw_text_center("BAD", 40, scale=3)
            draw_text_center("PUZZLE", 70, scale=2)
            show()
            time.sleep(2)
            sys.exit()

    eb = EdgeButtons()

    while True:
        action, pidx = pick_puzzle()
        if action == "exit":
            sys.exit()

        board = clone_board(PUZZLES[pidx])
        cur_r, cur_c = 4, 1
        grabbed = None
        moves = 0
        last_action_ms = 0

        wait_released()

        while True:
            render(board, cur_r, cur_c, grabbed, moves, pidx)

            pu, pd, pl, pr = eb.update()

            act = detect_ud_action(last_action_ms)
            if act:
                last_action_ms = time.ticks_ms()

            if act == "reset":
                board = clone_board(PUZZLES[pidx])
                cur_r, cur_c = 4, 1
                grabbed = None
                moves = 0
                time.sleep_ms(120)
                continue

            if act == "grab":
                if grabbed is None:
                    grabbed = pid_under_cursor(board, cur_r, cur_c)
                else:
                    grabbed = None
                time.sleep_ms(80)
                continue

            if grabbed is None:
                if pu: cur_r = (cur_r - 1) % BR
                elif pd: cur_r = (cur_r + 1) % BR
                elif pl: cur_c = (cur_c - 1) % BC
                elif pr: cur_c = (cur_c + 1) % BC
            else:
                moved = False
                if pu:   moved = move_piece(board, grabbed, -1, 0)
                elif pd: moved = move_piece(board, grabbed,  1, 0)
                elif pl: moved = move_piece(board, grabbed,  0,-1)
                elif pr: moved = move_piece(board, grabbed,  0, 1)

                if moved:
                    moves += 1
                    tl = piece_top_left(board, grabbed)
                    if tl:
                        cur_r, cur_c = tl

                    if is_win(board):
                        time.sleep_ms(150)
                        wact, new_pidx = win_menu(moves, pidx)
                        if wact == "exit":
                            sys.exit()
                        pidx = new_pidx
                        board = clone_board(PUZZLES[pidx])
                        cur_r, cur_c = 4, 1
                        grabbed = None
                        moves = 0
                        wait_released()
                        continue

            time.sleep_ms(35)

main()
