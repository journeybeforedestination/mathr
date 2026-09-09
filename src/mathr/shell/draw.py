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
COURT = (38, 72, 92)
COURT_LINE = (198, 216, 228)
BALL = (222, 240, 96)
CABINET = (44, 40, 86)

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


def draw_card(surface, rect: pygame.Rect, tone=PANEL, hovered: bool = False, dimmed: bool = False) -> None:
    """The box a button lives in.

    A dimmed card ignores `hovered` entirely: a coming-soon row that lights up
    under the cursor and then does nothing on click reads as broken rather than
    as unfinished.
    """
    if dimmed:
        pygame.draw.rect(surface, SPACE, rect, border_radius=16)
        pygame.draw.rect(surface, PANEL, rect, width=3, border_radius=16)
        return
    fill = tuple(min(255, c + 26) for c in tone) if hovered else tone
    pygame.draw.rect(surface, fill, rect, border_radius=16)
    pygame.draw.rect(surface, ACCENT if hovered else DIM, rect, width=3, border_radius=16)


def draw_button(surface, font, button: Button, hovered: bool, dimmed: bool = False) -> None:
    draw_card(surface, button.rect, button.tone, hovered, dimmed)
    text(surface, font, button.label, button.rect.center, DIM if dimmed else INK)


def text(surface, font, value, center, colour=INK) -> pygame.Rect:
    rendered = font.render(value, True, colour)
    rect = rendered.get_rect(center=center)
    surface.blit(rendered, rect.topleft)
    return rect


def draw_progress(surface, font, done: int, total: int, noun: str = "parts") -> None:
    for index in range(total):
        rect = pygame.Rect(700 + index * 46, 96, 34, 14)
        pygame.draw.rect(surface, GOOD if index < done else PANEL, rect, border_radius=7)
    text(surface, font, f"{done} / {total} {noun}", (880, 60), DIM)


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


