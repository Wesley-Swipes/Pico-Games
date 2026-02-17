from machine import Pin, I2C
from ssd1306 import SSD1306_I2C
import framebuf
import time
import urandom

# ---------- Hardware ----------
I2C_ADDR = 0x3C
i2c = I2C(0, scl=Pin(21), sda=Pin(20), freq=400000)
oled = SSD1306_I2C(128, 64, i2c, addr=I2C_ADDR)

btn_left  = Pin(17, Pin.IN, Pin.PULL_UP)
btn_right = Pin(16, Pin.IN, Pin.PULL_UP)
btn_up    = Pin(19, Pin.IN, Pin.PULL_UP)
btn_down  = Pin(18, Pin.IN, Pin.PULL_UP)

def pressed(pin):
    return pin.value() == 0  # active-low

# ---------- Virtual portrait screen (64x128) ----------
VW, VH = 64, 128
vbuf_bytes = bytearray(VW * (VH // 8))
vbuf = framebuf.FrameBuffer(vbuf_bytes, VW, VH, framebuf.MONO_VLSB)

# Rotation: X = y, Y = (VW-1-x)  (90° clockwise)
def show_virtual():
    oled.fill(0)
    obuf = oled.buffer
    ow = 128

    for y in range(VH):
        row_base = (y >> 3) * VW
        bitmask = 1 << (y & 7)
        for x in range(VW):
            if vbuf_bytes[row_base + x] & bitmask:
                X = y
                Y = (VW - 1 - x)
                idx = X + (Y >> 3) * ow
                obuf[idx] |= (1 << (Y & 7))

    oled.show()

# ---------- Helpers ----------
def clamp(v, lo, hi):
    if v < lo: return lo
    if v > hi: return hi
    return v

def draw_text_center(y, text):
    x = max(0, (VW - len(text) * 8) // 2)
    vbuf.text(text, x, y, 1)

def rects_overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay)

def rand_range(lo, hi):
    # inclusive lo..hi
    if hi <= lo:
        return lo
    span = hi - lo + 1
    return lo + (urandom.getrandbits(16) % span)

def choice3(a, b, c):
    r = urandom.getrandbits(2)
    if r == 0: return a
    if r == 1: return b
    return c

# ---------- Game constants (portrait) ----------
GROUND_Y = 112
DINO_X = 10

# “Chrome-ish” physics in our pixel scale
JUMP_V0 = -4.6          # initial impulse
GRAVITY = 0.34          # normal gravity
GRAVITY_RELEASE = 0.52  # if you let go early -> shorter jump
GRAVITY_FASTFALL = 0.60 # holding DOWN in air
MAX_FALL = 6.5

# Holding jump extends jump a bit (Chrome style)
JUMP_HOLD_FRAMES = 8
HOLD_GRAVITY = 0.22

# Speed curve
SPEED_START = 1.55
SPEED_MAX = 4.10
SPEED_RAMP_PER_TICK = 0.0009  # smooth, not stepwise

# Spacing in pixels (distance-based)
GAP_MIN_START = 22
GAP_MAX_START = 46

# Bird appears later
BIRD_SCORE_START = 180

# ---------- Sprites ----------
def draw_dino(x, y, ducking=False):
    if ducking:
        vbuf.fill_rect(x+1, y+6, 10, 4, 1)  # body
        vbuf.fill_rect(x+8, y+5,  5, 3, 1)  # head
        vbuf.pixel(x+12, y+6, 1)            # snout
        vbuf.fill_rect(x+2, y+10, 3, 2, 1)
        vbuf.fill_rect(x+6, y+10, 3, 2, 1)
    else:
        vbuf.fill_rect(x+2, y+7,  8, 8, 1)  # body
        vbuf.fill_rect(x+8, y+4,  6, 4, 1)  # head
        vbuf.pixel(x+13, y+6, 1)
        vbuf.fill_rect(x+3, y+15, 2, 3, 1)
        vbuf.fill_rect(x+6, y+15, 2, 3, 1)
        vbuf.pixel(x+1, y+10, 1)
        vbuf.pixel(x,   y+11, 1)

def dino_hitbox(x, y, ducking=False):
    if ducking:
        return (x+1, y+5, 12, 9)
    return (x+1, y+4, 13, 14)

def draw_cactus(x, base_y, variant=0):
    if variant == 0:
        vbuf.fill_rect(x,   base_y-10, 3, 10, 1)
        vbuf.fill_rect(x-2, base_y-8,  2, 2,  1)
        vbuf.fill_rect(x+3, base_y-6,  2, 2,  1)
        return (x-2, base_y-10, 7, 10)
    elif variant == 1:
        vbuf.fill_rect(x,   base_y-14, 4, 14, 1)
        vbuf.fill_rect(x-3, base_y-10, 3, 3,  1)
        vbuf.fill_rect(x+4, base_y-8,  3, 3,  1)
        return (x-3, base_y-14, 10, 14)
    else:
        vbuf.fill_rect(x,   base_y-9,  2, 9,  1)
        vbuf.fill_rect(x+3, base_y-12, 2, 12, 1)
        vbuf.fill_rect(x+6, base_y-10, 2, 10, 1)
        return (x, base_y-12, 8, 12)

def draw_ptero(x, y, flap=0):
    # “M” style wings, closer to Chrome vibe than a V
    if flap == 0:
        vbuf.pixel(x,   y+2, 1)
        vbuf.pixel(x+1, y+1, 1)
        vbuf.pixel(x+2, y,   1)
        vbuf.pixel(x+3, y+1, 1)
        vbuf.pixel(x+4, y+2, 1)
        vbuf.pixel(x+5, y+1, 1)
        vbuf.pixel(x+6, y,   1)
        vbuf.pixel(x+7, y+1, 1)
        vbuf.pixel(x+8, y+2, 1)
    else:
        vbuf.pixel(x,   y+1, 1)
        vbuf.pixel(x+1, y,   1)
        vbuf.pixel(x+2, y+1, 1)
        vbuf.pixel(x+3, y,   1)
        vbuf.pixel(x+4, y+1, 1)
        vbuf.pixel(x+5, y,   1)
        vbuf.pixel(x+6, y+1, 1)
        vbuf.pixel(x+7, y,   1)
        vbuf.pixel(x+8, y+1, 1)

    vbuf.pixel(x+4, y+2, 1)  # body
    return (x, y, 9, 3)

def ground_dash(x, y, w):
    vbuf.fill_rect(x, y, w, 1, 1)

# ---------- Obstacles ----------
class Obstacle:
    # kind: 0 cactus, 1 ptero
    def __init__(self, kind, x, speed, score):
        self.kind = kind
        self.x = float(x)
        self.speed = float(speed)
        self.variant = urandom.getrandbits(2)
        self.flap = 0
        self.y = 0
        if self.kind == 1:
            # Classic-ish heights:
            # high: safe, mid: must jump, low: must duck (or perfect jump)
            self.y = choice3(78, 88, 98)

    def step(self):
        self.x -= self.speed
        if self.kind == 1:
            self.flap ^= 1

    def draw_and_box(self):
        if self.kind == 0:
            return draw_cactus(int(self.x), GROUND_Y, self.variant % 3)
        return draw_ptero(int(self.x), int(self.y), self.flap)

# ---------- Game ----------
def play_game():
    # Title screen
    while True:
        vbuf.fill(0)
        draw_text_center(14, "DINO RUN")
        draw_text_center(38, "UP START")
        draw_text_center(50, "DN MENU")
        show_virtual()

        if pressed(btn_up):
            time.sleep(0.2)
            break
        if pressed(btn_down):
            time.sleep(0.2)
            return
        time.sleep(0.02)

    # State
    dino_y = GROUND_Y - 18
    vy = 0.0
    on_ground = True
    ducking = False

    jump_prev = False
    jump_hold = 0

    obstacles = []
    score = 0
    best = 0

    speed = SPEED_START
    ground_phase = 0

    # Distance-based spawner (Chrome-ish)
    next_spawn_dist = 28  # pixels until next spawn

    def reset_round():
        nonlocal dino_y, vy, on_ground, ducking, jump_prev, jump_hold
        nonlocal obstacles, score, speed, ground_phase, next_spawn_dist
        dino_y = GROUND_Y - 18
        vy = 0.0
        on_ground = True
        ducking = False
        jump_prev = False
        jump_hold = 0
        obstacles = []
        score = 0
        speed = SPEED_START
        ground_phase = 0
        next_spawn_dist = 28

    def compute_gap():
        # tighten gaps as speed increases
        t = (speed - SPEED_START) / (SPEED_MAX - SPEED_START)
        t = clamp(t, 0.0, 1.0)

        gmin = int(GAP_MIN_START - (6 * t))   # 22 -> 16
        gmax = int(GAP_MAX_START - (10 * t))  # 46 -> 36
        return gmin, gmax

    reset_round()

    while True:
        up_now = pressed(btn_up)
        down_now = pressed(btn_down)

        jump_click = up_now and (not jump_prev)
        jump_prev = up_now

        # Duck on ground
        ducking = down_now and on_ground

        # Optional tiny horizontal wiggle (purely cosmetic)
        if pressed(btn_left) or pressed(btn_right):
            # (intentionally minimal; Chrome is fixed-lane)
            pass

        # Start jump
        if jump_click and on_ground:
            vy = JUMP_V0
            on_ground = False
            jump_hold = JUMP_HOLD_FRAMES

        # Gravity rules (Chrome-ish)
        g = GRAVITY

        if not on_ground:
            if down_now:
                g = GRAVITY_FASTFALL
            else:
                # Variable jump height: if still holding UP and in early frames
                if up_now and jump_hold > 0 and vy < 0:
                    g = HOLD_GRAVITY
                # If you released early while rising: shorter hop
                if (not up_now) and vy < 0:
                    g = max(g, GRAVITY_RELEASE)

        # Apply physics
        if not on_ground:
            vy += g
            if vy > MAX_FALL:
                vy = MAX_FALL
            dino_y += vy

            if jump_hold > 0:
                jump_hold -= 1

            if dino_y >= (GROUND_Y - 18):
                dino_y = (GROUND_Y - 18)
                vy = 0.0
                on_ground = True

        # Speed ramp (smooth)
        speed = min(SPEED_MAX, speed + SPEED_RAMP_PER_TICK * (1.0 + score * 0.0006))

        # Spawn logic (distance-based)
        # Decrease distance by how far we "traveled" this frame
        next_spawn_dist -= speed

        # Prevent unfair spawns: require last obstacle to be far enough
        last_x = obstacles[-1].x if obstacles else -9999

        if next_spawn_dist <= 0 and (not obstacles or (last_x < (VW - 10))):
            kind = 0
            # Birds later in game
            if score >= BIRD_SCORE_START:
                # ~35% birds
                if (urandom.getrandbits(8) < 90):
                    kind = 1

            obstacles.append(Obstacle(kind, VW + 8, speed, score))

            gmin, gmax = compute_gap()
            next_spawn_dist = rand_range(gmin, gmax)

        # Step obstacles
        for o in obstacles:
            o.speed = speed
            o.step()
        obstacles = [o for o in obstacles if o.x > -20]

        # Draw
        vbuf.fill(0)

        # Ground dashes
        for x in range(0, VW, 6):
            if ((x + ground_phase) // 6) % 2 == 0:
                ground_dash(x, GROUND_Y, 4)
        ground_phase = (ground_phase + int(speed)) % 12

        # Dino + hitbox
        draw_dino(DINO_X, int(dino_y), ducking=ducking)
        dhb = dino_hitbox(DINO_X, int(dino_y), ducking=ducking)

        # Obstacles + collision
        hit = False
        for o in obstacles:
            box = o.draw_and_box()
            if rects_overlap(dhb, box):
                hit = True

        # Score (top-left in portrait)
        vbuf.text(str(score), 0, 0, 1)
        show_virtual()

        # Game over
        if hit:
            if score > best:
                best = score

            while True:
                vbuf.fill(0)
                draw_text_center(24, "GAME OVER")
                draw_text_center(44, "SCORE " + str(score))
                draw_text_center(56, "BEST  " + str(best))
                draw_text_center(96, "UP AGAIN")
                draw_text_center(108, "DN MENU")
                show_virtual()

                if pressed(btn_up):
                    time.sleep(0.2)
                    reset_round()
                    break
                if pressed(btn_down):
                    time.sleep(0.2)
                    return
                time.sleep(0.03)

        # Score increments like Chrome (time survived)
        score += 1
        time.sleep(0.028)
