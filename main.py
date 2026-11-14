#!/usr/bin/env python3
"""The Golden Smash Burger — a pure-stdlib procedural food picture.

Draws a golden smash burger with fries on a wooden board, steam rising,
under a "FRESH OFF THE GRILL" banner, and writes one deterministic
1024x1024 PNG to /output/entry.png (MAKEFUN_OUTPUT_DIR overrides it
locally). Standard library only: no PIL, no network, no embedded image.
"""

import math
import os
import struct
import zlib

W = H = 1024


# ---------------------------------------------------------------- PNG out
def _chunk(kind, data):
    return (struct.pack(">I", len(data)) + kind + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))


def write_png(path, px, w, h):
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)
        raw += px[y * stride:(y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr)
           + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + _chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = bytearray(w * h * 3)

    def blend(self, x, y, r, g, b, a=255):
        if a <= 0 or x < 0 or y < 0 or x >= self.w or y >= self.h:
            return
        i = (y * self.w + x) * 3
        if a >= 255:
            self.px[i] = r
            self.px[i + 1] = g
            self.px[i + 2] = b
            return
        inv = 255 - a
        self.px[i] = (r * a + self.px[i] * inv) // 255
        self.px[i + 1] = (g * a + self.px[i + 1] * inv) // 255
        self.px[i + 2] = (b * a + self.px[i + 2] * inv) // 255

    def hline(self, x0, x1, y, r, g, b, a=255):
        if y < 0 or y >= self.h:
            return
        x0 = max(0, x0)
        x1 = min(self.w - 1, x1)
        for x in range(x0, x1 + 1):
            self.blend(x, y, r, g, b, a)

    def vgrad(self, top, bottom):
        for y in range(self.h):
            t = y / (self.h - 1)
            r = int(top[0] + (bottom[0] - top[0]) * t)
            g = int(top[1] + (bottom[1] - top[1]) * t)
            b = int(top[2] + (bottom[2] - top[2]) * t)
            self.hline(0, self.w - 1, y, r, g, b)

    def fill_rect(self, x0, y0, x1, y1, color, a=255):
        for y in range(max(0, y0), min(self.h, y1 + 1)):
            self.hline(x0, x1, y, *color, a)

    def fill_circle(self, cx, cy, rad, color, a=255):
        for dy in range(-rad, rad + 1):
            dx = int(math.sqrt(max(0, rad * rad - dy * dy)))
            self.hline(cx - dx, cx + dx, cy + dy, *color, a)

    def fill_ellipse(self, cx, cy, rx, ry, color, a=255, y_max=None):
        for dy in range(-ry, ry + 1):
            y = cy + dy
            if y_max is not None and y > y_max:
                continue
            t = 1.0 - (dy * dy) / float(ry * ry)
            dx = int(rx * math.sqrt(max(0.0, t)))
            self.hline(cx - dx, cx + dx, y, *color, a)

    def fill_polygon(self, pts, color, a=255):
        ys = [p[1] for p in pts]
        y0, y1 = max(0, min(ys)), min(self.h - 1, max(ys))
        n = len(pts)
        for y in range(y0, y1 + 1):
            xs = []
            for i in range(n):
                x0, ya = pts[i]
                x1, yb = pts[(i + 1) % n]
                if ya == yb:
                    continue
                if (ya <= y < yb) or (yb <= y < ya):
                    xs.append(x0 + (y - ya) * (x1 - x0) / (yb - ya))
            xs.sort()
            for j in range(0, len(xs) - 1, 2):
                self.hline(int(xs[j]), int(xs[j + 1]), y, *color, a)

    def round_rect(self, x0, y0, x1, y1, rad, color, a=255):
        self.fill_rect(x0 + rad, y0, x1 - rad, y1, color, a)
        self.fill_rect(x0, y0 + rad, x1, y1 - rad, color, a)
        for cx, cy in ((x0 + rad, y0 + rad), (x1 - rad, y0 + rad),
                       (x0 + rad, y1 - rad), (x1 - rad, y1 - rad)):
            self.fill_circle(cx, cy, rad, color, a)

    def thick_line(self, x0, y0, x1, y1, rad, color, a=255):
        steps = max(abs(x1 - x0), abs(y1 - y0), 1) + 1
        for i in range(steps):
            t = i / (steps - 1)
            self.fill_circle(int(x0 + (x1 - x0) * t),
                             int(y0 + (y1 - y0) * t), rad, color, a)

    def rot_rect(self, cx, cy, w, h, deg, color, a=255):
        th = math.radians(deg)
        c, s = math.cos(th), math.sin(th)
        hw, hh = w / 2.0, h / 2.0
        corners = []
        for dx, dy in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)):
            corners.append((int(cx + dx * c - dy * s),
                            int(cy + dx * s + dy * c)))
        self.fill_polygon(corners, color, a)