def closing(seconds_left: float, cap: float) -> float:
    """0 when the clock is full or better, 1 when it is empty.

    A pure function of time *remaining*, which is what makes the saucer retreat
    — and the ball fly back — when he earns seconds back, instead of the threat
    only ever advancing. Both modes read their one moving thing from this.
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


# --- the tennis court -------------------------------------------------------
# Laid out in the same 1280x800 design space as everything else, left of the
# keypad at x=700. Nothing here does its own scaling.

COURT_TOP = 210
COURT_BOTTOM = 720
COURT_CENTRE = 350
COURT_FAR_HALF = 150  # half the court's width at the opponent's baseline
COURT_NEAR_HALF = 275  # and at his own, which is what makes it look deep

BALL_MIN = 8
BALL_MAX = 34


def court_lane(served: int) -> float:
    """Which way the ball is served, in [-1, 1], from the number of serves.

    Derived rather than random so the shell stays free of hidden state; the
    step of 7 across 5 lanes is what keeps consecutive serves apart.
    """
    return (((served * 7) % 5) / 2.0 - 1.0) * 0.8  # inset, so the ball stays on court


def court_ready(lane: float, travel: float) -> float:
    """The lane he has moved to, chasing a ball that is `travel` of the way down."""
    return lane * min(1.0, travel * 1.4)


def return_flight(lane: float, travel: float, t: float) -> tuple[float, float]:
    """His return, back over the net: from where he hit it to the far baseline."""
    return (lane * (1 - t), travel * (1 - t))


def past_flight(lane: float, travel: float, t: float) -> tuple[float, float]:
    """The one he missed, carrying on past him and out of the court."""
    return (lane, travel + 0.4 * t)


def court_point(lane: float, travel: float) -> tuple[float, float]:
    """Where a ball on `lane` sits when it is `travel` of the way down."""
    half = COURT_FAR_HALF + (COURT_NEAR_HALF - COURT_FAR_HALF) * travel
    return (COURT_CENTRE + lane * half, COURT_TOP + (COURT_BOTTOM - COURT_TOP) * travel)


def draw_court(surface) -> None:
    corners = [
        court_point(-1.0, 0.0),
        court_point(1.0, 0.0),
        court_point(1.0, 1.0),
        court_point(-1.0, 1.0),
    ]
    pygame.draw.polygon(surface, COURT, corners)
    pygame.draw.polygon(surface, COURT_LINE, corners, width=3)
    for travel in (0.22, 0.78):
        pygame.draw.line(surface, COURT_LINE, court_point(-1.0, travel), court_point(1.0, travel), 2)
    _net(surface)


def _net(surface) -> None:
    """Halfway down, and the one shape that says tennis before any ball moves."""
    left, right = court_point(-1.08, 0.5), court_point(1.08, 0.5)
    top = left[1] - 40
    pygame.draw.line(surface, INK, (left[0], top), (right[0], top), 4)
    for index in range(17):
        share = index / 16
        x = left[0] + (right[0] - left[0]) * share
        pygame.draw.line(surface, COURT_LINE, (x, top + 3), (x, left[1]), 1)
    for post in (left, right):
        pygame.draw.line(surface, HULL_DARK, post, (post[0], top - 6), 5)


def _figure(surface, centre: tuple[float, float], height: float, colour, swing: float = 0.0) -> None:
    x, y = centre
    body = pygame.Rect(0, 0, int(height * 0.45), int(height * 0.6))
    body.midbottom = (int(x), int(y))
    pygame.draw.rect(surface, colour, body, border_radius=int(height * 0.16))
    pygame.draw.circle(surface, colour, (int(x), int(body.top - height * 0.16)), int(height * 0.18))
    racket = pygame.Rect(0, 0, int(height * 0.26), int(height * 0.34))
    # The follow-through: the racket is still up when the ball leaves, and
    # settles back down as it flies away.
    racket.center = (
        int(x + height * (0.4 - 0.14 * swing)),
        int(body.centery - height * (0.1 + 0.45 * swing)),
    )
    pygame.draw.ellipse(surface, HULL, racket)
    pygame.draw.ellipse(surface, HULL_DARK, racket, width=2)


def draw_rally(
    surface, lane: float, travel: float, player_lane: float, now: float, swing: float = 0.0
) -> None:
    """The opponent, the ball wherever it is, and him under where it was.

    `player_lane` is passed rather than derived so that he stays put through
    his own follow-through instead of chasing his return back up the court.
    """
    _figure(surface, court_point(0.0, -0.08), 70, ALIEN)

    x, y = court_point(lane, travel)
    radius = BALL_MIN + (BALL_MAX - BALL_MIN) * travel
    shadow = court_point(lane, min(1.0, travel + 0.06))
    pygame.draw.ellipse(
        surface,
        (24, 46, 60),
        pygame.Rect(0, 0, int(radius * 2.1), int(radius * 0.7)).move(
            int(shadow[0] - radius * 1.05), int(shadow[1])
        ),
    )
    pygame.draw.circle(surface, BALL, (int(x), int(y)), int(radius))
    pygame.draw.arc(
        surface,
        (150, 170, 60),
        pygame.Rect(int(x - radius), int(y - radius), int(radius * 2), int(radius * 2)),
        0.6,
        2.4,
        max(2, int(radius * 0.18)),
    )

    # He slides under the ball as it comes, so the return reads as his doing.
    ready = court_point(player_lane, 1.0)
    bob = 3 * math.sin(now * 3)
    _figure(surface, (ready[0], ready[1] + bob), 130, GOOD, swing)


def draw_points(surface, font, points: int, lives: int) -> None:
    text(surface, font, "them", (74, 128), DIM)
    for index in range(lives):
        centre = (150 + index * 40, 128)
        pygame.draw.circle(surface, BAD if index < points else PANEL, centre, 14)


def draw_trophy(surface, centre: tuple[int, int], scale: float = 1.0) -> None:
    x, y = centre
    cup = pygame.Rect(0, 0, int(150 * scale), int(120 * scale))
    cup.midtop = (x, y)
    pygame.draw.ellipse(surface, ACCENT, cup)
    pygame.draw.rect(surface, ACCENT, pygame.Rect(cup.centerx - int(14 * scale), cup.bottom - int(10 * scale), int(28 * scale), int(50 * scale)))
    pygame.draw.rect(
        surface,
        ACCENT,
        pygame.Rect(cup.centerx - int(60 * scale), cup.bottom + int(36 * scale), int(120 * scale), int(24 * scale)),
        border_radius=int(8 * scale),
    )
    for side in (-1, 1):
        handle = pygame.Rect(0, 0, int(60 * scale), int(70 * scale))
        handle.center = (cup.centerx + side * int(80 * scale), cup.centery - int(10 * scale))
        pygame.draw.ellipse(surface, ACCENT, handle, width=max(3, int(12 * scale)))


# --- the arcade -------------------------------------------------------------


def draw_cabinet(surface, title_font, rect: pygame.Rect, title: str, hovered: bool) -> pygame.Rect:
    """A cabinet, returning the screen rect for the caller to fill with art."""
    draw_card(surface, rect, CABINET, hovered)
    marquee = pygame.Rect(rect.x + 24, rect.y + 20, rect.width - 48, 62)
    pygame.draw.rect(surface, PANEL, marquee, border_radius=12)
    text(surface, title_font, title, marquee.center, ACCENT if hovered else INK)
    screen = pygame.Rect(rect.x + 30, marquee.bottom + 18, rect.width - 60, 236)
    pygame.draw.rect(surface, SPACE, screen, border_radius=10)
    pygame.draw.rect(surface, PANEL, screen, width=3, border_radius=10)
    panel = pygame.Rect(rect.x + 30, screen.bottom + 20, rect.width - 60, rect.bottom - screen.bottom - 44)
    pygame.draw.rect(surface, PANEL, panel, border_radius=10)
    for index in range(4):
        pygame.draw.circle(
            surface,
            (ACCENT, GOOD, BAD, HULL)[index],
            (panel.x + 34 + index * 42, panel.centery),
            11,
        )
    return screen


def rocket_thumbnail(parts, height: int) -> pygame.Surface:
    """The rocket, once, small enough for a cabinet screen."""
    box = pygame.Surface(ROCKET_BOX, pygame.SRCALPHA)
    draw_rocket(box, parts, len(parts), origin=(0, 0))
    scale = height / ROCKET_BOX[1]
    return pygame.transform.smoothscale(box, (int(ROCKET_BOX[0] * scale), height))


def draw_mini_court(surface, rect: pygame.Rect, now: float) -> None:
    """The tennis cabinet's screen: a rally that never ends."""
    inset = rect.inflate(-36, -30)
    corners = [
        (inset.centerx - inset.width * 0.22, inset.top),
        (inset.centerx + inset.width * 0.22, inset.top),
        (inset.right, inset.bottom),
        (inset.left, inset.bottom),
    ]
    pygame.draw.polygon(surface, COURT, corners)
    pygame.draw.polygon(surface, COURT_LINE, corners, width=2)
    travel = (1 - math.cos(now * 1.8)) / 2
    x = inset.centerx + math.sin(now * 0.9) * inset.width * 0.18 * travel
    y = inset.top + inset.height * travel
    pygame.draw.circle(surface, BALL, (int(x), int(y)), int(4 + 9 * travel))
