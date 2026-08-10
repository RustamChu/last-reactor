#!/usr/bin/env python3
"""THE LAST REACTOR - tower defense.

Author: RustamChu
License: MIT
"""
from __future__ import annotations

import sys

import pygame as pg

import renderer as rdr
import savegame
from engine import Engine
from settings import FIELD_W, FPS, RES, TILE, TITLE
from sounds import SoundManager
from towers import BUILD_ORDER, MODES

# hotkeys are matched by SCANCODE (the physical key), so they work the same
# whatever keyboard layout is active - Ш is still F, and З is still P
SC = pg.KSCAN_1, pg.KSCAN_2, pg.KSCAN_3, pg.KSCAN_4
MENU, PLAY, PAUSE, HELP, END = "menu", "play", "pause", "help", "end"


class Game:
    def __init__(self):
        pg.init()
        pg.display.set_caption(TITLE)
        self.screen = pg.display.set_mode(RES)
        self.clock = pg.time.Clock()
        self.sound = SoundManager()
        self.renderer = rdr.Renderer(self.screen)

        self.engine = Engine(sound=self.sound)
        self.state = MENU
        self.help_parent = MENU
        self.difficulty_idx = 1
        self.t = 0.0
        self.running = True
        self.ui = {"hover_cell": None, "build_sel": None, "selected": None,
                   "show_flow": False, "speed": 1}

    # ------------------------------------------------------------ lifecycle
    def new_game(self, seed=None):
        self.engine = Engine(seed=seed, difficulty=self.difficulty_idx,
                             sound=self.sound)
        self.ui.update(build_sel=None, selected=None, speed=1)
        self.state = PLAY

    def continue_game(self):
        if not savegame.has_save():
            return False
        try:
            self.engine = savegame.load(sound=self.sound)
        except (OSError, ValueError, KeyError):
            return False
        self.difficulty_idx = self.engine.diff_index
        self.ui.update(build_sel=None, selected=None, speed=1)
        self.state = PLAY
        return True

    def to_menu(self):
        if self.state in (PLAY, PAUSE) and not self.engine.finished \
                and self.engine.phase == "build":
            savegame.save(self.engine)
        self.state = MENU

    # ---------------------------------------------------------------- input
    def handle_key(self, event):
        sc = event.scancode
        state = self.state

        if state == HELP:
            if sc in (pg.KSCAN_ESCAPE, pg.KSCAN_SLASH, pg.KSCAN_RETURN):
                self.state = self.help_parent
            return

        if state == MENU:
            if sc == pg.KSCAN_1:
                self.difficulty_idx = 0
            elif sc == pg.KSCAN_2:
                self.difficulty_idx = 1
            elif sc == pg.KSCAN_3:
                self.difficulty_idx = 2
            elif sc == pg.KSCAN_N:
                self.new_game()
            elif sc == pg.KSCAN_C:
                self.continue_game()
            elif sc == pg.KSCAN_SLASH:
                self.help_parent = MENU
                self.state = HELP
            elif sc == pg.KSCAN_ESCAPE:
                self.running = False
            return

        if state == END:
            if sc == pg.KSCAN_N:
                self.new_game()
            elif sc == pg.KSCAN_ESCAPE:
                self.state = MENU
            return

        if state == PAUSE:
            if sc in (pg.KSCAN_P, pg.KSCAN_ESCAPE, pg.KSCAN_SPACE):
                self.state = PLAY
            return

        # ---- playing
        if sc in SC:
            self.ui["build_sel"] = BUILD_ORDER[SC.index(sc)]
            self.ui["selected"] = None
        elif sc == pg.KSCAN_SPACE:
            self.engine.start_wave()
        elif sc == pg.KSCAN_T and self.ui["selected"]:
            tower = self.ui["selected"]
            tower.mode = (tower.mode + 1) % len(MODES)
        elif sc == pg.KSCAN_U and self.ui["selected"]:
            self.engine.upgrade_tower(self.ui["selected"])
        elif sc == pg.KSCAN_X and self.ui["selected"]:
            self.engine.sell_tower(self.ui["selected"])
            self.ui["selected"] = None
        elif sc == pg.KSCAN_F:
            self.ui["speed"] = {1: 2, 2: 3, 3: 1}[self.ui["speed"]]
        elif sc == pg.KSCAN_P:
            self.state = PAUSE
        elif sc == pg.KSCAN_V:
            self.ui["show_flow"] = not self.ui["show_flow"]
        elif sc == pg.KSCAN_SLASH:
            self.help_parent = PLAY
            self.state = HELP
        elif sc == pg.KSCAN_ESCAPE:
            if self.ui["build_sel"] or self.ui["selected"]:
                self.ui.update(build_sel=None, selected=None)
            else:
                self.to_menu()

    def handle_mouse(self, event):
        if self.state != PLAY:
            return
        mx, my = event.pos
        if event.button == 3:
            self.ui.update(build_sel=None, selected=None)
            return
        if event.button != 1:
            return

        if mx >= FIELD_W:                       # clicks on the panel
            for i, kind in enumerate(BUILD_ORDER):
                if rdr.shop_card_rect(i).collidepoint(mx, my):
                    self.ui["build_sel"] = kind
                    self.ui["selected"] = None
                    return
            if rdr.start_btn_rect().collidepoint(mx, my):
                self.engine.start_wave()
                return
            selected = self.ui["selected"]
            if selected is not None:
                if rdr.upgrade_btn_rect().collidepoint(mx, my):
                    self.engine.upgrade_tower(selected)
                elif rdr.sell_btn_rect().collidepoint(mx, my):
                    self.engine.sell_tower(selected)
                    self.ui["selected"] = None
            return

        cell = (mx // TILE, my // TILE)         # clicks on the field
        build = self.ui["build_sel"]
        if build:
            self.engine.place_tower(build, cell)
            return
        self.ui["selected"] = self.engine.tower_at(cell)

    def handle_events(self):
        for event in pg.event.get():
            if event.type == pg.QUIT:
                self.running = False
            elif event.type == pg.KEYDOWN:
                self.handle_key(event)
            elif event.type == pg.MOUSEBUTTONDOWN:
                self.handle_mouse(event)
            elif event.type == pg.MOUSEMOTION:
                mx, my = event.pos
                self.ui["hover_cell"] = (mx // TILE, my // TILE) \
                    if mx < FIELD_W else None

    # ----------------------------------------------------------------- loop
    def step(self):
        """One frame; separated so the headless test can drive the game."""
        self.handle_events()
        dt = min(self.clock.tick(FPS) / 1000.0, 0.1)
        self.t += dt

        if self.state == PLAY and not self.engine.finished:
            # fixed sub-steps keep collisions honest at x2/x3 speed
            remaining = dt * self.ui["speed"]
            while remaining > 1e-6:
                step = min(1 / 60, remaining)
                self.engine.update(step)
                remaining -= step
            if self.engine.save_pending:
                savegame.save(self.engine)
                self.engine.save_pending = False
            if self.engine.finished:
                savegame.delete_save()
                self.state = END

        self.draw()

    def draw(self):
        if self.state == MENU:
            self.renderer.draw_menu(self.difficulty_idx, savegame.has_save(),
                                    self.t)
        elif self.state == HELP and self.help_parent == MENU:
            self.renderer.draw_menu(self.difficulty_idx, savegame.has_save(),
                                    self.t)
            self.renderer.draw_help()
        else:
            self.renderer.draw_field(self.engine, self.ui, self.t)
            self.renderer.draw_panel(self.engine, self.ui)
            if self.state == PAUSE:
                self.renderer.draw_pause()
            elif self.state == HELP:
                self.renderer.draw_help()
            elif self.state == END:
                self.renderer.draw_end(self.engine, self.engine.victory)
        pg.display.flip()

    def run(self):
        while self.running:
            self.step()
        pg.quit()
        sys.exit()


if __name__ == "__main__":
    Game().run()
