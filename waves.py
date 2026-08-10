"""Wave composition.

Each wave gets a point budget that grows quadratically; the budget is spent
on enemy types unlocked by that point of the campaign. The composition is a
pure function of the wave number - no randomness - so a saved game does not
need to store any queue, and the wave preview on the panel is always exact.
"""
from __future__ import annotations

from collections import Counter

COST = {"bug": 4, "runner": 5, "tank": 14, "swarm": 9, "boss": 160}
GAP = {"bug": 0.70, "runner": 0.50, "tank": 1.10, "swarm": 0.90, "boss": 2.60}

UNLOCK = {"bug": 1, "runner": 2, "swarm": 4, "tank": 6}
SHARE = {"tank": 0.24, "swarm": 0.20, "runner": 0.28}


def budget(wave):
    return 24 + 18 * wave + int(2.3 * wave * wave)


def compose(wave):
    """Returns a list of (gap_seconds, enemy_kind), already interleaved."""
    out = []
    points = budget(wave)

    if wave % 5 == 0:                     # boss waves: 5, 10, 15, 20
        n_boss = 2 if wave >= 20 else 1
        for _ in range(n_boss):
            out.append(("boss"))
        points = max(points - n_boss * COST["boss"], 10 * wave)

    for kind in ("tank", "swarm", "runner"):
        if wave >= UNLOCK[kind]:
            n = int(min(SHARE[kind] * budget(wave), points) // COST[kind])
            out.extend([kind] * n)
            points -= n * COST[kind]

    out.extend(["bug"] * (points // COST["bug"]))

    # deterministic interleave so the same kinds do not clump together
    order = sorted(range(len(out)),
                   key=lambda i: (i * 2654435761 + wave * 97) % 100003)
    mixed = [out[i] for i in order]
    # bosses always arrive last, as a finale
    mixed.sort(key=lambda kind: kind == "boss")
    return [(GAP[kind], kind) for kind in mixed]


def preview(wave):
    """Counter of {kind: amount} for the panel."""
    return Counter(kind for _, kind in compose(wave))


def gap_scale(wave):
    """Later waves pour in faster."""
    return max(0.55, 1.0 - 0.02 * wave)
