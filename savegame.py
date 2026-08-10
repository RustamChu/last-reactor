"""JSON save between waves.

Only the build phase is saved - mid-wave state would need every enemy and
projectile serialised for no real benefit. Because the map is rebuilt from
its seed and the wave composition is a pure function of the wave number,
the file stays tiny: seed, money, lives, wave and the tower list.
"""
from __future__ import annotations

import json
import os

from engine import Engine
from towers import Tower

SAVE_VERSION = 1
SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "savegame.json")


def has_save(path=SAVE_PATH):
    return os.path.isfile(path)


def delete_save(path=SAVE_PATH):
    try:
        os.remove(path)
    except OSError:
        pass


def save(engine, path=SAVE_PATH):
    data = {
        "version": SAVE_VERSION,
        "seed": engine.seed,
        "difficulty": engine.diff_index,
        "money": engine.money,
        "lives": engine.lives,
        "wave": engine.wave,
        "stats": engine.stats,
        "towers": [{"kind": t.kind, "cx": t.cell[0], "cy": t.cell[1],
                    "level": t.level, "mode": t.mode, "invested": t.invested}
                   for t in engine.towers],
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=1)
    return path


def load(path=SAVE_PATH, sound=None):
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if data.get("version") != SAVE_VERSION:
        raise ValueError("сохранение от другой версии игры")

    engine = Engine(seed=data["seed"], difficulty=data["difficulty"],
                    sound=sound)
    engine.money = data["money"]
    engine.lives = data["lives"]
    engine.wave = data["wave"]
    engine.stats = data["stats"]
    for entry in data["towers"]:
        tower = Tower(entry["kind"], (entry["cx"], entry["cy"]))
        tower.level = entry["level"]
        tower.mode = entry["mode"]
        tower.invested = entry["invested"]
        engine.towers.append(tower)
        engine.grid.add_tower(tower.cell, tower)
    return engine
