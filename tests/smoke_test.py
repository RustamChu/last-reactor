"""Headless test run.

Boots the game with the dummy SDL drivers and drives every system: the flow
field and its guarantees, the no-blocking build rule, target prediction,
every tower type, armor, slows, splitters, the economy, targeting modes,
waves, save/load, victory and defeat - then renders every screen and writes
the screenshot used in the readme.

    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python tests/smoke_test.py
"""
import math
import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pygame as pg  # noqa: E402

import savegame  # noqa: E402
import waves  # noqa: E402
from enemies import Enemy  # noqa: E402
from engine import ATTACK, BUILD, Engine  # noqa: E402
from grid import Grid  # noqa: E402
from main import Game  # noqa: E402
from settings import DIFFICULTIES, START_MONEY, WAVES_TOTAL  # noqa: E402
from towers import MODES, TYPES, intercept_point  # noqa: E402

CHECKS = []
SHOT_SEED = 7


def check(label, condition):
    CHECKS.append(label)
    if not condition:
        raise AssertionError(label)


def run(engine, seconds, dt=1 / 30):
    steps = int(seconds / dt)
    for _ in range(steps):
        engine.update(dt)
        if engine.finished:
            break


def wave_over(engine):
    return engine.phase == BUILD or engine.finished


# --------------------------------------------------------------------------- 1
def test_grid_and_flow():
    for seed in range(30):
        grid = Grid(seed)
        for spawn in grid.spawns:
            check("seed {}: spawn reaches the core".format(seed),
                  spawn in grid.dist)
        monotonic = all(grid.dist[nxt] == grid.dist[cell] - 1
                        for cell, nxt in grid.flow.items() if nxt is not None)
        check("seed {}: every flow arrow steps closer to the core".format(seed),
              monotonic)

    # the no-sealing rule: walling off the last corridor must be refused
    grid = Grid(3)
    column = grid.spawns[0][0] + 2
    placed = []
    refused = False
    for y in range(grid.rows):
        cell = (column, y)
        if grid.can_build(cell):
            grid.add_tower(cell, object())
            placed.append(cell)
        elif grid.buildable(cell):
            refused = True
    check("some towers fit in the column", len(placed) >= grid.rows - 6)
    check("the final blocking cell is refused", refused)
    for spawn in grid.spawns:
        check("spawns still reach the core after the wall", spawn in grid.dist)

    # enemies must not be walled off either
    grid2 = Grid(5)
    enemy_cell = (grid2.spawns[0][0] + 1, grid2.spawns[0][1])
    ok_without = grid2.can_build(enemy_cell)
    ok_with = grid2.can_build(enemy_cell, {enemy_cell})
    check("a cell under an enemy is refused", ok_without and not ok_with)


# --------------------------------------------------------------------------- 2
def test_movement_and_leak():
    engine = Engine(seed=SHOT_SEED, difficulty=1)
    lives = engine.lives
    enemy = Enemy("bug", engine.grid.spawns[0])
    engine.enemies.append(enemy)
    run(engine, 60)
    check("an unopposed enemy reaches the core", not engine.enemies)
    check("a leak costs a life", engine.lives == lives - 1)
    check("leaks are counted", engine.stats["leaks"] == 1)

    # remaining must shrink as the enemy walks
    engine2 = Engine(seed=SHOT_SEED)
    walker = Enemy("bug", engine2.grid.spawns[0])
    engine2.enemies.append(walker)
    engine2.update(1 / 30)
    first = walker.remaining
    run(engine2, 2)
    check("distance-to-core falls while walking", walker.remaining < first)


