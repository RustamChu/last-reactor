"""Game state and the whole battle simulation.

The engine knows nothing about pygame: it is money, lives, enemies, towers
and projectiles advanced by update(dt). That keeps it importable from the
headless test and keeps every rule of the game in one file.
"""
from __future__ import annotations

import math
import random

import waves
from enemies import Enemy
from grid import Grid
from settings import (DIFFICULTIES, HP_GROWTH, START_MONEY, WAVES_TOTAL,
                      wave_bonus)
from towers import MODES, TYPES, Tower, intercept_point

BUILD, ATTACK = "build", "attack"


class _NoSound:
    def play(self, name):
        pass


class Engine:
    def __init__(self, seed=None, difficulty=1, sound=None):
        self.seed = seed if seed is not None else random.randrange(1 << 30)
        self.diff_index = difficulty
        self.diff = DIFFICULTIES[difficulty]
        self.sound = sound or _NoSound()

        self.grid = Grid(self.seed)
        self.money = START_MONEY
        self.lives = self.diff["lives"]
        self.wave = 1                       # the wave about to come / running
        self.phase = BUILD
        self.victory = False
        self.defeat = False

        self.enemies = []
        self.towers = []
        self.bullets = []
        self.shells = []
        self.effects = []

        self._queue = []
        self._qi = 0
        self._spawn_timer = 0.0
        self._portal_idx = 0
        self.core_flash = 0.0

        self.stats = {"kills": 0, "earned": 0, "built": 0, "waves": 0,
                      "time": 0.0, "leaks": 0}
        self.save_pending = False           # main writes the file when set

    # ------------------------------------------------------------- helpers
    @property
    def hp_mult(self):
        return (1.0 + HP_GROWTH * (self.wave - 1)) * self.diff["hp"]

    @property
    def finished(self):
        return self.victory or self.defeat

    def enemy_cells(self):
        return {(int(e.x), int(e.y)) for e in self.enemies if e.alive}

    def tower_at(self, cell):
        return self.grid.towers_at.get(cell)

    def fx(self, **kw):
        kw.setdefault("ttl", 0.4)
        kw["max_ttl"] = kw["ttl"]
        self.effects.append(kw)

    # ------------------------------------------------------------ building
    def can_place(self, kind, cell):
        return (self.money >= TYPES[kind]["cost"]
                and self.grid.can_build(cell, self.enemy_cells()))

    def place_tower(self, kind, cell):
        if not self.can_place(kind, cell):
            return None
        tower = Tower(kind, cell)
        self.money -= TYPES[kind]["cost"]
        self.towers.append(tower)
        self.grid.add_tower(cell, tower)
        self.stats["built"] += 1
        self.sound.play("build")
        self.fx(k="ring", x=tower.x, y=tower.y, r0=0.1, r1=0.9,
                color=(120, 230, 140), ttl=0.35)
        return tower

    def sell_tower(self, tower):
        self.money += tower.sell_price
        self.towers.remove(tower)
        self.grid.remove_tower(tower.cell)
        self.sound.play("sell")
        self.fx(k="text", x=tower.x, y=tower.y,
                s="+{}".format(tower.sell_price), color=(240, 200, 90),
                ttl=0.8)

    def upgrade_tower(self, tower):
        if not tower.can_upgrade or self.money < tower.upgrade_cost:
            return False
        self.money -= tower.upgrade_cost
        tower.upgrade()
        self.sound.play("build")
        self.fx(k="ring", x=tower.x, y=tower.y, r0=0.2, r1=0.7,
                color=(150, 150, 255), ttl=0.35)
        return True

    # --------------------------------------------------------------- waves
    def start_wave(self):
        if self.phase != BUILD or self.finished:
            return False
        self._queue = waves.compose(self.wave)
        self._qi = 0
        self._spawn_timer = 0.6
        self.phase = ATTACK
        self.sound.play("horn")
        return True

    def _spawn_next(self):
        gap, kind = self._queue[self._qi]
        self._qi += 1
        spawn = self.grid.spawns[self._portal_idx % len(self.grid.spawns)]
        self._portal_idx += 1
        self.enemies.append(Enemy(kind, spawn, self.hp_mult))
        self._spawn_timer = gap * waves.gap_scale(self.wave)

    def _wave_cleared(self):
        bonus = wave_bonus(self.wave)
        self.money += bonus
        self.stats["earned"] += bonus
        self.stats["waves"] += 1
        self.fx(k="text", x=self.grid.core[0] + 0.5, y=self.grid.core[1] - 0.8,
                s="волна отбита  +{}".format(bonus), color=(120, 230, 140),
                ttl=1.6)
        if self.wave >= WAVES_TOTAL:
            self.victory = True
            self.sound.play("win")
        else:
            self.wave += 1
            self.phase = BUILD
            self.save_pending = True

    # -------------------------------------------------------------- combat
    def damage_enemy(self, enemy, damage, ignore_armor=False):
        if not enemy.alive:
            return
        dealt = max(1, int(round(damage)) - (0 if ignore_armor else enemy.armor))
        enemy.hp -= dealt
        if enemy.hp <= 0:
            enemy.alive = False
            self._on_kill(enemy)

    def _on_kill(self, enemy):
        reward = int(round(enemy.reward * self.diff["reward"]))
        self.money += reward
        self.stats["earned"] += reward
        self.stats["kills"] += 1
        self.fx(k="spark", x=enemy.x, y=enemy.y, color=enemy.color, ttl=0.35)
        if enemy.kind == "boss":
            self.fx(k="boom", x=enemy.x, y=enemy.y, r=1.4, ttl=0.6)
            self.fx(k="text", x=enemy.x, y=enemy.y - 0.6,
                    s="+{}".format(reward), color=(240, 200, 90), ttl=1.2)
            self.sound.play("boom")
        if enemy.kind == "swarm":
            for k in range(3):
                mite = Enemy("mite", enemy.cell, self.hp_mult)
                angle = k * math.tau / 3
                mite.x = enemy.x + 0.22 * math.cos(angle)
                mite.y = enemy.y + 0.22 * math.sin(angle)
                self.enemies.append(mite)

    def _leak(self, enemy):
        self.lives -= enemy.core_damage
        self.stats["leaks"] += 1
        self.core_flash = 0.5
        self.sound.play("leak")
        self.fx(k="text", x=self.grid.core[0] + 0.5,
                y=self.grid.core[1] + 0.5, s="-{}".format(enemy.core_damage),
                color=(235, 90, 110), ttl=1.0)
        if self.lives <= 0:
            self.lives = 0
            self.defeat = True
            self.sound.play("lose")

    # -------------------------------------------------------------- firing
    def _fire(self, tower, target):
        kind = tower.kind
        tower.fired_total += 1
        if kind == "gun":
            ax, ay = intercept_point(tower.x, tower.y, target,
                                     tower.stats["bullet_speed"])
            angle = math.atan2(ay - tower.y, ax - tower.x)
            tower.aim_angle = angle
            speed = tower.stats["bullet_speed"]
            self.bullets.append({
                "x": tower.x, "y": tower.y,
                "vx": math.cos(angle) * speed, "vy": math.sin(angle) * speed,
                "dmg": tower.damage,
                "life": (tower.range + 1.2) / speed,
            })
            self.sound.play("shot")
        elif kind == "cannon":
            ax, ay = intercept_point(tower.x, tower.y, target,
                                     tower.stats["shell_speed"])
            tower.aim_angle = math.atan2(ay - tower.y, ax - tower.x)
            flight = math.hypot(ax - tower.x, ay - tower.y) \
                / tower.stats["shell_speed"]
            self.shells.append({
                "x0": tower.x, "y0": tower.y, "tx": ax, "ty": ay,
                "t": 0.0, "flight": max(0.15, flight),
                "dmg": tower.damage, "splash": tower.splash,
            })
            self.sound.play("shot")
        elif kind == "tesla":
            chain = [target]
            while len(chain) < tower.chains:
                last = chain[-1]
                pool = [e for e in self.enemies
                        if e.alive and e not in chain
                        and math.hypot(e.x - last.x, e.y - last.y)
                        <= tower.stats["chain_range"]]
                if not pool:
                    break
                chain.append(min(pool, key=lambda e: math.hypot(
                    e.x - last.x, e.y - last.y)))
            damage = tower.damage
            points = [(tower.x, tower.y)]
            for enemy in chain:
                points.append((enemy.x, enemy.y))
                self.damage_enemy(enemy, damage, ignore_armor=True)
                damage *= tower.stats["falloff"]
            self.fx(k="beam", pts=points, color=(195, 145, 255), ttl=0.12)
            self.sound.play("zap")

    def _frost_pulse(self, tower):
        hit = False
        for enemy in self.enemies:
            if enemy.alive and tower.in_range(enemy):
                enemy.apply_slow(tower.stats["slow_mult"],
                                 tower.stats["slow_time"])
                self.damage_enemy(enemy, tower.damage)
                hit = True
        if hit:
            self.fx(k="ring", x=tower.x, y=tower.y, r0=0.3, r1=tower.range,
                    color=(120, 200, 255), ttl=0.4)
            self.sound.play("frost")
        return hit

    # -------------------------------------------------------------- update
    def update(self, dt):
        if self.finished:
            return
        self.stats["time"] += dt
        if self.core_flash > 0:
            self.core_flash -= dt

        # spawning
        if self.phase == ATTACK and self._qi < len(self._queue):
            self._spawn_timer -= dt
            while self._spawn_timer <= 0 and self._qi < len(self._queue):
                self._spawn_next()

        # enemies
        for enemy in self.enemies:
            if enemy.alive and enemy.update(dt, self.grid):
                self._leak(enemy)
                if self.defeat:
                    return
        self.enemies = [e for e in self.enemies if e.alive]

        # towers
        for tower in self.towers:
            tower.cooldown -= dt
            if tower.cooldown > 0:
                continue
            if tower.kind == "frost":
                if self._frost_pulse(tower):
                    tower.cooldown = 1.0 / tower.rate
                else:
                    tower.cooldown = 0.08       # idle re-check, not a shot
                continue
            target = tower.acquire(self.enemies)
            if target is None:
                tower.cooldown = 0.05
                continue
            self._fire(tower, target)
            tower.cooldown = 1.0 / tower.rate

        # bullets: straight flight, hit the first enemy they touch
        for bullet in self.bullets:
            bullet["x"] += bullet["vx"] * dt
            bullet["y"] += bullet["vy"] * dt
            bullet["life"] -= dt
            for enemy in self.enemies:
                if not enemy.alive:
                    continue
                if math.hypot(enemy.x - bullet["x"],
                              enemy.y - bullet["y"]) <= enemy.radius + 0.12:
                    self.damage_enemy(enemy, bullet["dmg"])
                    bullet["life"] = 0
                    break
        self.bullets = [b for b in self.bullets if b["life"] > 0]

        # shells: fly to the predicted point, then splash
        for shell in self.shells:
            shell["t"] += dt / shell["flight"]
            if shell["t"] >= 1.0:
                self._explode(shell)
        self.shells = [s for s in self.shells if s["t"] < 1.0]

        # effects fade out
        for effect in self.effects:
            effect["ttl"] -= dt
        self.effects = [e for e in self.effects if e["ttl"] > 0]

        # end of wave
        if (self.phase == ATTACK and self._qi >= len(self._queue)
                and not self.enemies):
            self._wave_cleared()

    def _explode(self, shell):
        self.fx(k="boom", x=shell["tx"], y=shell["ty"], r=shell["splash"],
                ttl=0.35)
        self.sound.play("boom")
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            dist = math.hypot(enemy.x - shell["tx"], enemy.y - shell["ty"])
            if dist <= shell["splash"]:
                falloff = 1.0 - 0.5 * dist / shell["splash"]
                self.damage_enemy(enemy, shell["dmg"] * falloff)
