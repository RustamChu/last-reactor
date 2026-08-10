"""Procedural sprites - the project ships no image files.

The background, tower bases, turrets and panel icons are all drawn with
pygame primitives once at start-up and cached; per-frame work is plain
blitting. Enemies are animated shapes drawn directly by the renderer.
"""
from __future__ import annotations

import math
import random

import pygame as pg

from settings import (C_CANNON, C_FROST, C_GRIDLINE, C_GROUND_A, C_GROUND_B,
                      C_GUN, C_PORTAL, C_ROCK, C_ROCK_EDGE, C_TESLA, FIELD_COLS,
                      FIELD_ROWS, TILE)


def _mix(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


# ------------------------------------------------------------------ background
def make_background(grid):
    surf = pg.Surface((FIELD_COLS * TILE, FIELD_ROWS * TILE))
    rnd = random.Random(grid.seed if hasattr(grid, "seed") else 5)
    for cy in range(FIELD_ROWS):
        for cx in range(FIELD_COLS):
            base = C_GROUND_A if (cx + cy) % 2 == 0 else C_GROUND_B
            shade = _mix(base, (14, 16, 22), ((cx * 13 + cy * 7) % 5) * 0.05)
            pg.draw.rect(surf, shade, (cx * TILE, cy * TILE, TILE, TILE))
    for cx in range(FIELD_COLS + 1):
        pg.draw.line(surf, C_GRIDLINE, (cx * TILE, 0),
                     (cx * TILE, FIELD_ROWS * TILE))
    for cy in range(FIELD_ROWS + 1):
        pg.draw.line(surf, C_GRIDLINE, (0, cy * TILE),
                     (FIELD_COLS * TILE, cy * TILE))

    # rocks: jagged polygons with a lit edge
    for (cx, cy) in grid.rocks:
        rnd2 = random.Random(cx * 131 + cy * 17)
        px, py = cx * TILE, cy * TILE
        points = []
        for k in range(7):
            angle = k * math.tau / 7 + rnd2.uniform(-0.2, 0.2)
            radius = TILE * rnd2.uniform(0.30, 0.46)
            points.append((px + TILE / 2 + radius * math.cos(angle),
                           py + TILE / 2 + radius * math.sin(angle)))
        pg.draw.polygon(surf, C_ROCK, points)
        pg.draw.polygon(surf, C_ROCK_EDGE, points, 2)

    # spawn portal sockets (the swirl is animated by the renderer)
    for (cx, cy) in grid.spawns:
        rect = pg.Rect(cx * TILE + 3, cy * TILE + 3, TILE - 6, TILE - 6)
        pg.draw.rect(surf, (52, 26, 30), rect, border_radius=8)
        pg.draw.rect(surf, C_PORTAL, rect, 2, border_radius=8)
    return surf


# ---------------------------------------------------------------------- towers
def _base_plate(accent):
    size = TILE - 6
    surf = pg.Surface((size, size), pg.SRCALPHA)
    rect = surf.get_rect()
    pg.draw.rect(surf, (38, 42, 56), rect, border_radius=8)
    pg.draw.rect(surf, _mix(accent, (0, 0, 0), 0.45), rect, 3, border_radius=8)
    pg.draw.rect(surf, (24, 27, 38), rect.inflate(-10, -10), border_radius=6)
    return surf


def _turret_gun(accent):
    surf = pg.Surface((TILE + 8, TILE + 8), pg.SRCALPHA)
    cx = cy = (TILE + 8) // 2
    pg.draw.circle(surf, (58, 64, 84), (cx, cy), 9)
    pg.draw.rect(surf, accent, (cx, cy - 3, 19, 6), border_radius=2)
    pg.draw.rect(surf, _mix(accent, (0, 0, 0), 0.4),
                 (cx, cy - 3, 19, 6), 1, border_radius=2)
    pg.draw.circle(surf, accent, (cx, cy), 5)
    return surf


def _turret_cannon(accent):
    surf = pg.Surface((TILE + 8, TILE + 8), pg.SRCALPHA)
    cx = cy = (TILE + 8) // 2
    pg.draw.circle(surf, (58, 64, 84), (cx, cy), 11)
    pg.draw.rect(surf, accent, (cx - 2, cy - 5, 22, 10), border_radius=3)
    pg.draw.rect(surf, _mix(accent, (0, 0, 0), 0.4),
                 (cx - 2, cy - 5, 22, 10), 2, border_radius=3)
    pg.draw.circle(surf, _mix(accent, (255, 255, 255), 0.3), (cx, cy), 6)
    return surf


def _statue_frost(accent):
    surf = pg.Surface((TILE + 8, TILE + 8), pg.SRCALPHA)
    cx = cy = (TILE + 8) // 2
    points = [(cx, cy - 13), (cx + 8, cy), (cx, cy + 13), (cx - 8, cy)]
    pg.draw.polygon(surf, accent, points)
    pg.draw.polygon(surf, _mix(accent, (255, 255, 255), 0.5), points, 2)
    pg.draw.line(surf, (235, 250, 255), (cx, cy - 13), (cx, cy + 13), 1)
    return surf


def _statue_tesla(accent):
    surf = pg.Surface((TILE + 8, TILE + 8), pg.SRCALPHA)
    cx = cy = (TILE + 8) // 2
    pg.draw.rect(surf, (60, 56, 80), (cx - 4, cy - 4, 8, 14), border_radius=2)
    for k in range(3):
        y = cy + 2 + k * 4
        pg.draw.line(surf, accent, (cx - 7, y), (cx + 7, y), 2)
    pg.draw.circle(surf, _mix(accent, (255, 255, 255), 0.45), (cx, cy - 9), 6)
    pg.draw.circle(surf, accent, (cx, cy - 9), 6, 2)
    return surf


ACCENTS = {"gun": C_GUN, "cannon": C_CANNON, "frost": C_FROST,
           "tesla": C_TESLA}


def make_tower_sprites():
    """{kind: {"base": Surface, "turret": Surface|None, "rotates": bool}}."""
    return {
        "gun": {"base": _base_plate(C_GUN), "turret": _turret_gun(C_GUN),
                "rotates": True},
        "cannon": {"base": _base_plate(C_CANNON),
                   "turret": _turret_cannon(C_CANNON), "rotates": True},
        "frost": {"base": _base_plate(C_FROST),
                  "turret": _statue_frost(C_FROST), "rotates": False},
        "tesla": {"base": _base_plate(C_TESLA),
                  "turret": _statue_tesla(C_TESLA), "rotates": False},
    }


def make_shop_icons():
    sprites = make_tower_sprites()
    icons = {}
    for kind, parts in sprites.items():
        icon = pg.Surface((40, 40), pg.SRCALPHA)
        base = pg.transform.smoothscale(parts["base"], (34, 34))
        icon.blit(base, (3, 3))
        turret = pg.transform.smoothscale(parts["turret"], (40, 40))
        icon.blit(turret, (0, 0))
        icons[kind] = icon
    return icons
