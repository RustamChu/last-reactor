"""Tower types, target selection and firing.

The machine gun leads its target: enemy velocity is known, bullet speed is
known, so the intercept point is the solution of a quadratic - where will
the enemy be when the bullet gets there. The cannon does the same but lobs a
shell that lands on the predicted spot. Without prediction every fast enemy
would simply outrun the bullets.
"""
from __future__ import annotations

import math

from settings import (LVL_DMG, LVL_RANGE, LVL_RATE, MAX_LEVEL, SELL_RATIO,
                      UPGRADE_RATIO)

TYPES = {
    "gun": {
        "name": "Пулемёт", "cost": 55, "damage": 7, "rate": 2.4,
        "range": 3.3, "bullet_speed": 13.0,
        "desc": "быстрый, бьёт одну цель",
    },
    "cannon": {
        "name": "Мортира", "cost": 95, "damage": 20, "rate": 0.75,
        "range": 3.7, "shell_speed": 6.5, "splash": 1.35,
        "desc": "площадной урон",
    },
    "frost": {
        "name": "Криолуч", "cost": 70, "damage": 2, "rate": 0.9,
        "range": 2.6, "slow_mult": 0.55, "slow_time": 1.6,
        "desc": "замедляет всё вокруг",
    },
    "tesla": {
        "name": "Тесла", "cost": 125, "damage": 11, "rate": 1.1,
        "range": 3.1, "chains": 3, "chain_range": 2.3, "falloff": 0.72,
        "desc": "цепная молния",
    },
}

BUILD_ORDER = ("gun", "cannon", "frost", "tesla")
MODES = ("первый", "последний", "крепкий", "ближний")


def intercept_point(px, py, target, bullet_speed):
    """Where to shoot so a straight bullet meets a moving enemy."""
    vx, vy = target.velocity
    rx, ry = target.x - px, target.y - py
    a = vx * vx + vy * vy - bullet_speed * bullet_speed
    b = 2.0 * (rx * vx + ry * vy)
    c = rx * rx + ry * ry
    t = 0.0
    if abs(a) < 1e-9:
        if abs(b) > 1e-9:
            t = max(0.0, -c / b)
    else:
        disc = b * b - 4.0 * a * c
        if disc >= 0:
            root = math.sqrt(disc)
            t1 = (-b - root) / (2.0 * a)
            t2 = (-b + root) / (2.0 * a)
            candidates = [v for v in (t1, t2) if v > 0]
            if candidates:
                t = min(candidates)
    return target.x + vx * t, target.y + vy * t


class Tower:
    def __init__(self, kind, cell):
        self.kind = kind
        self.stats = TYPES[kind]
        self.cell = cell
        self.x = cell[0] + 0.5
        self.y = cell[1] + 0.5
        self.level = 1
        self.mode = 0                       # index into MODES
        self.cooldown = 0.0
        self.invested = self.stats["cost"]
        self.aim_angle = 0.0                # radians, for drawing the turret
        self.fired_total = 0

    # ------------------------------------------------------------- scaling
    @property
    def name(self):
        return self.stats["name"]

    @property
    def damage(self):
        return self.stats["damage"] * (LVL_DMG ** (self.level - 1))

    @property
    def rate(self):
        return self.stats["rate"] * (LVL_RATE ** (self.level - 1))

    @property
    def range(self):
        return self.stats["range"] + LVL_RANGE * (self.level - 1)

    @property
    def splash(self):
        return self.stats.get("splash", 0) + 0.15 * (self.level - 1)

    @property
    def chains(self):
        return self.stats.get("chains", 0) + (self.level - 1)

    @property
    def upgrade_cost(self):
        return int(self.stats["cost"] * UPGRADE_RATIO)

    @property
    def sell_price(self):
        return int(self.invested * SELL_RATIO)

    @property
    def can_upgrade(self):
        return self.level < MAX_LEVEL

    def upgrade(self):
        self.level += 1
        self.invested += self.upgrade_cost

    # ----------------------------------------------------------- targeting
    def in_range(self, enemy):
        return math.hypot(enemy.x - self.x, enemy.y - self.y) <= self.range

    def acquire(self, enemies):
        """Pick a target according to the current targeting mode."""
        pool = [e for e in enemies if e.alive and self.in_range(e)]
        if not pool:
            return None
        mode = MODES[self.mode]
        if mode == "первый":
            return min(pool, key=lambda e: e.remaining)
        if mode == "последний":
            return max(pool, key=lambda e: e.remaining)
        if mode == "крепкий":
            return max(pool, key=lambda e: e.hp)
        return min(pool, key=lambda e: math.hypot(e.x - self.x, e.y - self.y))
