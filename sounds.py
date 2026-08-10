"""Tiny procedural synthesizer - the project ships zero audio files.

Same trick as graphics: every effect is a few dozen lines of math written
straight into a sample buffer at start-up. Degrades to silence when there is
no audio device (headless test runs, broken drivers).
"""
from __future__ import annotations

import math
import random
from array import array

import pygame as pg

SAMPLE_RATE = 22050


def _synth(duration_ms, freq_start, freq_end=None, shape="sine",
           volume=0.5, noise=0.0, decay=1.5):
    freq_end = freq_end if freq_end is not None else freq_start
    n = int(SAMPLE_RATE * duration_ms / 1000)
    buf = array("h", bytes(2 * n))
    rnd = random.Random(3)
    phase = 0.0
    for i in range(n):
        t = i / n
        freq = freq_start + (freq_end - freq_start) * t
        phase += math.tau * freq / SAMPLE_RATE
        if shape == "square":
            sample = 1.0 if math.sin(phase) >= 0 else -1.0
        elif shape == "saw":
            sample = 2.0 * ((phase / math.tau) % 1.0) - 1.0
        else:
            sample = math.sin(phase)
        if noise:
            sample = (1 - noise) * sample + noise * rnd.uniform(-1, 1)
        env = (1.0 - t) ** decay
        buf[i] = int(30000 * volume * env * sample)
    return buf


class SoundManager:
    def __init__(self):
        self.enabled = True
        try:
            pg.mixer.pre_init(SAMPLE_RATE, -16, 1, 512)
            pg.mixer.init(SAMPLE_RATE, -16, 1, 512)
            self.sounds = {
                "shot": self._make(_synth(70, 900, 300, "square", 0.18, 0.5)),
                "boom": self._make(_synth(320, 160, 40, "sine", 0.55, 0.55)),
                "zap": self._make(_synth(120, 1400, 300, "saw", 0.30, 0.35)),
                "frost": self._make(_synth(200, 500, 900, "sine", 0.22)),
                "build": self._make(_synth(90, 300, 500, "square", 0.30)),
                "sell": self._make(_synth(130, 600, 250, "square", 0.28)),
                "leak": self._make(_synth(280, 220, 110, "square", 0.5, 0.2)),
                "horn": self._make(_synth(160, 196, 196, "saw", 0.4)
                                   + _synth(240, 262, 262, "saw", 0.4)),
                "win": self._make(_synth(150, 523, 523, "square", 0.35)
                                  + _synth(150, 659, 659, "square", 0.35)
                                  + _synth(320, 784, 784, "square", 0.35)),
                "lose": self._make(_synth(600, 220, 55, "saw", 0.5, 0.25)),
            }
        except pg.error:
            self.enabled = False

    @staticmethod
    def _make(buf):
        return pg.mixer.Sound(buffer=buf.tobytes())

    def play(self, name):
        if self.enabled and name in self.sounds:
            self.sounds[name].play()
