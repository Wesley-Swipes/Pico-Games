from machine import Pin, I2C
from ssd1306 import SSD1306_I2C
import time
import os
import sys

# =========================
# === IMPOSTAZIONI BASE ===
# =========================
i2c = I2C(0, scl=Pin(21), sda=Pin(20), freq=400000)
display = SSD1306_I2C(128, 64, i2c, addr=0x3C)

# Pulsanti (active-low)
btn_left  = Pin(17, Pin.IN, Pin.PULL_UP)
btn_right = Pin(16, Pin.IN, Pin.PULL_UP)
btn_up    = Pin(19, Pin.IN, Pin.PULL_UP)
btn_down  = Pin(18, Pin.IN, Pin.PULL_UP)

GAMES_FOLDER = "games"
if GAMES_FOLDER not in sys.path:
    sys.path.append(GAMES_FOLDER)

# =========================
# === PBM (P4) LOADER =====
# =========================
def read_pbm_p4(path):
    """Reads PBM P4 (raw). Returns (w, h, data_bytes)."""
    with open(path, "rb") as f:
        magic = f.readline().strip()
        if magic != b"P4":
            raise ValueError("Not P4 PBM")

        tokens = []
        while len(tokens) < 2:
            line = f.readline()
            if not line:
                raise ValueError("PBM header EOF")
            line = line.strip()
            if (not line) or line.startswith(b"#"):
                continue
            tokens += line.split()

        w = int(tokens[0])
        h = int(tokens[1])
        data = bytearray(f.read())

    row_bytes = (w + 7) // 8
    expected = row_bytes * h
    if len(data) != expected:
        raise ValueError("PBM bytes %d != %d" % (len(data), expected))

    return w, h, data


def draw_pbm_to_display(path, x0=0, y0=0):
    """
    Draw PBM P4 onto SSD1306 display buffer (MONO_VLSB).
    PBM P4 is MSB-first within each byte for each row.
    """
    w, h, pbm = read_pbm_p4(path)

    max_w = min(w, display.width - x0)
    max_h = min(h, display.height - y0)

    row_bytes = (w + 7) // 8
    buf = display.buffer
    dw = display.width

    display.fill(0)

    for y in range(max_h):
        row_start = y * row_bytes
        for x in range(max_w):
            b = pbm[row_start + (x >> 3)]
            bit = 7 - (x & 7)          # PBM: MSB first
            on = (b >> bit) & 1

            if on:
                dx = x0 + x
                dy = y0 + y
                idx = dx + (dy >> 3) * dw
                buf[idx] |= (1 << (dy & 7))

    # --- Artifact killer: wipe the top row of the menu image ---
    display.fill_rect(0, 0, display.width, 1, 0)

    display.show()

# =========================
# === FUNZIONI BASE =======
# =========================
def load_and_display_image(name):
    path = f"{GAMES_FOLDER}/{name}.pbm"
    try:
        draw_pbm_to_display(path)
    except Exception as e:
        display.fill(0)
        display.text(name[:16], 0, 25)
        display.text("[No image]", 0, 40)
        display.show()
        print("Warning: immagine non trovata o invalida:", path, e)

def show_logo():
    path = "logo.pbm"
    try:
        draw_pbm_to_display(path)
        time.sleep(2)
    except Exception as e:
        display.fill(0)
        display.text("Welcome!", 25, 25)
        display.show()
        time.sleep(1.5)
        print("Logo skipped:", e)

def launch_game(name):
    try:
        if name in sys.modules:
            del sys.modules[name]

        mod = __import__(name)
        if hasattr(mod, "play_game"):
            mod.play_game()

    except Exception as e:
        display.fill(0)
        display.text("Game crash", 0, 0)
        display.text(name[:16], 0, 10)
        display.show()
        print("Errore:", e)
        time.sleep(2)

    finally:
        display.fill(0)
        display.show()
        time.sleep(0.2)

# =========================
# === MENU DI SELEZIONE ===
# =========================
def run_menu():
    game_files = [f[:-3] for f in os.listdir(GAMES_FOLDER) if f.endswith(".py")]
    game_files.sort()

    if not game_files:
        display.fill(0)
        display.text("Nessun gioco", 10, 20)
        display.text("trovato!", 30, 35)
        display.show()
        return

    current_game = 0
    load_and_display_image(game_files[current_game])

    while True:
        if not btn_right.value():
            current_game = (current_game + 1) % len(game_files)
            load_and_display_image(game_files[current_game])
            time.sleep(0.2)

        if not btn_left.value():
            current_game = (current_game - 1) % len(game_files)
            load_and_display_image(game_files[current_game])
            time.sleep(0.2)

        if not btn_up.value() or not btn_down.value():
            display.fill(0)
            display.text("Starting game...", 0, 0)
            display.show()
            time.sleep(0.5)

            launch_game(game_files[current_game])

            load_and_display_image(game_files[current_game])
            time.sleep(0.2)

        time.sleep(0.02)

# =========================
# === AVVIO DEL PROGRAMMA ===
# =========================
show_logo()
run_menu()
