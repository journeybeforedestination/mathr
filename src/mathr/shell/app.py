"""The imperative shell: one window, one event loop, three screens."""

import random
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Mapping

import pygame

from ..domain.facts import LEVELS_BY_ID
from ..domain.facts import SPAN
from ..domain.round import (
    ALARMS,
    CODE,
    CURLING,
    FOOTBALL,
    PLACE_MAX,
    PLACE_TOLERANCE,
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
UNLOCK_HOLD = 1.1  # how long a vault is held open before the next lock loads
SWING_DELAY = 0.5  # bolts back on a full combination, before the leaf moves
SWING_TIME = 1.5  # and how long the door takes to swing off the hoard

#: What a placement's end says, and in what colour. Held for `THROW_HOLD` with
#: the pennants still up, which is also why the next call cannot be clicked yet.
#: A miss is not in here: it is worth reading rather than glimpsing, so it gets
#: `render_miss` and a button instead of a second and a bit.
VERDICTS = {
    Outcome.SECURED: ("CAUGHT!", draw.GOOD, "the ball is on the {units}"),
    Outcome.LAPSED: ("DROPPED", draw.BAD, "too slow to bring it in"),
    Outcome.SETBACK: ("RIGHT SPOT", draw.GOOD, "the ball is on the {units}"),
}

#: The one way out of a panel that is being read: a click on the play area must
#: never double as a dismissal, or reading the miss throws the next one at
#: whatever the eye happened to be resting on. Its label is per mode.
NEXT_UP = Button(pygame.Rect(510, 716, 260, 76), "Next", "next", draw.PANEL)

#: The call. Two buttons and no keypad: the keypad below is for the repair that
#: only a correct overturn opens, and a keystroke must never stand in for one of
#: these — see `press`.
ROCKET_HEART = (draw.ROCKET_ORIGIN[0] + draw.BODY_X, draw.ROCKET_ORIGIN[1] + 300)


# --- the level screen -------------------------------------------------------
# Four columns rather than a list: a fourth level would run the old single
# column off the bottom of the 800-tall design surface.
COLUMN_X = tuple(64 + index * 294 for index in range(4))
ROW_Y = (216, 356, 496)
CARD = (270, 120)


@dataclass(frozen=True)
class LevelScreen:
    """The cards one cabinet leads to.

    Four cabinets share one screen because they ask the same questions in
    different clothes. The fifth asks a different *kind* of question, and a
    curling cabinet with the arithmetic cards behind it is a wrong game one
    click deep — so this is a field of `Mode` with no default, the way the
    renderer dispatch is a dict with no fallthrough.
    """

    titles: tuple[str, ...]
    cards: tuple[Button, ...]
    #: Drawn, never clickable — see `draw.draw_card`, which will not hover these.
    soon: tuple[Button, ...] = ()

    @property
    def first(self) -> str:
        """Where *Try again* goes when there is no round left to ask."""
        return self.cards[0].value


def level_screen(columns, titles, tall: str | None = None, soon: str | None = None) -> LevelScreen:
    """Columns of level ids, plus one double-height card in the column after
    them — which is always the level that is every other level at once."""
    cards = tuple(
        Button(
            pygame.Rect(COLUMN_X[column], ROW_Y[row], *CARD),
            LEVELS_BY_ID[level_id].name,
            level_id,
        )
        for column, ids in enumerate(columns)
        for row, level_id in enumerate(ids)
    )
    if tall is not None:
        cards += (
            Button(
                pygame.Rect(COLUMN_X[len(columns)], ROW_Y[0], CARD[0], 260),
                LEVELS_BY_ID[tall].name,
                tall,
            ),
        )
    dark = (
        (Button(pygame.Rect(COLUMN_X[len(columns)], ROW_Y[2], *CARD), soon, "soon"),)
        if soon is not None
        else ()
    )
    return LevelScreen(titles, cards, dark)


ARITHMETIC = level_screen(
    (
        ("fives", "tens", "bridge"),
        ("twos", "fives_times", "tens_times"),
        ("divide_two", "divide_five", "divide_ten"),
    ),
    ("Addition", "Multiply", "Division", "Everything"),
    tall="everything",
    soon="Tricky Facts",
)

FRACTIONS = level_screen(
    (("halves", "thirds"), ("fifths", "eighths"), ("same_as",)),
    # The column says the idea, the card says it in his words: the fifth level
    # is the only one where the ticks are not the denominator.
    ("Start Here", "Trickier", "Equivalent", "Everything"),
    tall="fractions",
)


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
    levels: LevelScreen  # and which cards the cabinet leads to
    noun: str
    per_part: int  # what one part is worth, in `noun`
    won: str
    lost: str
    lost_line: str  # formatted with parts and units
    win_hold: float
    lose_hold: float  # before *Try again* appears
    rally: bool = False  # a ball flies between questions, and the clock waits
    warns: bool = False  # the bank pulses as it empties
    #: A sentence is three times the width of `8 + 5 = ?`, and at the size the
    #: other cabinets ask a question it runs off both ends of the monitor.
    prompt_font: str = "big"


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
        ARITHMETIC,
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
        ARITHMETIC,
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
            Outcome.SETBACK: "tackle",
            Outcome.WON: "cheer",
            Outcome.LOST: "abducted",
        },
        draw.DOWNFIELD,
        ARITHMETIC,
        "yards",
        1,  # the marker is the line: a part is a yard, and a catch spots it exactly
        "TOUCHDOWN!",
        "TURNOVER",
        "you reached the {units}",
        2.8,
        0.7,
        warns=True,
    ),
    "code": Mode(
        "code",
        "Code Breaker",
        CODE,
        {
            Outcome.CORRECT: "tumbler",
            Outcome.CRACKED: "unlock",
            Outcome.WRONG: "alarm",
            Outcome.WON: "cheer",
            Outcome.LOST: "alarm",
        },
        draw.CODEBREAK,
        ARITHMETIC,
        "lines",
        1,
        "VAULT OPEN!",
        "LOCKED DOWN",
        "you cracked {units} lines",
        3.4,
        0.9,
        prompt_font="mid",
    ),
    "curling": Mode(
        "curling",
        "Curling Club",
        CURLING,
        {
            Outcome.PLACED: "inhouse",
            Outcome.ADRIFT: "slide",
            Outcome.WON: "cheer",
            Outcome.LOST: "drop",
        },
        draw.ONICE,
        FRACTIONS,
        "stones",
        1,
        "GREAT END!",
        "OUT OF STONES",
        "you had {units} in the house",
        2.8,
        0.7,
    ),
}

