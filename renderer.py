"""Everything that puts pixels on the screen."""
from __future__ import annotations

import math
import random

import pygame as pg

import graphics
import waves
from enemies import TYPES as ENEMY_TYPES
from settings import (C_BAD, C_CORE, C_CORE_GLOW, C_DIM, C_GOOD, C_LIVES,
                      C_MONEY, C_PANEL, C_PANEL_EDGE, C_PORTAL, C_TEXT, C_WARN,
                      DIFFICULTIES, HEIGHT, PANEL_W, PANEL_X, TILE, TITLE,
                      WAVES_TOTAL, WIDTH)
from towers import BUILD_ORDER, MODES, TYPES as TOWER_TYPES

SHOP_Y = 150
CARD_H = 62
CARD_GAP = 6
INFO_Y = SHOP_Y + 4 * (CARD_H + CARD_GAP) + 8


def shop_card_rect(i):
    return pg.Rect(PANEL_X + 10, SHOP_Y + i * (CARD_H + CARD_GAP),
                   PANEL_W - 20, CARD_H)


def start_btn_rect():
    return pg.Rect(PANEL_X + 10, 104, PANEL_W - 20, 36)


def upgrade_btn_rect():
    return pg.Rect(PANEL_X + 12, INFO_Y + 112, 122, 30)


def sell_btn_rect():
    return pg.Rect(PANEL_X + 144, INFO_Y + 112, 122, 30)