# --------------------------------------------------------------------------- 3
def test_intercept():
    class Dummy:
        x, y = 10.0, 5.0
        velocity = (0.0, 2.0)
    ax, ay = intercept_point(0.0, 5.0, Dummy, 10.0)
    # bullet flies 10/s over ~10 tiles => ~1s; enemy moves 2 down in that time
    check("intercept leads the target", ay > 5.4)
    flight = math.hypot(ax, ay - 5.0) / 10.0
    check("intercept point is consistent",
          abs((5.0 + 2.0 * flight) - ay) < 0.05)

    # and a live gun actually hits a sprinting runner: park it right next to
    # the spawn, so the runner is in range whatever route the flow picks
    engine = Engine(seed=SHOT_SEED)
    engine.money = 10 ** 6
    sx, sy = engine.grid.spawns[0]
    tower = None
    for cell in [(sx + 1, sy + 1), (sx + 1, sy - 1), (sx + 2, sy),
                 (sx + 1, sy + 2), (sx + 2, sy + 1)]:
        if engine.can_place("gun", cell):
            tower = engine.place_tower("gun", cell)
            break
    check("gun placed for the hit test", tower is not None)
    runner = Enemy("runner", engine.grid.spawns[0])
    engine.enemies.append(runner)
    run(engine, 4)
    check("the gun hits a fast mover", (not runner.alive)
          or runner.hp < runner.max_hp)


# --------------------------------------------------------------------------- 4
def test_tower_mechanics():
    engine = Engine(seed=SHOT_SEED)
    engine.money = 10 ** 6
    anchor = (10, 8)

    # cannon splash hits a pack
    check("cannon placed", engine.place_tower("cannon", anchor))
    pack = []
    for k in range(3):
        enemy = Enemy("bug", (12, 8))
        enemy.x, enemy.y = 12.5 + 0.3 * k, 8.5
        enemy.speed = 0.0                      # hold still for the shell
        pack.append(enemy)
        engine.enemies.append(enemy)
    run(engine, 4)
    hurt = sum(1 for e in pack if not e.alive or e.hp < e.max_hp)
    check("splash damages several enemies at once", hurt >= 2)
    engine.sell_tower(engine.towers[0])

    # tesla chains through several targets, ignoring armor
    check("tesla placed", engine.place_tower("tesla", anchor))
    chained = []
    for k in range(3):
        enemy = Enemy("tank", (12, 8))
        enemy.x, enemy.y = 12.5 + 0.5 * k, 8.5
        enemy.speed = 0.0
        chained.append(enemy)
        engine.enemies.append(enemy)
    run(engine, 1.5)
    check("the lightning chains to at least 3 targets",
          sum(1 for e in chained if e.hp < e.max_hp) >= 3)
    check("chain damage falls off with each hop",
          chained[0].max_hp - chained[0].hp
          > chained[2].max_hp - chained[2].hp)
    engine.sell_tower(engine.towers[0])
    engine.enemies.clear()

    # frost slows and armor soaks
    check("frost placed", engine.place_tower("frost", anchor))
    tank = Enemy("tank", (11, 8))
    tank.x, tank.y = 11.5, 8.5
    engine.enemies.append(tank)
    engine.update(1 / 30)
    run(engine, 1.2)
    check("frost applies a slow", tank.slow_timer > 0
          and tank.effective_speed < tank.speed)
    check("armor keeps chip damage at 1 per pulse",
          0 < tank.max_hp - tank.hp <= 4)
    engine.enemies.clear()
    engine.sell_tower(engine.towers[0])

    # swarm splits into mites on death
    engine.enemies.append(Enemy("swarm", (5, 5)))
    swarm = engine.enemies[0]
    engine.damage_enemy(swarm, 10 ** 4)
    mites = [e for e in engine.enemies if e.kind == "mite"]
    check("a swarm bursts into three mites", len(mites) == 3)


# --------------------------------------------------------------------------- 5
def test_targeting_modes():
    engine = Engine(seed=SHOT_SEED)
    engine.money = 10 ** 6
    cell = (10, 8)
    check("gun placed for targeting test", engine.place_tower("gun", cell))
    tower = engine.towers[0]

    near = Enemy("bug", (11, 8)); near.x, near.y = 11.5, 8.5
    far = Enemy("bug", (8, 8)); far.x, far.y = 8.6, 8.5
    tough = Enemy("tank", (10, 10)); tough.x, tough.y = 10.5, 10.4
    for enemy, remaining in ((near, 3.0), (far, 9.0), (tough, 6.0)):
        enemy.remaining = remaining
        engine.enemies.append(enemy)

    expectations = {"первый": near, "последний": far,
                    "крепкий": tough, "ближний": near}
    for mode_idx, mode_name in enumerate(MODES):
        tower.mode = mode_idx
        check("mode '{}' picks the right enemy".format(mode_name),
              tower.acquire(engine.enemies) is expectations[mode_name])