BACK = Button(pygame.Rect(40, 40, 150, 64), "Back", "back")

#: Three across by two down: five cabinets and one still dark. The `"soon"`
#: guards are what keep that last slot honest — `click` skips the id and
#: `draw_card` will not hover it, and without them the click would set a mode
#: that does not exist and `App.game` would raise on the next frame.
#:
#: The height is deliberately still 220: `draw.cabinet_parts` scales its offsets
#: by the height they were drawn against, and a test pins that 440 is unchanged.
#: Only the width moved — 44 + 3 x 368 + 3 x 44 spans the design surface exactly.
CABINETS = (
    ("rocket", pygame.Rect(44, 186, 368, 220)),
    ("tennis", pygame.Rect(456, 186, 368, 220)),
    ("football", pygame.Rect(868, 186, 368, 220)),
    ("code", pygame.Rect(44, 420, 368, 220)),
    ("curling", pygame.Rect(456, 420, 368, 220)),
    ("soon", pygame.Rect(868, 420, 368, 220)),
)

MENU_BUTTONS = (
    Button(pygame.Rect(190, 666, 280, 76), "Sound: On", "sound"),
    Button(pygame.Rect(500, 666, 280, 76), "Timer: On", "timer"),
    Button(pygame.Rect(810, 666, 280, 76), "Quit", "quit"),
)

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
    jump: tuple[int, int] | None = None  # a sack, drawn as a hop back down the line
    review: tuple[int, int, bool] | None = None  # a miss being explained; last is "was a sack"
    opened: tuple = ()  # the lines of a lock that has just swung, while it is shown
    stones: list[tuple[int, bool]] = field(default_factory=list)  # where each landed, and whether it counted
    #: A wide stone being read: the target it was thrown at, and where it went.
    #: The *target* and not just the numbers, because the queue has already moved
    #: on and the sheet has to keep the partition of the question he is reading.
    ghost: tuple | None = None


