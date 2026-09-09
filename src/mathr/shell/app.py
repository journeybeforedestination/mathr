"""The imperative shell: one window, one event loop, three screens."""

import random
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Mapping

import pygame

from ..domain.facts import LEVELS, LEVELS_BY_ID
from ..domain.round import (
    FOOTBALL,
    PLACE_MAX,
    ROCKET,
    TENNIS,
    Outcome,
    Round,
    Rules,
    apply,
    dismiss,
    new_round,
    place,
    tick,
)
from ..storage import LevelRecord, Progress, load, merge, save
from . import draw
from .audio import Sounds
from .draw import DESIGN, Button, FallingPart

COUNTDOWN = 3.0
RETURN_FLIGHT = 0.34  # his shot, on its way back to the opponent
PAST_FLIGHT = 0.5  # and the one that got past him, on its way out
LIFTOFF = 2.6
FLASH_TIME = 0.45
ABDUCT_BEAM = 1.6
THROW_HOLD = 1.3  # how long a finished play is held before the next call

#: What a placement's end says, and in what colour. Held for `THROW_HOLD` with
#: the pennants still up, which is also why the next call cannot be clicked yet.
VERDICTS = {
    Outcome.SECURED: ("CAUGHT!", draw.GOOD, "the ball is on the {units}"),
    Outcome.ADRIFT: ("INCOMPLETE", draw.BAD, "same spot, throw again"),
    Outcome.LAPSED: ("DROPPED", draw.BAD, "too slow to bring it in"),
}
ROCKET_HEART = (draw.ROCKET_ORIGIN[0] + draw.BODY_X, draw.ROCKET_ORIGIN[1] + 300)


@dataclass(frozen=True)
class Mode:
    """A cabinet in the arcade: its rules, its words, and its noises.

    `clips` is spelled out per mode rather than derived from the outcome name,
    because `Sounds.play` returns silently on a name it does not know — a clip
    keyed by an enum value goes quiet the day the enum is renamed, and nothing
    anywhere raises.

    `rally` and `warns` are here rather than read off the mode id because both
    gate behaviour, not art: a mode that answers the wrong way to either plays
    a different game while drawing correctly.
    """

    id: str
    title: str
    rules: Rules
    clips: Mapping[Outcome, str]
    layout: draw.Layout  # where the prompt, the entry box and a hint go
    noun: str
    per_part: int  # what one part is worth, in `noun`
    won: str
    lost: str
    lost_line: str  # formatted with parts and units
    win_hold: float
    lose_hold: float  # before *Try again* appears
    rally: bool = False  # a ball flies between questions, and the clock waits
    warns: bool = False  # the bank pulses as it empties


MODES = {
    "rocket": Mode(
        "rocket",
        "Rocket Builder",
        ROCKET,
        {
            Outcome.CORRECT: "correct",
            Outcome.WRONG: "wrong",
            Outcome.WON: "launch",
            Outcome.LOST: "abducted",
        },
        draw.CLASSIC,
        "parts",
        1,
        "BLAST OFF!",
        "ABDUCTED!",
        "you got {units} parts on",
        COUNTDOWN + LIFTOFF,
        ABDUCT_BEAM,
        warns=True,
    ),
    "tennis": Mode(
        "tennis",
        "Tennis Match",
        TENNIS,
        {
            Outcome.CORRECT: "pock",
            Outcome.WRONG: "wrong",
            Outcome.POINT: "drop",
            Outcome.WON: "cheer",
            Outcome.LOST: "drop",
        },
        draw.CLASSIC,
        "returns",
        1,
        "YOU WIN!",
        "GAME OVER",
        "you returned {units}",
        2.8,
        0.7,
        rally=True,
    ),
    "football": Mode(
        "football",
        "Touchdown Drive",
        FOOTBALL,
        {
            Outcome.CORRECT: "correct",
            Outcome.WRONG: "wrong",
            Outcome.PLACED: "throw",  # in the air, not yet caught
            Outcome.ADRIFT: "incomplete",
            Outcome.SECURED: "catch",
            Outcome.LAPSED: "drop",
            Outcome.WON: "cheer",
            Outcome.LOST: "abducted",
        },
        draw.DOWNFIELD,
        "yards",
        10,  # a part is ten yards, so the readout and the field agree
        "TOUCHDOWN!",
        "TURNOVER",
        "you reached the {units}",
        2.8,
        0.7,
        warns=True,
    ),
}