# --------------------------------------------------------------------------- 6
def test_economy():
    engine = Engine(seed=SHOT_SEED)
    start = engine.money
    cell = (8, 8)
    cost = TYPES["gun"]["cost"]
    check("tower is bought", engine.place_tower("gun", cell))
    check("gold is spent", engine.money == start - cost)

    tower = engine.towers[0]
    up_cost = tower.upgrade_cost
    check("upgrade works", engine.upgrade_tower(tower))
    check("upgrade is paid for", engine.money == start - cost - up_cost)
    check("level rose", tower.level == 2)
    dmg1 = TYPES["gun"]["damage"]
    check("damage grew with the level", tower.damage > dmg1)

    engine.money = 0
    check("no money - no upgrade", not engine.upgrade_tower(tower))

    invested = tower.invested
    price = tower.sell_price
    check("sell price is 70% of everything invested",
          price == int(invested * 0.7))
    engine.sell_tower(tower)
    check("selling refunds", engine.money == price)
    check("the cell is free again", engine.grid.can_build(cell))


# --------------------------------------------------------------------------- 7
def test_waves():
    total = 0
    for wave in range(1, WAVES_TOTAL + 1):
        queue = waves.compose(wave)
        check("wave {} is not empty".format(wave), queue)
        total += len(queue)
        counted = waves.preview(wave)
        check("preview matches composition, wave {}".format(wave),
              sum(counted.values()) == len(queue))
    check("later waves are bigger",
          len(waves.compose(18)) > len(waves.compose(2)))
    for wave in (5, 10, 15):
        check("wave {} brings a boss".format(wave),
              waves.preview(wave)["boss"] == 1)
    check("the final wave brings two bosses", waves.preview(20)["boss"] == 2)
    print("  total enemies across the campaign:", total)


# --------------------------------------------------------------------------- 8
def test_defended_wave():
    engine = Engine(seed=SHOT_SEED, difficulty=1)
    core_x, core_y = engine.grid.core
    placed = 0
    for cell in [(core_x - 3, core_y - 1), (core_x - 3, core_y + 1),
                 (core_x - 5, core_y), (core_x - 4, core_y - 2),
                 (core_x - 4, core_y + 2), (core_x - 6, core_y - 1)]:
        if placed < 3 and engine.can_place("gun", cell):
            engine.place_tower("gun", cell)
            placed += 1
    check("three guns found room near the core", placed == 3)
    check("build phase before the horn", engine.phase == BUILD)
    check("the wave starts", engine.start_wave())
    check("attack phase after the horn", engine.phase == ATTACK)
    check("starting twice is refused", not engine.start_wave())

    lives = engine.lives
    run(engine, 120)
    check("three guns clear wave one", wave_over(engine))
    check("no leaks with a proper defense", engine.lives == lives)
    check("kills were counted", engine.stats["kills"] >= 11)
    check("the wave bonus was paid", engine.money > 240 - 3 * 55)
    check("the next wave is queued up", engine.wave == 2)


# --------------------------------------------------------------------------- 9
def test_save_roundtrip():
    path = os.path.join(os.path.dirname(__file__), "roundtrip_save.json")
    engine = Engine(seed=SHOT_SEED, difficulty=2)
    engine.money = 500
    engine.wave = 7
    engine.place_tower("tesla", (10, 8))
    engine.towers[0].upgrade()
    engine.towers[0].mode = 2
    engine.stats["kills"] = 55
    savegame.save(engine, path)

    loaded = savegame.load(path)
    check("seed survives", loaded.seed == engine.seed)
    check("difficulty survives", loaded.diff_index == 2)
    check("money survives", loaded.money == engine.money)
    check("wave survives", loaded.wave == 7)
    check("stats survive", loaded.stats["kills"] == 55)
    check("the tower is back", len(loaded.towers) == 1)
    tower = loaded.towers[0]
    check("its level survives", tower.level == 2)
    check("its targeting mode survives", tower.mode == 2)
    check("its cell is occupied on the map",
          loaded.grid.towers_at.get((10, 8)) is tower)
    check("the rocks came back identical",
          loaded.grid.rocks == engine.grid.rocks)
    os.remove(path)


