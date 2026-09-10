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
PANEL_DARK = (20, 24, 46)
PANEL_LIT = (32, 38, 72)
VAULT = (16, 38, 46)  # the panel behind the intercepted lines
VAULT_LINE = (96, 206, 190)
STEEL = (150, 162, 186)
DOOR_FACE = (58, 66, 94)  # the safe's plate: gunmetal, not the panel blue
DOOR_EDGE = (112, 124, 158)
DOOR_DARK = (30, 34, 54)
BRASS = (206, 158, 74)
CHAMBER = (8, 10, 20)  # inside the safe, where no light has been
WALL = (20, 22, 40)
GOLD_DARK = (188, 132, 36)
GEM_RED = (226, 84, 104)
GEM_BLUE = (96, 160, 236)
GEM_GREEN = (96, 214, 150)

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


PIPS = 10  # the widest the row gets; a hundred of them is a texture, not a count


def draw_progress(surface, font, done: int, total: int, noun: str = "parts", per: int = 1) -> None:
    """A row of pips and the count itself.

    One pip per part while the parts are few, and a tenth of the way each once
    they are not: football counts in yards, so a pip is ten of them and the
    number beside it is the yard line he is actually on.
    """
    pips = min(total, PIPS)
    for index in range(pips):
        rect = pygame.Rect(700 + index * 46, 96, 34, 14)
        lit = index < done * pips // total
        pygame.draw.rect(surface, GOOD if lit else PANEL, rect, border_radius=7)
    text(surface, font, f"{done * per} / {total * per} {noun}", (880, 60), DIM)


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


CABINET_HEIGHT = 440  # what the offsets below were drawn against


def cabinet_parts(rect: pygame.Rect) -> tuple[pygame.Rect, pygame.Rect, pygame.Rect]:
    """Marquee, screen and control panel, scaled to whatever height is given.

    Four cabinets in a 2x2 grid are half as tall as two side by side, and the
    original absolute offsets gave the panel a negative height below about 380
    — which pygame draws inverted or not at all. Scaling by the height they
    were drawn against reproduces the original cabinet exactly at 440.
    """
    scale = rect.height / CABINET_HEIGHT
    marquee = pygame.Rect(rect.x + 24, rect.y + int(20 * scale), rect.width - 48, int(62 * scale))
    screen = pygame.Rect(
        rect.x + 30, marquee.bottom + int(18 * scale), rect.width - 60, int(236 * scale)
    )
    panel = pygame.Rect(
        rect.x + 30,
        screen.bottom + int(20 * scale),
        rect.width - 60,
        rect.bottom - screen.bottom - int(44 * scale),
    )
    return marquee, screen, panel


def draw_cabinet(
    surface, title_font, rect: pygame.Rect, title: str, hovered: bool, dimmed: bool = False
) -> pygame.Rect:
    """A cabinet, returning the screen rect for the caller to fill with art."""
    scale = rect.height / CABINET_HEIGHT
    marquee, screen, panel = cabinet_parts(rect)
    draw_card(surface, rect, CABINET, hovered, dimmed)
    pygame.draw.rect(surface, SPACE if dimmed else PANEL, marquee, border_radius=12)
    text(surface, title_font, title, marquee.center, DIM if dimmed else ACCENT if hovered else INK)
    pygame.draw.rect(surface, SPACE, screen, border_radius=10)
    pygame.draw.rect(surface, PANEL, screen, width=3, border_radius=10)
    if dimmed:
        return screen
    pygame.draw.rect(surface, PANEL, panel, border_radius=10)
    for index in range(4):
        pygame.draw.circle(
            surface,
            (ACCENT, GOOD, BAD, HULL)[index],
            (panel.x + int((34 + index * 42) * scale), panel.centery),
            max(3, int(11 * scale)),
        )
    return screen


# --- the safe ---------------------------------------------------------------
# The whole left column is one door he is working on all round: the intercepted
# lines behind its glass, the combination on its face, and the dial and bolts
# below them. It is drawn as a door rather than a readout because this is the
# one mode with no clock and no object being built — see `plan.md`, *the maths
# has to be the reward*. The rect names are `CODE_*`: `PANEL` is a colour, and a
# rect of the same name silently replaced it once already.
CODE_DOOR = pygame.Rect(16, 148, 676, 644)
CODE_PANEL = pygame.Rect(76, 210, 548, 434)
LOCK_ROW = pygame.Rect(76, 660, 548, 116)
#: A hint covers the glass, and needs about 470px for two routes. Not
#: `CODE_PANEL` itself: the panel is sized for six lines, and tying the hint to
#: it means retuning the lines squeezes the number line. It clears the alarm
#: lamps above and the combination below, both of which stay readable under it.
CODE_HINT = pygame.Rect(52, 198, 604, 470)
#: Behind the door, revealed as it swings. Inset only by the frame: the rail,
#: the combination and the dial are all *on* the door and go with it.
CODE_CHAMBER = CODE_DOOR.inflate(-40, -40)
_LINE_HEIGHT = 62
_HINGE = 30  # how far the hinge barrels sit in from the door's left edge


def line_rows(count: int) -> tuple[pygame.Rect, ...]:
    """Where each line of the current lock sits.

    Centred as a block rather than filled from the top, so a four-line lock and
    a six-line lock both look deliberate instead of leaving a hole underneath.
    """
    top = CODE_PANEL.centery - count * _LINE_HEIGHT // 2
    return tuple(
        pygame.Rect(CODE_PANEL.x + 20, top + index * _LINE_HEIGHT, CODE_PANEL.width - 40, _LINE_HEIGHT - 8)
        for index in range(count)
    )


def draw_bolts(surface, opening: float) -> None:
    """Three bolts in the rim opposite the hinges, drawn back as a lock opens.

    They sit in the rim rather than beside the combination so that the side the
    door is held shut on is the side that visibly lets go — and they are drawn
    after the glass, or the retracted position is behind it.
    """
    for index in range(3):
        bolt = pygame.Rect(0, 0, 34, 26)
        bolt.center = (CODE_DOOR.right - 24 - int(16 * opening), 300 + index * 150)
        pygame.draw.rect(surface, GOOD if opening > 0 else STEEL, bolt, border_radius=6)
        pygame.draw.rect(surface, DOOR_DARK, bolt, width=2, border_radius=6)


def _hinges(surface) -> None:
    for y in (300, 600):
        barrel = pygame.Rect(0, 0, 30, 96)
        barrel.center = (CODE_DOOR.left + _HINGE, y)
        pygame.draw.rect(surface, DOOR_EDGE, barrel, border_radius=14)
        pygame.draw.rect(surface, DOOR_DARK, barrel, width=3, border_radius=14)
        pygame.draw.circle(surface, DOOR_DARK, barrel.center, 6)


