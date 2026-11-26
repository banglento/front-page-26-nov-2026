#!/usr/bin/env python3
"""Front page of one day's world news: Thursday 26 November 2026.

Draws a 1024x1024 newspaper front page with a self-written 5x7 bitmap
font, procedural illustrations, and a hand-rolled PNG encoder.
Standard library only, no network, fully deterministic.
"""
import math
import os
import struct
import zlib

W, H = 1024, 1024

PAPER = (248, 243, 232)
INK = (18, 18, 18)
RED = (178, 34, 34)
BLUE = (32, 80, 122)
NAVY = (22, 38, 66)
ORANGE = (216, 106, 28)
YELLOW = (234, 180, 44)
GREY = (122, 122, 118)
LIGHTGREY = (202, 198, 188)
GREEN = (48, 112, 62)
SKY = (180, 210, 230)
SEA = (48, 112, 160)
NIGHT = (36, 44, 66)
SMOKE = (150, 150, 146)
SAND = (214, 196, 158)


# ---------------------------------------------------------------- PNG encoder
def png_bytes(w, h, rgb):
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", comp) + chunk(b"IEND", b""))


# ------------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.px = bytearray(w * h * 3)
        self.fill_rect(0, 0, w, h, bg)

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i], self.px[i + 1], self.px[i + 2] = c

    def fill_rect(self, x, y, w, h, c):
        x0, y0 = max(x, 0), max(y, 0)
        x1, y1 = min(x + w, self.w), min(y + h, self.h)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            for xx in range(x0, x1):
                self.px[i], self.px[i + 1], self.px[i + 2] = c
                i += 3

    def hline(self, x, y, w, c, t=1):
        self.fill_rect(x, y, w, t, c)

    def vline(self, x, y, h, c, t=1):
        self.fill_rect(x, y, t, h, c)

    def line(self, x0, y0, x1, y1, c, t=1):
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            self.fill_rect(x0 - t // 2, y0 - t // 2, t, t, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def circle(self, cx, cy, r, c):
        for yy in range(cy - r, cy + r + 1):
            if abs(yy - cy) > r:
                continue
            dx = int((r * r - (yy - cy) ** 2) ** 0.5)
            self.hline(cx - dx, yy, 2 * dx + 1, c)

    def ellipse(self, cx, cy, rx, ry, c):
        for yy in range(cy - ry, cy + ry + 1):
            t = 1.0 - ((yy - cy) / ry) ** 2
            dx = int(rx * (t ** 0.5)) if t > 0 else 0
            self.hline(cx - dx, yy, 2 * dx + 1, c)

    def ring(self, cx, cy, r, c, t=2):
        for yy in range(cy - r, cy + r + 1):
            for xx in range(cx - r, cx + r + 1):
                d = ((xx - cx) ** 2 + (yy - cy) ** 2) ** 0.5
                if r - t <= d <= r:
                    self.set(xx, yy, c)

    def polygon(self, pts, c):
        ys = [p[1] for p in pts]
        for yy in range(min(ys), max(ys) + 1):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= yy < y1) or (y1 <= yy < y0):
                    xs.append(x0 + (yy - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self.hline(int(xs[i]), yy, max(1, int(xs[i + 1]) - int(xs[i])), c)

    def star(self, cx, cy, r_out, r_in, points, c):
        pts = []
        for i in range(points * 2):
            r = r_out if i % 2 == 0 else r_in
            a = math.pi * i / points - math.pi / 2
            pts.append((int(cx + r * math.cos(a)), int(cy + r * math.sin(a))))
        self.polygon(pts, c)

    def flame(self, cx, cy, r):
        """Layered teardrop flame: orange outer, yellow core, red base."""
        self.ellipse(cx, cy, r, int(r * 1.4), ORANGE)
        self.polygon([(cx - r, cy + r), (cx, cy - int(r * 1.8)),
                      (cx + r, cy + r)], ORANGE)
        self.ellipse(cx, cy + 2, int(r * 0.55), int(r * 0.8), YELLOW)
        self.ellipse(cx, cy + 5, int(r * 0.3), int(r * 0.45), RED)


# --------------------------------------------------------------------- font
# 5x7 bitmap font, uppercase + digits + punctuation, drawn from scratch.
FONT = {
    "A": (" ### ", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"),
    "B": ("#### ", "#   #", "#   #", "#### ", "#   #", "#   #", "#### "),
    "C": (" ####", "#    ", "#    ", "#    ", "#    ", "#    ", " ####"),
    "D": ("#### ", "#   #", "#   #", "#   #", "#   #", "#   #", "#### "),
    "E": ("#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#####"),
    "F": ("#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#    "),
    "G": (" ####", "#    ", "#    ", "# ###", "#   #", "#   #", " ### "),
    "H": ("#   #", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"),
    "I": ("#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "#####"),
    "J": ("  ###", "   # ", "   # ", "   # ", "   # ", "#  # ", " ##  "),
    "K": ("#   #", "#  # ", "# #  ", "##   ", "# #  ", "#  # ", "#   #"),
    "L": ("#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#####"),
    "M": ("#   #", "## ##", "# # #", "# # #", "#   #", "#   #", "#   #"),
    "N": ("#   #", "##  #", "# # #", "#  ##", "#   #", "#   #", "#   #"),
    "O": (" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "),
    "P": ("#### ", "#   #", "#   #", "#### ", "#    ", "#    ", "#    "),
    "Q": (" ### ", "#   #", "#   #", "#   #", "# # #", "#  # ", " ## #"),
    "R": ("#### ", "#   #", "#   #", "#### ", "# #  ", "#  # ", "#   #"),
    "S": (" ####", "#    ", "#    ", " ### ", "    #", "    #", "#### "),
    "T": ("#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "),
    "U": ("#   #", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "),
    "V": ("#   #", "#   #", "#   #", "#   #", "#   #", " # # ", "  #  "),
    "W": ("#   #", "#   #", "#   #", "# # #", "# # #", "## ##", "#   #"),
    "X": ("#   #", "#   #", " # # ", "  #  ", " # # ", "#   #", "#   #"),
    "Y": ("#   #", "#   #", " # # ", "  #  ", "  #  ", "  #  ", "  #  "),
    "Z": ("#####", "    #", "   # ", "  #  ", " #   ", "#    ", "#####"),
    "0": (" ### ", "#   #", "#  ##", "# # #", "##  #", "#   #", " ### "),
    "1": ("  #  ", " ##  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "),
    "2": (" ### ", "#   #", "    #", "   # ", "  #  ", " #   ", "#####"),
    "3": ("#### ", "    #", "    #", " ### ", "    #", "    #", "#### "),
    "4": ("   # ", "  ## ", " # # ", "#  # ", "#####", "   # ", "   # "),
    "5": ("#####", "#    ", "#### ", "    #", "    #", "#   #", " ### "),
    "6": (" ### ", "#    ", "#    ", "#### ", "#   #", "#   #", " ### "),
    "7": ("#####", "    #", "   # ", "  #  ", "  #  ", "  #  ", "  #  "),
    "8": (" ### ", "#   #", "#   #", " ### ", "#   #", "#   #", " ### "),
    "9": (" ### ", "#   #", "#   #", " ####", "    #", "    #", " ### "),
    " ": ("     ", "     ", "     ", "     ", "     ", "     ", "     "),
    ",": ("     ", "     ", "     ", "     ", "     ", " ##  ", " #   "),
    ".": ("     ", "     ", "     ", "     ", "     ", " ##  ", " ##  "),
    "'": (" #   ", " #   ", "  #  ", "     ", "     ", "     ", "     "),
    "-": ("     ", "     ", "     ", " ####", "     ", "     ", "     "),
    ":": ("     ", " ##  ", " ##  ", "     ", " ##  ", " ##  ", "     "),
    "!": ("  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "     ", "  #  "),
    "?": (" ### ", "#   #", "    #", "   # ", "  #  ", "     ", "  #  "),
    "&": (" ##  ", "#  # ", "# #  ", " #   ", "# # #", "#  # ", " ## #"),
    "/": ("    #", "    #", "   # ", "  #  ", " #   ", "#    ", "#    "),
    "(": ("   # ", "  #  ", " #   ", " #   ", " #   ", "  #  ", "   # "),
    ")": (" #   ", "  #  ", "   # ", "   # ", "   # ", "  #  ", " #   "),
    "%": ("#   #", "#  # ", "   # ", "  #  ", " #   ", "#  # ", "#   #"),
    "+": ("     ", "  #  ", "  #  ", "#####", "  #  ", "  #  ", "     "),
    "=": ("     ", "     ", "#####", "     ", "#####", "     ", "     "),
    "~": ("     ", "     ", " ## #", "# ## ", "     ", "     ", "     "),
    ";": ("     ", " ##  ", " ##  ", "     ", " ##  ", " ##  ", " #   "),
    "*": ("     ", " # # ", "  #  ", "#####", "  #  ", " # # ", "     "),
    "$": ("  #  ", " ####", "# # #", " ### ", "  # #", "#### ", "  #  "),
}


def text_width(s, scale):
    return len(s) * 6 * scale - scale


def draw_text(cv, x, y, s, scale, color):
    for ch in s:
        glyph = FONT.get(ch.upper(), FONT[" "])
        for row in range(7):
            for col in range(5):
                if glyph[row][col] == "#":
                    cv.fill_rect(x + col * scale, y + row * scale,
                                 scale, scale, color)
        x += 6 * scale
    return x


def draw_text_centered(cv, cx, y, s, scale, color):
    draw_text(cv, cx - text_width(s, scale) // 2, y, s, scale, color)


def draw_wrapped(cv, x, y, max_w, text, scale, color, gap=4):
    lines, cur = [], ""
    for word in text.split(" "):
        trial = (cur + " " + word).strip()
        if text_width(trial, scale) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    for ln in lines:
        draw_text(cv, x, y, ln, scale, color)
        y += 7 * scale + gap
    return y


def panel(cv, x, y, w, h):
    cv.fill_rect(x, y, w, h, PAPER)
    cv.fill_rect(x, y, w, 2, INK)
    cv.fill_rect(x, y + h - 2, w, 2, INK)
    cv.fill_rect(x, y, 2, h, INK)
    cv.fill_rect(x + w - 2, y, 2, h, INK)


def kicker(cv, x, y, s, color=RED):
    draw_text(cv, x, y, s, 2, color)


# ------------------------------------------------------------- illustrations
def draw_refinery_scene(cv, x, y, w, h):
    """Oil refinery at dusk: distillation towers, flame, rising price chart."""
    cv.fill_rect(x, y, w, h, (226, 214, 188))
    ground = y + h - 26
    cv.fill_rect(x, ground, w, h - (ground - y), (96, 88, 76))
    # distillation tower 1 (left)
    t1x, t1w = x + 26, 40
    cv.fill_rect(t1x, y + 66, t1w, ground - (y + 66), (84, 92, 104))
    cv.ellipse(t1x + t1w // 2, y + 66, t1w // 2, 10, (84, 92, 104))
    for i in range(4):
        cv.hline(t1x - 4, y + 92 + i * 26, t1w + 8, INK, 2)
    # distillation tower 2 (middle, taller, on fire)
    t2x, t2w = x + 96, 46
    cv.fill_rect(t2x, y + 40, t2w, ground - (y + 40), (70, 78, 92))
    cv.ellipse(t2x + t2w // 2, y + 40, t2w // 2, 11, (70, 78, 92))
    for i in range(5):
        cv.hline(t2x - 4, y + 66 + i * 26, t2w + 8, INK, 2)
    # flame + smoke over tower 2
    cv.flame(t2x + t2w // 2, y + 22, 13)
    for (sx, sy, r) in ((t2x + 4, y + 4, 6), (t2x + 22, y - 2, 7),
                        (t2x + 40, y + 4, 6)):
        cv.circle(sx, sy, r, SMOKE)
    # connecting pipes
    cv.hline(t1x + t1w, y + 120, t2x - (t1x + t1w), INK, 3)
    cv.hline(t2x + t2w, y + 150, 44, INK, 3)
    # storage tank (right)
    tkx = x + 196
    cv.ellipse(tkx + 34, y + 128, 34, 10, (160, 158, 148))
    cv.fill_rect(tkx, y + 128, 68, ground - (y + 128), (160, 158, 148))
    cv.hline(tkx, y + 128, 68, INK, 2)
    # price chart box (far right)
    bx, by, bw, bh = x + w - 162, y + 14, 150, 118
    cv.fill_rect(bx, by, bw, bh, (250, 248, 242))
    cv.fill_rect(bx, by, bw, 2, INK)
    cv.fill_rect(bx, by + bh - 2, bw, 2, INK)
    cv.fill_rect(bx, by, 2, bh, INK)
    cv.fill_rect(bx + bw - 2, by, 2, bh, INK)
    pts = [(bx + 10, by + 92), (bx + 38, by + 84), (bx + 66, by + 88),
           (bx + 94, by + 52), (bx + 122, by + 30), (bx + 136, by + 16)]
    for i in range(len(pts) - 1):
        cv.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], RED, 3)
    cv.polygon([(pts[-1][0], pts[-1][1]), (pts[-1][0] - 12, pts[-1][1] + 2),
                (pts[-1][0] - 2, pts[-1][1] + 12)], RED)
    draw_text(cv, bx + 4, by + bh - 20, "BRENT $94.61", 2, INK)
    # ground line
    cv.hline(x, ground, w, INK, 2)


def draw_tanker_scene(cv, x, y, w, h):
    """Night highway: fuel tanker engulfed in flames, smoke rising."""
    cv.fill_rect(x, y, w, h, NIGHT)
    # stars
    for i in range(9):
        sx = x + 12 + (i * 47) % (w - 24)
        sy = y + 6 + (i * 13) % 16
        cv.set(sx, sy, YELLOW)
        cv.set(sx + 1, sy, YELLOW)
    # road
    road_y = y + h - 22
    cv.fill_rect(x, road_y, w, 22, (52, 52, 56))
    for i in range(0, w, 34):
        cv.hline(x + i, road_y + 10, 18, (240, 230, 180), 2)
    # tanker: tank + cab, left side
    tx, ty = x + 30, road_y - 26
    cv.ellipse(tx + 78, ty + 12, 78, 13, (190, 188, 178))
    cv.fill_rect(tx, ty, 156, 26, (190, 188, 178))
    cv.hline(tx, ty, 156, INK, 2)
    cv.fill_rect(tx + 158, ty + 6, 30, 20, RED)
    cv.fill_rect(tx + 164, ty + 10, 10, 8, SKY)
    # wheels
    for wx in (tx + 22, tx + 66, tx + 118, tx + 172):
        cv.circle(wx, road_y + 2, 6, INK)
        cv.circle(wx, road_y + 2, 2, GREY)
    # big flame over the tank + smoke
    cv.flame(tx + 78, ty - 8, 16)
    cv.flame(tx + 118, ty - 2, 11)
    for (sx, sy, r) in ((tx + 60, y + 8, 7), (tx + 88, y + 2, 9),
                        (tx + 116, y + 8, 7)):
        cv.circle(sx, sy, r, SMOKE)


def draw_airbase_scene(cv, x, y, w, h):
    """Air base runway: two jets, one hit, smoke plume rising."""
    cv.fill_rect(x, y, w, h, SKY)
    # clouds
    for (cx, cy, r) in ((x + 46, y + 10, 9), (x + 60, y + 14, 7),
                        (x + w - 70, y + 8, 8)):
        cv.circle(cx, cy, r, (250, 250, 246))
    # runway
    rw_y = y + h - 24
    cv.fill_rect(x, rw_y, w, 24, (88, 88, 90))
    for i in range(0, w, 36):
        cv.hline(x + i, rw_y + 11, 20, (250, 248, 240), 2)
    # jet 1 (intact, left)
    jx, jy = x + 34, rw_y - 16
    cv.polygon([(jx, jy + 6), (jx + 66, jy + 6), (jx + 82, jy + 10),
                (jx + 66, jy + 14), (jx, jy + 14)], (60, 64, 70))
    cv.polygon([(jx + 22, jy + 6), (jx + 34, jy - 6), (jx + 42, jy - 6),
                (jx + 36, jy + 6)], (60, 64, 70))
    cv.polygon([(jx + 52, jy + 14), (jx + 58, jy + 22), (jx + 66, jy + 22),
                (jx + 62, jy + 14)], (60, 64, 70))
    # jet 2 (hit, right) tilted, with burst + smoke
    j2x, j2y = x + w - 170, rw_y - 12
    cv.polygon([(j2x, j2y + 4), (j2x + 60, j2y + 2), (j2x + 74, j2y + 6),
                (j2x + 60, j2y + 10), (j2x, j2y + 10)], (60, 64, 70))
    cv.polygon([(j2x + 20, j2y + 4), (j2x + 30, j2y - 8), (j2x + 38, j2y - 8),
                (j2x + 32, j2y + 4)], (60, 64, 70))
    cv.star(j2x + 40, j2y - 12, 16, 7, 8, ORANGE)
    cv.star(j2x + 40, j2y - 12, 9, 4, 8, YELLOW)
    for (sx, sy, r) in ((j2x + 30, y + 6, 6), (j2x + 48, y + 2, 8),
                        (j2x + 66, y + 6, 6)):
        cv.circle(sx, sy, r, SMOKE)


def draw_rocket_scene(cv, x, y, w, h):
    """Night sky: horizontal rocket flying to a space station module."""
    cv.fill_rect(x, y, w, h, NAVY)
    # stars (fixed positions, deterministic)
    for i in range(14):
        sx = x + 8 + (i * 31) % (w - 16)
        sy = y + 4 + (i * 17) % (h - 40)
        cv.set(sx, sy, (255, 255, 255))
        if i % 3 == 0:
            cv.set(sx + 1, sy, (255, 255, 255))
    # station module (right): body + solar panels
    sx, sy = x + w - 118, y + 22
    cv.fill_rect(sx, sy, 74, 18, (200, 200, 196))
    cv.fill_rect(sx - 8, sy + 4, 8, 10, (160, 160, 156))
    cv.fill_rect(sx + 74, sy + 4, 10, 10, (160, 160, 156))
    cv.fill_rect(sx + 6, sy - 12, 62, 10, BLUE)
    cv.fill_rect(sx + 6, sy + 20, 62, 10, BLUE)
    cv.hline(sx + 6, sy - 7, 62, INK, 1)
    cv.hline(sx + 6, sy + 25, 62, INK, 1)
    cv.fill_rect(sx + 30, sy + 6, 14, 6, YELLOW)  # lit window
    # rocket (left, horizontal, nose right)
    rx, ry = x + 24, y + 30
    cv.polygon([(rx + 96, ry), (rx + 118, ry + 9), (rx + 96, ry + 18)],
               RED)
    cv.fill_rect(rx, ry, 96, 18, (240, 240, 236))
    cv.fill_rect(rx + 30, ry + 4, 18, 10, SKY)  # window
    cv.polygon([(rx + 6, ry), (rx + 22, ry - 10), (rx + 30, ry),
                (rx + 22, ry + 18), (rx + 6, ry + 18)], RED)
    # exhaust flame
    cv.polygon([(rx, ry + 2), (rx - 26, ry + 9), (rx, ry + 16)], ORANGE)
    cv.polygon([(rx, ry + 5), (rx - 16, ry + 9), (rx, ry + 13)], YELLOW)
    # ground hint
    cv.hline(x, y + h - 4, w, (120, 130, 160), 1)


def draw_trade_scene(cv, x, y, w, h):
    """Container ship at sea beside a tariff bar chart."""
    cv.fill_rect(x, y, w, h, SKY)
    sea_y = y + h - 20
    cv.fill_rect(x, sea_y, w, h - (sea_y - y), SEA)
    for i in range(0, w, 30):
        cv.hline(x + i, sea_y + 8, 18, (255, 255, 255))
    # container ship (left)
    hx, hy = x + 16, sea_y - 22
    cv.polygon([(hx, hy), (hx + 190, hy), (hx + 172, hy + 22),
                (hx + 12, hy + 22)], (58, 58, 64))
    cv.fill_rect(hx + 16, hy - 20, 34, 20, RED)
    cv.fill_rect(hx + 54, hy - 20, 34, 20, YELLOW)
    cv.fill_rect(hx + 92, hy - 20, 34, 20, BLUE)
    cv.fill_rect(hx + 130, hy - 34, 34, 34, GREEN)
    cv.fill_rect(hx + 168, hy - 30, 10, 30, INK)  # bridge tower
    # bar chart (right): three bars, tallest red, labelled 15%
    bx, by = x + w - 148, y + 8
    base = y + h - 6
    cv.fill_rect(bx, by, 132, base - by, (250, 248, 242))
    cv.fill_rect(bx, by, 132, 2, INK)
    cv.fill_rect(bx, base - 2, 132, 2, INK)
    cv.fill_rect(bx, by, 2, base - by, INK)
    cv.fill_rect(bx + 130, by, 2, base - by, INK)
    bars = [(bx + 10, 16, 28, GREY), (bx + 46, 30, 28, BLUE),
            (bx + 82, 48, 36, RED)]
    for (bx0, bh, bwid, bc) in bars:
        cv.fill_rect(bx0, base - 2 - bh, bwid, bh, bc)
    draw_text(cv, bx + 84, by + 16, "15%", 2, PAPER)


# ---------------------------------------------------------------------- page
def build():
    cv = Canvas(W, H, PAPER)

    # ---- masthead
    draw_text_centered(cv, W // 2, 28, "THE WORLD TODAY", 9, INK)
    cv.hline(28, 102, W - 56, INK, 4)
    cv.hline(28, 110, W - 56, INK, 1)
    draw_text(cv, 28, 124, "NO. 330", 2, INK)
    draw_text_centered(cv, W // 2, 120, "THURSDAY 26 NOVEMBER 2026", 4, RED)
    draw_text(cv, W - 28 - text_width("PRICE: FREE", 2), 124, "PRICE: FREE",
              2, INK)
    cv.hline(28, 162, W - 56, INK, 2)

    # ---- lead story: Houthis claim Ras Tanura, oil jumps
    lx, ly, lw, lh = 28, 176, W - 56, 272
    panel(cv, lx, ly, lw, lh)
    kicker(cv, lx + 20, ly + 14, "ENERGY - RAS TANURA")
    draw_text(cv, lx + 20, ly + 42, "OIL JUMPS AS HOUTHIS", 3, INK)
    draw_text(cv, lx + 20, ly + 70, "CLAIM REFINERY HIT", 3, INK)
    draw_wrapped(cv, lx + 20, ly + 110, 470,
                 "Yemen's Houthis say they hit Saudi Arabia's Ras Tanura "
                 "refinery and Riyadh's financial district. Brent crude "
                 "settles $3.21 higher at $94.61 a barrel. Riyadh says it "
                 "shot down four drones; no damage is confirmed.", 2, INK)
    draw_refinery_scene(cv, lx + 520, ly + 14, lw - 540, lh - 28)

    # ---- row 2: Giza tanker fire / Savasleyka strike
    ry, rh = 464, 236
    pw = (W - 56 - 16) // 2
    # Giza
    panel(cv, 28, ry, pw, rh)
    kicker(cv, 48, ry + 12, "EGYPT - GIZA")
    draw_text(cv, 48, ry + 38, "31 KILLED IN", 3, RED)
    draw_text(cv, 48, ry + 66, "TANKER FIRE", 3, INK)
    draw_wrapped(cv, 48, ry + 98, pw - 40,
                 "A fuel tanker overturns on Cairo's Ring Road in Al "
                 "Warraq and bursts into flames. 31 killed, 21 hurt.",
                 2, INK)
    draw_tanker_scene(cv, 48, ry + 168, pw - 40, 56)
    # Savasleyka
    rx = 28 + pw + 16
    panel(cv, rx, ry, pw, rh)
    kicker(cv, rx + 20, ry + 12, "WAR - RUSSIA")
    draw_text(cv, rx + 20, ry + 38, "UKRAINE HITS", 3, INK)
    draw_text(cv, rx + 20, ry + 66, "5 WARPLANES", 3, INK)
    draw_wrapped(cv, rx + 20, ry + 98, pw - 40,
                 "Kyiv says it struck the Savasleyka air base east of "
                 "Moscow: three MiG-31 jets and two Su-34 bombers hit.",
                 2, INK)
    draw_airbase_scene(cv, rx + 20, ry + 168, pw - 40, 56)

    # ---- row 3: Shenzhou-24 / US tariffs
    ry3, rh3 = 716, 236
    panel(cv, 28, ry3, pw, rh3)
    kicker(cv, 48, ry3 + 12, "SPACE - TIANGONG")
    draw_text(cv, 48, ry3 + 38, "FIRST FOREIGN", 3, INK)
    draw_text(cv, 48, ry3 + 66, "ASTRONAUT ABOARD", 3, INK)
    draw_wrapped(cv, 48, ry3 + 98, pw - 40,
                 "Shenzhou-24 docks at Tiangong with Muhammad Zeeshan Ali "
                 "- the first foreign astronaut on China's station.",
                 2, INK)
    draw_rocket_scene(cv, 48, ry3 + 168, pw - 40, 56)
    # Tariffs
    panel(cv, rx, ry3, pw, rh3)
    kicker(cv, rx + 20, ry3 + 12, "TRADE - WASHINGTON")
    draw_text(cv, rx + 20, ry3 + 38, "TARIFFS UP TO 15%", 3, INK)
    draw_text(cv, rx + 20, ry3 + 66, "ON TAIWAN GOODS", 3, INK)
    draw_wrapped(cv, rx + 20, ry3 + 98, pw - 40,
                 "US proposes tariffs of up to 15% on Taiwan goods in an "
                 "overcapacity probe. Taiwan lands in the lowest tier.",
                 2, INK)
    draw_trade_scene(cv, rx + 20, ry3 + 168, pw - 40, 56)

    # ---- bottom strip: obituary + markets
    by = 966
    panel(cv, 28, by, W - 56, 34)
    cv.fill_rect(44, by + 12, 10, 10, RED)
    draw_text(cv, 64, by + 10,
              "ALSO: ANDY TAYLOR DIES AT 65; NASDAQ DOWN ALMOST 4% ON AI "
              "FEARS", 2, INK)

    return png_bytes(W, H, cv.px)


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "out")
    os.makedirs(out_dir, exist_ok=True)
    data = build()
    with open(os.path.join(out_dir, "entry.png"), "wb") as f:
        f.write(data)


if __name__ == "__main__":
    main()
