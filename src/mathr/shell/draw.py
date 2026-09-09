"""Everything that puts pixels on the design surface.

This module owns the mapping from `parts: int` to which shapes are on screen;
the domain deliberately does not know a rocket exists.
"""

import math
import random
from dataclasses import dataclass

import pygame

DESIGN = (1280, 800)

SPACE = (12, 14, 32)
PANEL = (26, 30, 58)
INK = (236, 240, 255)
DIM = (140, 150, 190)
ACCENT = (255, 196, 74)
GOOD = (86, 214, 138)
BAD = (232, 96, 110)
HULL = (222, 226, 240)
ALIEN = (146, 96, 214)
ALIEN_DARK = (86, 52, 138)
BEAM = (168, 240, 190)
HULL_DARK = (168, 176, 204)
FLAME = (255, 140, 60)

ROCKET_BOX = (360, 580)
ROCKET_ORIGIN = (110, 130)
BODY_X = 180


def _fins(surface: pygame.Surface) -> None:
    pygame.draw.polygon(surface, BAD, [(120, 470), (120, 545), (60, 545)])


def _fins_right(surface: pygame.Surface) -> None:
    pygame.draw.polygon(surface, BAD, [(240, 470), (240, 545), (300, 545)])


def _nozzle(surface: pygame.Surface) -> None:
    pygame.draw.polygon(surface, HULL_DARK, [(145, 520), (215, 520), (235, 570), (125, 570)])


def _tank(surface: pygame.Surface) -> None:
    pygame.draw.rect(surface, HULL, (120, 400, 120, 125), border_radius=14)


def _band(surface: pygame.Surface) -> None:
    pygame.draw.rect(surface, BAD, (118, 378, 124, 26), border_radius=8)


def _mid_body(surface: pygame.Surface) -> None:
    pygame.draw.rect(surface, HULL, (120, 268, 120, 112), border_radius=10)


def _porthole(surface: pygame.Surface) -> None:
    pygame.draw.circle(surface, HULL_DARK, (BODY_X, 320), 34)
    pygame.draw.circle(surface, (108, 196, 255), (BODY_X, 320), 26)
    pygame.draw.circle(surface, INK, (BODY_X - 9, 311), 8)


def _upper_body(surface: pygame.Surface) -> None:
    pygame.draw.rect(surface, HULL, (128, 168, 104, 104), border_radius=10)


def _nose(surface: pygame.Surface) -> None:
    pygame.draw.polygon(surface, ACCENT, [(BODY_X, 60), (232, 172), (128, 172)])


def _antenna(surface: pygame.Surface) -> None:
    pygame.draw.line(surface, HULL_DARK, (BODY_X, 60), (BODY_X, 22), 6)
    pygame.draw.circle(surface, GOOD, (BODY_X, 18), 10)


#: Bottom-up, so the part that tumbles off is always the top one.
PART_PAINTERS = (
    _fins,
    _fins_right,
    _nozzle,
    _tank,
    _band,
    _mid_body,
    _porthole,
    _upper_body,
    _nose,
    _antenna,
)


@dataclass(frozen=True)
class Part:
    """A part pre-rendered to a tight surface, plus where it sits in the box."""

    image: pygame.Surface
    offset: tuple[int, int]


def render_parts() -> tuple[Part, ...]:
    parts = []
    for painter in PART_PAINTERS:
        canvas = pygame.Surface(ROCKET_BOX, pygame.SRCALPHA)
        painter(canvas)
        bounds = canvas.get_bounding_rect()
        parts.append(Part(canvas.subsurface(bounds).copy(), bounds.topleft))
    return tuple(parts)


def draw_rocket(surface, parts, count, origin=ROCKET_ORIGIN, flame=0.0) -> None:
    ox, oy = origin
    if flame > 0:
        length = 40 + 90 * flame
        width = 26 + 14 * flame
        pygame.draw.polygon(
            surface,
            FLAME,
            [
                (ox + BODY_X - width, oy + 566),
                (ox + BODY_X + width, oy + 566),
                (ox + BODY_X, oy + 566 + length),
            ],
        )
        pygame.draw.polygon(
            surface,
            ACCENT,
            [
                (ox + BODY_X - width * 0.5, oy + 566),
                (ox + BODY_X + width * 0.5, oy + 566),
                (ox + BODY_X, oy + 566 + length * 0.55),
            ],
        )
    for part in parts[:count]:
        surface.blit(part.image, (ox + part.offset[0], oy + part.offset[1]))


@dataclass
class FallingPart:
    """A knocked-off part, integrated per frame."""

    image: pygame.Surface
    x: float
    y: float
    vx: float
    vy: float
    spin: float
    angle: float = 0.0

    def step(self, dt: float) -> None:
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 1400 * dt
        self.angle += self.spin * dt

    @property
    def gone(self) -> bool:
        return self.y > DESIGN[1] + 200

    def draw(self, surface: pygame.Surface) -> None:
        rotated = pygame.transform.rotate(self.image, self.angle)
        surface.blit(rotated, rotated.get_rect(center=(int(self.x), int(self.y))).topleft)


def knock_off(part: Part, rng: random.Random, origin=ROCKET_ORIGIN) -> FallingPart:
    rect = part.image.get_rect(topleft=(origin[0] + part.offset[0], origin[1] + part.offset[1]))
    return FallingPart(
        image=part.image,
        x=rect.centerx,
        y=rect.centery,
        vx=rng.choice((-1, 1)) * rng.uniform(120, 260),
        vy=rng.uniform(-520, -320),
        spin=rng.uniform(-360, 360),
    )