# ---------------------------------------------------------------- 5x7 font
FONT = {
    "F": ["11111", "10000", "11110", "10000", "10000", "10000", "10000"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "G": ["01110", "10001", "10000", "10111", "10001", "10001", "01111"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
}


def draw_text(cv, text, x, y, scale, color):
    cx = x
    for ch in text:
        glyph = FONT.get(ch, FONT[" "])
        for row in range(7):
            for col in range(5):
                if glyph[row][col] == "1":
                    cv.fill_rect(cx + col * scale, y + row * scale,
                                 cx + col * scale + scale - 1,
                                 y + row * scale + scale - 1, color)
        cx += 6 * scale


def text_width(text, scale):
    return len(text) * 6 * scale - scale


# ---------------------------------------------------------------- palette
BG_TOP = (64, 40, 26)
BG_BOT = (26, 15, 9)
GLOW = (255, 170, 60)
BOARD = (146, 96, 54)
BOARD_DARK = (110, 70, 38)
BOARD_EDGE = (88, 56, 30)
GRAIN = (96, 62, 34)
CARTON = (178, 39, 46)
CARTON_DARK = (140, 28, 34)
STRIPE = (245, 235, 220)
FRY = (242, 178, 52)
FRY_EDGE = (217, 143, 31)
FRY_TIP = (250, 205, 90)
BUN = (234, 169, 79)
BUN_LIGHT = (247, 196, 110)
BUN_SHADE = (205, 130, 44)
BUN_BOT = (226, 160, 74)
BUN_BOT_SHADE = (181, 119, 46)
PATTY = (74, 44, 23)
PATTY_DARK = (52, 30, 15)
PATTY_HI = (96, 60, 32)
CHEESE = (255, 157, 27)
CHEESE_LIGHT = (255, 183, 70)
TOMATO = (217, 56, 43)
TOMATO_LIGHT = (232, 90, 72)
LETTUCE = (124, 179, 66)
LETTUCE_DARK = (93, 143, 46)
SESAME = (255, 230, 168)
SESAME_EDGE = (214, 170, 90)
BANNER = (168, 35, 42)
BANNER_DARK = (120, 22, 28)
CREAM = (255, 243, 214)
SHADOW = (0, 0, 0)


# ---------------------------------------------------------------- scene
def draw_background(cv):
    cv.vgrad(BG_TOP, BG_BOT)
    cv.fill_circle(430, 620, 330, GLOW, 18)
    cv.fill_circle(430, 620, 220, GLOW, 22)
    bokeh = [
        (120, 180, 55, (255, 190, 90), 26), (900, 150, 70, (255, 170, 70), 22),
        (950, 420, 48, (255, 200, 110), 24), (80, 500, 40, (255, 180, 80), 20),
        (850, 900, 60, (255, 170, 70), 18), (150, 880, 45, (255, 190, 100), 20),
        (700, 120, 38, (255, 200, 120), 24), (250, 300, 30, (255, 185, 95), 18),
        (780, 300, 26, (255, 195, 110), 20), (950, 700, 34, (255, 175, 75), 18),
        (60, 760, 30, (255, 190, 100), 16), (600, 950, 50, (255, 180, 85), 16),
    ]
    for x, y, r, col, a in bokeh:
        cv.fill_circle(x, y, r, col, a)


def draw_board(cv):
    cv.round_rect(90, 700, 934, 950, 28, BOARD_EDGE)
    cv.round_rect(96, 704, 928, 944, 24, BOARD)
    cv.hline(110, 920, 712, 172, 118, 68, 160)
    for gy in (760, 830, 890, 920):
        for x in range(120, 920, 14):
            wob = int(3 * math.sin(x * 0.05 + gy))
            cv.blend(x, gy + wob, *GRAIN, 70)
    cv.fill_ellipse(430, 826, 240, 26, SHADOW, 70)


def draw_fries(cv):
    sticks = [
        (712, 600, -14), (748, 580, -6), (782, 572, 2), (818, 580, 8),
        (852, 598, 14), (730, 620, -10), (790, 612, 4), (838, 622, 12),
        (762, 636, -2), (812, 634, 6),
    ]
    for cx, cy, ang in sticks:
        cv.rot_rect(cx, cy, 30, 118, ang, FRY_EDGE)
        cv.rot_rect(cx, cy, 24, 112, ang, FRY)
        cv.rot_rect(cx, cy - 44, 24, 16, ang, FRY_TIP)
    carton = [(690, 786), (880, 786), (858, 640), (712, 640)]
    cv.fill_polygon(carton, CARTON_DARK)
    inner = [(700, 780), (870, 780), (850, 648), (720, 648)]
    cv.fill_polygon(inner, CARTON)
    for sx in (736, 776, 816):
        cv.fill_polygon([(sx, 780), (sx + 18, 780), (sx + 12, 648),
                         (sx - 4, 648)], STRIPE, 235)
    cv.fill_polygon([(700, 780), (870, 780), (866, 764), (704, 764)],
                    CARTON_DARK)


def draw_burger(cv):
    cx = 430
    # bottom bun
    cv.fill_ellipse(cx, 776, 218, 56, BUN_BOT)
    cv.fill_ellipse(cx, 802, 196, 26, BUN_BOT_SHADE, 200)
    # patty with bumpy edge and char marks
    cv.round_rect(212, 702, 648, 774, 18, PATTY)
    for bx in range(234, 636, 28):
        cv.fill_circle(bx, 772, 10, PATTY)
    cv.fill_rect(234, 706, 626, 714, PATTY_HI, 120)
    for mx in (280, 360, 470, 560):
        cv.fill_rect(mx, 726, mx + 26, 736, PATTY_DARK, 160)
    # cheese, wavy with drips
    cheese = [(222, 686), (638, 686), (638, 708), (620, 716), (608, 736),
              (594, 712), (562, 716), (550, 734), (536, 712), (478, 716),
              (466, 738), (452, 712), (392, 716), (380, 732), (366, 712),
              (312, 716), (300, 734), (286, 712), (222, 708)]
    cv.fill_polygon(cheese, CHEESE)
    cv.fill_polygon([(222, 686), (638, 686), (638, 694), (222, 694)],
                    CHEESE_LIGHT, 200)
    # tomato
    cv.fill_ellipse(cx, 674, 192, 26, TOMATO)
    cv.fill_ellipse(cx, 672, 160, 16, TOMATO_LIGHT, 160)
    # lettuce, scalloped edge
    pts = [(238, 650), (622, 650)]
    x = 622
    down = True
    while x > 238:
        pts.append((x, 674 if down else 656))
        down = not down
        x -= 14
    pts.append((238, 656))
    cv.fill_polygon(pts, LETTUCE)
    for lx in range(260, 610, 34):
        cv.fill_circle(lx, 668, 8, LETTUCE_DARK, 120)
    # top bun dome (clipped at the lettuce line)
    cv.fill_ellipse(cx, 634, 240, 134, BUN, y_max=652)
    cv.fill_ellipse(360, 570, 126, 48, BUN_LIGHT, 110, y_max=652)
    cv.fill_ellipse(cx, 650, 236, 18, BUN_SHADE, 160, y_max=652)
    seeds = [(330, 550), (390, 530), (450, 522), (510, 535), (560, 558),
             (300, 590), (360, 595), (470, 595), (540, 600), (410, 565),
             (500, 570), (340, 620), (580, 610), (420, 610)]
    for sx, sy in seeds:
        cv.fill_ellipse(sx, sy, 9, 5, SESAME_EDGE)
        cv.fill_ellipse(sx, sy - 1, 8, 4, SESAME)


def draw_steam(cv):
    for cx, phase in ((350, 0.0), (430, 1.4), (510, 2.6)):
        for t in range(15):
            y = 500 - t * 9
            x = int(cx + 14 * math.sin(t * 0.7 + phase))
            r = 11 + (t % 3)
            cv.fill_circle(x, y, r, (255, 255, 255), 34 + 8 * (t % 3))


def draw_banner(cv):
    cv.round_rect(144, 50, 880, 140, 10, BANNER_DARK)
    cv.round_rect(150, 56, 874, 134, 10, BANNER)
    cv.fill_polygon([(150, 56), (176, 56), (176, 134), (150, 134)],
                    BANNER_DARK, 120)
    cv.fill_polygon([(874, 56), (848, 56), (848, 134), (874, 134)],
                    BANNER_DARK, 120)
    text = "FRESH OFF THE GRILL"
    tw = text_width(text, 5)
    draw_text(cv, text, (W - tw) // 2, 79, 5, CREAM)


def draw_garnish(cv):
    # dipping sauce bowl on the board, left of the burger
    cv.fill_ellipse(180, 852, 48, 22, (245, 235, 220))
    cv.fill_ellipse(180, 848, 40, 16, (232, 90, 72))
    cv.fill_ellipse(172, 844, 22, 8, (240, 120, 100), 180)
    for sx, sy in ((180, 860), (260, 900), (880, 860), (820, 905),
                   (620, 880), (240, 760), (700, 850), (300, 905),
                   (660, 920), (900, 800)):
        cv.fill_ellipse(sx, sy, 6, 4, SESAME)
    for hx, hy in ((300, 830), (560, 850), (860, 800), (200, 830)):
        cv.fill_rect(hx, hy, hx + 10, hy + 4, LETTUCE_DARK, 200)
    for cx, cy in ((350, 900), (520, 920), (760, 880), (880, 920)):
        cv.fill_circle(cx, cy, 4, (120, 78, 40), 200)


def build():
    cv = Canvas(W, H)
    draw_background(cv)
    draw_board(cv)
    draw_fries(cv)
    draw_burger(cv)
    draw_steam(cv)
    draw_banner(cv)
    draw_garnish(cv)
    return cv


def main():
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR")
    if not outdir:
        outdir = "/output" if os.path.isdir("/output") else "out"
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "entry.png")
    cv = build()
    size = write_png(path, cv.px, W, H)
    print("wrote %s (%d bytes, %dx%d)" % (path, size, W, H))


if __name__ == "__main__":
    main()