def draw_door(surface, small, lock: int, locks: int, tripped: int, alarms: int) -> None:
    """The safe's face: the frame, its hinges, its bolts, and the alarm lamps.

    The lamps are on the door rather than in a corner of the screen because a
    wrong answer should light up the thing he is trying to open, and because the
    labelled row they replace was the last of the old readout the safe stands in
    for.
    """
    pygame.draw.rect(surface, DOOR_FACE, CODE_DOOR, border_radius=22)
    pygame.draw.rect(surface, DOOR_EDGE, CODE_DOOR, width=4, border_radius=22)
    pygame.draw.rect(surface, DOOR_DARK, CODE_DOOR.inflate(-24, -24), width=3, border_radius=16)
    for x in range(CODE_DOOR.left + 60, CODE_DOOR.right - 40, 84):
        pygame.draw.circle(surface, DOOR_EDGE, (x, CODE_DOOR.top + 12), 4)
        pygame.draw.circle(surface, DOOR_EDGE, (x, CODE_DOOR.bottom - 12), 4)
    _hinges(surface)

    rail = CODE_DOOR.top + 32
    text(surface, small, f"LOCK {lock + 1} OF {locks}", (CODE_DOOR.left + 180, rail), DIM)
    text(surface, small, "ALARMS", (424, rail), DIM)
    for index in range(alarms):
        centre = (528 + index * 46, rail)
        pygame.draw.circle(surface, BAD if index < tripped else DOOR_DARK, centre, 15)
        pygame.draw.circle(surface, DOOR_EDGE, centre, 15, width=3)
        if index < tripped:
            pygame.draw.circle(surface, INK, centre, 6)


def draw_panel(surface, font, lines, active: int) -> None:
    """The glass, and what is behind it: what is open, what he is on, what is dark.

    `lines` is every line of this lock in order, each one either a solved
    sentence or an unsolved one; `active` is which of them is his now. An
    unsolved line below the active one is drawn as a bare row with no numbers on
    it — the transmissions have not been decoded yet, and showing them early
    turns a lock into a worksheet he can read ahead on.
    """
    pygame.draw.rect(surface, VAULT, CODE_PANEL, border_radius=16)
    pygame.draw.rect(surface, VAULT_LINE, CODE_PANEL, width=3, border_radius=16)

    for row, (rect, line) in enumerate(zip(line_rows(len(lines)), lines)):
        done = row < active
        if row > active:
            # Still encrypted: a row of blocks, so he can see how much is left
            # without being able to work ahead.
            for block in range(7):
                pygame.draw.rect(
                    surface,
                    PANEL_DARK,
                    pygame.Rect(rect.x + 30 + block * 34, rect.centery - 7, 24, 14),
                    border_radius=4,
                )
            continue
        pygame.draw.rect(surface, SPACE if done else PANEL_LIT, rect, border_radius=10)
        if not done:
            pygame.draw.rect(surface, ACCENT, rect, width=3, border_radius=10)
        text(
            surface,
            font,
            line.filled if done else line.prompt,
            (rect.centerx - 30, rect.centery),
            GOOD if done else INK,
        )
        if done:
            pygame.draw.circle(surface, GOOD, (rect.right - 30, rect.centery), 11)


def draw_dial(surface, centre: tuple[int, int], radius: int, turn: float) -> None:
    """The dial, at rest between answers and turning on each one.

    `turn` is in radians and comes from how much of the combination is in, so
    the motion says what he just did rather than running on the wall clock the
    way the cabinet's dial does.
    """
    pygame.draw.circle(surface, DOOR_EDGE, centre, radius)
    pygame.draw.circle(surface, DOOR_DARK, centre, radius - 6)
    pygame.draw.circle(surface, BRASS, centre, radius, width=4)
    for notch in range(12):
        angle = turn + notch * math.pi / 6
        inner = radius - 14
        pygame.draw.line(
            surface,
            BRASS,
            (centre[0] + math.cos(angle) * inner, centre[1] + math.sin(angle) * inner),
            (centre[0] + math.cos(angle) * (radius - 6), centre[1] + math.sin(angle) * (radius - 6)),
            3,
        )
    pygame.draw.line(
        surface,
        INK,
        centre,
        (centre[0] + math.cos(turn) * (radius - 12), centre[1] + math.sin(turn) * (radius - 12)),
        5,
    )
    pygame.draw.circle(surface, BRASS, centre, 7)
    # The index mark the combination is read against: fixed, so the dial turning
    # under it is what reads as motion.
    pygame.draw.polygon(
        surface,
        INK,
        [
            (centre[0] - 7, centre[1] - radius - 4),
            (centre[0] + 7, centre[1] - radius - 4),
            (centre[0], centre[1] - radius + 8),
        ],
    )


def draw_lock(surface, font, small, digits, size: int, opening: float = 0.0) -> None:
    """The combination as it fills, one cell per line of the lock, and the dial.

    A cracked lock is held with its digits still showing — see `App.opening`.
    The numbers he worked out are the reward, and the frame that cleared them to
    animate a bar over the empty row was showing him the code being erased.
    """
    # Beside the cells rather than over them: a heading above the row would sit
    # under the hint box, which covers the glass down to the top of this row.
    text(surface, small, "CODE", (LOCK_ROW.left + 36, LOCK_ROW.top + 72), DIM)
    width, gap = 56, 10
    span = size * width + (size - 1) * gap
    left = LOCK_ROW.centerx - span // 2
    for index in range(size):
        cell = pygame.Rect(left + index * (width + gap), LOCK_ROW.top + 40, width, 64)
        filled = index < len(digits)
        pygame.draw.rect(surface, PANEL_LIT if filled else PANEL_DARK, cell, border_radius=8)
        pygame.draw.rect(
            surface,
            GOOD if opening > 0 else ACCENT if filled else STEEL,
            cell,
            width=3,
            border_radius=8,
        )
        if filled:
            text(surface, font, str(digits[index]), cell.center, GOOD if opening > 0 else ACCENT)
    # A notch per number in, and a fast spin as the bolts go back.
    draw_dial(surface, (588, LOCK_ROW.top + 72), 40, len(digits) * 0.9 + opening * 7.0)


#: Gold, coins and gems, at fixed spots: a hoard that reshuffled every frame
#: would shimmer rather than sit there.
_SHELF = 470  # a second ledge, so the chamber is stocked rather than floored
_BARS = (
    (188, 664), (268, 664), (348, 664), (228, 620), (308, 620), (268, 576), (438, 664),
    (232, _SHELF), (312, _SHELF), (272, _SHELF - 40),
)
_COINS = (
    (132, 700), (176, 708), (222, 702), (426, 704), (470, 694), (512, 706), (556, 692),
    (596, 704), (152, 662), (424, _SHELF - 20), (468, _SHELF - 14), (150, _SHELF - 20),
)
_GEMS = (
    (404, 624, GEM_RED), (486, 638, GEM_BLUE), (534, 620, GEM_GREEN), (146, 630, GEM_BLUE),
    (588, 646, GEM_RED), (526, _SHELF - 20, GEM_BLUE), (566, _SHELF - 18, GEM_GREEN),
)


