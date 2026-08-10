"""Enemy types and their movement along the flow field."""
from __future__ import annotations

import math

TYPES = {
    "bug": {
        "name": "жук", "hp": 22, "speed": 1.5, "armor": 0,
        "reward": 6, "core_damage": 1, "radius": 0.30,
        "color": (210, 130, 80),
    },
    "runner": {
        "name": "бегун", "hp": 13, "speed": 2.9, "armor": 0,
        "reward": 6, "core_damage": 1, "radius": 0.24,
        "color": (240, 95, 95),
    },
    "tank": {
        "name": "броненосец", "hp": 95, "speed": 0.95, "armor": 4,
        "reward": 14, "core_damage": 2, "radius": 0.40,
        "color": (185, 100, 60),
    },
    "swarm": {
        "name": "рой", "hp": 28, "speed": 1.7, "armor": 0,
        "reward": 8, "core_damage": 1, "radius": 0.34,
        "color": (225, 180, 70),
    },
    "mite": {
        "name": "клещ", "hp": 6, "speed": 2.6, "armor": 0,
        "reward": 2, "core_damage": 1, "radius": 0.16,
        "color": (235, 205, 110),
    },
    "boss": {
        "name": "исполин", "hp": 750, "speed": 0.72, "armor": 6,
        "reward": 120, "core_damage": 5, "radius": 0.55,
        "color": (255, 80, 120),
    },
}

_next_id = [0]


class Enemy:
    def __init__(self, kind, cell, hp_mult=1.0):
        stats = TYPES[kind]
        self.kind = kind
        self.name = stats["name"]
        self.max_hp = max(1, int(stats["hp"] * hp_mult))
        self.hp = self.max_hp
        self.speed = stats["speed"]
        self.armor = stats["armor"]
        self.reward = stats["reward"]
        self.core_damage = stats["core_damage"]
        self.radius = stats["radius"]
        self.color = stats["color"]

        self.cell = cell
        self.x = cell[0] + 0.5
        self.y = cell[1] + 0.5
        self.dir = (1.0, 0.0)               # facing, for bullet prediction
        self.slow_mult = 1.0
        self.slow_timer = 0.0
        self.alive = True
        self.leaked = False
        self.remaining = 9999.0             # steps left to the core
        _next_id[0] += 1
        self.uid = _next_id[0]              # stable phase for animation

    # ------------------------------------------------------------- status
    def apply_slow(self, mult, duration):
        """The strongest slow wins; a fresh one refreshes the clock."""
        self.slow_mult = min(self.slow_mult, mult) if self.slow_timer > 0 else mult
        self.slow_timer = max(self.slow_timer, duration)

    @property
    def effective_speed(self):
        return self.speed * (self.slow_mult if self.slow_timer > 0 else 1.0)

    @property
    def velocity(self):
        v = self.effective_speed
        return (self.dir[0] * v, self.dir[1] * v)

    # ----------------------------------------------------------- movement
    def update(self, dt, grid):
        """Follow the flow arrows; returns True on reaching the core."""
        if self.slow_timer > 0:
            self.slow_timer -= dt
            if self.slow_timer <= 0:
                self.slow_mult = 1.0

        waypoint = grid.flow.get(self.cell)
        if waypoint is None:                    # standing on the core cell
            if self.cell == grid.core:
                self.leaked = True
                self.alive = False
                return True
            return False                        # cut off; wait for a route

        tx, ty = waypoint[0] + 0.5, waypoint[1] + 0.5
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        step = self.effective_speed * dt

        if dist > 1e-6:
            self.dir = (dx / dist, dy / dist)

        if step >= dist:                        # arrived at the next cell
            self.x, self.y = tx, ty
            self.cell = waypoint
            if self.cell == grid.core:
                self.leaked = True
                self.alive = False
                return True
        else:
            self.x += self.dir[0] * step
            self.y += self.dir[1] * step

        # steps still to walk: distance of the NEXT cell plus the leg to it
        ahead = grid.flow.get(self.cell)
        if ahead is None:
            self.remaining = 0.0
        else:
            self.remaining = grid.dist.get(ahead, 999) + math.hypot(
                ahead[0] + 0.5 - self.x, ahead[1] + 0.5 - self.y)
        return False
