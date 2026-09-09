# mathr — plan

A desktop math game for one specific second grader. Menu picks a **game mode**;
the only mode now is **Rocket Builder**. Inside it he picks a **level**
(bonds of five → bonds of ten → bridging ten). Each correct math fact bolts
another part onto a rocket drawn on screen; each miss knocks the top part off
and re-queues that fact to be asked again. Ten parts on and it counts down and
launches. Progress and per-fact attempt counts persist to a local JSON file.

Nothing exists yet — `/home/jmc/Projects/mathr` is an empty, non-git directory.
This is a greenfield build, so there is no existing code to falsify.

---

## The load-bearing decision: render to a fixed design surface, always

Everything is drawn to a fixed **1280×800 `pygame.Surface`**, which is then
`smoothscale`d onto the real window every frame. Mouse coordinates are mapped
**back** through that same transform before any hit-testing.

This is not polish. The target machine runs **Hyprland**, a tiling compositor.
A tiled window gets whatever size the layout gives it and ignores what the
application asked for. The concrete failure without a design surface:

1. Code calls `pygame.display.set_mode((1280, 800))` and lays the keypad out at
   absolute coordinates — the "7" key at `(980, 520)`.
2. Hyprland tiles the window to, say, 960×1040 instead.
3. The rocket is drawn off the bottom of the window; the keypad's lower row is
   not visible at all.
4. He clicks where "7" *appears* to be. `pygame.mouse.get_pos()` returns window
   coordinates, the hit-test compares them against 1280×800 layout rectangles,
   and he hits "4" — or nothing.

The bug presents as "the buttons are wrong", which does not name its cause, and
it is unfixable by nudging coordinates because the offset changes with every
window size. Retrofitting the mapping later means touching every draw call and
every click site, which is why **step 5 lands before any rocket art (step 6)**.

The alternative — a Hyprland float/size window rule in `~/.config/hypr/` — was
rejected: it edits the user's desktop config to work around an application bug,
it does not survive fullscreen or a different machine, and it does nothing for
the coordinate mapping, which is the half that actually breaks silently.

---

## Verified environment facts

All of these were run on this machine, not remembered:

| Fact | Value |
|---|---|
| Python | 3.14.7 |
| `uv` | 0.10.0, at `/home/jmc/.local/bin/uv` |
| `pygame-ce` | 2.5.8 (bundles SDL 2.32.10) — **has a cp314 wheel** |
| upstream `pygame` | 2.6.1 — **no cp314 wheel**, would build from source and fail |
| `tkinter` | 9.0 present (not used; see rejected) |
| Session | Hyprland / Wayland |
| Audio | PipeWire-Pulse (`pactl` reports `/run/user/1000/pulse/native`) |
| Data dir | `$XDG_DATA_HOME` unset → `/home/jmc/.local/share` |
| Not installed | `pytest`, `ruff`, `pipx`, `poetry` |

Confirmed working under `pygame-ce` 2.5.8 on Python 3.14.7:

- `pygame.mixer.Sound(buffer=...)` accepts raw PCM bytes from `array.array` —
  **numpy is genuinely not needed** (probe ran with numpy absent and succeeded).
- `pygame.transform.rotate` on an `SRCALPHA` surface — needed for tumbling parts.
- `pygame.transform.smoothscale` — the design-surface blit.
- `pygame.font.SysFont(None, 72)` renders — no font files needed.
- `set_mode(..., pygame.RESIZABLE)` returns a surface.

Confirmed for project layout:

- `uv init --package --name mathr` produces `src/mathr/__init__.py`, a
  `[project.scripts] mathr = "mathr:main"` entry point, `requires-python = ">=3.14"`,
  and the `uv_build` backend. `uv run mathr` then works.

### What was NOT verified — do these first, do not assume

- **Windowing under Hyprland/Wayland was never exercised.** Every probe ran with
  `SDL_VIDEODRIVER=dummy`. pygame-ce bundles its own SDL 2.32.10; whether it
  selects the `wayland` or `x11` (XWayland) backend here, and whether resize
  events arrive correctly under a tiling layout, is **unknown**. Step 1's gate is
  opening a real window and confirming this.
- **Audio was never played.** The mixer probe also ran on the `dummy` driver.
  `Sound` construction from a buffer is proven; actual audible output through
  PipeWire is not. Step 7 must confirm it.
- `pygame.display.get_num_video_drivers()` **does not exist** in pygame-ce 2.5.8
  — do not reach for it when debugging driver selection.

