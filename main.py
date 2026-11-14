#!/usr/bin/env python3
"""Procedural 1024x1024 PNG for make.fun food-picture-01.

"The Golden Smash Burger" -- a hero shot of a smash burger, drawn
entirely in code: glossy brioche bun with sesame seeds, melted
cheddar dripping over a char-marked patty, tomato, scalloped
lettuce, a cup of golden fries, and steam rising off the bun,
on a cream plate over a dark walnut table. A small caption,
"FRESH OFF THE GRILL", sits under the plate.

Pure standard library (math, os, random, struct, zlib, pathlib).
Fully deterministic: the same bytes on every run (fixed seed for
the sesame seeds and fry angles). Renders at 2x supersampling
into a 2048x2048 RGB buffer, box-downsamples to 1024x1024, and
writes the PNG with a hand-rolled encoder (filter byte 0 per row,
8-bit colour type 2). Output is well under the 1 MiB limit.
"""

import math
import os
import random
import struct
import zlib
from pathlib import Path

# ---------------------------------------------------------------------------
# Canvas: design space is 1024x1024; the buffer is 2x supersampled.
# ---------------------------------------------------------------------------
W = 1024
S = 2
IW = W * S  # 2048

buf = bytearray(IW * IW * 3)

# Palette: warm dark backdrop, golden food.
BG_TOP = (38, 24, 15)
BG_BOT = (15, 9, 5)
GLOW = (255, 166, 58)
TABLE = (44, 29, 17)
TABLE_LINE = (30, 19, 10)
TABLE_EDGE = (74, 50, 30)
PLATE_OUT = (224, 211, 192)
PLATE_RIM = (226, 214, 196)
PLATE_IN = (249, 243, 231)
BUN = (216, 140, 46)
BUN_RIM = (186, 108, 30)
BUN_HI = (244, 182, 92)
BUN_SHADE = (172, 98, 26)
SESAME = (247, 226, 174)
SESAME_SH = (186, 120, 40)
PATTY = (97, 55, 29)
PATTY_HI = (148, 90, 47)
PATTY_CHAR = (63, 33, 15)
PATTY_SH = (70, 38, 18)
CHEESE = (255, 170, 22)
CHEESE_HI = (255, 198, 90)
TOMATO = (216, 54, 40)
TOMATO_HI = (232, 92, 70)
LETTUCE = (106, 166, 66)
LETTUCE_HI = (152, 198, 92)
BUN_BOT = (207, 133, 45)
BUN_BOT_HI = (233, 170, 82)
BUN_BOT_SH = (170, 99, 29)
FRY = (233, 179, 76)
FRY_TIP = (196, 138, 48)
CUP = (196, 42, 38)
CUP_HI = (216, 58, 50)
CUP_WHITE = (248, 242, 230)
STEAM = (255, 248, 238)
HERB = (90, 150, 70)
CAPTION = (238, 214, 178)
RULE = (178, 138, 88)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

RNG = random.Random(20261114)