# -------------------------------------------------------------------------- 10
def test_victory_and_defeat():
    engine = Engine(seed=SHOT_SEED)
    engine.wave = WAVES_TOTAL
    engine.phase = ATTACK
    engine._queue = []
    engine._qi = 0
    engine.update(1 / 30)
    check("clearing the last wave wins the game", engine.victory)

    engine2 = Engine(seed=SHOT_SEED)
    engine2.lives = 1
    boss = Enemy("boss", engine2.grid.spawns[0])
    engine2.enemies.append(boss)
    run(engine2, 90)
    check("losing every life is defeat", engine2.defeat)
    check("update is inert after the end", engine2.update(1 / 30) is None
          and engine2.defeat)


# -------------------------------------------------------------------------- 11
def test_screens(game):
    def key(scancode):
        return pg.event.Event(pg.KEYDOWN, {"key": 0, "scancode": scancode,
                                           "mod": 0})

    game.state = "menu"
    game.draw()
    game.handle_key(key(pg.KSCAN_3))
    check("the menu picks a difficulty", game.difficulty_idx == 2)
    game.handle_key(key(pg.KSCAN_SLASH))
    check("help opens from the menu", game.state == "help")
    game.draw()
    game.handle_key(key(pg.KSCAN_ESCAPE))
    game.handle_key(key(pg.KSCAN_N))
    check("a new defense starts on that difficulty",
          game.state == "play" and game.engine.diff_index == 2)
    game.draw()

    game.handle_key(key(pg.KSCAN_P))
    check("pause opens", game.state == "pause")
    game.draw()
    game.handle_key(key(pg.KSCAN_P))
    game.handle_key(key(pg.KSCAN_F))
    check("speed cycles", game.ui["speed"] == 2)
    game.handle_key(key(pg.KSCAN_V))
    check("flow arrows toggle", game.ui["show_flow"])
    game.draw()
    game.handle_key(key(pg.KSCAN_V))          # and back off

    # place a tower with the mouse, select it, open its info panel
    game.engine.money = 1000
    cell = (8, 8)
    if not game.engine.grid.buildable(cell):
        cell = (9, 8)
    game.handle_key(key(pg.KSCAN_1))
    check("the shop arms the gun", game.ui["build_sel"] == "gun")
    import settings
    click = pg.event.Event(pg.MOUSEBUTTONDOWN, {
        "pos": (cell[0] * 40 + 20, cell[1] * 40 + 20), "button": 1})
    game.handle_mouse(click)
    check("a click builds the tower",
          game.engine.tower_at(cell) is not None)
    game.handle_mouse(pg.event.Event(pg.MOUSEBUTTONDOWN, {
        "pos": (settings.WIDTH, 0), "button": 3}))
    game.handle_mouse(click)
    check("a click selects the tower",
          game.ui["selected"] is game.engine.tower_at(cell))
    game.handle_key(key(pg.KSCAN_T))
    check("T cycles the targeting mode", game.ui["selected"].mode == 1)
    game.draw()
    game.handle_key(key(pg.KSCAN_X))
    check("X sells the selected tower", game.engine.tower_at(cell) is None)

    game.engine.victory = True
    game.state = "end"
    game.draw()
    game.handle_key(key(pg.KSCAN_ESCAPE))
    check("the end screen returns to the menu", game.state == "menu")