BACK = Button(pygame.Rect(40, 40, 150, 64), "Back", "back")

#: Two rows of two. The fourth is drawn and never clicked — see `click`, which
#: skips it, and `draw_card`, which will not hover it.
CABINETS = (
    ("rocket", pygame.Rect(160, 186, 400, 220)),
    ("tennis", pygame.Rect(720, 186, 400, 220)),
    ("football", pygame.Rect(160, 420, 400, 220)),
    ("soon", pygame.Rect(720, 420, 400, 220)),
)

MENU_BUTTONS = (
    Button(pygame.Rect(190, 666, 280, 76), "Sound: On", "sound"),
    Button(pygame.Rect(500, 666, 280, 76), "Timer: On", "timer"),
    Button(pygame.Rect(810, 666, 280, 76), "Quit", "quit"),
)

# Four columns rather than a list: a fourth level would run the old single
# column off the bottom of the 800-tall design surface.
COLUMN_X = tuple(64 + index * 294 for index in range(4))
ROW_Y = (216, 356, 496)
CARD = (270, 120)
COLUMN_TITLES = ("Addition", "Multiply", "Division", "Everything")

LEVEL_COLUMNS = (("fives", "tens", "bridge"), ("twos", "fives_times", "tens_times"))

LEVEL_BUTTONS = tuple(
    Button(pygame.Rect(COLUMN_X[column], ROW_Y[row], *CARD), LEVELS_BY_ID[level_id].name, level_id)
    for column, ids in enumerate(LEVEL_COLUMNS)
    for row, level_id in enumerate(ids)
) + (
    Button(
        pygame.Rect(COLUMN_X[3], ROW_Y[0], CARD[0], 260),
        LEVELS_BY_ID["everything"].name,
        "everything",
    ),
)

#: Drawn, never clickable — see `draw.draw_card`, which will not hover these.
SOON_BUTTONS = tuple(
    Button(pygame.Rect(COLUMN_X[2], ROW_Y[row], *CARD), label, "soon")
    for row, label in enumerate(("Divide by 2", "Divide by 5", "Divide by 10"))
) + (Button(pygame.Rect(COLUMN_X[3], ROW_Y[2], *CARD), "Tricky Facts", "soon"),)

FAIL_BUTTONS = (
    Button(pygame.Rect(660, 500, 260, 92), "Try again", "retry", draw.PANEL),
    Button(pygame.Rect(950, 500, 200, 92), "Back", "back"),
)

KEYPAD = tuple(
    Button(
        pygame.Rect(700 + column * 156, 396 + row * 100, 140, 88),
        label,
        label,
        draw.PANEL,
    )
    for row, labels in enumerate((("1", "2", "3"), ("4", "5", "6"), ("7", "8", "9"), ("<", "0", "OK")))
    for column, label in enumerate(labels)
)


@dataclass
class Volley:
    """The ball between rallies, and the clock waits for it.

    Purely shell: the domain resets the rally the instant the answer lands, and
    a ball that teleports back to the far baseline never looks *hit*. The
    outgoing flight is the only thing that makes it a rally rather than a
    countdown, so it is worth the third of a second it costs.
    """

    flight: str  # "return" | "past"
    lane: float
    travel: float
    player_lane: float
    seconds: float
    elapsed: float = 0.0

    @property
    def done(self) -> bool:
        return self.elapsed >= self.seconds

    @property
    def position(self) -> tuple[float, float]:
        t = min(1.0, self.elapsed / self.seconds)
        path = draw.return_flight if self.flight == "return" else draw.past_flight
        return path(self.lane, self.travel, t)

    @property
    def swing(self) -> float:
        return max(0.0, 1.0 - self.elapsed / self.seconds) if self.flight == "return" else 0.0