---

## Content model

A **fact** is an equation with exactly one slot blank. All three levels are
small enough to **enumerate completely** rather than generate randomly — the
whole pool is built once as a tuple, and asking a question is sampling from it.
This is both simpler and far easier to test than a random generator, and it makes
the pool sizes below verifiable by assertion.

```python
@dataclass(frozen=True)
class Fact:
    a: int
    op: str       # "+" or "-"
    b: int
    result: int   # invariant: a op b == result
    blank: str    # "a" | "b" | "result"
```

`Fact.answer` is the value hidden in `blank`. `Fact.key` is a stable string
(e.g. `"3+2=5@b"`) used as the mastery-record dict key — see traps.

| Level id | Name | Content | Approx. pool |
|---|---|---|---|
| `fives` | Make Five | pairs summing to 5, and 5 − n | ~24 items |
| `tens` | Make Ten | pairs summing to 10, and 10 − n | ~44 items |
| `bridge` | Over the Ten | within-20 facts crossing ten (8+6, 15−7) | ~40 items |

**Both question forms are asked.** `3 + ? = 5` appears alongside `3 + 2 = ?`.
The missing addend *is* the number bond, and it is the mental move `bridge`
depends on — 8+6 is 8+2+4, which is a bond of ten. This is why the levels are in
this order: level 3 is the payoff of levels 1 and 2, not a separate topic.

Pools are smaller than a 10-part level needs questions for, so facts repeat
within a run. That is intended for a fluency drill.

---

## Architecture

Three layers, one direction, mirroring the convention in the sibling repo
`/home/jmc/Projects/leatherpros` (see its `CLAUDE.md`): a pure domain that knows
nothing about the UI, and a presentational shell that only draws and reads keys.

```
src/mathr/
  domain/
    facts.py     # Fact, the three level pools, pool construction
    round.py     # Round state + apply(round, answer) -> (round, Outcome)
  storage.py     # load/save progress JSON (the only I/O in the core)
  shell/
    app.py       # screen switching, event loop, design-surface scaling
    draw.py      # rocket parts, starfield, keypad, palette
    audio.py     # synthesized tones
  __init__.py    # main()
tests/           # pytest, domain + storage only
```

### The seam that matters

**Mode and content are orthogonal, and the seam goes in from the start.** A
*level* is a pure fact source. A *mode* consumes a stream of correct/wrong
outcomes and renders progress however it likes. Rocket Builder is one consumer
of that stream; it is the only one today.

`domain/round.py` therefore knows about `parts: int` and nothing about rockets —
no part names, no coordinates, no art. `shell/draw.py` maps the integer 0–10 to
which shapes are on screen. This costs nothing now and means a second game mode
reuses all three levels instead of reinventing them.

Do **not** put the part list in the domain. The moment `round.py` imports a part
name, the next mode has to either fake one or fork the reducer.

### Round state

```python
@dataclass(frozen=True)
class Round:
    level_id: str
    seconds_per_part: float
    deck: tuple[Fact, ...]       # the shuffled pool, replayed when the queue runs low
    queue: tuple[Fact, ...]      # upcoming; queue[0] is on screen
    parts: int                   # 0..PARTS_TO_LAUNCH
    asked: int
    missed: int
    attempts: Mapping[str, Tally]             # fact.key -> Tally
    launched: bool
    failed: bool
    seconds_left: float | None                # None is an untimed round
    on_current: float                         # spent on the question showing now
    elapsed: float                            # wall time, for the best-time record
```

`apply(round, given: int) -> tuple[Round, Outcome]` where `Outcome` is
`CORRECT | WRONG | LAUNCHED | ABDUCTED`. The shell uses the outcome to pick a sound and an
animation; it does not re-derive it by diffing `parts`, because a wrong answer at
zero parts leaves `parts` unchanged and would be read as correct.

Constants, all in one place and all deliberately easy to retune after watching
him play:

- `PARTS_TO_LAUNCH = 10` — roughly 1–2 minutes per launch.
- `RETRY_GAP = 3` — a missed fact is re-inserted 3 questions later. Far enough
  that he must actually retrieve it rather than echo the answer he was just shown.

Rules the tests must pin:

- Correct → `parts + 1`, capped at `PARTS_TO_LAUNCH`.
- Wrong → `parts - 1`, **floored at 0**, and the fact is re-queued.
- Reaching `PARTS_TO_LAUNCH` sets `launched`; further answers are rejected.
- `attempts` accumulates for every answer, right or wrong.

