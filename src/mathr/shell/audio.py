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


def _pock():
    """The racket. Short and percussive, because it fires on every return."""
    seconds = 0.09

    def wave(t):
        thud = math.sin(2 * math.pi * 320 * t)
        click = math.sin(2 * math.pi * 1800 * t) * math.exp(-t * 90)
        return (0.7 * thud + 0.6 * click) * _envelope(t, seconds, attack=0.002)

    return _Shape(seconds, wave)


def _drop():
    seconds = 0.45

    def wave(t):
        pitch = 520 - 380 * (t / seconds)
        return math.sin(2 * math.pi * pitch * t) * _envelope(t, seconds, attack=0.01)

    return _Shape(seconds, wave)


def _cheer():
    seconds = 0.9
    notes = (523, 659, 784, 1047)

    def wave(t):
        pitch = notes[min(len(notes) - 1, int(t / seconds * len(notes)))]
        return math.sin(2 * math.pi * pitch * t) * _envelope(t, seconds, attack=0.02)

    return _Shape(seconds, wave)


def _catch():
    """A completed pass: a soft thump, then a third rising off it. A reward,
    which is why it is not `correct` — it has to feel bigger than an answer."""
    seconds = 0.5

    def wave(t):
        thump = math.sin(2 * math.pi * 180 * t) * math.exp(-t * 22)
        note = 523 if t < seconds * 0.45 else 659
        rise = math.sin(2 * math.pi * note * t) * _envelope(t, seconds, attack=0.01)
        return 0.7 * thump + 0.6 * rise

    return _Shape(seconds, wave)


def _tackle():
    """The sack: a low thud with no ring to it. It is not a failure sound —
    getting the spot right is a small win inside a bad play."""
    seconds = 0.28
    rng = random.Random(31)
    noise = [rng.uniform(-1, 1) for _ in range(2048)]

    def wave(t):
        thud = math.sin(2 * math.pi * (150 - 60 * t / seconds) * t)
        return (0.8 * thud + 0.3 * noise[int(t * 4000) % len(noise)]) * _envelope(
            t, seconds, attack=0.005
        )

    return _Shape(seconds, wave)


def _tumbler():
    """One pin of the lock dropping: a dry click with a little metal on it.
    Fires on every solved line, so it has to stay short."""
    seconds = 0.08

    def wave(t):
        click = math.sin(2 * math.pi * 900 * t) * math.exp(-t * 70)
        metal = math.sin(2 * math.pi * 2600 * t) * math.exp(-t * 120)
        return (0.8 * click + 0.5 * metal) * _envelope(t, seconds, attack=0.001)

    return _Shape(seconds, wave)


def _unlock():
    """A vault swinging: the bolt drawing back, then a rising third. The only
    reward that arrives three times a round, so it can afford to be the big one."""
    seconds = 0.75

    def wave(t):
        share = t / seconds
        if share < 0.35:
            # The bolt: low and mechanical.
            return math.sin(2 * math.pi * 120 * t) * 0.9 * _envelope(t, seconds, attack=0.004)
        pitch = 523 if share < 0.62 else 784
        return math.sin(2 * math.pi * pitch * t) * _envelope(t, seconds, attack=0.01)

    return _Shape(seconds, wave)


def _alarm():
    """Tripped: two falling squawks. Deliberately unpleasant and deliberately
    brief — it fires at most three times in a round."""
    seconds = 0.42

    def wave(t):
        share = t / seconds
        pitch = 660 if share % 0.5 < 0.25 else 440
        square = 1.0 if math.sin(2 * math.pi * pitch * t) >= 0 else -1.0
        return square * _envelope(t, seconds, attack=0.006)

    return _Shape(seconds, wave)


def _throw():
    """The ball leaving his hand: a short rising whoosh, so a good placement is
    audibly *not* the catch it might still become."""
    seconds = 0.26
    rng = random.Random(13)
    noise = [rng.uniform(-1, 1) for _ in range(2048)]

    def wave(t):
        share = t / seconds
        air = noise[int(t * (3000 + 9000 * share)) % len(noise)]
        return air * _envelope(t, seconds, attack=0.06)

    return _Shape(seconds, wave)


def _incomplete():
    """A wide throw costs nothing, so this is dry and short — clearly not
    `wrong`, which is a buzzer."""
    seconds = 0.22
    rng = random.Random(5)
    noise = [rng.uniform(-1, 1) for _ in range(2048)]

    def wave(t):
        return noise[int(t * 12000) % len(noise)] * _envelope(t, seconds, attack=0.01)

    return _Shape(seconds, wave)


def _slide():
    """A stone on ice: a long, soft rush with no pitch in it. It plays on every
    thrown stone that does not count, so it has to be the *absence* of a reward
    rather than a failure noise — nothing about a wide stone is a buzzer."""
    seconds = 0.55
    rng = random.Random(19)
    noise = [rng.uniform(-1, 1) for _ in range(4096)]

    def wave(t):
        share = t / seconds
        # The rush slows as the stone does: the sampling rate falls away.
        rush = noise[int(t * (5200 - 3000 * share)) % len(noise)]
        return rush * _envelope(t, seconds, attack=0.08) * (1.0 - 0.5 * share)

    return _Shape(seconds, wave)


def _inhouse():
    """A stone coming to rest in the house: the granite knock, then a third
    rising off it. Sibling of `_catch` — it is the reward in a mode that has
    exactly one."""
    seconds = 0.42

    def wave(t):
        knock = math.sin(2 * math.pi * 220 * t) * math.exp(-t * 26)
        note = 587 if t < seconds * 0.4 else 880
        ring = math.sin(2 * math.pi * note * t) * _envelope(t, seconds, attack=0.01)
        return 0.7 * knock + 0.55 * ring

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
                "pock": _tone(_pock(), amplitude=0.45),
                "drop": _tone(_drop(), amplitude=0.4),
                "cheer": _tone(_cheer(), amplitude=0.4),
                "catch": _tone(_catch(), amplitude=0.45),
                "incomplete": _tone(_incomplete(), amplitude=0.25),
                "throw": _tone(_throw(), amplitude=0.3),
                "tackle": _tone(_tackle(), amplitude=0.4),
                "tumbler": _tone(_tumbler(), amplitude=0.4),
                "unlock": _tone(_unlock(), amplitude=0.42),
                "alarm": _tone(_alarm(), amplitude=0.22),
                "slide": _tone(_slide(), amplitude=0.2),
                "inhouse": _tone(_inhouse(), amplitude=0.45),
            }
        except pygame.error:
            self._clips = {}

    def play(self, name: str) -> None:
        clip = self._clips.get(name)
        if clip and not self.muted:
            clip.play()