class Renderer:
    def __init__(self, screen):
        self.screen = screen
        self.font_big = pg.font.Font(None, 84)
        self.font_mid = pg.font.Font(None, 34)
        self.font_ui = pg.font.Font(None, 26)
        self.font_small = pg.font.Font(None, 21)
        self.tower_sprites = graphics.make_tower_sprites()
        self.shop_icons = graphics.make_shop_icons()
        self.background = None
        self._bg_seed = None

    # ------------------------------------------------------------- helpers
    def _text(self, font, text, color, pos, center=False, shadow=True):
        if shadow:
            dark = font.render(text, True, (5, 6, 10))
            rect = dark.get_rect()
            if center:
                rect.center = (pos[0] + 2, pos[1] + 2)
            else:
                rect.topleft = (pos[0] + 2, pos[1] + 2)
            self.screen.blit(dark, rect)
        image = font.render(text, True, color)
        rect = image.get_rect()
        if center:
            rect.center = pos
        else:
            rect.topleft = pos
        self.screen.blit(image, rect)
        return rect

    @staticmethod
    def to_px(x, y):
        return int(x * TILE), int(y * TILE)

    def _ensure_background(self, grid):
        if self._bg_seed != grid.seed:
            self.background = graphics.make_background(grid)
            self._bg_seed = grid.seed

    # ================================================================ field
    def draw_field(self, engine, ui, t):
        grid = engine.grid
        self._ensure_background(grid)
        self.screen.blit(self.background, (0, 0))

        self._draw_portals(grid, t)
        if ui.get("show_flow"):
            self._draw_flow(grid)
        self._draw_core(engine, t)
        for tower in engine.towers:
            self._draw_tower(tower)
        for enemy in engine.enemies:
            self._draw_enemy(enemy, t)
        self._draw_projectiles(engine)
        self._draw_effects(engine)
        self._draw_placement(engine, ui)

    def _draw_portals(self, grid, t):
        for i, (cx, cy) in enumerate(grid.spawns):
            px, py = cx * TILE + TILE // 2, cy * TILE + TILE // 2
            for k in range(3):
                angle = t * 2.2 + i * 1.7 + k * math.tau / 3
                radius = 8 + 4 * math.sin(t * 3 + k)
                pg.draw.circle(self.screen, C_PORTAL,
                               (px + radius * math.cos(angle),
                                py + radius * math.sin(angle)), 3)
            pg.draw.circle(self.screen, (255, 170, 150), (px, py), 4)

    def _draw_flow(self, grid):
        for cell, nxt in grid.flow.items():
            if nxt is None:
                continue
            x1 = cell[0] * TILE + TILE // 2
            y1 = cell[1] * TILE + TILE // 2
            x2 = x1 + (nxt[0] - cell[0]) * TILE * 0.32
            y2 = y1 + (nxt[1] - cell[1]) * TILE * 0.32
            pg.draw.line(self.screen, (70, 90, 120), (x1, y1), (x2, y2), 2)
            pg.draw.circle(self.screen, (90, 120, 160), (int(x2), int(y2)), 2)

    def _draw_core(self, engine, t):
        cx, cy = engine.grid.core
        px, py = cx * TILE + TILE // 2, cy * TILE + TILE // 2
        pulse = 1.0 + 0.10 * math.sin(t * 4)
        for radius, color in ((17, C_CORE_GLOW), (12, C_CORE)):
            pg.draw.circle(self.screen, color, (px, py), int(radius * pulse))
        for k in range(4):
            angle = t * 1.6 + k * math.tau / 4
            pg.draw.circle(self.screen, (200, 245, 255),
                           (px + 14 * pulse * math.cos(angle),
                            py + 14 * pulse * math.sin(angle)), 2)
        if engine.core_flash > 0:
            alpha = int(160 * engine.core_flash / 0.5)
            veil = pg.Surface((TILE * 3, TILE * 3), pg.SRCALPHA)
            pg.draw.circle(veil, (255, 80, 90, alpha),
                           (TILE * 3 // 2, TILE * 3 // 2), TILE * 3 // 2)
            self.screen.blit(veil, (px - TILE * 3 // 2, py - TILE * 3 // 2))

    def _draw_tower(self, tower):
        parts = self.tower_sprites[tower.kind]
        px, py = self.to_px(tower.x, tower.y)
        base = parts["base"]
        self.screen.blit(base, base.get_rect(center=(px, py)))
        turret = parts["turret"]
        if parts["rotates"]:
            turret = pg.transform.rotate(
                turret, -math.degrees(tower.aim_angle))
        self.screen.blit(turret, turret.get_rect(center=(px, py)))
        for k in range(tower.level - 1):        # level pips
            pg.draw.rect(self.screen, C_MONEY,
                         (px - 14 + k * 8, py + 13, 6, 4), border_radius=1)

    def _draw_enemy(self, enemy, t):
        px, py = self.to_px(enemy.x, enemy.y)
        radius = int(enemy.radius * TILE)
        color = enemy.color
        wobble = math.sin(t * 9 + enemy.uid)

        if enemy.slow_timer > 0:                # frost tint halo
            pg.draw.circle(self.screen, (120, 200, 255), (px, py), radius + 3, 1)

        if enemy.kind == "runner":
            dx, dy = enemy.dir
            tip = (px + dx * radius * 1.6, py + dy * radius * 1.6)
            left = (px - dy * radius, py + dx * radius)
            right = (px + dy * radius, py - dx * radius)
            pg.draw.polygon(self.screen, color, (tip, left, right))
        elif enemy.kind == "tank":
            points = [(px + radius * math.cos(k * math.tau / 6 + math.pi / 6),
                       py + radius * math.sin(k * math.tau / 6 + math.pi / 6))
                      for k in range(6)]
            pg.draw.polygon(self.screen, color, points)
            pg.draw.polygon(self.screen, (240, 210, 170), points, 2)
        elif enemy.kind == "boss":
            spin = t * 1.5
            points = []
            for k in range(10):
                r = radius * (1.25 if k % 2 == 0 else 0.85)
                angle = spin + k * math.tau / 10
                points.append((px + r * math.cos(angle),
                               py + r * math.sin(angle)))
            pg.draw.polygon(self.screen, color, points)
            pg.draw.circle(self.screen, (255, 220, 230), (px, py),
                           int(radius * 0.45))
        elif enemy.kind == "swarm":
            for k in range(3):
                angle = t * 4 + k * math.tau / 3
                pg.draw.circle(self.screen, color,
                               (px + 5 * math.cos(angle),
                                py + 5 * math.sin(angle)),
                               max(3, radius - 6))
        else:                                   # bug, mite
            squash = 1.0 + 0.12 * wobble
            rect = pg.Rect(0, 0, int(radius * 2 * squash),
                           int(radius * 2 / squash))
            rect.center = (px, py)
            pg.draw.ellipse(self.screen, color, rect)
            pg.draw.ellipse(self.screen, tuple(min(255, c + 45) for c in color),
                            rect, 1)

        if enemy.hp < enemy.max_hp:             # hp bar
            w = max(14, radius * 2)
            frac = enemy.hp / enemy.max_hp
            bar = pg.Rect(px - w // 2, py - radius - 7, w, 3)
            pg.draw.rect(self.screen, (40, 20, 24), bar)
            pg.draw.rect(self.screen, C_GOOD if frac > 0.4 else C_BAD,
                         (bar.x, bar.y, int(w * frac), 3))

    def _draw_projectiles(self, engine):
        for bullet in engine.bullets:
            px, py = self.to_px(bullet["x"], bullet["y"])
            pg.draw.circle(self.screen, (255, 240, 190), (px, py), 3)
            pg.draw.circle(self.screen, (200, 160, 80), (px, py), 5, 1)
        for shell in engine.shells:
            tt = shell["t"]
            x = shell["x0"] + (shell["tx"] - shell["x0"]) * tt
            y = shell["y0"] + (shell["ty"] - shell["y0"]) * tt
            arc = 4.0 * tt * (1.0 - tt)
            px, py = self.to_px(x, y)
            pg.draw.circle(self.screen, (20, 22, 30), (px, py), 3)  # shadow
            py -= int(arc * TILE * 0.7)
            pg.draw.circle(self.screen, (255, 190, 120), (px, py), 5)
            pg.draw.circle(self.screen, (150, 90, 40), (px, py), 5, 1)

    def _draw_effects(self, engine):
        rnd = random.Random(int(engine.stats["time"] * 60))
        for effect in engine.effects:
            frac = 1.0 - effect["ttl"] / effect["max_ttl"]
            alpha = int(255 * (1.0 - frac))
            kind = effect["k"]
            if kind == "ring":
                radius = effect["r0"] + (effect["r1"] - effect["r0"]) * frac
                px, py = self.to_px(effect["x"], effect["y"])
                pg.draw.circle(self.screen, effect["color"], (px, py),
                               int(radius * TILE), 2)
            elif kind == "boom":
                px, py = self.to_px(effect["x"], effect["y"])
                radius = int(effect["r"] * TILE * (0.4 + 0.6 * frac))
                veil = pg.Surface((radius * 2 + 4, radius * 2 + 4), pg.SRCALPHA)
                pg.draw.circle(veil, (255, 160, 70, alpha),
                               (radius + 2, radius + 2), radius)
                pg.draw.circle(veil, (255, 230, 150, alpha),
                               (radius + 2, radius + 2), int(radius * 0.55))
                self.screen.blit(veil, (px - radius - 2, py - radius - 2))
            elif kind == "spark":
                px, py = self.to_px(effect["x"], effect["y"])
                for k in range(6):
                    angle = k * math.tau / 6 + frac * 2
                    dist = 4 + frac * 14
                    pg.draw.circle(self.screen, effect["color"],
                                   (px + dist * math.cos(angle),
                                    py + dist * math.sin(angle)), 2)
            elif kind == "beam":
                points = []
                pts = effect["pts"]
                for i in range(len(pts) - 1):
                    x1, y1 = self.to_px(*pts[i])
                    x2, y2 = self.to_px(*pts[i + 1])
                    points.append((x1, y1))
                    midx, midy = (x1 + x2) / 2, (y1 + y2) / 2
                    points.append((midx + rnd.randint(-6, 6),
                                   midy + rnd.randint(-6, 6)))
                points.append(self.to_px(*pts[-1]))
                if len(points) >= 2:
                    pg.draw.lines(self.screen, (240, 225, 255), False,
                                  points, 3)
                    pg.draw.lines(self.screen, effect["color"], False,
                                  points, 1)
            elif kind == "text":
                px, py = self.to_px(effect["x"], effect["y"])
                image = self.font_ui.render(effect["s"], True, effect["color"])
                image.set_alpha(alpha)
                self.screen.blit(image, image.get_rect(
                    center=(px, py - int(frac * 22))))

    def _draw_placement(self, engine, ui):
        hover = ui.get("hover_cell")
        selected = ui.get("selected")
        build = ui.get("build_sel")

        if selected is not None:
            px, py = self.to_px(selected.x, selected.y)
            pg.draw.circle(self.screen, (120, 190, 255), (px, py),
                           int(selected.range * TILE), 1)
            rect = pg.Rect(selected.cell[0] * TILE, selected.cell[1] * TILE,
                           TILE, TILE)
            pg.draw.rect(self.screen, (120, 190, 255), rect, 2, border_radius=4)

        if build and hover and hover[0] < engine.grid.cols:
            ok = engine.can_place(build, hover)
            color = C_GOOD if ok else C_BAD
            px = hover[0] * TILE + TILE // 2
            py = hover[1] * TILE + TILE // 2
            pg.draw.circle(self.screen, color, (px, py),
                           int(TOWER_TYPES[build]["range"] * TILE), 1)
            rect = pg.Rect(hover[0] * TILE + 3, hover[1] * TILE + 3,
                           TILE - 6, TILE - 6)
            pg.draw.rect(self.screen, color, rect, 2, border_radius=6)
            icon = self.shop_icons[build].copy()
            icon.set_alpha(170)
            self.screen.blit(icon, icon.get_rect(center=(px, py)))
        elif hover and hover[0] < engine.grid.cols:
            rect = pg.Rect(hover[0] * TILE, hover[1] * TILE, TILE, TILE)
            pg.draw.rect(self.screen, (90, 100, 125), rect, 1)

    # ================================================================ panel
    def draw_panel(self, engine, ui):
        pg.draw.rect(self.screen, C_PANEL, (PANEL_X, 0, PANEL_W, HEIGHT))
        pg.draw.line(self.screen, C_PANEL_EDGE, (PANEL_X, 0),
                     (PANEL_X, HEIGHT), 2)
        x = PANEL_X + 14

        self._text(self.font_mid, "{} кр.".format(engine.money), C_MONEY,
                   (x, 14))
        self._text(self.font_mid, "жизни: {}".format(engine.lives), C_LIVES,
                   (x, 46))
        self._text(self.font_ui, "волна {} / {}   [{}]".format(
            engine.wave, WAVES_TOTAL, engine.diff["name"]), C_TEXT, (x, 78))

        button = start_btn_rect()
        if engine.phase == "build":
            pg.draw.rect(self.screen, (34, 52, 40), button, border_radius=6)
            pg.draw.rect(self.screen, C_GOOD, button, 2, border_radius=6)
            self._text(self.font_ui, "SPACE — выпустить волну", C_GOOD,
                       button.center, center=True, shadow=False)
        else:
            pg.draw.rect(self.screen, (48, 36, 30), button, border_radius=6)
            pg.draw.rect(self.screen, C_WARN, button, 2, border_radius=6)
            left = len(engine._queue) - engine._qi + len(engine.enemies)
            self._text(self.font_ui, "идёт волна — осталось {}".format(left),
                       C_WARN, button.center, center=True, shadow=False)

        self._draw_shop(engine, ui)

        selected = ui.get("selected")
        if selected is not None:
            self._draw_tower_info(engine, selected)
        else:
            self._draw_wave_preview(engine)

        speed = ui.get("speed", 1)
        self._text(self.font_small,
                   "F скорость ×{}    P пауза    V пути".format(speed),
                   C_DIM, (x, HEIGHT - 48))
        self._text(self.font_small, "?  помощь        ESC  в меню",
                   C_DIM, (x, HEIGHT - 26))

    def _draw_shop(self, engine, ui):
        build = ui.get("build_sel")
        for i, kind in enumerate(BUILD_ORDER):
            stats = TOWER_TYPES[kind]
            rect = shop_card_rect(i)
            selected = build == kind
            affordable = engine.money >= stats["cost"]
            back = (30, 36, 50) if selected else (22, 25, 36)
            pg.draw.rect(self.screen, back, rect, border_radius=8)
            edge = graphics.ACCENTS[kind] if selected else C_PANEL_EDGE
            pg.draw.rect(self.screen, edge, rect, 2, border_radius=8)
            self.screen.blit(self.shop_icons[kind], (rect.x + 8, rect.y + 11))
            name_color = C_TEXT if affordable else C_DIM
            self._text(self.font_ui, "{}  [{}]".format(stats["name"], i + 1),
                       name_color, (rect.x + 56, rect.y + 8), shadow=False)
            self._text(self.font_small, stats["desc"], C_DIM,
                       (rect.x + 56, rect.y + 30), shadow=False)
            cost_color = C_MONEY if affordable else C_BAD
            self._text(self.font_ui, str(stats["cost"]), cost_color,
                       (rect.right - 46, rect.y + 8), shadow=False)

    def _draw_tower_info(self, engine, tower):
        rect = pg.Rect(PANEL_X + 10, INFO_Y, PANEL_W - 20, 150)
        pg.draw.rect(self.screen, (22, 25, 36), rect, border_radius=8)
        pg.draw.rect(self.screen, graphics.ACCENTS[tower.kind], rect, 2,
                     border_radius=8)
        x = rect.x + 12
        self._text(self.font_ui, "{}  ур. {}".format(tower.name, tower.level),
                   C_TEXT, (x, rect.y + 8), shadow=False)
        self._text(self.font_small,
                   "урон {:.0f}   темп {:.2f}/с   радиус {:.1f}".format(
                       tower.damage, tower.rate, tower.range),
                   C_DIM, (x, rect.y + 34), shadow=False)
        self._text(self.font_small,
                   "цель: {}   [T — сменить]".format(MODES[tower.mode]),
                   C_TEXT, (x, rect.y + 56), shadow=False)
        self._text(self.font_small,
                   "выстрелов: {}   вложено: {}".format(
                       tower.fired_total, tower.invested),
                   C_DIM, (x, rect.y + 78), shadow=False)

        up = upgrade_btn_rect()
        if tower.can_upgrade:
            can_pay = engine.money >= tower.upgrade_cost
            pg.draw.rect(self.screen, (30, 44, 36), up, border_radius=6)
            pg.draw.rect(self.screen, C_GOOD if can_pay else C_DIM, up, 2,
                         border_radius=6)
            self._text(self.font_small,
                       "U улучшить {}".format(tower.upgrade_cost),
                       C_GOOD if can_pay else C_DIM, up.center, center=True,
                       shadow=False)
        else:
            pg.draw.rect(self.screen, (26, 29, 40), up, border_radius=6)
            self._text(self.font_small, "макс. уровень", C_DIM, up.center,
                       center=True, shadow=False)

        sell = sell_btn_rect()
        pg.draw.rect(self.screen, (48, 32, 30), sell, border_radius=6)
        pg.draw.rect(self.screen, C_WARN, sell, 2, border_radius=6)
        self._text(self.font_small, "X продать {}".format(tower.sell_price),
                   C_WARN, sell.center, center=True, shadow=False)

    def _draw_wave_preview(self, engine):
        rect = pg.Rect(PANEL_X + 10, INFO_Y, PANEL_W - 20, 150)
        pg.draw.rect(self.screen, (22, 25, 36), rect, border_radius=8)
        pg.draw.rect(self.screen, C_PANEL_EDGE, rect, 2, border_radius=8)
        x = rect.x + 12
        wave = engine.wave
        title = "СЛЕДУЮЩАЯ ВОЛНА" if engine.phase == "build" else "В ЭТОЙ ВОЛНЕ"
        self._text(self.font_ui, title, C_TEXT, (x, rect.y + 8), shadow=False)
        y = rect.y + 38
        for kind, amount in waves.preview(wave).most_common():
            stats = ENEMY_TYPES[kind]
            pg.draw.circle(self.screen, stats["color"], (x + 7, y + 8), 6)
            self._text(self.font_small,
                       "{} × {}".format(stats["name"], amount), C_TEXT,
                       (x + 22, y), shadow=False)
            hint = "броня {}".format(stats["armor"]) if stats["armor"] else ""
            if kind == "boss":
                hint = "босс!"
            self._text(self.font_small, hint, C_DIM, (x + 150, y),
                       shadow=False)
            y += 21
            if y > rect.bottom - 20:
                break

    # ============================================================== overlays
    def dim(self, alpha=190):
        veil = pg.Surface((WIDTH, HEIGHT), pg.SRCALPHA)
        veil.fill((5, 6, 12, alpha))
        self.screen.blit(veil, (0, 0))

    def draw_menu(self, difficulty_idx, save_exists, t):
        self.screen.fill((8, 9, 14))
        cx = WIDTH // 2
        pulse = 1.0 + 0.06 * math.sin(t * 2.5)
        for radius, color in ((150, (16, 40, 52)), (110, (20, 60, 76)),
                              (70, (28, 90, 110))):
            pg.draw.circle(self.screen, color, (cx, 150), int(radius * pulse))
        pg.draw.circle(self.screen, C_CORE, (cx, 150), int(34 * pulse))
        self._text(self.font_big, TITLE, C_TEXT, (cx, 270), center=True)
        self._text(self.font_ui,
                   "tower defense: враги обходят ваши башни, стройте лабиринт",
                   C_DIM, (cx, 322), center=True)

        y = 390
        for i, diff in enumerate(DIFFICULTIES):
            selected = i == difficulty_idx
            label = "[{}] {}".format(i + 1, diff["name"])
            if selected:
                label = "> " + label + " <"
            self._text(self.font_mid, label,
                       C_WARN if selected else C_DIM, (cx, y), center=True)
            y += 40

        y += 16
        self._text(self.font_mid, "[n]  новая оборона", C_TEXT, (cx, y),
                   center=True)
        y += 40
        cont_color = C_TEXT if save_exists else (70, 74, 86)
        suffix = "" if save_exists else "  (сохранения нет)"
        self._text(self.font_mid, "[c]  продолжить" + suffix, cont_color,
                   (cx, y), center=True)
        y += 40
        self._text(self.font_mid, "[?]  как играть      [esc] выход", C_DIM,
                   (cx, y), center=True)

    def draw_help(self):
        self.dim()
        rect = pg.Rect(0, 0, 760, 560)
        rect.center = (WIDTH // 2, HEIGHT // 2)
        pg.draw.rect(self.screen, (14, 16, 24), rect, border_radius=10)
        pg.draw.rect(self.screen, C_PANEL_EDGE, rect, 2, border_radius=10)
        self._text(self.font_mid, "КАК ИГРАТЬ", C_WARN,
                   (rect.centerx, rect.y + 28), center=True)

        rows = [
            ("1 2 3 4", "выбрать башню, клик — поставить"),
            ("ПКМ / esc", "отменить выбор"),
            ("клик по башне", "выбрать; U — улучшить, X — продать"),
            ("T", "режим цели: первый / последний / крепкий / ближний"),
            ("SPACE", "выпустить следующую волну"),
            ("F", "скорость игры ×1 ×2 ×3"),
            ("P", "пауза"),
            ("V", "показать, как враги пойдут"),
            ("esc", "в меню (партия сохранится)"),
        ]
        y = rect.y + 70
        for key, what in rows:
            self._text(self.font_ui, key, C_MONEY, (rect.x + 46, y))
            self._text(self.font_ui, what, C_TEXT, (rect.x + 220, y))
            y += 34

        tips = [
            "Башни — это стены: враги не идут сквозь них, а обходят.",
            "Стройте длинный коридор, но полностью путь не перекрыть —",
            "игра не даст. Криоизлучатель в изгибе коридора творит чудеса.",
        ]
        y += 8
        for line in tips:
            self._text(self.font_small, line, C_DIM, (rect.x + 46, y))
            y += 24

    def draw_pause(self):
        self.dim(150)
        self._text(self.font_big, "ПАУЗА", C_TEXT,
                   (WIDTH // 2, HEIGHT // 2 - 20), center=True)
        self._text(self.font_ui, "P — продолжить", C_DIM,
                   (WIDTH // 2, HEIGHT // 2 + 40), center=True)

    def draw_end(self, engine, victory):
        self.dim(205)
        cx = WIDTH // 2
        title = "РЕАКТОР УСТОЯЛ" if victory else "РЕАКТОР ПОТЕРЯН"
        self._text(self.font_big, title, C_GOOD if victory else C_BAD,
                   (cx, HEIGHT // 2 - 130), center=True)
        stats = engine.stats
        rows = [
            "волн отбито: {} из {}".format(stats["waves"], WAVES_TOTAL),
            "врагов уничтожено: {}".format(stats["kills"]),
            "пропущено к ядру: {}".format(stats["leaks"]),
            "заработано: {} кр.".format(stats["earned"]),
            "башен построено: {}".format(stats["built"]),
            "время: {:.0f} с".format(stats["time"]),
        ]
        y = HEIGHT // 2 - 55
        for line in rows:
            self._text(self.font_ui, line, C_TEXT, (cx, y), center=True)
            y += 30
        self._text(self.font_mid, "[n] ещё раз      [esc] меню", C_WARN,
                   (cx, y + 24), center=True)