Randomness enters through an injected `random.Random`, never module-level
`random.*`, so tests are deterministic.

---

## Storage

`$XDG_DATA_HOME/mathr/progress.json`, defaulting to
`/home/jmc/.local/share/mathr/progress.json`.

```json
{
  "version": 1,
  "settings": { "sound": true, "timer": true },
  "levels": { "fives": { "launches": 3, "practice": 1, "failures": 2, "best_seconds": 41.5 } },
  "facts":  { "3+2=5@b": { "right": 4, "wrong": 1, "answered": 5, "seconds": 18.25 } }
}
```

Everything after `right`/`wrong` arrived with the clock and is read through
`.get` with a default, so a file written before it still loads. `Fact.key` did
not change, which is why this needed no `version` bump: the trap below is about
the key format, not about adding fields beside it.

Per-fact counts are recorded with **no UI reading them yet**. They cost almost
nothing to write and are impossible to reconstruct later; they are what a
"practice your tricky facts" mode or a parent view would need.

Write atomically: serialize to a temp file in the same directory, then
`os.replace`. A seven-year-old will close the window mid-write, and a truncated
JSON file that wipes his progress is the one bug guaranteed to end use of the
program. A missing *or unparseable* file must load as empty progress, not raise.

---

## Steps

Each lands independently. The order encodes real constraints, noted per step.

**1. Skeleton.** `uv init --package --name mathr`; `uv add pygame-ce`;
`uv add --dev pytest`. Write `CLAUDE.md` (commands + the layering rule) and
`.gitignore`. `main()` opens a resizable window, fills it, and quits on Escape.
*Gate:* `uv run mathr` opens a real window under Hyprland — this is where the
unverified Wayland question above gets answered, before anything depends on it.

**2. `domain/facts.py`.** `Fact`, `Fact.answer`, `Fact.key`, and the three
pools. *Tests:* every fact satisfies `a op b == result`; pool sizes are as
expected; both blank forms appear in each pool; keys are unique and stable.

**3. `domain/round.py`.** `Round`, `apply`, re-queue, floor, launch. *Tests:*
the four rules above, plus a wrong answer at `parts == 0` staying at 0 while
still returning `WRONG`, and a missed fact provably reappearing later in the
queue.
*Before the shell* — the shell is written against a real reducer, not a stub.

**4. `storage.py`.** Load/save/atomic-replace. *Tests:* round-trip; missing file
→ empty; corrupt file → empty, not an exception; temp file cleaned up.

**5. Shell skeleton.** Design surface + coordinate mapping + screen switching
(menu → level select → play). Plain rectangles for now, no rocket art.
*Gate:* clicks land on the right button at three different window sizes,
including a tall narrow tile. **This must precede step 6** — retrofitting the
coordinate mapping into finished draw code touches every draw call and every
hit-test.

**6. Rocket art and animation.** Ten parts assembled **bottom-up** (fins → tank →
body → porthole → nose cone), so the part that tumbles off is always the top one
— a stack: last on, first off. Falling parts carry position, velocity and
rotation and are integrated per frame. Starfield, palette, launch sequence with a
countdown.

**7. Audio.** Synthesized in code with `array.array` → `mixer.Sound(buffer=...)`:
rising blip for correct, low buzz for wrong, noise sweep for launch. Mutable from
the menu. *Gate:* actually audible — the probe only proved construction.

**8. Wire persistence.** Load on start, save on launch and on quit. Badge beaten
levels in the level-select screen.

---

## Time pressure

Added after v1 was playable, overturning the *timer* entry under
**Considered and rejected**. He wanted a sense of urgency; the shape it took is
a **shared bank of seconds**, not a stopwatch per problem.

The bank drains in real time. Every correct answer credits the level's
`seconds_per_part` back, so the pace he must sustain is three seconds per
*correct answer* while a slow problem is paid for by a fast one — which is what
"averaged over the whole set" has to mean mechanically. A wrong answer carries
no extra time penalty: it already costs a part and the seconds it burned.

Credit lands on **correct answers only**. Crediting every answer was considered
and rejected: mashing `OK` on any digit would then top the bank up, and this is
a kid who will find that.

### The dials

`Level.seconds_per_part` is the only per-level number. Everything else derives
from it, so a level is retuned by changing one value and nothing needs tuning
twice:

