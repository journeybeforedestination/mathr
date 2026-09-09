"""The imperative shell: one window, one event loop, three screens."""

import random
from dataclasses import dataclass, field, replace
from pathlib import Path

import pygame

from ..domain.facts import LEVELS, LEVELS_BY_ID
from ..domain.round import PARTS_TO_LAUNCH, Outcome, Round, apply, new_round, tick
from ..storage import LevelRecord, Progress, load, merge, save
from . import draw
from .audio import Sounds
from .draw import DESIGN, Button, FallingPart

COUNTDOWN = 3.0
LIFTOFF = 2.6
FLASH_TIME = 0.45
ABDUCT_BEAM = 1.6
ROCKET_HEART = (draw.ROCKET_ORIGIN[0] + draw.BODY_X, draw.ROCKET_ORIGIN[1] + 300)

BACK = Button(pygame.Rect(40, 40, 150, 64), "Back", "back")

MENU_BUTTONS = (
    Button(pygame.Rect(440, 300, 400, 96), "Rocket Builder", "play", draw.PANEL),
    Button(pygame.Rect(440, 424, 400, 76), "Sound: On", "sound"),
    Button(pygame.Rect(440, 516, 400, 76), "Timer: On", "timer"),
    Button(pygame.Rect(440, 608, 400, 76), "Quit", "quit"),
)

