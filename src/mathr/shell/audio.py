"""Tones synthesized in code, so the game ships no asset files.

`array.array` feeds `mixer.Sound(buffer=...)` directly; numpy is not needed.
"""

import math
import random
from array import array

import pygame

RATE = 44100


def pre_init() -> None:
    """Must run before `pygame.init()`, and fixes the buffer format below."""
    pygame.mixer.pre_init(RATE, -16, 1, 512)


def _tone(shape, amplitude=0.32):
    """Build 16-bit signed mono samples, the format `pre_init` asked for.

    A buffer that disagrees with `mixer.get_init()` does not raise — it plays
    as static or at the wrong pitch — so the rate is read back, never assumed.
    """
    init = pygame.mixer.get_init()
    if init is None:
        return None
    rate, size, channels = init
    if (size, channels) != (-16, 1):
        return None
    samples = array(
        "h",
        (
            int(max(-1.0, min(1.0, shape(i / rate))) * amplitude * 32767)
            for i in range(int(rate * shape.seconds))
        ),
    )
    return pygame.mixer.Sound(buffer=samples.tobytes())


class _Shape:
    def __init__(self, seconds, fn):
        self.seconds = seconds
        self.fn = fn

    def __call__(self, t):
        return self.fn(t)


def _envelope(t, seconds, attack=0.01):
    return min(1.0, t / attack) * max(0.0, 1.0 - t / seconds)


def _rising_blip():
    seconds = 0.22

    def wave(t):
        pitch = 660 + 500 * (t / seconds)
        return math.sin(2 * math.pi * pitch * t) * _envelope(t, seconds)

    return _Shape(seconds, wave)


def _buzz():
    seconds = 0.3

    def wave(t):
        square = 1.0 if math.sin(2 * math.pi * 150 * t) > 0 else -1.0
        return square * 0.6 * _envelope(t, seconds, attack=0.02)

    return _Shape(seconds, wave)


def _launch_sweep():
    seconds = 1.6
    rng = random.Random(9)
    noise = [rng.uniform(-1, 1) for _ in range(2048)]

    def wave(t):
        rumble = math.sin(2 * math.pi * (70 + 40 * t) * t)
        hiss = noise[int(t * 9000) % len(noise)]
        return (0.6 * rumble + 0.4 * hiss) * _envelope(t, seconds, attack=0.15)

    return _Shape(seconds, wave)


def _warn():
    seconds = 0.12

    def wave(t):
        return math.sin(2 * math.pi * 220 * t) * _envelope(t, seconds, attack=0.005)

    return _Shape(seconds, wave)


def _abducted():
    seconds = 1.4
    rng = random.Random(21)
    noise = [rng.uniform(-1, 1) for _ in range(2048)]

    def wave(t):
        pitch = 900 * (1 - t / seconds) ** 2 + 90
        warble = math.sin(2 * math.pi * pitch * t + 3 * math.sin(2 * math.pi * 7 * t))
        return (0.75 * warble + 0.25 * noise[int(t * 6000) % len(noise)]) * _envelope(t, seconds, attack=0.02)

    return _Shape(seconds, wave)


class Sounds:
    """Silent by construction if the mixer is unavailable."""

    def __init__(self) -> None:
        self.muted = False
        try:
            pygame.mixer.init()
            self._clips = {
                "correct": _tone(_rising_blip()),
                "wrong": _tone(_buzz()),
                "launch": _tone(_launch_sweep(), amplitude=0.5),
                "warn": _tone(_warn(), amplitude=0.22),
                "abducted": _tone(_abducted(), amplitude=0.45),
            }
        except pygame.error:
            self._clips = {}

    def play(self, name: str) -> None:
        clip = self._clips.get(name)
        if clip and not self.muted:
            clip.play()