def hint_caption(question) -> str | None:
    """What the number line cannot say by itself, which is division only.

    Every other operation ends its route on its own answer, so the highlighted
    last dot *is* the answer. `12 ÷ 2` ends on 12 — the number already in the
    question — and the answer is how many hops it took to get there.
    """
    fact = question.fact
    if fact.op != "÷":
        return None
    return f"{fact.result} hop{'' if fact.result == 1 else 's'} of {fact.b}"


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
            for button in self.game.levels.cards:
                if button.rect.collidepoint(position):
                    self.start(button.value)
        elif self.screen == "play":
            if BACK.rect.collidepoint(position):
                self.back()
            elif self.showing_failure:
                for button in FAIL_BUTTONS:
                    if button.rect.collidepoint(position):
                        self.fail_action(button.value)
            elif self.play is not None and (
                self.play.review is not None or self.play.ghost is not None
            ):
                if NEXT_UP.rect.collidepoint(position):
                    self.play.review = None
                    self.play.ghost = None
            elif self.play is not None and self.play.round.placing is not None:
                if self.game.rules.targets_from_deck:
                    self.slide(position)
                else:
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
        # This mode's first level, never the module's: *Try again* on a curling
        # failure must not start a rocket level.
        level_id = self.play.round.level_id if self.play else self.game.levels.first
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
        # The Timer toggle belongs to the rocket. A rally has no untimed form —
        # without a deadline the ball has nowhere to be — and the booth is the
        # other way round: what it measures is reasoning faster than his own
        # arithmetic, and a clock suppresses the thing being measured. The ice
        # is the booth's case again, and a clock there would drain against a
        # mode with nothing to spend it on until `tick` ended a round nobody was
        # racing.
        if mode.rules.locks or mode.rules.targets_from_deck:
            timed = False
        elif mode.rules.lives is not None:
            timed = True
        else:
            timed = self.progress.settings.timer
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
        if play.review is not None or play.ghost is not None:
            # Nothing to type against, so any key means "next" — the keyboard
            # must not be the one way out of a screen that has a button.
            play.review = None
            play.ghost = None
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
        # The lock as it stands *before* the answer: if this is the one that
        # swings it, the domain will have cleared `cracked` by the time the
        # shell has anything to draw.
        lock_lines = (*play.round.cracked, play.round.current) if self.game.rules.locks else ()
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
        if outcome in (Outcome.CRACKED, Outcome.WON) and lock_lines:
            play.opened = lock_lines
        if outcome is Outcome.CRACKED:
            # Not `FLASH_TIME`: a swung vault is the one moving reward here and
            # gets the hold the tuning table has always said it does. Without
            # this the bolts start 59% back and finish in 0.45s.
            play.flash_left = UNLOCK_HOLD
        if outcome is Outcome.LOST:
            # Only a mode whose lives a wrong *answer* spends reaches this: for
            # every other mode the round ends in `tick` or in `throw`, and
            # without this branch the domain is over while the shell sits there
            # with a dead keypad and no failure screen.
            self.lose()
            return
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
        if self.verdict(play) is not None or play.review is not None:
            return  # the last play is still on screen; this click is not aimed yet
        called = play.round.placing
        was_sack = play.round.sacked is not None
        before = play.round.parts
        aimed = draw.field_yards(position, PLACE_MAX)
        if aimed is None:
            return
        play.round, outcome = place(play.round, aimed)
        # A sack leaves no pass on the field to draw pennants for: the marker
        # has already moved to where it was going to move.
        play.throw = None if was_sack else (aimed, called)
        # Both kinds of backwards move get the hop drawn over the field: the
        # sack's, and the penalty a wide throw gives up.
        moved = play.round.parts != before
        play.jump = (before, play.round.parts) if moved else None
        play.throw_left = THROW_HOLD
        play.flash = outcome
        play.flash_left = FLASH_TIME
        if outcome is Outcome.LOST:
            # The third incompletion: `lose` owns the failure screen and its clip.
            self.lose()
            return
        if outcome is Outcome.ADRIFT:
            play.review = (aimed, called, was_sack)
        self.sounds.play(self.game.clips[outcome])

    def slide(self, position: tuple[int, int]) -> None:
        """A click on the ice, resolved as the stone.

        One stone, thrown once: `place` advances the queue itself in this mode,
        so there is nothing here to hold the question open for.
        """
        play = self.play
        if play.ghost is not None:
            return  # the last stone is still being read; this click is not aimed
        target = play.round.current
        aimed = draw.sheet_units(position, SPAN)
        if aimed is None:
            return
        before = play.round.parts
        play.round, outcome = place(play.round, aimed)
        play.stones.append((aimed, play.round.parts > before))
        play.flash = outcome
        play.flash_left = FLASH_TIME
        if outcome is Outcome.LOST:
            # The third wide stone: `lose` owns the failure screen and its clip.
            self.lose()
            return
        if outcome is Outcome.ADRIFT:
            play.ghost = (target, aimed)
        if outcome is Outcome.WON:
            play.since_launch = 0.0
            self.record()
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
        if play.round.pending is None and play.review is None:
            # The two pennants stay up for as long as the placement is live, so
            # he can see what he called and what he actually threw while he
            # answers for it — and for a moment after it resolves.
            play.throw_left = max(0.0, play.throw_left - dt)
            if play.throw_left == 0.0:
                play.throw = None
                play.jump = None

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
            elif mode_id == "code":
                draw.draw_mini_vault(self.canvas, screen, self.clock_now)
            elif mode_id == "curling":
                draw.draw_rink(self.canvas, screen, self.clock_now)
        labels = {
            "sound": f"Sound: {'On' if self.progress.settings.sound else 'Off'}",
            "timer": f"Timer: {'On' if self.progress.settings.timer else 'Off'}",
        }
        for button in MENU_BUTTONS:
            self.button(button, labels.get(button.value))

    def render_levels(self) -> None:
        draw.text(self.canvas, self.fonts["big"], self.game.title, (640, 116), draw.INK)
        self.button(BACK)
        screen = self.game.levels
        for index, title in enumerate(screen.titles):
            draw.text(
                self.canvas, self.fonts["mid"], title, (COLUMN_X[index] + CARD[0] // 2, 176), draw.ACCENT
            )
        for button in screen.soon:
            draw.draw_button(self.canvas, self.fonts["small"], button, False, dimmed=True)
        for button in screen.cards:
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
            "code": self.render_code,
            "curling": self.render_sheet,
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
            self.render_hint(play)
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
            play.jump,
        )
        if play.round.rules.place_lives is not None:
            draw.draw_attempts(
                self.canvas, self.fonts["tiny"], play.round.adrift, play.round.rules.place_lives
            )
        if play.review is not None:
            self.render_miss(play)
            return
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
        elif play.round.sacked is not None:
            draw.draw_sack_call(
                self.canvas, self.fonts["big"], self.fonts["small"], play.round.sacked
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

    def render_sheet(self, play: Play) -> None:
        round_ = play.round
        # While a miss is being read, the sheet keeps the partition of the
        # question he is reading — the queue has already moved on, and redrawing
        # the ticks in the next fraction's denominator under his stone would
        # explain the wrong question.
        target = play.ghost[0] if play.ghost else None if round_.over else round_.current
        draw.draw_sheet(
            self.canvas,
            self.fonts["small"],
            SPAN,
            target,
            play.stones,
            play.ghost[1] if play.ghost else None,
            self.clock_now,
        )
        if round_.rules.place_lives is not None:
            draw.draw_attempts(
                self.canvas, self.fonts["tiny"], round_.adrift, round_.rules.place_lives
            )
        if play.ghost is not None:
            self.render_ghost(play)
        elif not round_.over:
            draw.draw_stone_call(self.canvas, self.fonts["huge"], self.fonts["small"], target)

    def render_ghost(self, play: Play) -> None:
        """A wide stone, held until he says he has read it.

        Self-paced and it costs him nothing: a placement is due, so nothing is
        running — the same bargain the football miss makes. The button is what
        makes it safe, and `press` clears it so the keyboard is not dead in
        front of a screen the mouse can leave.
        """
        target, aimed = play.ghost
        hops = target.num * (target.ticks // target.den)
        draw.text(self.canvas, self.fonts["big"], "WIDE", (640, 470), draw.BAD)
        draw.text(
            self.canvas,
            self.fonts["small"],
            f"your stone is {'short of' if aimed < target.value else 'past'} {target.prompt}",
            (640, 524),
            draw.DIM,
        )
        # The count, said out loud, because it is the whole of the lesson where
        # the partition is not the denominator: 1/3 is two ticks of six.
        draw.text(
            self.canvas,
            self.fonts["small"],
            f"{target.prompt} is {hops} tick{'' if hops == 1 else 's'} along"
            f" a line cut into {target.ticks}",
            (640, 566),
            draw.ACCENT,
        )
        self.button(NEXT_UP, "Next stone")

    def render_miss(self, play: Play) -> None:
        """A miss, held until he says he has read it.

        Self-paced and it costs him nothing: a placement is due, so the domain
        has every clock stopped already — the same reason a hint can be read at
        leisure.
        """
        aimed, called, was_sack = play.review
        draw.text(
            self.canvas,
            self.fonts["big"],
            "WRONG SPOT" if was_sack else "INCOMPLETE",
            (640, 432),
            draw.BAD,
        )
        draw.text(
            self.canvas,
            self.fonts["small"],
            self.miss_line(aimed, called, was_sack),
            (640, 478),
            draw.DIM,
        )
        draw.draw_miss(
            self.canvas,
            self.fonts["mid"],
            self.fonts["small"],
            PLACE_MAX,
            called,
            aimed,
            PLACE_TOLERANCE,
        )
        draw.text(
            self.canvas,
            self.fonts["small"],
            f"the {'spot' if was_sack else 'pass'} has to be in the green"
            f" — within {PLACE_TOLERANCE} yards",
            (640, 655),
            draw.DIM,
        )
        if play.jump is not None:
            start, end = play.jump
            draw.text(
                self.canvas,
                self.fonts["small"],
                f"holding on the play — back {start - end}, the ball is on the {end}",
                (640, 692),
                draw.BAD,
            )
        self.button(NEXT_UP, "Next pass")

    @staticmethod
    def miss_line(aimed: int, called: int, was_sack: bool = False) -> str:
        # Which side he was on, not just by how much: "short" and "past" are the
        # correction, and the number alone is not.
        side = "short of" if aimed < called else "past"
        verb = "you picked the" if was_sack else "you threw to the"
        return f"{verb} {aimed}, {abs(aimed - called)} {side} the {called}"

    def render_hint(self, play: Play) -> None:
        """Two routes where the items are sentences, one where they are facts.

        Dispatched on what the mode asks rather than on the type of the item, for
        the reason `render_play` dispatches through a dict: a mode handed the
        wrong hint would draw, be wrong, and raise nothing.
        """
        hint = play.round.hint
        if self.game.rules.locks:
            draw.draw_two_routes(
                self.canvas,
                self.fonts["mid"],
                self.fonts["tiny"],
                hint.strategies,
                hint.prompt,
                self.game.layout.hint,
            )
            return
        draw.draw_number_line(
            self.canvas,
            self.fonts["mid"],
            self.fonts["tiny"],
            hint.strategy,
            hint.prompt,
            self.game.layout.hint,
            hint_caption(hint),
        )

    def render_code(self, play: Play) -> None:
        round_ = play.round
        index, done, size = round_.lock
        opening = self.opening(play)
        held = play.opened if opening is not None else ()
        if held:
            # The lock that just swung, held with its lines and its digits still
            # on the door. The domain cleared `cracked` and `lock` moved on to
            # the one still shut on the same frame, so without this the one
            # moving reward in the mode is the code being wiped.
            lines, active, size = held, len(held), len(held)
            if not round_.over:
                index -= 1
        else:
            # The lines of this lock: the ones already open, then the one he is
            # on and the ones still dark behind it.
            lines, active = (*round_.cracked, *round_.queue[: size - done]), done
        draw.draw_door(
            self.canvas, self.fonts["small"],
            index, len(round_.rules.locks), round_.points, ALARMS,
        )
        draw.draw_panel(self.canvas, self.fonts[self.game.prompt_font], lines, active)
        draw.draw_bolts(self.canvas, opening or 0.0)
        draw.draw_lock(
            self.canvas, self.fonts["mid"], self.fonts["small"],
            tuple(line.answer for line in lines[:active]), size, opening or 0.0,
        )

    def opening(self, play: Play) -> float | None:
        """How far the bolts have drawn back, or `None` if no lock is swinging.

        `None` rather than zero because a swing *starts* at zero: on the frame a
        lock is cracked there is nothing back yet, and a renderer that read the
        number alone would spend that frame showing the next lock, empty.

        The win is the third lock swinging, so it opens the same way and then
        keeps going: `SWING_DELAY` of thrown bolts on a full combination before
        the leaf itself starts to move.
        """
        if play.since_launch is not None:
            return min(1.0, play.since_launch / SWING_DELAY)
        if play.flash is not Outcome.CRACKED or play.flash_left <= 0:
            return None
        return 1.0 - play.flash_left / UNLOCK_HOLD

    def render_entry(self, play: Play) -> None:
        layout = self.game.layout
        if play.round.hint is None and not self.game.rules.locks:
            # The hint carries its own prompt: in the rocket the queue has
            # already moved on, so drawing both would put two questions on
            # screen at once.
            draw.text(
                self.canvas,
                self.fonts[self.game.prompt_font],
                play.round.current.prompt,
                layout.prompt,
                draw.INK,
            )
        box = layout.entry
        colour = draw.INK
        if play.flash_left > 0 and play.flash is not None:
            colour = (
                draw.GOOD
                if play.flash
                in (
                    Outcome.CORRECT,
                    Outcome.PLACED,
                    Outcome.SECURED,
                    Outcome.CRACKED,
                )
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
        if self.mode == "code":
            swing = (play.since_launch - SWING_DELAY) / SWING_TIME
            if swing <= 0:
                return  # the bolts are still going back; `render_code` owns the door
            draw.draw_treasure(self.canvas, min(1.0, swing))
            if swing < 0.55:
                return  # the leaf is still over where the words go
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
