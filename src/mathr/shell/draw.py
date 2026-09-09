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


def draw_progress(surface, font, done: int, total: int, noun: str = "parts", per: int = 1) -> None:
    """One pip per part, and the count in whatever the part is worth: a
    football part is ten yards, and "3 / 10 yards" would be a lie the field
    standing next to it immediately contradicts."""
    for index in range(total):
        rect = pygame.Rect(700 + index * 46, 96, 34, 14)
        pygame.draw.rect(surface, GOOD if index < done else PANEL, rect, border_radius=7)
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


def draw_field(surface, label_font, span: int, yards: int, throw, now: float) -> None:
    """The drive: the line, and the ball carrier standing where it has reached.

    `throw` is (aimed, called) from the last placement, held for a moment so he
    sees the two side by side. That comparison is the whole teaching moment;
    without it a wide throw is only a noise.
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
    """Incomplete passes, under the Back button and above the field.

    Filled from the left as they are spent, the same reading as the tennis
    scoreboard: what is left is what is not red yet.
    """
    text(surface, font, "incomplete", (108, 128), DIM)
    for index in range(lives):
        pygame.draw.circle(surface, BAD if index < adrift else PANEL, (210 + index * 36, 128), 12)


def draw_call(surface, font, label_font, target: int, rect=CATCH) -> None:
    """The yard he is being asked for, where his hands are about to be."""
    text(surface, label_font, "throw to the", (rect.centerx, rect.top + 60), DIM)
    text(surface, font, str(target), (rect.centerx, rect.top + 140), ACCENT)
    text(surface, label_font, "click the field", (rect.centerx, rect.top + 220), DIM)


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
DOWNFIELD = Layout(
    (516, 432),
    pygame.Rect(416, 466, 200, 96),
    pygame.Rect(60, 150, 620, 236),
    (390, 500),  # left of the Try again row, and clear of the field above it
)


def _hint_positions(strategy) -> tuple[int, ...]:
    place = strategy.start
    places = [place]
    for jump in strategy.jumps:
        place += jump
        places.append(place)
    return tuple(places)


def draw_number_line(surface, font, label_font, strategy, prompt: str, rect=HINT_BOX) -> None:
    """The route to the answer: a hop per step, labelled and signed.

    The renderer owns the span, because the domain hands over numbers only. It
    also owns the degenerate shapes those numbers really produce: a jump of zero
    (`0 + 5`, `5 - 0`), which draws as a labelled dot rather than being special
    cased away, and an empty jump list (`2 x 0`), which is a single dot.
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