| | `fives` | `tens` | `bridge` |
|---|---|---|---|
| `seconds_per_part` | 3s | 3s | 5s |
| start (`GRACE_PARTS` = 5x) | 15s | 15s | 25s |
| cap (`BANK_PARTS` = 4x) | 12s | 12s | 20s |

`bridge` gets longer because bridging ten is a two-step move — 15 − 7 is
15 − 5 − 2 — and three seconds is a fluency bar for a fact he already owns, not
for one he is still assembling. A fixed cap in *seconds* would have been
harshest in *problems* on exactly the level that is already hardest.

The round opens **above** its own cap, and that is deliberate: the first five
problems' worth is a one-time grace he can never climb back to. Once spent, he
lives at four problems' worth or less.

### The alien is the readout

Size is a pure function of seconds *remaining* (`draw.alien_scale`), so the
saucer retreats when he earns time back rather than only ever looming. That
makes speed a visible reward instead of merely an avoided punishment, and it
means he never has to read a number. A slim bar under the parts pips gives the
precision the saucer lacks. **No digits** — a ticking decimal is the most
anxiety-producing thing that could share a screen with an equation.

At zero the saucer beams the rocket up, every part scatters through the
existing falling-part physics, and the round ends in `ABDUCTED` with a
*Try again* panel. Launching returns to level select on its own; failing does
not, because the moment his motivation to retry is highest is the moment he
just lost.

### Where the clock lives

In the domain, beside `apply`: `Round.seconds_left` and a pure
`tick(round, dt) -> (Round, Outcome | None)`. Pacing is a rule, and `CLAUDE.md`
says the shell holds none. It also means "the bank cannot exceed the cap" and
"zero ends the round" are tested without opening a window.

`seconds_left is None` **is** the untimed round. The Timer toggle needs no
second flag anywhere, and `tick` degrades to a no-op rather than a branch.

### Traps

**`tick` accumulates time on the current question even when untimed.** The
per-fact response times are worth having either way, and practice is precisely
where the slowest facts surface. Skipping the accumulation for untimed rounds
would silently produce a mastery record that is blind to the mode he actually
uses when he is struggling.

**Credit must never push the bank down.** `min(left + per_part, cap)` alone
would *cut* a 15s grace bank to 12s as a reward for answering correctly. The
credit is `max(left, min(left + per_part, cap))`.

**Untimed launches must not count on the badge.** They are recorded as
`practice`, separately from `launches`, or the number that means "I beat it"
is farmable by flipping a toggle in the menu.

**The clock pauses on `WINDOWFOCUSLOST`** (confirmed present in pygame-ce
2.5.8; `WINDOWFOCUSGAINED` resumes it). He will wander off mid-round, and
coming back to a rocket he never saw die reads as the program cheating.

**Do not pause the clock for the 0.45s answer flash.** It stutters the bar on
every single answer; the grace period is what absorbs it.

### Accepted with known risk

**3s and 5s are guesses**, exactly like `PARTS_TO_LAUNCH`. `failures` is
recorded per level for precisely this reason: without it you cannot tell "he
never plays `bridge`" from "he plays it constantly and the alien always wins",
and nothing else in the file would tell you the dial is wrong.

**The Timer toggle may be the whole experiment.** If he turns it off every
time, the feature is wrong rather than the constants.

---

## Traps

**Mouse coordinates must be inverse-mapped through the design-surface scale.**
`pygame.mouse.get_pos()` is in *window* space; every layout rectangle is in
*design* space. Convert once, at the event boundary, and let nothing downstream
see window coordinates. Symptom if missed: clicks are accurate near the top-left
corner and drift further away the further out you go — which reads as "sloppy
hitboxes", never as a scaling bug.

**Install `pygame-ce`, never `pygame`.** Upstream `pygame` 2.6.1 publishes no
cp314 wheel. On Python 3.14 `uv add pygame` will attempt a source build and fail
with C compiler errors that say nothing about Python versions. The two packages
share the `import pygame` name, so a stray `pygame` in the lockfile is invisible
in the source.

**`mixer.pre_init()` must run before `pygame.init()`,** and the bytes handed to
`Sound(buffer=...)` must match `mixer.get_init()` exactly — the probe used
`pre_init(44100, -16, 1, 512)` and built `array.array("h", ...)`, i.e. 16-bit
signed mono. A mismatched buffer does **not** raise; it plays as static or at the
wrong pitch. Always derive the sample count from `mixer.get_init()[0]` rather
than hardcoding 44100 twice.