@dataclass
class Play:
    round: Round
    entry: str = ""
    falling: list[FallingPart] = field(default_factory=list)
    flash: Outcome | None = None
    flash_left: float = 0.0
    since_launch: float | None = None
    since_failure: float | None = None
    warn_left: float = 0.0
    volley: Volley | None = None
    throw: tuple[int, int] | None = None  # (aimed, called), from the last placement
    throw_left: float = 0.0


class App:
    def __init__(self, progress_path: Path, rng: random.Random) -> None:
        self.progress_path = progress_path
        self.rng = rng
        self.progress: Progress = load(progress_path)
        self.screen = "menu"
        self.mode = "rocket"
        self.play: Play | None = None
        self.running = True
        self.focused = True
        self.clock_now = 0.0

        self.window = pygame.display.set_mode(DESIGN, pygame.RESIZABLE)
        pygame.display.set_caption("mathr")
        self.canvas = pygame.Surface(DESIGN)
        self.fonts = {
            "huge": pygame.font.SysFont(None, 120),
            "big": pygame.font.SysFont(None, 84),
            "mid": pygame.font.SysFont(None, 54),
            "small": pygame.font.SysFont(None, 36),
            "tiny": pygame.font.SysFont(None, 30),
        }
        self.parts = draw.render_parts()
        # Sized from the cabinet rather than a constant: the screen is a fixed
        # share of the cabinet's height, and the grid halved it.
        self.thumbnail = draw.rocket_thumbnail(self.parts, int(CABINETS[0][1].height * 0.45))
        self.stars = draw.make_stars(self.rng)
        self.sounds = Sounds()
        self.sounds.muted = not self.progress.settings.sound
        self.pointer = (0, 0)

    # --- the design-surface transform -------------------------------------
    # Layout is written once, in 1280x800 design space. Hyprland tiles the
    # window to whatever the layout gives it, so both the frame and every
    # mouse position pass through draw.fit and nothing downstream ever sees
    # window coordinates.

    def to_design(self, position: tuple[int, int]) -> tuple[int, int]:
        return draw.to_design(position, self.window.get_size())

    def present(self) -> None:
        scale, offset = draw.fit(self.window.get_size())
        size = (max(1, int(DESIGN[0] * scale)), max(1, int(DESIGN[1] * scale)))
        self.window.fill((0, 0, 0))
        self.window.blit(pygame.transform.smoothscale(self.canvas, size), offset)
        pygame.display.flip()

    # --- loop -------------------------------------------------------------

    def run(self) -> None:
        clock = pygame.time.Clock()
        while self.running:
            dt = clock.tick(60) / 1000
            self.clock_now += dt
            self.pointer = self.to_design(pygame.mouse.get_pos())
            for event in pygame.event.get():
                self.handle(event)
            self.update(dt)
            self.render()
            self.present()
        self.finish_round()
        save(self.progress_path, self.progress)

    def handle(self, event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.WINDOWFOCUSLOST:
            # He will wander off mid-round. Coming back to a rocket he never
            # saw die is worse than the clock waiting for him.
            self.focused = False
        elif event.type == pygame.WINDOWFOCUSGAINED:
            self.focused = True
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.click(self.to_design(event.pos))
        elif event.type == pygame.KEYDOWN:
            self.key(event)

    def key(self, event) -> None:
        if event.key == pygame.K_ESCAPE:
            self.back()
        elif self.play is not None:
            if event.unicode.isdigit():
                self.press(event.unicode)
            elif event.key == pygame.K_BACKSPACE:
                self.press("<")
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.press("OK")

    def click(self, position: tuple[int, int]) -> None:
        if self.screen == "menu":
            for mode_id, rect in CABINETS:
                if mode_id != "soon" and rect.collidepoint(position):
                    self.mode = mode_id
                    self.screen = "levels"
            for button in MENU_BUTTONS:
                if button.rect.collidepoint(position):
                    self.menu_action(button.value)
        elif self.screen == "levels":
            if BACK.rect.collidepoint(position):
                self.back()
            for button in LEVEL_BUTTONS:
                if button.rect.collidepoint(position):
                    self.start(button.value)
        elif self.screen == "play":
            if BACK.rect.collidepoint(position):
                self.back()
            elif self.showing_failure:
                for button in FAIL_BUTTONS:
                    if button.rect.collidepoint(position):
                        self.fail_action(button.value)
            elif self.play is not None and self.play.round.placing is not None:
                self.throw(position)
            else:
                for button in KEYPAD:
                    if button.rect.collidepoint(position):
                        self.press(button.value)

    def menu_action(self, value: str) -> None:
        if value == "sound":
            self.set_settings(sound=not self.progress.settings.sound)
            self.sounds.muted = not self.progress.settings.sound
        elif value == "timer":
            self.set_settings(timer=not self.progress.settings.timer)
        elif value == "quit":
            self.running = False

    def set_settings(self, **changes) -> None:
        self.progress = replace(
            self.progress, settings=replace(self.progress.settings, **changes)
        )

    def back(self) -> None:
        if self.screen == "play":
            self.finish_round()
            self.screen = "levels"
        elif self.screen == "levels":
            self.screen = "menu"
        else:
            self.running = False

    def fail_action(self, value: str) -> None:
        level_id = self.play.round.level_id if self.play else LEVELS[0].id
        self.play = None
        if value == "retry":
            self.start(level_id)
        else:
            self.screen = "levels"

    # --- a round ----------------------------------------------------------

    @property
    def game(self) -> Mode:
        return MODES[self.mode]

    @property
    def showing_failure(self) -> bool:
        play = self.play
        return (
            play is not None
            and play.since_failure is not None
            and play.since_failure > self.game.lose_hold
        )

    def start(self, level_id: str) -> None:
        mode = self.game
        # The Timer toggle belongs to the rocket. A rally has no untimed form:
        # without a deadline the ball has nowhere to be.
        timed = True if mode.rules.lives is not None else self.progress.settings.timer
        self.play = Play(
            round=new_round(
                LEVELS_BY_ID[level_id],
                self.rng,
                timed=timed,
                rules=mode.rules,
                history=self.progress.facts,
                mode_id=mode.id,
            )
        )
        self.screen = "play"

    def finish_round(self) -> None:
        """Fold whatever was practised into progress, launched or not."""
        if self.play is None:
            return
        self.progress = merge(self.progress, self.play.round)
        self.play = None

    def press(self, value: str) -> None:
        play = self.play
        if play is None or play.round.over:
            return
        if play.round.placing is not None:
            # The click *is* the estimate. A key that resolved or dismissed a
            # placement would record an aim he never made, and typing an answer
            # here would queue it against a question hidden behind the throw.
            return
        # The keystroke that puts the hint away is also entry: he is already
        # typing the answer, and losing that first digit reads as a dropped key.
        play.round = dismiss(play.round)
        if value == "<":
            play.entry = play.entry[:-1]
        elif value == "OK":
            self.submit()
        elif value.isdigit() and len(play.entry) < 2:
            # Capped, or a held-down key runs the answer off the screen.
            play.entry += value

    def submit(self) -> None:
        play = self.play
        if not play.entry:
            return
        before = play.round.parts
        struck = self.ball(play) if self.game.rally else None
        play.round, outcome = apply(play.round, int(play.entry))
        play.entry = ""
        play.flash = outcome
        play.flash_left = FLASH_TIME
        # Rocket art, and only rocket art: a mode without parts to shed simply
        # does not take this branch. The branch that must never fall through is
        # the renderer dispatch in `render_play`.
        if self.mode == "rocket" and outcome is Outcome.WRONG and before > 0:
            play.falling.append(draw.knock_off(self.parts[before - 1], self.rng))
        if outcome is Outcome.SECURED:
            play.throw_left = THROW_HOLD
        if outcome is Outcome.WON:
            play.since_launch = 0.0
            self.record()
        elif outcome is Outcome.CORRECT and struck is not None:
            self.hit(play, "return", struck)
        self.sounds.play(self.game.clips[outcome])

    def verdict(self, play: Play):
        """The last play's ending, while it is still being shown."""
        return VERDICTS.get(play.flash) if play.throw_left > 0 else None

    def throw(self, position: tuple[int, int]) -> None:
        """A click on the field, resolved as the pending placement."""
        play = self.play
        if self.verdict(play) is not None:
            return  # the last play is still on screen; this click is not aimed yet
        called = play.round.placing
        aimed = draw.field_yards(position, PLACE_MAX)
        if aimed is None:
            return
        play.round, outcome = place(play.round, aimed)
        play.throw = (aimed, called)
        play.throw_left = THROW_HOLD
        play.flash = outcome
        play.flash_left = FLASH_TIME
        if outcome is Outcome.LOST:
            # The third incompletion: `lose` owns the failure screen and its clip.
            self.lose()
            return
        self.sounds.play(self.game.clips[outcome])

    def ball(self, play: Play) -> tuple[float, float]:
        """Where the ball is drawn: mid-flight, or falling with the clock.

        Tennis only, and it reads `seconds_left` — an untimed rocket round has
        no clock to read, so callers ask only when there is a ball.
        """
        if play.volley is not None:
            return play.volley.position
        lane = draw.court_lane(play.round.asked + play.round.points)
        return (lane, draw.closing(play.round.seconds_left, play.round.cap))

    def hit(self, play: Play, flight: str, from_ball: tuple[float, float]) -> None:
        lane, travel = from_ball
        play.volley = Volley(
            flight,
            lane,
            travel,
            draw.court_ready(lane, travel),
            RETURN_FLIGHT if flight == "return" else PAST_FLIGHT,
        )

    def flash(self, play: Play, outcome: Outcome) -> None:
        play.flash = outcome
        play.flash_left = FLASH_TIME
        self.sounds.play(self.game.clips[outcome])

    def record(self) -> None:
        self.progress = merge(self.progress, self.play.round)
        save(self.progress_path, self.progress)

    def lose(self) -> None:
        play = self.play
        play.since_failure = 0.0
        play.entry = ""
        if self.mode == "rocket":
            for index in range(play.round.parts):
                play.falling.append(draw.knock_off(self.parts[index], self.rng))
        self.record()
        self.sounds.play(self.game.clips[Outcome.LOST])

    def concede(self, struck: tuple[float, float]) -> None:
        """A ball got past him. The match goes on; only the entry is cleared."""
        play = self.play
        play.entry = ""
        self.hit(play, "past", struck)
        play.flash = Outcome.POINT
        play.flash_left = FLASH_TIME
        self.sounds.play(self.game.clips[Outcome.POINT])

    def update(self, dt: float) -> None:
        play = self.play
        if play is None:
            return
        for part in play.falling:
            part.step(dt)
        play.falling = [part for part in play.falling if not part.gone]
        play.flash_left = max(0.0, play.flash_left - dt)
        if play.round.pending is None:
            # The two pennants stay up for as long as the placement is live, so
            # he can see what he called and what he actually threw while he
            # answers for it — and for a moment after it resolves.
            play.throw_left = max(0.0, play.throw_left - dt)
            if play.throw_left == 0.0:
                play.throw = None

        if play.volley is not None:
            # The clock waits out the flight, the same way it waits out a lost
            # window: no ball is in play, so nothing is being asked of him yet.
            play.volley.elapsed += dt
            if play.volley.done:
                play.volley = None
        elif play.since_launch is None and play.since_failure is None and self.focused:
            struck = self.ball(play) if self.game.rally else None
            play.round, outcome = tick(play.round, dt)
            if outcome is Outcome.LOST:
                self.lose()
            elif outcome is Outcome.POINT:
                self.concede(struck)
            elif outcome is Outcome.LAPSED:
                # The domain has already moved on to the next fact; a half-typed
                # answer to the one that got away would be sitting in the box
                # ready to be submitted against it.
                play.entry = ""
                play.throw_left = THROW_HOLD
                self.flash(play, outcome)
            elif self.game.warns and play.round.hint is None and play.round.placing is None:
                # `warn` sets its own interval from how full the bank is, so
                # under a stopped clock — a hint, or a throw being aimed — it
                # degenerates into a metronome at a fixed rate, the opposite of
                # a pulse that quickens.
                self.warn(play, dt)

        if play.since_launch is not None:
            play.since_launch += dt
            if play.since_launch > self.game.win_hold:
                self.play = None
                self.screen = "levels"
        elif play.since_failure is not None:
            play.since_failure += dt

    def warn(self, play: Play, dt: float) -> None:
        """A pulse that quickens as the bank empties. He is looking at the
        keypad, not at the saucer.

        Rocket only: a rally deadline is under the threshold most of the time,
        so the same pulse in tennis would simply be a metronome.
        """
        left = play.round.seconds_left
        threshold = play.round.cap / 3
        if left is None or left > threshold:
            play.warn_left = 0.0
            return
        play.warn_left -= dt
        if play.warn_left <= 0:
            self.sounds.play("warn")
            play.warn_left = 0.18 + 0.5 * (left / threshold)

    # --- screens ----------------------------------------------------------

    def render(self) -> None:
        draw.draw_stars(self.canvas, self.stars)
        {"menu": self.render_menu, "levels": self.render_levels, "play": self.render_play}[self.screen]()

    def button(self, button: Button, label: str | None = None) -> None:
        shown = button if label is None else Button(button.rect, label, button.value, button.tone)
        draw.draw_button(self.canvas, self.fonts["mid"], shown, button.rect.collidepoint(self.pointer))

    def render_menu(self) -> None:
        draw.text(self.canvas, self.fonts["huge"], "mathr", (640, 96), draw.ACCENT)
        draw.text(self.canvas, self.fonts["small"], "pick a game", (640, 156), draw.DIM)
        for mode_id, rect in CABINETS:
            dimmed = mode_id == "soon"
            screen = draw.draw_cabinet(
                self.canvas,
                self.fonts["small"],
                rect,
                "Coming soon" if dimmed else MODES[mode_id].title,
                rect.collidepoint(self.pointer),
                dimmed=dimmed,
            )
            if mode_id == "rocket":
                self.canvas.blit(self.thumbnail, self.thumbnail.get_rect(center=screen.center))
            elif mode_id == "tennis":
                draw.draw_mini_court(self.canvas, screen, self.clock_now)
            elif mode_id == "football":
                draw.draw_gridiron(self.canvas, screen, self.clock_now)
        labels = {
            "sound": f"Sound: {'On' if self.progress.settings.sound else 'Off'}",
            "timer": f"Timer: {'On' if self.progress.settings.timer else 'Off'}",
        }
        for button in MENU_BUTTONS:
            self.button(button, labels.get(button.value))

    def render_levels(self) -> None:
        draw.text(self.canvas, self.fonts["big"], self.game.title, (640, 116), draw.INK)
        self.button(BACK)
        for index, title in enumerate(COLUMN_TITLES):
            colour = draw.DIM if title == "Division" else draw.ACCENT
            draw.text(self.canvas, self.fonts["mid"], title, (COLUMN_X[index] + CARD[0] // 2, 176), colour)
        for button in SOON_BUTTONS:
            draw.draw_button(self.canvas, self.fonts["small"], button, False, dimmed=True)
        for button in LEVEL_BUTTONS:
            self.level_card(button)

    def level_card(self, button: Button) -> None:
        draw.draw_card(self.canvas, button.rect, button.tone, button.rect.collidepoint(self.pointer))
        lines = [(button.label, self.fonts["small"], draw.INK)] + [
            (label, self.fonts["tiny"], colour)
            for label, colour in _badge(self.progress.level(self.mode, button.value))
        ]
        # Centred as a block, so the tall Everything card is not top-heavy and
        # a level with no record yet is not a name floating above empty space.
        top = button.rect.centery - (len(lines) - 1) * 17
        for index, (label, font, colour) in enumerate(lines):
            draw.text(self.canvas, font, label, (button.rect.centerx, top + index * 34), colour)

    def render_play(self) -> None:
        play = self.play
        if play is None:
            return
        # A dict, not a two-way branch: a mode added to MODES without a
        # renderer used to fall through to the tennis court, which compiles,
        # draws, and plays as the wrong game. This raises instead.
        {
            "rocket": self.render_rocket,
            "tennis": self.render_court,
            "football": self.render_field,
        }[self.mode](play)

        self.button(BACK)
        draw.draw_progress(
            self.canvas,
            self.fonts["small"],
            play.round.parts,
            play.round.rules.target,
            self.game.noun,
            self.game.per_part,
        )

        if play.since_failure is not None:
            self.render_failure(play)
            return
        if play.since_launch is not None:
            self.render_win(play)
            return
        if play.round.hint is not None:
            draw.draw_number_line(
                self.canvas,
                self.fonts["mid"],
                self.fonts["tiny"],
                play.round.hint.strategy,
                play.round.hint.prompt,
                self.game.layout.hint,
            )
        if play.round.placing is None:
            self.render_entry(play)
        # Nothing else while a throw is called: no keypad, no question. The
        # click is the answer, and a prompt beside it is a second thing to
        # answer. The called yard is drawn over the field, where he is aiming.

    def render_rocket(self, play: Play) -> None:
        if play.round.timed:
            draw.draw_alien(
                self.canvas,
                draw.closing(play.round.seconds_left, play.round.cap),
                self.clock_now,
            )
        lift = 0.0
        flame = 0.0
        if play.since_launch is not None and play.since_launch > COUNTDOWN:
            rising = play.since_launch - COUNTDOWN
            lift = 340 * rising * rising
            flame = 1.0
        origin = (draw.ROCKET_ORIGIN[0], draw.ROCKET_ORIGIN[1] - lift)
        showing = 0 if play.since_failure is not None else play.round.parts
        draw.draw_rocket(self.canvas, self.parts, showing, origin=origin, flame=flame)
        for part in play.falling:
            part.draw(self.canvas)
        if play.round.timed:
            draw.draw_time_bar(self.canvas, play.round.seconds_left / play.round.cap)

    def render_court(self, play: Play) -> None:
        draw.draw_court(self.canvas)
        draw.draw_points(
            self.canvas, self.fonts["small"], play.round.points, play.round.rules.lives
        )
        if play.since_launch is not None:
            draw.draw_trophy(self.canvas, (draw.COURT_CENTRE, 380))
            return
        if play.since_failure is not None:
            return
        lane, travel = self.ball(play)
        player_lane = (
            play.volley.player_lane if play.volley else draw.court_ready(lane, travel)
        )
        draw.draw_rally(
            self.canvas,
            lane,
            travel,
            player_lane,
            self.clock_now,
            play.volley.swing if play.volley else 0.0,
        )

    def render_field(self, play: Play) -> None:
        if play.round.timed:
            draw.draw_time_bar(self.canvas, play.round.seconds_left / play.round.cap)
        draw.draw_field(
            self.canvas,
            self.fonts["small"],
            PLACE_MAX,
            play.round.parts * self.game.per_part,
            play.throw,
            self.clock_now,
        )
        if play.round.rules.place_lives is not None:
            draw.draw_attempts(
                self.canvas, self.fonts["tiny"], play.round.adrift, play.round.rules.place_lives
            )
        verdict = self.verdict(play)
        if verdict is not None:
            word, colour, aside = verdict
            draw.draw_verdict(
                self.canvas,
                self.fonts["big"],
                self.fonts["small"],
                word,
                colour,
                aside.format(units=play.round.parts * self.game.per_part),
            )
        elif play.round.placing is not None:
            draw.draw_call(
                self.canvas, self.fonts["huge"], self.fonts["small"], play.round.placing
            )
        elif play.round.pending is not None:
            # An untimed drive has no deadline to draw, so the ball hangs where
            # it was thrown rather than dropping in on a clock that is not there.
            draw.draw_incoming(
                self.canvas,
                draw.closing(play.round.pending_left, play.round.confirm_seconds)
                if play.round.pending_left is not None
                else 0.5,
                self.clock_now,
            )

    def render_entry(self, play: Play) -> None:
        layout = self.game.layout
        if play.round.hint is None:
            # The hint carries its own prompt: in the rocket the queue has
            # already moved on, so drawing both would put two questions on
            # screen at once.
            draw.text(
                self.canvas, self.fonts["big"], play.round.current.prompt, layout.prompt, draw.INK
            )
        box = layout.entry
        colour = draw.INK
        if play.flash_left > 0 and play.flash is not None:
            colour = (
                draw.GOOD
                if play.flash in (Outcome.CORRECT, Outcome.PLACED, Outcome.SECURED)
                else draw.BAD
            )
        pygame.draw.rect(self.canvas, draw.PANEL, box, border_radius=14)
        pygame.draw.rect(self.canvas, colour, box, width=4, border_radius=14)
        draw.text(self.canvas, self.fonts["big"], play.entry or "_", box.center, colour)
        for button in KEYPAD:
            self.button(button)

    def render_win(self, play: Play) -> None:
        banner = self.game.layout.banner
        if self.mode == "rocket" and play.since_launch < COUNTDOWN:
            count = int(COUNTDOWN - play.since_launch) + 1
            draw.text(self.canvas, self.fonts["huge"], str(min(3, count)), banner, draw.ACCENT)
            return
        draw.text(self.canvas, self.fonts["huge"], self.game.won, banner, draw.ACCENT)

    def render_failure(self, play: Play) -> None:
        mode = self.game
        if play.since_failure < mode.lose_hold:
            if self.mode == "rocket":
                draw.draw_beam(self.canvas, ROCKET_HEART, play.since_failure / mode.lose_hold)
            return
        banner = mode.layout.banner
        draw.text(self.canvas, self.fonts["huge"], mode.lost, banner, draw.BAD)
        draw.text(
            self.canvas,
            self.fonts["mid"],
            mode.lost_line.format(units=play.round.parts * mode.per_part),
            (banner[0], banner[1] + 90),
            draw.DIM,
        )
        for button in FAIL_BUTTONS:
            self.button(button)


def _badge(record: LevelRecord) -> list[tuple[str, tuple[int, int, int]]]:
    lines: list[tuple[str, tuple[int, int, int]]] = []
    if record.launches:
        extra = f" (+{record.practice})" if record.practice else ""
        lines.append((f"{record.launches} won{extra}", draw.GOOD))
    elif record.practice:
        lines.append((f"{record.practice} practice", draw.DIM))
    if record.best_seconds is not None:
        lines.append((f"best {record.best_seconds:.0f}s", draw.ACCENT))
    return lines