def draw_treasure(surface, swing: float) -> None:
    """What is inside, and the door leaf swinging off it.

    `swing` runs 0 to 1. The leaf is the door's own face with its width taken
    away toward the hinges, which is what a door opening away from you does on
    screen; it is drawn over the hoard so that it covers it until it is out of
    the way.
    """
    # The face is repainted first: everything `render_code` drew on it — the
    # rail, the glass, the combination, the dial — is on the door, and a door
    # that has swung away cannot still be showing them.
    pygame.draw.rect(surface, DOOR_FACE, CODE_DOOR, border_radius=22)
    pygame.draw.rect(surface, DOOR_EDGE, CODE_DOOR, width=4, border_radius=22)
    pygame.draw.rect(surface, CHAMBER, CODE_CHAMBER, border_radius=12)
    pygame.draw.rect(surface, DOOR_DARK, CODE_CHAMBER, width=4, border_radius=12)
    # A back wall short of the opening, so the chamber has a depth to it.
    pygame.draw.rect(surface, WALL, CODE_CHAMBER.inflate(-56, -56), border_radius=8)
    for ledge in (_SHELF, 716):
        pygame.draw.rect(
            surface, DOOR_DARK, pygame.Rect(CODE_CHAMBER.left + 20, ledge, CODE_CHAMBER.width - 40, 14)
        )
    for bar_x, bar_y in _BARS:
        pygame.draw.polygon(
            surface,
            ACCENT,
            [(bar_x, bar_y), (bar_x + 76, bar_y), (bar_x + 66, bar_y - 40), (bar_x + 10, bar_y - 40)],
        )
        pygame.draw.polygon(
            surface,
            GOLD_DARK,
            [(bar_x, bar_y), (bar_x + 76, bar_y), (bar_x + 66, bar_y - 40), (bar_x + 10, bar_y - 40)],
            width=3,
        )
    for coin_x, coin_y in _COINS:
        pygame.draw.circle(surface, ACCENT, (coin_x, coin_y), 20)
        pygame.draw.circle(surface, GOLD_DARK, (coin_x, coin_y), 20, width=3)
        pygame.draw.circle(surface, GOLD_DARK, (coin_x, coin_y), 8, width=2)
    for gem_x, gem_y, colour in _GEMS:
        pygame.draw.polygon(
            surface,
            colour,
            [(gem_x, gem_y - 20), (gem_x + 18, gem_y), (gem_x, gem_y + 20), (gem_x - 18, gem_y)],
        )
        pygame.draw.polygon(surface, INK, [(gem_x, gem_y - 20), (gem_x + 18, gem_y), (gem_x - 18, gem_y)], width=2)

    if swing < 1.0:
        leaf = pygame.Rect(
            CODE_DOOR.left, CODE_DOOR.top, max(8, int(CODE_DOOR.width * (1 - swing))), CODE_DOOR.height
        )
        pygame.draw.rect(surface, DOOR_FACE, leaf, border_radius=22)
        pygame.draw.rect(surface, DOOR_EDGE, leaf, width=4, border_radius=22)
        # The edge of the leaf, which is the only part of it with any thickness.
        pygame.draw.rect(surface, DOOR_EDGE, pygame.Rect(leaf.right - 12, leaf.top + 10, 12, leaf.height - 20))
    # Last, and on both paths: the hinges are what the leaf is still attached to,
    # so a leaf drawn over them reads as a slab sliding sideways.
    _hinges(surface)