**Floor `parts` at zero inside the reducer, not in the renderer.** Negative parts
would index the part list from the end and draw a nose cone floating alone. Fix
it where the invariant lives.

**`Fact.key` must be stable across runs and releases.** It is the dict key for
accumulated mastery data in a file that outlives the code. Derive it only from
`a`, `op`, `b`, `result`, `blank` — never from list position, `id()`, hash
randomization, or pool ordering. Changing the key format silently orphans every
count already recorded; that needs a `version` bump and a migration.

**Re-queue must not silently drop the retry.** Inserting at `RETRY_GAP` when the
queue is shorter than that must append rather than fall off the end — otherwise a
fact missed near the end of a level is never re-asked, quietly defeating the
entire "he must learn the one he missed" rule.

**Guard the answer input against a seven-year-old.** Accept digits only, cap at
two characters, ignore `Enter` on an empty box. Without the cap he will hold a
key down and the text will run off the screen.

**`pygame.display.get_num_video_drivers()` does not exist** in pygame-ce 2.5.8
(confirmed: `AttributeError`). Do not use it while debugging step 1's gate.

---

## Considered and rejected

- **Web app (React + Vite + Tailwind), mirroring `leatherpros`.** *This was my
  own first recommendation and I changed my mind — the most likely path for a
  fresh context to re-walk.* The argument for it is real: in a browser a part
  tumbling off is a CSS transform and the art is resolution-independent SVG,
  where pygame requires integrating rotation per frame by hand. It loses because
  the user chose a desktop app with local-file storage, which removes the
  browser's decisive advantage (playing on a tablet with no dev server). What
  remains is `node_modules` versus one dependency. **Revisit only if the game
  needs to run on a tablet.**
- **Upstream `pygame`.** No cp314 wheel. Decided by a fact, not a preference.
- **`tkinter`** (present, zero dependencies, `Canvas` + `after()` can animate
  this). Rejected: no game loop, no sound, and manual easing anyway — the
  dependency saved is one package.
- **Kivy / PyQt.** Install weight and licensing complexity far beyond a
  single-screen kid's game.
- **numpy for sound synthesis.** Proven unnecessary; `array.array` feeds
  `Sound(buffer=...)` directly.
- **Sequential level unlocking.** Rejected as *more* code than open access, and
  it would force a kid who already owns bonds of five to grind past them.
- **A Hyprland window rule instead of design-surface scaling.** See the
  load-bearing decision.
- **Random fact generation.** Pools are small enough to enumerate; enumeration is
  simpler and testable.
- **Multiple-choice answers.** Trains recognition, and a smart kid reverse-engineers
  distractors. Typed answers force recall, which is the point of fluency.
- **A timer or speed pressure.** Rejected for v1 and **overturned afterwards** —
  see *Time pressure* below. The original reasoning (timers cause anxiety) was
  not wrong, which is why the clock ships with an off switch.

---

## Accepted with known risk

**Level 1 (`fives`) may bore him within about ninety seconds.** Raised during the
dig and accepted. The mitigation is already in the design: every level is
unlocked from the start, so he can skip straight to `bridge`. `fives` stays
because it is what makes `bridge` make sense. *Revisit if* he never voluntarily
plays it — at which point it becomes a warm-up folded into level 2 rather than a
level of its own.

**Ten parts per launch is a guess at pacing.** Accepted as a single constant to
retune after watching him play. *Revisit if* a launch takes over three minutes or
under forty seconds.

---

## Environment constraints not visible in the repository

- **Hyprland tiles the window.** The application cannot choose its own size. See
  the load-bearing decision.
- **`pytest` and `ruff` are not installed system-wide.** They must come in as
  `uv add --dev`; `pytest` is invoked as `uv run pytest`.
- **This directory is not a git repository.** `git init` is required and, per the
  user's standing instruction, **the user creates commits, branches, and anything
  on GitHub** — do not commit or push without asking.
- Author identity from git config is `Jared Campbell <jaredc@hey.com>`, which
  `uv init` already writes into `pyproject.toml`.

---

## Out of scope

Recorded in `ideas.md`, not built here: the parent-facing view of weak facts, a
second game mode, multiplication and skip-counting levels, two-digit addition
with regrouping (levels 4–5), adaptive difficulty, timed modes, and packaging or
distribution beyond `uv run mathr`.