def _clip(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def _lerp(c0, c1, t):
    return (int(c0[0] + (c1[0] - c0[0]) * t),
            int(c0[1] + (c1[1] - c0[1]) * t),
            int(c0[2] + (c1[2] - c0[2]) * t))


def _ix(v):
    return int(round(v * S))


def span(y, x0, x1, color):
    """Fill buffer row y from x0 to x1 (buffer px), opaque, fast."""
    if y < 0 or y >= IW:
        return
    x0 = _clip(x0, 0, IW)
    x1 = _clip(x1, 0, IW)
    if x1 <= x0:
        return
    n = x1 - x0
    buf[(y * IW + x0) * 3:(y * IW + x1) * 3] = bytes(color) * n


def blend_span(y, x0, x1, color, alpha):
    """Fill buffer row y from x0 to x1, alpha-blended (alpha 0..255)."""
    if y < 0 or y >= IW or alpha <= 0:
        return
    x0 = _clip(x0, 0, IW)
    x1 = _clip(x1, 0, IW)
    if x1 <= x0:
        return
    if alpha >= 255:
        span(y, x0, x1, color)
        return
    base = (y * IW + x0) * 3
    n = x1 - x0
    r, g, b = color
    ia = 255 - alpha
    old = buf[base:base + n * 3]
    out = bytearray(n * 3)
    for i in range(n):
        o = i * 3
        out[o] = (r * alpha + old[o] * ia) // 255
        out[o + 1] = (g * alpha + old[o + 1] * ia) // 255
        out[o + 2] = (b * alpha + old[o + 2] * ia) // 255
    buf[base:base + n * 3] = out


def fill_rect(x, y, w, h, color):
    x0, y0 = _ix(x), _ix(y)
    x1, y1 = _ix(x + w), _ix(y + h)
    for yy in range(y0, y1):
        span(yy, x0, x1, color)


def disc(cx, cy, r, color):
    cx, cy, r = _ix(cx), _ix(cy), _ix(r)
    r2 = r * r
    for yy in range(cy - r, cy + r + 1):
        dy = yy - cy
        dx = int(math.sqrt(max(0, r2 - dy * dy)))
        span(yy, cx - dx, cx + dx + 1, color)


def blend_disc(cx, cy, r, color, alpha):
    cx, cy, r = _ix(cx), _ix(cy), _ix(r)
    r2 = r * r
    for yy in range(cy - r, cy + r + 1):
        dy = yy - cy
        dx = int(math.sqrt(max(0, r2 - dy * dy)))
        blend_span(yy, cx - dx, cx + dx + 1, color, alpha)


def ellipse(cx, cy, rx, ry, color):
    cx, cy, rx, ry = _ix(cx), _ix(cy), _ix(rx), _ix(ry)
    for yy in range(cy - ry, cy + ry + 1):
        dy = (yy - cy) / max(1, ry)
        dx = int(rx * math.sqrt(max(0.0, 1.0 - dy * dy)))
        span(yy, cx - dx, cx + dx + 1, color)


def blend_ellipse(cx, cy, rx, ry, color, alpha):
    cx, cy, rx, ry = _ix(cx), _ix(cy), _ix(rx), _ix(ry)
    for yy in range(cy - ry, cy + ry + 1):
        dy = (yy - cy) / max(1, ry)
        dx = int(rx * math.sqrt(max(0.0, 1.0 - dy * dy)))
        blend_span(yy, cx - dx, cx + dx + 1, color, alpha)


def dome(cx, cy, rx, ry, color):
    """Upper half of an ellipse only (flat bottom edge at y=cy)."""
    cx, cy, rx, ry = _ix(cx), _ix(cy), _ix(rx), _ix(ry)
    for yy in range(cy - ry, cy + 1):
        dy = (yy - cy) / max(1, ry)
        dx = int(rx * math.sqrt(max(0.0, 1.0 - dy * dy)))
        span(yy, cx - dx, cx + dx + 1, color)


def rrect(x, y, w, h, r, color):
    fill_rect(x + r, y, w - 2 * r, h, color)
    fill_rect(x, y + r, w, h - 2 * r, color)
    disc(x + r, y + r, r, color)
    disc(x + w - r, y + r, r, color)
    disc(x + r, y + h - r, r, color)
    disc(x + w - r, y + h - r, r, color)


def polygon(points, color):
    """Scanline-fill a polygon given in design coordinates."""
    pts = [(_ix(x), _ix(y)) for x, y in points]
    ys = [p[1] for p in pts]
    for yy in range(min(ys), max(ys) + 1):
        xs = []
        n = len(pts)
        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            if (y0 <= yy < y1) or (y1 <= yy < y0):
                t = (yy - y0) / (y1 - y0)
                xs.append(int(x0 + t * (x1 - x0)))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            span(yy, xs[i], xs[i + 1] + 1, color)


def thick_line(x0, y0, x1, y1, width, color):
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length == 0:
        disc(x0, y0, width / 2, color)
        return
    nx, ny = -dy / length * width / 2, dx / length * width / 2
    polygon([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
             (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], color)


def bg_row_color(yy):
    """Vertical gradient colour at buffer row yy."""
    return _lerp(BG_TOP, BG_BOT, yy / IW)


def background():
    for yy in range(IW):
        span(yy, 0, IW, bg_row_color(yy))


def glow(cx, cy, rx, ry, color, amax, bands=40):
    """Warm radial glow over the background, as opaque bands.

    Each band is drawn full-width with the exact final colour for
    its radius, so no per-pixel blending is needed: the background
    is a known vertical gradient.
    """
    cx, cy, rx, ry = _ix(cx), _ix(cy), _ix(rx), _ix(ry)
    edges = [1.0 - i / bands for i in range(bands + 1)]
    for yy in range(cy - ry, cy + ry + 1):
        dy = (yy - cy) / max(1, ry)
        chord = int(rx * math.sqrt(max(0.0, 1.0 - dy * dy)))
        if chord <= 0:
            continue
        bgc = bg_row_color(yy)
        for b in range(len(edges) - 1):
            f_out, f_in = edges[b], edges[b + 1]
            f_mid = (f_out + f_in) / 2
            alpha = amax * (1.0 - f_mid * f_mid)
            col = _lerp(bgc, color, alpha / 255.0)
            span(yy, cx - int(chord * f_out), cx + int(chord * f_out) + 1, col)


# ---------------------------------------------------------------------------
# PNG encoder: 8-bit RGB, filter 0 per row, zlib level 9.
# ---------------------------------------------------------------------------
def _chunk(kind, data):
    c = struct.pack(">I", len(data)) + kind + data
    return c + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def encode_png(rgb, w, h):
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += rgb[y * w * 3:(y + 1) * w * 3]
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + _chunk(b"IEND", b""))


def downsample():
    out = bytearray(W * W * 3)
    for y in range(W):
        for x in range(W):
            sr = sg = sb = 0
            for dy in range(S):
                base = ((y * S + dy) * IW + x * S) * 3
                for dx in range(S):
                    i = base + dx * 3
                    sr += buf[i]
                    sg += buf[i + 1]
                    sb += buf[i + 2]
            o = (y * W + x) * 3
            out[o] = sr // (S * S)
            out[o + 1] = sg // (S * S)
            out[o + 2] = sb // (S * S)
    return out

# ---------------------------------------------------------------------------
# 5x7 bitmap font. 7 rows of 5 bits, '1' = filled.
# ---------------------------------------------------------------------------
FONT = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01110", "10001", "10000", "10111", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["01110", "00100", "00100", "00100", "00100", "00100", "01110"],
    "J": ["00111", "00010", "00010", "00010", "00010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00110", "01000", "10000", "11111"],
    "3": ["11111", "00010", "00100", "00010", "00001", "10001", "01110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
    "6": ["00110", "01000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00010", "01100"],
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
    ".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
    ",": ["00000", "00000", "00000", "00000", "01100", "00100", "01000"],
    ":": ["00000", "01100", "01100", "00000", "01100", "01100", "00000"],
    "!": ["00100", "00100", "00100", "00100", "00100", "00000", "00100"],
    "?": ["01110", "10001", "00001", "00110", "00100", "00000", "00100"],
    "'": ["00100", "00100", "01000", "00000", "00000", "00000", "00000"],
    "-": ["00000", "00000", "00000", "01110", "00000", "00000", "00000"],
    "*": ["00000", "10101", "01110", "10101", "00000", "00000", "00000"],
}


def draw_text(text, x, y, scale, color):
    """Draw text; one font pixel is a scale x scale design-px block."""
    cx = x
    for ch in text:
        glyph = FONT.get(ch)
        if glyph:
            for r, row in enumerate(glyph):
                for c, bit in enumerate(row):
                    if bit == "1":
                        fill_rect(cx + c * scale, y + r * scale, scale, scale, color)
        cx += 6 * scale


def text_width(text, scale):
    return len(text) * 6 * scale - scale


def draw_text_centered(text, y, scale, color, cx=W // 2):
    draw_text(text, cx - text_width(text, scale) // 2, y, scale, color)


# ---------------------------------------------------------------------------
# Scene: the golden smash burger.
# ---------------------------------------------------------------------------
def draw_table():
    fill_rect(0, 700, W, W - 700, TABLE)
    fill_rect(0, 700, W, 3, TABLE_EDGE)
    for y in (800, 880, 960):
        fill_rect(0, y, W, 3, TABLE_LINE)


def draw_plate():
    blend_ellipse(512, 752, 350, 36, BLACK, 100)
    ellipse(512, 652, 338, 102, PLATE_OUT)
    ellipse(512, 650, 306, 88, PLATE_RIM)
    ellipse(512, 650, 292, 80, PLATE_IN)


def draw_fries():
    # Golden sticks, tops sticking out of the cup at slight angles.
    sticks = []
    for i in range(11):
        bx = 780 + i * 9
        top_y = 518 + RNG.randint(0, 36)
        lean = RNG.randint(-16, 14)
        sticks.append((bx, top_y, lean))
    for bx, top_y, lean in sticks:
        thick_line(bx, 648, bx + lean, top_y, 19, FRY)
        disc(bx + lean, top_y, 8, FRY_TIP)
    # Cup: red trapezoid with white stripes and a rim.
    polygon([(762, 616), (878, 616), (864, 742), (776, 742)], CUP)
    polygon([(792, 616), (812, 616), (808, 742), (796, 742)], CUP_WHITE)
    polygon([(832, 616), (852, 616), (848, 742), (836, 742)], CUP_WHITE)
    rrect(758, 606, 124, 18, 6, CUP_HI)


def draw_burger():
    cx = 512
    # Bottom bun (patty covers its top edge).
    rrect(296, 580, 432, 64, 24, BUN_BOT)
    fill_rect(306, 586, 412, 10, BUN_BOT_HI)
    fill_rect(296, 632, 432, 12, BUN_BOT_SH)
    # Patty with char marks.
    rrect(284, 524, 456, 60, 20, PATTY)
    fill_rect(292, 524, 440, 10, PATTY_HI)
    for sx in (330, 408, 486, 564, 642):
        fill_rect(sx, 534, 12, 48, PATTY_CHAR)
    fill_rect(284, 574, 456, 10, PATTY_SH)
    # Tomato slice peeking out.
    ellipse(cx, 520, 242, 22, TOMATO)
    ellipse(480, 512, 120, 8, TOMATO_HI)
    # Melted cheddar, dripping over the patty.
    fill_rect(290, 496, 444, 28, CHEESE)
    fill_rect(298, 500, 428, 8, CHEESE_HI)
    for dx, dw, dl in ((340, 26, 556), (440, 22, 548),
                       (560, 28, 562), (668, 22, 544)):
        fill_rect(dx, 496, dw, dl - 496, CHEESE)
        disc(dx + dw // 2, dl, dw // 2, CHEESE)
    # Scalloped lettuce.
    fill_rect(262, 476, 500, 26, LETTUCE)
    for lx in range(278, 747, 32):
        disc(lx, 502, 15, LETTUCE)
    for lx in range(294, 731, 32):
        disc(lx, 496, 8, LETTUCE_HI)
    # Top bun: golden dome with rim, shade, sheen and sesame.
    dome(cx, 484, 238, 146, BUN_RIM)
    dome(cx, 482, 234, 144, BUN)
    blend_ellipse(512, 512, 225, 55, BUN_SHADE, 80)
    blend_ellipse(462, 408, 150, 82, BUN_HI, 85)
    blend_ellipse(470, 400, 120, 55, WHITE, 46)
    seeds = []
    while len(seeds) < 16:
        sx = RNG.randint(350, 674)
        sy = RNG.randint(350, 470)
        if ((sx - cx) / 225.0) ** 2 + ((sy - 478) / 135.0) ** 2 < 0.62:
            seeds.append((sx, sy))
    for sx, sy in seeds:
        ellipse(sx + 2, sy + 3, 9, 5, SESAME_SH)
        ellipse(sx, sy, 9, 5, SESAME)


def soft_wisp(cx, y_top, y_bot, phase, width, amax):
    """A smooth vertical wisp: per buffer row, annulus bands of
    alpha-blended spans, so no disc edge ever shows."""
    edges = [1.0, 0.8, 0.6, 0.4, 0.2, 0.0]
    for yy in range(_ix(y_top), _ix(y_bot) + 1):
        dy = yy / S
        s = (y_bot - dy) / max(1.0, y_bot - y_top)  # 0 bottom, 1 top
        ccx = _ix(cx + 26 * math.sin(s * 3.0 + phase))
        w = _ix(width * (0.8 + 0.4 * s))
        env = math.sin(math.pi * (0.2 + 0.8 * s))
        if env <= 0.01:
            continue
        for b in range(len(edges) - 1):
            f_out, f_in = edges[b], edges[b + 1]
            f_mid = (f_out + f_in) / 2
            alpha = int(amax * env * (1.0 - f_mid * f_mid))
            if alpha <= 0:
                continue
            xo = int(w * f_out)
            xi = int(w * f_in)
            blend_span(yy, ccx - xo, ccx - xi, STEAM, alpha)
            blend_span(yy, ccx + xi, ccx + xo, STEAM, alpha)


def draw_steam():
    for cx, phase in ((440, 0.0), (512, 1.3), (584, 2.6)):
        soft_wisp(cx, 150, 332, phase, 30, 26)
    for cx, phase in ((800, 0.4), (842, 1.9)):
        soft_wisp(cx, 440, 522, phase, 20, 20)


def draw_garnish():
    for gx, gy, grx in ((300, 700, 14), (720, 712, 12), (640, 726, 10)):
        ellipse(gx, gy, grx, 6, HERB)
    for gx, gy in ((360, 716), (700, 690), (420, 728)):
        ellipse(gx, gy, 5, 3, SESAME)


def draw_caption():
    text = "FRESH OFF THE GRILL"
    draw_text_centered(text, 930, 4, CAPTION)
    fill_rect(190, 942, 70, 4, RULE)
    fill_rect(764, 942, 70, 4, RULE)


def render():
    background()
    glow(512, 440, 470, 330, GLOW, 36)
    draw_table()
    draw_plate()
    draw_fries()
    draw_burger()
    draw_steam()
    draw_garnish()
    draw_caption()


def main():
    render()
    rgb = downsample()
    png = encode_png(rgb, W, W)
    outdir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / "entry.png"
    out.write_bytes(png)
    print(f"wrote {out} ({len(png)} bytes, {W}x{W})")


if __name__ == "__main__":
    main()