def draw_vault(surface, rect: pygame.Rect, open_by: float = 0.0) -> None:
    """A round vault door, for the cabinet screen.

    Not the door he plays against: that one wraps a 584-wide panel and is
    rectangular. This one has to read at 200px on a cabinet, where a turning
    dial does and a rectangular box does not.
    """
    radius = min(rect.width, rect.height) // 2 - 6
    centre = rect.center
    pygame.draw.circle(surface, STEEL, centre, radius)
    pygame.draw.circle(surface, VAULT, centre, radius, width=max(2, radius // 8))
    pygame.draw.circle(surface, VAULT_LINE, centre, max(4, radius // 3), width=3)
    for spoke in range(4):
        angle = spoke * math.pi / 2 + open_by * math.pi
        pygame.draw.line(
            surface,
            VAULT,
            centre,
            (centre[0] + math.cos(angle) * radius * 0.8, centre[1] + math.sin(angle) * radius * 0.8),
            5,
        )


def draw_mini_vault(surface, rect: pygame.Rect, now: float) -> None:
    """The cabinet's screen: a dial turning, forever."""
    inset = rect.inflate(-int(rect.width * 0.3), -int(rect.height * 0.12))
    draw_vault(surface, inset, (1 - math.cos(now * 1.1)) / 2)


def rocket_thumbnail(parts, height: int) -> pygame.Surface:
    """The rocket, once, small enough for a cabinet screen."""
    box = pygame.Surface(ROCKET_BOX, pygame.SRCALPHA)
    draw_rocket(box, parts, len(parts), origin=(0, 0))
    scale = height / ROCKET_BOX[1]
    return pygame.transform.smoothscale(box, (int(ROCKET_BOX[0] * scale), height))


def draw_mini_court(surface, rect: pygame.Rect, now: float) -> None:
    """The tennis cabinet's screen: a rally that never ends."""
    # Proportional: at half a cabinet's height a fixed inset is most of the screen.
    inset = rect.inflate(-int(rect.width * 0.09), -int(rect.height * 0.13))
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


# --- the football field -----------------------------------------------------
# Full width across the top, with everything he types below it. The line gets
# ten pixels a yard that way instead of five, which is what makes a placement a
# judgement rather than a guess at which half of a stripe he is on.
#
# Nothing marks it but the two goal lines and the 50. Yard stripes were tried
# and taken out again: they are what a real field looks like, and they are also
# a benchmark to count along instead of a distance to judge. `STRIPE_EVERY = 5`
# puts them back.

FIELD = pygame.Rect(60, 150, 1160, 236)
END_ZONE = 60  # beyond each goal line, so 0 and 100 are not against the edge
GRASS = (26, 78, 52)
GRASS_DARK = (18, 58, 40)
STRIPE = (44, 104, 72)  # the yard lines, in green: present, not shouting
STRIPE_TEN = (58, 124, 88)
STRIPE_EVERY = None  # yards between stripes; None for the bare line

PIGSKIN = (146, 84, 48)
PIGSKIN_DARK = (104, 58, 32)
JERSEY = (232, 236, 248)
JERSEY_DARK = (60, 96, 190)
SKIN = (222, 176, 132)

#: Below the field: the ball coming in, then the question, then the keypad.
CATCH = pygame.Rect(66, 400, 330, 392)
#: A finished play owns the whole band — the keypad is not drawn while it shows.
VERDICT = pygame.Rect(60, 400, 1160, 392)

RUNNER_HEIGHT = 46  # feet on the yard line, so the sprite reads as standing on it


def _football(surface, centre: tuple[float, float], size: float) -> None:
    """Brown, with the white ring and the laces — at any size down to a pip."""
    box = pygame.Rect(0, 0, max(3, int(size)), max(2, int(size * 0.62)))
    box.center = (int(centre[0]), int(centre[1]))
    pygame.draw.ellipse(surface, PIGSKIN, box)
    pygame.draw.ellipse(surface, PIGSKIN_DARK, box, width=max(1, int(size * 0.05)))
    if size < 26:
        return  # below this the markings are one grey smear
    thick = max(1, int(size * 0.045))
    for side in (-1, 1):  # the rings around each end
        x = box.centerx + side * box.width * 0.3
        pygame.draw.line(
            surface, INK, (x, box.centery - box.height * 0.24), (x, box.centery + box.height * 0.24), thick
        )
    pygame.draw.line(
        surface, INK, (box.centerx - box.width * 0.15, box.centery),
        (box.centerx + box.width * 0.15, box.centery), thick
    )
    for index in (-1, 0, 1):  # the laces
        x = box.centerx + index * box.width * 0.09
        pygame.draw.line(
            surface, INK, (x, box.centery - box.height * 0.13), (x, box.centery + box.height * 0.13), thick
        )


def _runner(surface, x: int, feet_y: int, height: float, now: float, carrying: bool = True) -> None:
    """The ball carrier, as the arcade football games drew him: eight blocks
    tall, two frames of run cycle, facing the end zone he is running at.

    Rectangles rather than curves. At this size a rounded figure is a blob, and
    the blocky one is legible down to a cabinet screen — which is where the same
    sprite runs. The helmet is narrower than the shoulders and the legs are
    narrower again, because that silhouette is what says *football player* at
    fifty pixels tall; colour alone does not.

    `carrying` off is the receiver waiting under a pass: both arms up, and
    nothing in them yet.
    """
    unit = height / 8
    stride = int(now * 7) % 2  # two frames, swapped fast enough to read as a run
    top = feet_y - height + (unit * 0.3 if stride else 0)

    def block(left, up, wide, tall, colour) -> None:
        pygame.draw.rect(
            surface,
            colour,
            pygame.Rect(
                int(x + left * unit),
                int(top + up * unit),
                max(1, int(wide * unit)),
                max(1, int(tall * unit)),
            ),
        )

    # Legs first, so the jersey overlaps them at the hip. One leg is planted and
    # the other is off the ground in both frames; they swap.
    if stride:
        block(-1.7, 5.0, 1.2, 3.0, JERSEY_DARK)
        block(0.5, 5.0, 1.2, 2.2, JERSEY_DARK)
        block(0.5, 6.6, 1.9, 0.8, JERSEY_DARK)  # the lifted knee, driving forward
    else:
        block(-1.6, 5.0, 1.2, 2.2, JERSEY_DARK)
        block(0.5, 5.0, 1.2, 3.0, JERSEY_DARK)
        block(-2.6, 6.7, 1.9, 0.8, JERSEY_DARK)  # and trailing behind

    block(-1.9, 2.1, 3.8, 2.9, JERSEY)  # shoulders, wider than the helmet
    block(-1.9, 3.1, 3.8, 0.6, JERSEY_DARK)  # the stripe across the numbers
    if carrying:
        # The arm tucks the ball against the ribs, which is what makes him a
        # ball carrier rather than a man standing on a line.
        block(1.4, 3.4, 1.3, 0.8, SKIN)
        _football(surface, (x + 2.9 * unit, top + 3.8 * unit), 1.9 * unit)
    else:
        for side in (-2.6, 1.9):  # both arms up, waiting for it
            block(side, 0.6, 0.7, 1.9, SKIN)
    block(-1.3, 0.1, 2.9, 2.1, BAD)  # helmet, set forward on the shoulders
    block(0.9, 1.2, 1.4, 0.5, JERSEY)  # facemask, on the side he is running toward


def field_x(yards: float, span: int) -> int:
    """Where a yard number sits across the field. The one mapping, both ways."""
    playable = FIELD.width - 2 * END_ZONE
    return int(FIELD.left + END_ZONE + playable * max(0.0, min(1.0, yards / span)))


def field_yards(position: tuple[int, int], span: int) -> int | None:
    """A click in design space, as a yard number. None if it missed the field.

    Vertically generous: he is aiming at a horizontal position, and a throw
    that reads as on the line should not be lost for being an inch high.
    """
    x, y = position
    if not FIELD.inflate(0, 40).collidepoint(x, y):
        return None
    playable = FIELD.width - 2 * END_ZONE
    # Clamped: the end zones are inside the field rect, and a click in one is
    # a throw to the goal line rather than a throw off the line entirely.
    return max(0, min(span, round(span * (x - FIELD.left - END_ZONE) / playable)))


def _pennant(surface, x: int, y: int, colour, size: int = 10) -> None:
    pygame.draw.polygon(surface, colour, [(x, y), (x - size, y - size), (x + size, y - size)])


def draw_field(surface, label_font, span: int, yards: int, throw, now: float, jump=None) -> None:
    """The drive: the line, and the ball carrier standing where it has reached.

    `throw` is (aimed, called) from the last placement, held for a moment so he
    sees the two side by side. That comparison is the whole teaching moment;
    without it a wide throw is only a noise.

    `jump` is (from, to) after a sack, drawn as a labelled hop backwards — the
    same picture `draw_number_line` draws over a missed fact, because it is the
    same thing: a subtraction with the line underneath it.
    """
    pygame.draw.rect(surface, GRASS, FIELD, border_radius=8)
    for zone in (
        pygame.Rect(FIELD.left, FIELD.top, END_ZONE, FIELD.height),
        pygame.Rect(FIELD.right - END_ZONE, FIELD.top, END_ZONE, FIELD.height),
    ):
        pygame.draw.rect(surface, GRASS_DARK, zone, border_radius=8)

    line_y = FIELD.centery + 14
    left, right = field_x(0, span), field_x(span, span)
    if STRIPE_EVERY:
        for value in range(STRIPE_EVERY, span, STRIPE_EVERY):
            x = field_x(value, span)
            ten = value % 10 == 0
            pygame.draw.line(
                surface,
                STRIPE_TEN if ten else STRIPE,
                (x, FIELD.top + 12),
                (x, FIELD.bottom - 12),
                2 if ten else 1,
            )
    pygame.draw.line(surface, COURT_LINE, (left, line_y), (right, line_y), 4)
    for value in (0, span):
        x = field_x(value, span)
        pygame.draw.line(surface, COURT_LINE, (x, FIELD.top + 16), (x, FIELD.bottom - 52), 5)
        text(surface, label_font, str(value), (x, FIELD.bottom - 26), COURT_LINE)
    middle = field_x(span // 2, span)
    pygame.draw.line(surface, COURT_LINE, (middle, line_y - 22), (middle, line_y + 22), 3)

    if jump is not None:
        start, end = field_x(jump[0], span), field_x(jump[1], span)
        peak = line_y - 54
        pygame.draw.lines(
            surface, BAD, False, [(start, line_y), ((start + end) // 2, peak), (end, line_y)], 4
        )
        text(surface, label_font, f"-{jump[0] - jump[1]}", ((start + end) // 2, peak - 22), BAD)

    _runner(surface, field_x(yards, span), line_y + 3, RUNNER_HEIGHT, now)

    if throw is not None:
        aimed, called = throw
        _pennant(surface, field_x(called, span), line_y - 26, GOOD)
        _pennant(surface, field_x(aimed, span), line_y + 38, INK)
        pygame.draw.line(
            surface,
            INK,
            (field_x(aimed, span), line_y + 28),
            (field_x(called, span), line_y - 16),
            2,
        )


def draw_gridiron(surface, rect: pygame.Rect, now: float) -> None:
    """The football cabinet's screen: the same runner, never tackled."""
    inset = rect.inflate(-int(rect.width * 0.09), -int(rect.height * 0.13))
    pygame.draw.rect(surface, GRASS, inset, border_radius=6)
    pygame.draw.line(
        surface, COURT_LINE, (inset.centerx, inset.top), (inset.centerx, inset.bottom), 2
    )
    for side in (inset.left + 6, inset.right - 6):
        pygame.draw.line(surface, COURT_LINE, (side, inset.top), (side, inset.bottom), 3)
    share = (now * 0.28) % 1.0
    _runner(
        surface,
        int(inset.left + inset.width * share),
        inset.centery + int(inset.height * 0.2),
        inset.height * 0.4,
        now,
    )


def draw_attempts(surface, font, adrift: int, lives: int) -> None:
    """Placements thrown or picked wide, under the Back button and above the
    field. Both kinds count: the rule is that a placement more than the
    tolerance out costs an attempt, whatever the play was.

    Filled from the left as they are spent, the same reading as the tennis
    scoreboard: what is left is what is not red yet.
    """
    text(surface, font, "misses", (86, 128), DIM)
    for index in range(lives):
        pygame.draw.circle(surface, BAD if index < adrift else PANEL, (150 + index * 36, 128), 12)


def draw_call(surface, font, label_font, target: int, rect=CATCH) -> None:
    """The yard he is being asked for, where his hands are about to be."""
    text(surface, label_font, "throw to the", (rect.centerx, rect.top + 60), DIM)
    text(surface, font, str(target), (rect.centerx, rect.top + 140), ACCENT)
    text(surface, label_font, "click the field", (rect.centerx, rect.top + 220), DIM)


#: The panel that explains a miss. Self-paced, so it owns the band below the
#: field on its own — the keypad is not drawn while a placement is due.
REVIEW = pygame.Rect(100, 500, 1080, 140)


def _review_x(value: float, span: int, rect: pygame.Rect) -> int:
    return int(rect.left + 40 + (rect.width - 80) * max(0, min(span, value)) / span)


def draw_miss(surface, font, label_font, span: int, called: int, aimed: int, tolerance: int,
              rect=REVIEW) -> None:
    """Why the pass fell incomplete: the window it had to land in, and where it
    actually went.

    The same 0-100 span as the field above it, never rescaled to the two numbers
    at hand — a window that changed size between misses would teach that six
    yards is however wide it looks today.
    """
    y = rect.centery
    left, right = _review_x(0, span, rect), _review_x(span, span, rect)
    pygame.draw.line(surface, DIM, (left, y), (right, y), 3)
    for value in (0, span):
        x = _review_x(value, span, rect)
        pygame.draw.line(surface, DIM, (x, y - 12), (x, y + 12), 3)
        # Below where his own mark is labelled, so a miss near an end of the
        # line does not print one number on top of the other.
        text(surface, label_font, str(value), (x, y + 64), DIM)

    thrown = _review_x(aimed, span, rect)
    middle = _review_x(called, span, rect)
    # The gap first, so the window is drawn over the run into it: what is left
    # red is exactly how far outside the green he was.
    pygame.draw.line(surface, BAD, (thrown, y), (middle, y), 3)

    low = _review_x(called - tolerance, span, rect)
    high = _review_x(called + tolerance, span, rect)
    pygame.draw.rect(surface, GOOD, pygame.Rect(low, y - 14, max(4, high - low), 28), border_radius=6)
    pygame.draw.line(surface, INK, (middle, y - 28), (middle, y + 28), 3)
    text(surface, label_font, str(called), (middle, y - 50), GOOD)

    pygame.draw.circle(surface, BAD, (thrown, y), 12)
    text(surface, label_font, str(aimed), (thrown, y + 40), BAD)


def draw_sack_call(surface, font, label_font, loss: int, rect=VERDICT) -> None:
    """A sack: what it cost, and the question that is really being asked.

    The band, not the corner the throw call uses — there is no ball coming in to
    leave room for, and the sentence is the whole play.
    """
    text(surface, font, f"SACKED! back {loss} yards", (rect.centerx, rect.top + 60), BAD)
    text(surface, label_font, "click where that leaves you", (rect.centerx, rect.top + 130), DIM)


def draw_verdict(surface, font, label_font, word: str, colour, aside: str, rect=VERDICT) -> None:
    """How the play ended, held for a beat before the next call.

    The beat is the point: the two pennants are still on the field, and a fresh
    number appearing beside them would be read as pointing at one of them.
    """
    text(surface, font, word, (rect.centerx, rect.top + 130), colour)
    text(surface, label_font, aside, (rect.centerx, rect.top + 196), DIM)


def draw_incoming(surface, closeness: float, now: float, rect=CATCH) -> None:
    """The pass on its way down, and the receiver under it.

    It grows as its time runs out — the same reading as the saucer, and for the
    same reason: he is looking at the keypad, and a thing getting bigger in the
    corner of his eye is the only clock he will notice.
    """
    close = max(0.0, min(1.0, closeness))
    feet = rect.bottom - 30
    _runner(surface, rect.centerx, feet, 108, now, carrying=False)
    hands = feet - 116
    _football(
        surface,
        (rect.centerx, rect.top + 40 + (hands - rect.top - 40) * close * close),
        16 + 74 * close,
    )


# --- the number line --------------------------------------------------------
# The picture drawn on a miss. It gets the left half, which every mode leaves
# to it: the rocket sits at x 110-410 behind it, the court spans x 75-625, the
# field x 80-660, and the keypad at x >= 700 stays clear — which matters, because in tennis he
# retypes the same answer while the hint is up.

HINT_BOX = pygame.Rect(60, 220, 600, 420)
HINT_MARGIN = 56  # room for the end labels, which sit under the outermost dots


@dataclass(frozen=True)
class Layout:
    """Where the words go on the play screen.

    Two of the three modes draw their art on the left and type on the right;
    football's field runs the whole width, so everything it types sits under the
    field instead, and its hint lands over the field's left half — which is free
    for it, because a hint stops the ball dead anyway.
    """

    prompt: tuple[int, int]
    entry: pygame.Rect
    hint: pygame.Rect
    banner: tuple[int, int]  # how the round ended; its one line of detail sits below


CLASSIC = Layout((940, 210), pygame.Rect(840, 280, 200, 96), HINT_BOX, (910, 320))
#: The panel owns the prompt — the line he is on is drawn in place, in the list
#: — so `prompt` here is only where a hint's title would go. Everything he types
#: is to the right, the way the rocket and the court are laid out.
#: `prompt` is never drawn in this mode — the panel draws the line he is on, in
#: place — so it is only where a hint's title would go. The banner sits high in
#: the door so that the hoard behind it has the rest of the opening to itself.
CODEBREAK = Layout(
    (CODE_PANEL.centerx, CODE_PANEL.top - 40),
    pygame.Rect(840, 280, 200, 96),
    CODE_HINT,  # over the door, which is dead while a hint is up
    (CODE_PANEL.centerx, 262),
)
DOWNFIELD = Layout(
    (516, 432),
    pygame.Rect(416, 466, 200, 96),
    pygame.Rect(60, 150, 620, 236),
    (390, 500),  # left of the Try again row, and clear of the field above it
)
#: The one mode with nothing to type. `entry` is an empty rect because there is
#: no box: the click on the ice is the whole answer, and `render_entry` — which
#: is what would draw one — is never reached while a placement is due, which in
#: this mode is always.
ONICE = Layout(
    (640, 470),
    pygame.Rect(0, 0, 0, 0),
    HINT_BOX,
    (400, 500),  # left of the Try again row, as the field's is
)


def _hint_positions(strategy) -> tuple[int, ...]:
    place = strategy.start
    places = [place]
    for jump in strategy.jumps:
        place += jump
        places.append(place)
    return tuple(places)


def _route(surface, label_font, strategy, baseline: int, at, colour) -> int:
    """One side's hops and dots on a given baseline. Returns where it landed."""
    places = _hint_positions(strategy)
    for index, jump in enumerate(strategy.jumps):
        start_x, end_x = at(places[index]), at(places[index + 1])
        peak = baseline - 34
        pygame.draw.lines(
            surface,
            colour,
            False,
            [(start_x, baseline), ((start_x + end_x) // 2, peak), (end_x, baseline)],
            4,
        )
        sign = "+" if jump >= 0 else "−"
        text(surface, label_font, f"{sign}{abs(jump)}", ((start_x + end_x) // 2, peak - 16), colour)
    for index, place in enumerate(places):
        last = index == len(places) - 1
        pygame.draw.circle(surface, colour if last else HULL, (at(place), baseline), 9 if last else 6)
    text(surface, label_font, str(places[-1]), (at(places[-1]), baseline + 24), colour)
    return places[-1]


def draw_two_routes(surface, font, label_font, strategies, prompt: str, rect=HINT_BOX) -> None:
    """Both sides of a sentence, over one shared span.

    The span is shared on purpose: two lines each scaled to their own numbers
    would draw `7 + 6` and `9 + 5` landing in the same place, which is the exact
    opposite of what the picture is for. Over one span the gap between 13 and 14
    is a distance he can see, and that gap is the whole lesson.
    """
    pygame.draw.rect(surface, PANEL, rect, border_radius=18)
    pygame.draw.rect(surface, ACCENT, rect, width=3, border_radius=18)
    text(surface, font, prompt, (rect.centerx, rect.top + 44), INK)

    places = [place for strategy in strategies for place in _hint_positions(strategy)]
    low, high = min(places), max(places)
    left, right = rect.left + HINT_MARGIN, rect.right - HINT_MARGIN

    def at(value: int) -> int:
        if high == low:
            return rect.centerx
        return int(left + (right - left) * (value - low) / (high - low))

    # Proportional to the box: the two routes plus their labels need most of it,
    # and fixed offsets put the first arc through the prompt in anything short.
    ends = []
    for index, strategy in enumerate(strategies):
        baseline = int(rect.top + rect.height * (0.42 + 0.30 * index))
        pygame.draw.line(surface, DIM, (rect.left + 30, baseline), (rect.right - 30, baseline), 3)
        ends.append(_route(surface, label_font, strategy, baseline, at, ACCENT))

    same = ends[0] == ends[1]
    verdict = (
        f"both land on {ends[0]}"
        if same
        else f"{ends[0]} and {ends[1]} — not the same"
    )
    text(surface, label_font, verdict, (rect.centerx, rect.bottom - 44), GOOD if same else BAD)


def draw_number_line(
    surface, font, label_font, strategy, prompt: str, rect=HINT_BOX, caption: str | None = None
) -> None:
    """The route to the answer: a hop per step, labelled and signed.

    The renderer owns the span, because the domain hands over numbers only. It
    also owns the degenerate shapes those numbers really produce: a jump of zero
    (`0 + 5`, `5 - 0`), which draws as a labelled dot rather than being special
    cased away, and an empty jump list (`2 x 0`), which is a single dot.

    `caption` exists for division, the one operation whose answer is the *number
    of hops* rather than where they land: the line for `12 ÷ 2` ends on 12, and
    12 is the number he was already given. Without it the picture shows him
    everything except the thing he was asked for.
    """
    pygame.draw.rect(surface, PANEL, rect, border_radius=18)
    pygame.draw.rect(surface, ACCENT, rect, width=3, border_radius=18)
    text(surface, font, prompt, (rect.centerx, rect.top + 48), INK)

    places = _hint_positions(strategy)
    low, high = min(places), max(places)
    baseline = rect.bottom - 96
    left, right = rect.left + HINT_MARGIN, rect.right - HINT_MARGIN

    def at(value: int) -> int:
        # A line with no width to it — every hop was zero — puts its one dot in
        # the middle rather than dividing by nothing.
        if high == low:
            return rect.centerx
        return int(left + (right - left) * (value - low) / (high - low))

    pygame.draw.line(surface, DIM, (rect.left + 30, baseline), (rect.right - 30, baseline), 3)

    for index, jump in enumerate(strategy.jumps):
        start_x, end_x = at(places[index]), at(places[index + 1])
        peak = baseline - 46
        pygame.draw.lines(
            surface,
            GOOD if jump >= 0 else ACCENT,
            False,
            [(start_x, baseline), ((start_x + end_x) // 2, peak), (end_x, baseline)],
            4,
        )
        sign = "+" if jump >= 0 else "−"
        text(
            surface,
            label_font,
            f"{sign}{abs(jump)}",
            ((start_x + end_x) // 2, peak - 20),
            GOOD if jump >= 0 else ACCENT,
        )

    for index, place in enumerate(places):
        x = at(place)
        last = index == len(places) - 1
        pygame.draw.circle(surface, ACCENT if last else HULL, (x, baseline), 9 if last else 7)
        text(surface, label_font, str(place), (x, baseline + 30), ACCENT if last else DIM)

    if caption is not None:
        text(surface, label_font, caption, (rect.centerx, rect.bottom - 30), GOOD)


# --- the ice ----------------------------------------------------------------
# A sheet marked 0 to 1 and ticked into equal parts. Everything about it is
# drawn from the target's own numbers: the ticks are its partition and the house
# is exactly its tolerance wide, so the ring shrinking as denominators grow is
# the only thing on screen that says the shot got harder.

SHEET = pygame.Rect(60, 156, 1160, 254)
SHEET_EDGE = 80  # room outside the line for the 0 and 1 labels
ICE = (222, 234, 244)
ICE_DARK = (196, 212, 228)
ICE_LINE = (120, 140, 160)
HOUSE_BLUE = (74, 130, 200)
HOUSE_RED = (206, 82, 96)
GRANITE = (110, 116, 132)
GRANITE_DARK = (72, 78, 92)

#: The line the stones sit on, and how they pile up when two share a mark.
SHEET_LINE = SHEET.centery + 18
STONE_RADIUS = 17
STONE_ROW = 2 * STONE_RADIUS + 2  # how far above the line the next one stands
SWEEPER_HEIGHT = 76  # the figure at the hack, in design pixels

#: Below the ice: what he is being asked for, and nothing else. There is no
#: keypad in this mode, so the band is the call's alone.
CALL_BAND = pygame.Rect(60, 430, 1160, 300)


def sheet_x(value: float, span: int) -> int:
    """Where a position on the line sits across the ice. The one mapping, both
    ways — the sibling of `field_x`."""
    playable = SHEET.width - 2 * SHEET_EDGE
    return int(SHEET.left + SHEET_EDGE + playable * max(0.0, min(1.0, value / span)))


def sheet_units(position: tuple[int, int], span: int) -> int | None:
    """A click in design space, as a position on the line. None if it missed.

    Vertically generous for the reason `field_yards` is: he is aiming at a
    horizontal position, and a throw that reads as on the line should not be
    lost for being an inch high.
    """
    x, y = position
    if not SHEET.inflate(0, 40).collidepoint(x, y):
        return None
    playable = SHEET.width - 2 * SHEET_EDGE
    # Clamped rather than rejected: the strip outside the line is still a throw
    # at the end of it, the way a click in an end zone is a throw to the goal.
    return max(0, min(span, round(span * (x - SHEET.left - SHEET_EDGE) / playable)))


def _stone(surface, centre: tuple[int, int], radius: int, handle) -> None:
    """Granite with a coloured handle on it, which is what says *stone* rather
    than *dot* at this size."""
    x, y = int(centre[0]), int(centre[1])
    pygame.draw.circle(surface, GRANITE_DARK, (x, y + 2), radius)
    pygame.draw.circle(surface, GRANITE, (x, y), radius)
    pygame.draw.circle(surface, GRANITE_DARK, (x, y), radius, width=max(1, radius // 6))
    pygame.draw.circle(surface, handle, (x, y - int(radius * 0.15)), max(2, int(radius * 0.42)))


def _sweeper(surface, x: int, feet_y: int, height: float, now: float) -> None:
    """The figure at the hack, drawn the way the ball carrier is: eight blocks
    tall, two frames, rectangles rather than curves.

    Same idiom rather than the same function — `_runner` is a helmet, a jersey
    and a football, and parameterising all three to share the legs would be more
    code than the second figure is. What they share is the block grid, which is
    the part that has to match for the two cabinets to look like one program.

    The broom sweeps toward the house, which is the direction the stone goes.
    """
    unit = height / 8
    stroke = int(now * 3) % 2  # slow, so it reads as sweeping and not as running
    top = feet_y - height

    def block(left, up, wide, tall, colour) -> None:
        pygame.draw.rect(
            surface,
            colour,
            pygame.Rect(
                int(x + left * unit),
                int(top + up * unit),
                max(1, int(wide * unit)),
                max(1, int(tall * unit)),
            ),
        )

    block(-1.5, 5.1, 1.3, 2.9, PANEL_DARK)  # legs, planted: he is going nowhere
    block(0.3, 5.1, 1.3, 2.9, PANEL_DARK)
    block(-1.8, 2.3, 3.6, 3.0, HOUSE_RED)  # the sweater: the one colour on the ice
    block(-1.2, 1.0, 2.4, 1.5, SKIN)  # face under the hat
    # Blue, not white: a pale hat on pale ice is a hole in his head.
    block(-1.5, 0.1, 3.0, 1.1, HOUSE_BLUE)  # the toque, wider than the head
    pygame.draw.circle(
        surface, ACCENT, (int(x), int(top + 0.1 * unit)), max(3, int(unit * 0.38))
    )

    # Both hands down the shaft, and the head of the broom flat on the ice in
    # front of him — the two frames are the sweep.
    reach = 3.6 + 1.0 * stroke
    block(1.0, 2.8, 1.6, 0.8, SKIN)
    shaft_top = (x + 1.4 * unit, top + 2.6 * unit)
    shaft_foot = (x + reach * unit, feet_y - 0.3 * unit)
    pygame.draw.line(surface, BRASS, shaft_top, shaft_foot, max(3, int(unit * 0.26)))
    head = pygame.Rect(0, 0, max(4, int(unit * 2.0)), max(3, int(unit * 0.6)))
    head.center = (int(shaft_foot[0]), int(feet_y - unit * 0.2))
    # Dark, because the head of a broom lies *on* the ice and a pale one on pale
    # ice is a gap in the drawing.
    pygame.draw.rect(surface, PANEL, head, border_radius=3)


def stone_rows(positions, span: int, radius: int = STONE_RADIUS) -> tuple[int, ...]:
    """Which row each stone stands in, counting up from the line.

    Two stones on the same mark is the whole point of some of these levels —
    `1/2` and `2/4` are the same place — and drawn on top of each other they are
    one stone, which reads as a stone having gone missing. Real ones would nudge
    each other sideways; sideways is the answer here, so they stack instead.

    Capped at what fits between the line and the top of the ice: past that they
    do overlap, which is better than a stone drawn off the sheet.
    """
    ceiling = max(0, (SHEET_LINE - SHEET.top - radius - 8) // STONE_ROW)
    placed: list[tuple[int, int]] = []
    rows: list[int] = []
    for value in positions:
        x = sheet_x(value, span)
        row = 0
        while row < ceiling and any(
            other_row == row and abs(other_x - x) < 2 * radius for other_x, other_row in placed
        ):
            row += 1
        placed.append((x, row))
        rows.append(row)
    return tuple(rows)


def _house(surface, centre_x: int, line_y: int, spread: int) -> None:
    """The rings, exactly as wide as the shot is forgiving.

    Ellipses rather than circles: at the easy denominators the tolerance is a
    quarter of the whole line, and a circle that wide is taller than the sheet.
    Squashed, it reads as a house seen from behind the hack, which is the view
    the ice is already drawn in.
    """
    tall = min(spread, SHEET.height // 2 - 14)
    for share, colour in ((1.0, HOUSE_BLUE), (0.6, INK), (0.3, HOUSE_RED)):
        rings = pygame.Rect(0, 0, max(4, int(spread * 2 * share)), max(4, int(tall * 2 * share)))
        rings.center = (centre_x, line_y)
        pygame.draw.ellipse(surface, colour, rings)
    pygame.draw.circle(surface, INK, (centre_x, line_y), 5)


def draw_sheet(surface, font, span: int, target, stones, ghost: int | None = None,
               now: float = 0.0) -> None:
    """The ice: the line, its ticks, the house, and every stone thrown so far.

    `target` is what is being asked *now* — or, while a miss is being read, the
    one that was asked, because the queue has already moved on and redrawing the
    ticks in the next fraction's partition under a stone he is still reading
    would explain the wrong question.

    `ghost` is where his last stone actually went, drawn against the true mark —
    and it is also what brings the house out, because the rings say where the
    answer was.
    """
    pygame.draw.rect(surface, ICE, SHEET, border_radius=10)
    pygame.draw.rect(surface, ICE_DARK, SHEET, width=3, border_radius=10)
    line_y = SHEET_LINE
    left, right = sheet_x(0, span), sheet_x(span, span)

    if ghost is not None and target is not None:
        # Only once the stone has come to rest. The house is centred on the mark
        # that was called, so drawing it while he is still aiming is drawing him
        # the answer — and the rings are the tolerance, which is the one thing
        # he must not be able to read off the ice before he throws.
        _house(surface, sheet_x(target.value, span), line_y, sheet_x(target.tolerance, span) - left)

    pygame.draw.line(surface, ICE_LINE, (left, line_y), (right, line_y), 4)
    if target is not None:
        # Every tick, including the ones he is not being asked for: the
        # partition *is* the denominator, and a line ticked in sixths is what
        # makes 1/3 findable at all.
        for step in range(target.ticks + 1):
            x = sheet_x(span * step // target.ticks, span)
            pygame.draw.line(surface, ICE_LINE, (x, line_y - 14), (x, line_y + 14), 2)
    for value, label in ((0, "0"), (span, "1")):
        x = sheet_x(value, span)
        pygame.draw.line(surface, ICE_LINE, (x, SHEET.top + 16), (x, line_y + 26), 4)
        text(surface, font, label, (x, line_y + 52), ICE_LINE)

    # Just behind the zero end, which is where a curler throws from — and it
    # keeps the mark for nought clear of him, rather than running up through his
    # head like a flagpole.
    _sweeper(surface, left - 24, line_y + 2, SWEEPER_HEIGHT, now)

    rows = stone_rows([value for value, _ in stones], span)
    if ghost is not None and target is not None:
        true_x = sheet_x(target.value, span)
        # The stone he has just thrown is the last one in the list, so the gap is
        # drawn to where it actually stands — a stone lifted into a row with a
        # line still pointing at the ice below it explains nothing.
        thrown = (sheet_x(ghost, span), line_y - (rows[-1] if rows else 0) * STONE_ROW)
        pygame.draw.line(surface, GOOD, (true_x, line_y - 30), (true_x, line_y + 58), 4)
        pygame.draw.line(surface, BAD, thrown, (true_x, line_y), 3)
        # Below the line, clear of however high the stones have piled.
        text(surface, font, target.prompt, (true_x, line_y + 80), GOOD)

    for (value, counted), row in zip(stones, rows):
        # The handle is the whole of what says whether it counted, and a grey
        # one on grey granite says nothing at all.
        _stone(
            surface,
            (sheet_x(value, span), line_y - row * STONE_ROW),
            STONE_RADIUS,
            GOOD if counted else BAD,
        )


def draw_stone_call(surface, font, label_font, target, rect=CALL_BAND) -> None:
    """The fraction he is being asked to place. No keypad under it — the click
    is the whole answer, and a second thing to answer is what the other four
    cabinets are for."""
    text(surface, label_font, "slide the stone to", (rect.centerx, rect.top + 40), DIM)
    text(surface, font, target.prompt, (rect.centerx, rect.top + 128), ACCENT)
    text(surface, label_font, "click the ice", (rect.centerx, rect.top + 216), DIM)


def draw_rink(surface, rect: pygame.Rect, now: float) -> None:
    """The curling cabinet's screen: a stone sliding at a house, forever."""
    inset = rect.inflate(-int(rect.width * 0.09), -int(rect.height * 0.13))
    pygame.draw.rect(surface, ICE, inset, border_radius=6)
    line_y = inset.centery + int(inset.height * 0.1)
    pygame.draw.line(surface, ICE_LINE, (inset.left + 6, line_y), (inset.right - 6, line_y), 2)
    house = int(inset.height * 0.3)
    centre = inset.right - int(inset.width * 0.22)
    for share, colour in ((1.0, HOUSE_BLUE), (0.55, INK), (0.28, HOUSE_RED)):
        rings = pygame.Rect(0, 0, max(3, int(house * 2 * share)), max(3, int(house * 1.2 * share)))
        rings.center = (centre, line_y)
        pygame.draw.ellipse(surface, colour, rings)
    share = (now * 0.35) % 1.0
    stone = max(3, int(inset.height * 0.11))
    # From inside the ice, not from its edge: a stone half off the sheet reads
    # as a drawing bug rather than as one still on its way.
    start = inset.left + stone
    _stone(surface, (int(start + (centre - start) * share), line_y), stone, ACCENT)
