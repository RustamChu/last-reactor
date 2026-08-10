"""The battlefield grid, its obstacles and the flow field.

Pathfinding here is deliberately NOT per-enemy A*. A tower defense may have a
hundred walkers heading to the same place, so we compute one breadth-first
"flow field" outward from the reactor: every walkable cell remembers its
distance and the neighbouring cell that leads closer. Enemies then just read
an arrow per step, which costs nothing no matter how many of them are alive,
and rebuilding the whole field after construction is a single BFS over ~450
cells.

The maze is the player's to build: towers are walls, enemies re-route around
them. The one hard rule - you may never seal the path completely - is
enforced right here, in `can_build`.
"""
from __future__ import annotations

import random
from collections import deque

from settings import FIELD_COLS, FIELD_ROWS, ROCK_COUNT

NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1))


class Grid:
    def __init__(self, seed=0):
        self.seed = seed
        self.cols = FIELD_COLS
        self.rows = FIELD_ROWS
        self.core = (self.cols - 3, self.rows // 2)
        self.spawns = [(0, 3), (0, self.rows - 4)]
        self.rocks = set()
        self.towers_at = {}                     # cell -> Tower
        self._place_rocks(random.Random(seed))
        self.dist = {}
        self.flow = {}
        self.recompute()

    # -------------------------------------------------------------- terrain
    def _place_rocks(self, rng):
        """Scatter obstacles, keeping every spawn connected to the core."""
        protected = {self.core, *self.spawns}
        attempts = 0
        while len(self.rocks) < ROCK_COUNT and attempts < 400:
            attempts += 1
            cell = (rng.randrange(2, self.cols - 4),
                    rng.randrange(1, self.rows - 1))
            near_key = any(abs(cell[0] - px) + abs(cell[1] - py) <= 2
                           for px, py in protected)
            if near_key or cell in self.rocks:
                continue
            self.rocks.add(cell)
            if not self._connected(self.rocks | set(self.towers_at)):
                self.rocks.discard(cell)

    # -------------------------------------------------------------- queries
    def in_bounds(self, cell):
        return 0 <= cell[0] < self.cols and 0 <= cell[1] < self.rows

    def walkable(self, cell):
        return (self.in_bounds(cell) and cell not in self.rocks
                and cell not in self.towers_at)

    def buildable(self, cell):
        return (self.walkable(cell) and cell != self.core
                and cell not in self.spawns)

    # ---------------------------------------------------------- flow field
    def _bfs(self, blocked):
        """Distances to the core over cells not in `blocked`."""
        dist = {self.core: 0}
        flow = {self.core: None}
        queue = deque([self.core])
        while queue:
            cell = queue.popleft()
            cx, cy = cell
            step = dist[cell] + 1
            for dx, dy in NEIGHBOURS:
                nxt = (cx + dx, cy + dy)
                if nxt in dist or not self.in_bounds(nxt) or nxt in blocked:
                    continue
                dist[nxt] = step
                flow[nxt] = cell            # the arrow points toward the core
                queue.append(nxt)
        return dist, flow

    def recompute(self):
        blocked = self.rocks | set(self.towers_at)
        self.dist, self.flow = self._bfs(blocked)

    def _connected(self, blocked, extra_cells=()):
        dist, _ = self._bfs(blocked)
        if any(spawn not in dist for spawn in self.spawns):
            return False
        return all(cell in dist for cell in extra_cells)

    # ------------------------------------------------------------ building
    def can_build(self, cell, enemy_cells=()):
        """A tower may stand here only if nobody gets walled off.

        Checked: the cell itself is free, no enemy is standing on it, and
        with the cell blocked every spawn AND every living enemy still has a
        route to the core.
        """
        if not self.buildable(cell):
            return False
        if cell in enemy_cells:
            return False
        blocked = self.rocks | set(self.towers_at) | {cell}
        needed = [c for c in enemy_cells if c != cell]
        return self._connected(blocked, needed)

    def add_tower(self, cell, tower):
        self.towers_at[cell] = tower
        self.recompute()

    def remove_tower(self, cell):
        self.towers_at.pop(cell, None)
        self.recompute()