# -------------------------------------------------------------------------- 12
def shoot_screenshot(game):
    """A believable mid-battle frame on a seeded map for the readme."""
    game.difficulty_idx = 1
    game.new_game(seed=SHOT_SEED)
    engine = game.engine
    engine.money = 10 ** 4

    core_x, core_y = engine.grid.core
    plan = [
        ("gun", (core_x - 3, core_y - 1), 2),
        ("gun", (core_x - 4, core_y + 1), 1),
        ("cannon", (core_x - 6, core_y), 2),
        ("frost", (core_x - 5, core_y - 2), 1),
        ("tesla", (core_x - 7, core_y + 1), 3),
        ("gun", (core_x - 9, core_y - 1), 1),
    ]
    built = []
    for kind, cell, level in plan:
        candidates = [cell, (cell[0], cell[1] - 1), (cell[0] - 1, cell[1]),
                      (cell[0], cell[1] + 1), (cell[0] + 1, cell[1])]
        for option in candidates:
            if engine.can_place(kind, option):
                tower = engine.place_tower(kind, option)
                for _ in range(level - 1):
                    engine.upgrade_tower(tower)
                built.append(tower)
                break
    check("the screenshot defense is built", len(built) >= 5)

    engine.money = 385                       # believable mid-game wallet
    engine.wave = 8
    engine.start_wave()
    for _ in range(int(30.0 * 60)):
        engine.update(1 / 60)
        if engine.finished:
            break
        fighting = sum(1 for t in built if t.fired_total > 0)
        close = sum(1 for e in engine.enemies if e.remaining < 10)
        if fighting >= 3 and close >= 3 and engine.stats["time"] > 15:
            break
    check("the screenshot wave is still raging", engine.enemies)
    check("the defense is actually firing",
          any(t.fired_total > 0 for t in built))

    # catch a lively frame: bullets in the air or an explosion on screen
    for _ in range(int(3 * 60)):
        engine.update(1 / 60)
        if engine.bullets or any(e["k"] == "boom" for e in engine.effects):
            break

    game.ui.update(selected=built[2] if len(built) > 2 else built[0],
                   build_sel=None, show_flow=False)
    game.t = 4.2
    game.state = "play"
    game.draw()

    out = os.path.join(os.path.dirname(__file__), "..", "docs",
                       "screenshot.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    pg.image.save(game.screen, out)
    return os.path.normpath(out)


# -------------------------------------------------------------------------- 13
def test_performance(game):
    game.new_game(seed=SHOT_SEED)
    engine = game.engine
    engine.money = 10 ** 4
    for x in range(6, 20, 2):
        for y in (5, 9, 13):
            if engine.can_place("gun", (x, y)):
                engine.place_tower("gun", (x, y))
    engine.wave = 12
    engine.start_wave()
    run(engine, 8, dt=1 / 60)

    start = time.perf_counter()
    for _ in range(60):
        game.draw()
    frame_ms = (time.perf_counter() - start) / 60 * 1000

    start = time.perf_counter()
    for _ in range(300):
        engine.grid.recompute()
    flow_ms = (time.perf_counter() - start) / 300 * 1000
    return frame_ms, flow_ms


# ===========================================================================
def main():
    save_backup = savegame.SAVE_PATH + ".bak"
    if savegame.has_save():
        os.replace(savegame.SAVE_PATH, save_backup)

    try:
        test_grid_and_flow()
        test_movement_and_leak()
        test_intercept()
        test_tower_mechanics()
        test_targeting_modes()
        test_economy()
        test_waves()
        test_defended_wave()
        test_save_roundtrip()
        test_victory_and_defeat()

        game = Game()
        game.draw()
        test_screens(game)
        shot = shoot_screenshot(game)
        frame_ms, flow_ms = test_performance(game)

        print("{} checks passed".format(len(CHECKS)))
        print("frame: {:.1f} ms    flow field rebuild: {:.2f} ms".format(
            frame_ms, flow_ms))
        print("screenshot saved to", shot)
    finally:
        savegame.delete_save()
        if os.path.isfile(save_backup):
            os.replace(save_backup, savegame.SAVE_PATH)


if __name__ == "__main__":
    main()