def make_stars(rng: random.Random, count: int = 140) -> tuple[tuple[int, int, int], ...]:
    return tuple(
        (rng.randrange(DESIGN[0]), rng.randrange(DESIGN[1]), rng.randrange(1, 4))
        for _ in range(count)
    )


def draw_stars(surface, stars, drift: float = 0.0) -> None:
    surface.fill(SPACE)
    for x, y, size in stars:
        shade = 90 + size * 50
        pygame.draw.circle(surface, (shade, shade, min(255, shade + 30)), (x, int(y + drift) % DESIGN[1]), size)


@dataclass(frozen=True)
class Button:
    rect: pygame.Rect
    label: str
    value: str
    tone: tuple[int, int, int] = PANEL


def draw_button(surface, font, button: Button, hovered: bool) -> None:
    fill = tuple(min(255, c + 26) for c in button.tone) if hovered else button.tone
    pygame.draw.rect(surface, fill, button.rect, border_radius=16)
    pygame.draw.rect(surface, DIM if not hovered else ACCENT, button.rect, width=3, border_radius=16)
    text(surface, font, button.label, button.rect.center, INK)


def text(surface, font, value, center, colour=INK) -> pygame.Rect:
    rendered = font.render(value, True, colour)
    rect = rendered.get_rect(center=center)
    surface.blit(rendered, rect.topleft)
    return rect


def draw_progress(surface, font, done: int, total: int) -> None:
    for index in range(total):
        rect = pygame.Rect(700 + index * 46, 96, 34, 14)
        pygame.draw.rect(surface, GOOD if index < done else PANEL, rect, border_radius=7)
    text(surface, font, f"{done} / {total} parts", (880, 60), DIM)


TIME_BAR = pygame.Rect(700, 124, 10 * 46 - 12, 12)


def draw_time_bar(surface, fraction: float) -> None:
    """No digits: a ticking decimal is the most anxious thing on a screen, and
    it competes with the equation for a seven-year-old's attention."""
    pygame.draw.rect(surface, PANEL, TIME_BAR, border_radius=6)
    filled = pygame.Rect(TIME_BAR)
    filled.width = max(0, int(TIME_BAR.width * max(0.0, min(1.0, fraction))))
    colour = BAD if fraction < 0.25 else ACCENT if fraction < 0.5 else GOOD
    if filled.width:
        pygame.draw.rect(surface, colour, filled, border_radius=6)


ALIEN_HOME = (430, 250)
ALIEN_MIN = 70
ALIEN_MAX = 520


def alien_scale(seconds_left: float, cap: float) -> float:
    """0 when the bank is full or better, 1 when it is empty.

    A pure function of time *remaining*, which is what makes the saucer
    retreat when he earns seconds back instead of only ever looming.
    """
    if cap <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - seconds_left / cap))


def draw_alien(surface, scale: float, now: float) -> None:
    width = ALIEN_MIN + (ALIEN_MAX - ALIEN_MIN) * scale
    height = width * 0.40
    cx, cy = ALIEN_HOME
    cy += 30 * scale
    bob = (2 + 8 * scale) * math.sin(now * 1.6)
    body = pygame.Rect(0, 0, int(width), int(height))
    body.center = (int(cx), int(cy + bob))

    dome = pygame.Rect(0, 0, int(width * 0.46), int(height * 1.05))
    dome.midbottom = (body.centerx, body.centery + int(height * 0.10))
    pygame.draw.ellipse(surface, ALIEN_DARK, dome)
    pygame.draw.ellipse(surface, (188, 232, 255), dome.inflate(-int(width * 0.06), -int(height * 0.22)))

    pygame.draw.ellipse(surface, ALIEN, body)
    pygame.draw.ellipse(surface, ALIEN_DARK, body, width=max(2, int(width * 0.012)))

    lights = max(3, int(5 + 3 * scale))
    radius = max(2, int(width * 0.028))
    for index in range(lights):
        share = (index + 0.5) / lights
        x = body.left + int(body.width * share)
        lit = (math.sin(now * 4 + index) + 1) * 0.5
        shade = tuple(min(255, int(base + span * lit)) for base, span in ((120, 135), (40, 200), (140, 80)))
        pygame.draw.circle(surface, shade, (x, body.centery + int(height * 0.22)), radius)


def draw_beam(surface, target: tuple[int, int], progress: float) -> None:
    """The abduction: a cone from the saucer down onto the rocket."""
    cx, cy = ALIEN_HOME
    cy += 30
    spread = 40 + 120 * progress
    cone = pygame.Surface(DESIGN, pygame.SRCALPHA)
    pygame.draw.polygon(
        cone,
        (*BEAM, int(70 + 110 * progress)),
        [
            (cx - 30, cy),
            (cx + 30, cy),
            (target[0] + spread, target[1]),
            (target[0] - spread, target[1]),
        ],
    )
    surface.blit(cone, (0, 0))



def fit(window_size: tuple[int, int]) -> tuple[float, tuple[int, int]]:
    """Scale and letterbox offset for the design surface in a given window.

    Hyprland tiles the window to whatever the layout gives it, so this is the
    single place the two coordinate spaces meet.
    """
    width, height = window_size
    scale = min(width / DESIGN[0], height / DESIGN[1])
    return scale, (int((width - DESIGN[0] * scale) / 2), int((height - DESIGN[1] * scale) / 2))


def to_design(position: tuple[int, int], window_size: tuple[int, int]) -> tuple[int, int]:
    scale, (ox, oy) = fit(window_size)
    return (int((position[0] - ox) / scale), int((position[1] - oy) / scale))


def to_window(position: tuple[int, int], window_size: tuple[int, int]) -> tuple[int, int]:
    scale, (ox, oy) = fit(window_size)
    return (int(position[0] * scale + ox), int(position[1] * scale + oy))