LEVEL_BUTTONS = tuple(
    Button(pygame.Rect(240, 240 + index * 130, 800, 104), level.name, level.id)
    for index, level in enumerate(LEVELS)
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
class Play:
    round: Round
    entry: str = ""
    falling: list[FallingPart] = field(default_factory=list)
    flash: Outcome | None = None
    flash_left: float = 0.0
    since_launch: float | None = None
    since_failure: float | None = None
    warn_left: float = 0.0


class App:
    def __init__(self, progress_path: Path, rng: random.Random) -> None:
        self.progress_path = progress_path
        self.rng = rng
        self.progress: Progress = load(progress_path)
        self.screen = "menu"
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
        }
        self.parts = draw.render_parts()
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
            else:
                for button in KEYPAD:
                    if button.rect.collidepoint(position):
                        self.press(button.value)

    def menu_action(self, value: str) -> None:
        if value == "play":
            self.screen = "levels"
        elif value == "sound":
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
    def showing_failure(self) -> bool:
        play = self.play
        return play is not None and play.since_failure is not None and play.since_failure > ABDUCT_BEAM

    def start(self, level_id: str) -> None:
        self.play = Play(
            round=new_round(
                LEVELS_BY_ID[level_id], self.rng, timed=self.progress.settings.timer
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
        play.round, outcome = apply(play.round, int(play.entry))
        play.entry = ""
        play.flash = outcome
        play.flash_left = FLASH_TIME
        if outcome is Outcome.WRONG and before > 0:
            play.falling.append(draw.knock_off(self.parts[before - 1], self.rng))
        if outcome is Outcome.LAUNCHED:
            play.since_launch = 0.0
            self.record()
            self.sounds.play("launch")
        else:
            self.sounds.play(outcome.value)

    def record(self) -> None:
        self.progress = merge(self.progress, self.play.round)
        save(self.progress_path, self.progress)

    def abduct(self) -> None:
        play = self.play
        play.since_failure = 0.0
        play.entry = ""
        for index in range(play.round.parts):
            play.falling.append(draw.knock_off(self.parts[index], self.rng))
        self.record()
        self.sounds.play("abducted")

    def update(self, dt: float) -> None:
        play = self.play
        if play is None:
            return
        for part in play.falling:
            part.step(dt)
        play.falling = [part for part in play.falling if not part.gone]
        play.flash_left = max(0.0, play.flash_left - dt)

        if play.since_launch is None and play.since_failure is None and self.focused:
            play.round, outcome = tick(play.round, dt)
            if outcome is Outcome.ABDUCTED:
                self.abduct()
            else:
                self.warn(play, dt)

        if play.since_launch is not None:
            play.since_launch += dt
            if play.since_launch > COUNTDOWN + LIFTOFF:
                self.play = None
                self.screen = "levels"
        elif play.since_failure is not None:
            play.since_failure += dt

    def warn(self, play: Play, dt: float) -> None:
        """A pulse that quickens as the bank empties. He is looking at the
        keypad, not at the saucer."""
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
        draw.text(self.canvas, self.fonts["huge"], "mathr", (640, 170), draw.ACCENT)
        draw.text(self.canvas, self.fonts["small"], "build a rocket out of math facts", (640, 238), draw.DIM)
        draw.draw_rocket(self.canvas, self.parts, len(self.parts), origin=(940, 130))
        labels = {
            "sound": f"Sound: {'On' if self.progress.settings.sound else 'Off'}",
            "timer": f"Timer: {'On' if self.progress.settings.timer else 'Off'}",
        }
        for button in MENU_BUTTONS:
            self.button(button, labels.get(button.value))

    def render_levels(self) -> None:
        draw.text(self.canvas, self.fonts["big"], "Pick a level", (640, 140), draw.INK)
        self.button(BACK)
        for button, level in zip(LEVEL_BUTTONS, LEVELS):
            self.button(button)
            lines = _badge(self.progress.level(level.id))
            for index, (label, colour) in enumerate(lines):
                offset = -20 + 38 * index if len(lines) > 1 else 0
                draw.text(
                    self.canvas,
                    self.fonts["small"],
                    label,
                    (button.rect.right - 140, button.rect.centery + offset),
                    colour,
                )

    def render_play(self) -> None:
        play = self.play
        if play is None:
            return
        if play.round.timed:
            draw.draw_alien(
                self.canvas,
                draw.alien_scale(play.round.seconds_left, play.round.cap),
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

        self.button(BACK)
        draw.draw_progress(self.canvas, self.fonts["small"], play.round.parts, PARTS_TO_LAUNCH)
        if play.round.timed:
            draw.draw_time_bar(self.canvas, play.round.seconds_left / play.round.cap)

        if play.since_failure is not None:
            self.render_failure(play)
            return
        if play.since_launch is not None:
            self.render_launch(play.since_launch)
            return

        draw.text(self.canvas, self.fonts["big"], play.round.current.prompt, (940, 210), draw.INK)
        box = pygame.Rect(840, 280, 200, 96)
        colour = draw.INK
        if play.flash_left > 0 and play.flash is not None:
            colour = draw.GOOD if play.flash is Outcome.CORRECT else draw.BAD
        pygame.draw.rect(self.canvas, draw.PANEL, box, border_radius=14)
        pygame.draw.rect(self.canvas, colour, box, width=4, border_radius=14)
        draw.text(self.canvas, self.fonts["big"], play.entry or "_", box.center, colour)
        for button in KEYPAD:
            self.button(button)

    def render_launch(self, elapsed: float) -> None:
        if elapsed < COUNTDOWN:
            count = int(COUNTDOWN - elapsed) + 1
            draw.text(self.canvas, self.fonts["huge"], str(min(3, count)), (940, 340), draw.ACCENT)
        else:
            draw.text(self.canvas, self.fonts["huge"], "BLAST OFF!", (940, 340), draw.ACCENT)

    def render_failure(self, play: Play) -> None:
        if play.since_failure < ABDUCT_BEAM:
            draw.draw_beam(self.canvas, ROCKET_HEART, play.since_failure / ABDUCT_BEAM)
            return
        draw.text(self.canvas, self.fonts["huge"], "ABDUCTED!", (900, 300), draw.BAD)
        draw.text(
            self.canvas,
            self.fonts["mid"],
            f"you got {play.round.parts} parts on",
            (900, 390),
            draw.DIM,
        )
        for button in FAIL_BUTTONS:
            self.button(button)


def _badge(record: LevelRecord) -> list[tuple[str, tuple[int, int, int]]]:
    lines: list[tuple[str, tuple[int, int, int]]] = []
    if record.launches:
        extra = f" (+{record.practice})" if record.practice else ""
        lines.append((f"{record.launches} launched{extra}", draw.GOOD))
    elif record.practice:
        lines.append((f"{record.practice} practice", draw.DIM))
    if record.best_seconds is not None:
        lines.append((f"best {record.best_seconds:.0f}s", draw.ACCENT))
    return lines
