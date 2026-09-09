# mathr — plan

A desktop math game for one specific second grader. An **arcade** picks a game
mode — **Rocket Builder** or **Tennis Match** — and inside either he picks a
**level** from a grid of addition, multiplication and mixed pools. Each correct
math fact bolts another part onto a rocket drawn on screen; each miss knocks the
top part off and re-queues that fact to be asked again. Ten parts on and it
counts down and launches. Progress and per-fact attempt counts persist to a
local JSON file.

*(v1 shipped with Rocket Builder alone; the arcade and tennis are the section
at the end of this file.)*

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

## The arcade: a second mode, multiplication, and the flipped equation

Written after the v1 sections above, in the same spirit: the reasoning, not just
the outcome. **Built** — all four steps; what follows is why, not a proposal.

### What changes

The menu becomes an **arcade**: two drawn cabinets, Rocket Builder and Tennis
Match, either of which leads to a shared level screen of four columns —
Addition, Multiply, Division (dimmed), Everything. **Tennis Match** is the second
mode the architecture was built for: an opponent serves, the ball falls down a
perspective court toward the player, and solving the problem before it arrives
swats it back. Wrong answers cost nothing and can be retyped while the ball is
still in flight; a ball that gets past him scores for the opponent, three points
loses the match, ten returns wins a trophy. Three **multiplication** levels
(×2, ×5, ×10) join the three addition ones, plus a derived **Everything** pool.
And every equation now renders with the `=` on a randomly chosen side, so
`? = 3 + 2` is asked as often as `3 + 2 = ?`.

`storage.py` does not change at all.

---

### The load-bearing decision: tennis differs in *rules*, not in rendering

The v1 plan bets that a mode is only a renderer — *"a mode consumes a stream of
correct/wrong outcomes and renders progress however it likes"* (**The seam that
matters**, above). That bet does not survive tennis. Rocket Builder's clock is a
**shared bank** of seconds; tennis is a **per-rally deadline**. Five rules differ,
so `Round` gains a frozen `Rules` bundle with `ROCKET` and `TENNIS` constants,
and `tick` and `apply` read policy from it.

Here is what building tennis as a pure renderer over the existing rules actually
produces. Take `tens` (`seconds_per_part = 3.0`, `domain/facts.py:78`), so
`new_round` opens `seconds_left = GRACE_PARTS * 3.0 = 15.0` with `cap = 12.0`
(`domain/round.py:93`, `:73`), and draw the ball's position from
`seconds_left / cap` the way `draw.alien_scale` does (`shell/draw.py:238`):

1. **The serve does not move for three seconds.** `15.0 / 12.0` is above 1.0, so
   the ball sits pinned at the opponent's baseline until the bank falls under the
   cap. `alien_scale` clamps this deliberately — a saucer that starts off-screen
   is fine, a ball that hangs motionless is not.
2. **A correct answer does not reset the rally.** He answers at t=4.0 with 11.0
   left; `_credit` (`domain/round.py:123`) returns
   `max(11.0, min(11.0 + 3.0, 12.0)) = 12.0`. The ball retreats by one twelfth of
   the court and keeps coming. It never flies back to the opponent, so there is
   no rally — just a ball creeping inexorably closer.
3. **A wrong answer removes a return he already hit.** `apply` does
   `max(round.parts - 1, 0)` (`domain/round.py:148`). His score counter drops
   while the ball is still in the air. Nothing in tennis does that.
4. **The first ball he misses ends the match.** The bank empties, `tick` sets
   `failed=True` (`domain/round.py:119`), and there is no such thing as an
   opponent point. The three-point cushion cannot exist.

The symptom is what makes this load-bearing: **nothing fails**. It compiles, it
draws, every existing test passes, and it plays as a different game than the one
specified. There is no error message that says "your clock model is wrong".

```python
@dataclass(frozen=True)
class Rules:
    opening_parts: float      # bank at serve, in problems      5   | 1
    credit: str               # "cap" | "reset"                cap  | reset
    wrong_costs_part: bool    # parts - 1 on a wrong answer    True | False
    wrong_advances: bool      # move to the next question      True | False
    empty: str                # what a zero clock does         fail | point
    lives: int | None         # opponent points before a loss  None | 3
    target: int               # parts/returns to win            10  | 10

ROCKET = Rules(GRACE_PARTS, "cap",   True,  True,  "fail",  None, 10)
TENNIS = Rules(BALL_FLIGHT, "reset", False, False, "point", 3,    10)
```

`Round` carries `rules: Rules` and `points: int`. `PARTS_TO_LAUNCH` becomes
`rules.target`; `GRACE_PARTS` stays as `ROCKET.opening_parts`.

---

### The steps

Four, in this order for two concrete reasons: `Question` first because it is the
only change that touches every pool test, and doing it after `Rules` would mean
rewriting the reducer's deck handling twice; and the level screen must land in
the *same* step as the multiplication levels, because `LEVEL_BUTTONS`
(`shell/app.py:31`) lays levels out at `240 + index * 130` and seven levels reach
y=1020 of an 800-tall design surface. There is no order in which the current
screen survives a fourth level.

#### 1. `Question`: the `=` lands on either side

`domain/facts.py`, `domain/round.py`, `tests/test_facts.py`.

A frozen `Question(fact: Fact, flipped: bool)` renders `Fact.prompt`'s two
orientations and delegates `.answer` and `.key` to its fact. `Round.deck` and
`Round.queue` become `tuple[Question, ...]`; `new_round` draws each orientation
from the injected `rng` alongside the existing `rng.sample`, so rounds stay
deterministic per seed.

`Fact.key` (`domain/facts.py:26`) does **not** change, so pool sizes, the file
format and every recorded count are untouched — see the traps.

*Gate:* `uv run pytest`. `test_answer_is_the_blank_slot` moves to `Question` and
must assert `prompt.count("?") == 1` in **both** orientations — that is the
assertion that catches a flip that drops or duplicates the blank.
`test_shuffle_is_deterministic_per_seed` must still pass, which is what proves
the orientations came from the injected rng and not module-level `random`.

*Falsifies:* `README.md` lines 24-26, which show only `8 + ? = 10`-shaped
prompts. Add a flipped example in the same step.

#### 2. `Rules`, `lives`, and honest `Outcome` names

`domain/round.py`, `tests/test_round.py`, `tests/test_clock.py`,
`shell/app.py` (wiring only).

Add `Rules` as above. Rename `Outcome.LAUNCHED` → `WON` and `ABDUCTED` → `LOST`,
and add `POINT` for a ball getting past him. `Round.launched` / `failed` keep
their names: `storage._fold` (`storage.py:124`) reads them, and renaming them
would touch the file format for no gain.

Rocket behaviour must be **bit-identical** after this step. `TENNIS` exists and
is unused.

*Gate:* `uv run pytest`, with `test_clock.py`'s bank tests now parameterized over
both rule sets. The rocket half must still assert the *derivation*
(`GRACE_PARTS * seconds_per_part`, `BANK_PARTS * seconds_per_part`) rather than
literals, exactly as `test_start_and_cap_scale_with_the_level`
(`tests/test_clock.py:37`) does now — otherwise retuning a level breaks the suite,
which the v1 plan went out of its way to avoid.

*Falsifies:* the `Outcome` names in **The seam that matters** above, and
`CLAUDE.md`'s claim that `round.py` "knows `parts: int` and a bank of seconds" —
it now knows a rules bundle. Update both.

#### 3. The arcade, the four-column level screen, and multiplication

`shell/draw.py`, `shell/app.py`, `domain/facts.py`, `tests/test_facts.py`.

Domain: `_times_pair(a, b)` yields the two multiplication forms — `a × b = ?`
and `a × ? = c`. It is a sibling of `_from_pair` (`domain/facts.py:43`), not a
parameterization of it: `_from_pair` yields four questions including the two
subtraction forms, and the multiplication equivalents of those are division,
which is deliberately not built. Three levels — `twos`, `fives_times`, `tens_times`
— each 11 pairs (`n × 0` through `n × 10`), 22 facts apiece, all at
`seconds_per_part = 5.0`. Then `everything`, whose `facts` is the concatenation
of every other level's pool: **278 facts** (24 + 44 + 144 + 66, verified against
the running pools).

Note the id collision: the existing addition level is already `fives`
(`domain/facts.py:77`). The multiplication level must not reuse that id — it
keys `LevelRecord` in `progress.json`.

Shell: `render_menu` (`shell/app.py:316`) becomes the arcade — two drawn cabinets
with marquees and small live screens (the rocket reusing `draw_rocket`, tennis a
bouncing ball), with Sound / Timer / Quit as a small row along the bottom.
`render_levels` (`:327`) becomes four columns at roughly 270px wide; `_badge`
(`:412`) keeps its text but re-anchors **under** the level name rather than at
`button.rect.right - 140`, which no longer fits. Division shows three dimmed rows,
Everything shows one tall live button above a dimmed **Tricky Facts** button.
`self.screen` gains no new value — it stays `menu` / `levels` / `play`, with the
chosen mode carried on `App`.

**The keypad keeps its exact coordinates** (`shell/app.py:41`). Its hitboxes are
the one piece of UI verified by hand at several window sizes.

*Gate:* `uv run pytest` — `test_pool_sizes` becomes
`{fives: 24, tens: 44, bridge: 144, twos: 22, fives_times: 22, tens_times: 22,
everything: 278}`; `test_both_blank_forms_in_every_pool`
(`tests/test_facts.py:27`) asserts `ops == {"+", "-"}` for *every* level and must
become per-topic; `test_every_fact_is_true` (`:4`) only knows `+` and `-` and
needs a `×` arm. Then, by hand: `uv run mathr`, and check that both cabinets are
clickable, that the dimmed columns do nothing on click **and do not highlight on
hover**, and that the keypad still registers accurately in a tall narrow tile.

*Falsifies:* `plan.md` lines 3-4 ("the only mode now is **Rocket Builder**"),
`README.md`'s "Playing" section and level table, and `CLAUDE.md`'s **The map**
and **Making the two likely changes** (the level-button arithmetic it quotes is
now wrong). Fix all four here.

#### 4. Tennis

`shell/draw.py`, `shell/app.py`, `shell/audio.py`.

The court renders left of x=680: opponent small and far at the top, player near
and large at the bottom-left, the ball growing as it drops. Opponent points draw
as three markers, returns as a row like `draw_progress` (`shell/draw.py:212`).
Ball position is a pure function of `seconds_left / (seconds_per_part *
BALL_FLIGHT)` — the same shape as `alien_scale`, and for the same reason: it
retreats when he earns time back instead of only ever advancing.

`BALL_FLIGHT = 2.0` goes in `domain/round.py` beside the other dials, because
pacing is a rule.

Audio: three new clips built with the existing `_Shape` pattern — a percussive
`pock` for a return, a descending `drop` for a lost point, a bright `cheer` for
the trophy. The existing `wrong` buzz and `warn` are reused.
`self.sounds.play(outcome.value)` (`shell/app.py:254`) is replaced by a per-mode
outcome→clip mapping — see the traps.

*Gate:* `uv run pytest` for the domain half. Then by hand: `uv run mathr`, play a
tennis match on `tens`, and check that the ball resets on a hit, that a wrong
answer leaves the problem on screen with the ball still falling, that three
missed balls ends the match, and that all three new clips are actually audible —
clip *construction* is proven in tests, output through PipeWire is not.

*Falsifies:* `ideas.md`'s **A second game mode** entry, which becomes *built*,
following the pattern already set there by **Timed / speed modes**. Its
**Multiplication via skip counting** line under *More levels* is also now built.
Add the reserved spot for **A "tricky facts" practice mode** in the same edit.

---

### Traps

**`Fact.key` must not learn about orientation.** It is the storage format:
`"3+2=5@b"` keys counts in a file that outlives the code. Putting `flipped` in
the key orphans every count already recorded and needs a `version` bump plus a
migration. Orientation lives on `Question`, which is never serialized. The
symptom of getting this wrong is not a crash — it is a child's mastery record
silently resetting to zero.

**The reset credit must still never push the bank down.** The v1 trap holds in
the new rule: tennis credit is `max(left, flight)`, not `flight`. A hit that
arrives while the previous ball still had time on it must not *shorten* the next
rally as a reward for being fast.

**A wrong answer in tennis must not touch the queue at all.** Not advance it, and
not re-queue the fact. `apply` currently inserts the missed fact at `RETRY_GAP`
(`domain/round.py:144`); doing that while also leaving the question on screen puts
the same fact in the deck twice. The re-queue moves to the **timeout** path
instead — when a ball gets past him, the fact comes back three questions later
exactly as a missed rocket fact does.

**`Sounds.play` fails silently on an unknown name.** It is
`clip = self._clips.get(name)` (`shell/audio.py:128`) — a missing clip plays
nothing and raises nothing. `self.sounds.play(outcome.value)` (`shell/app.py:254`)
couples clip names to enum values, so renaming `LAUNCHED` → `WON` in step 2 turns
the launch sound off with no error anywhere. Replace that call with an explicit
per-mode map in the same step as the rename, not later.

**New clips must match `mixer.get_init()` exactly — 16-bit signed mono.**
`_tone` returns `None` on a mismatch (`shell/audio.py:30-31`) and `_tone` reads
the rate back rather than hardcoding it. From `CLAUDE.md`, verbatim: *"A mismatch
does not raise; it plays as static or at the wrong pitch."* Build the three new
clips through `_tone` and the `_Shape` pattern; do not hand-roll a buffer.

**Dimmed buttons must not hover.** `draw_button` (`shell/draw.py:198`) brightens
the fill and switches the border to `ACCENT` whenever `hovered` is true. A Division
row that lights up under the cursor and then does nothing on click reads as broken,
not as coming-soon. The dimmed path needs its own branch, and the click handlers
must skip those rects entirely.

**Tennis must never run untimed.** The Timer toggle applies to Rocket only. If
`TENNIS` were ever constructed with `seconds_left=None`, the `POINT` path has no
clock to reset and the ball has nowhere to be. Assert it where the round is built.

**Floor `parts` at zero in the reducer, not the renderer.** Unchanged from v1, and
newly relevant: tennis's `wrong_costs_part=False` means the floor is untested by
the tennis path, so the rocket tests are the only thing holding it.

**The `everything` pool must be derived, not hand-listed.** Concatenate the other
levels' `facts` at module level. A hand-copied list silently drifts the moment a
level is retuned, and `test_pool_sizes` would keep passing on a stale number.

**The court must not do its own scaling.** Everything is laid out in 1280×800 and
`draw.to_design` converts mouse positions once, at the event boundary. From
`CLAUDE.md`, verbatim: *"clicks are accurate near the top-left and drift further
out, which reads as 'sloppy hitboxes' and never as a scaling bug."*

---

### Considered and rejected

- **Tennis as a pure renderer over the existing bank clock.** My own first
  recommendation during the dig, and the one a fresh context is most likely to
  reach for, because it costs zero domain change. Walked through with real
  numbers above; it produces a ball that hangs motionless for three seconds, never
  resets, and ends the match on the first miss. Changed my mind before proposing
  it.
- **Two reducers over a shared `domain/deck.py`.** Rocket and tennis rules each
  stated with no flags at all. Rejected in favour of `Rules`: ~30 lines of
  near-duplicate reducer, two `Round`-ish types, and `storage.merge` would have to
  accept either.
- **Tennis rules in the shell**, wrapping `Round` with lives and reset. Violates
  the one-direction layering; `shell/` holds no rules.
- **Sudden-death tennis**, and **a wrong answer scoring a point immediately.**
  Both harsher than the rocket, which warns as the bank drains and lets him climb
  back out. With the keypad capped at two digits a mistype is cheap and common.
- **A wrong answer costing a return**, rocket-style. "My score went down" is not
  a thing that happens in tennis.
- **Ball flight = `seconds_per_part` exactly** (no `BALL_FLIGHT`). Honest to what
  the constant means, but strictly harder than any rocket round, since the rocket
  softens the same pace with a five-problem grace bank.
- **A ball that speeds up as the rally grows.** More arcade, but it makes "why did
  I lose" opaque to a seven-year-old, and it is a formula where a dial suffices.
- **Orientation as part of `Fact`.** Pools double, mastery tracks each orientation
  separately, and `Fact.key` changes shape — `VERSION 2` plus a migration of every
  recorded count. Not worth it: `3 + 2 = ?` and `? = 3 + 2` are the same retrieval.
- **One orientation per whole round.** Calmer, but he settles into the shape after
  two questions, which is most of what the flip was for.
- **Per-mode storage**, either as `"rocket:tens"` keys (changes an existing key's
  shape → version bump + migration) or as extra per-mode fields (additive and
  cheap, but `best_seconds` has to fork or become meaningless). One record per
  level; the per-fact tallies were always mode-agnostic.
- **A separate topic screen** (arcade → topic → level), and **topic tabs** on the
  level screen. Both add a click or a piece of screen state to save a layout
  problem that four columns solve outright.
- **A full-width court with the keypad moved to the bottom.** Best-looking court,
  but it relocates the only UI whose hitboxes were verified by hand across window
  sizes.
- **Three graded mixes in the Everything column** (Add Mix / Times Mix /
  Everything). Two of the three overlap almost entirely with the columns beside
  them.
- **Building tricky-facts now.** It needs a rule for what "tricky" means and has
  nothing to draw from on a fresh `progress.json`. It gets a dimmed spot instead.
- **Stars instead of text badges**, which would drop `best_seconds` from the
  screen, and **Division as one tall panel**, which hides how many levels are
  coming.
- **Division as empty `Level`s in `LEVELS`.** Every domain test that iterates
  levels would have to special-case a pool with no facts. The dimmed rows are
  shell-only.
- **Settings behind a gear icon.** Buries the Timer toggle, which exists precisely
  for the day the clock is too much and someone needs to find it fast.

---

### Accepted with known risk

**Wrong answers are free in tennis, so the answers are brute-forceable.** With
`tens` and a 6-second ball, a bright kid can type 8, 9, 10, 11 and let the pock
tell him when he is right — recognition instead of recall, which is the exact
failure that ruled out multiple-choice in v1. Accepted because the alternative
punishes mistypes. *Revisit if* his `wrong` counts in `progress.json` climb
sharply on tennis levels while `right` stays flat: at that point a wrong answer
should cost a point.

**Tennis at `BALL_FLIGHT = 2.0` is still harder than the rocket at the same
level.** There is no grace bank and no way to bank ahead. *Revisit if* he loses
0-3 repeatedly on `tens` — raise `BALL_FLIGHT` before touching `seconds_per_part`,
which would change the rocket too.

> **Revised after watching it played.** `BALL_FLIGHT` is now **1.5**, and the
> reason was not difficulty. At 2.0 the ball crept, and — worse — a correct
> answer reset the rally in the same frame, so the ball vanished from in front
> of him and reappeared at the far baseline. It never looked *hit*, which is the
> one thing the mode exists to make it look like. The fix is a shell-side
> `Volley`: his return flies back over the net for `RETURN_FLIGHT` (0.34s) with
> the clock paused, the same gate focus-loss already used. The pause is not
> charity — it is the follow-through, and it is why the faster ball is still
> fair. A ball that gets past him now carries on out of the court for 0.5s
> instead of teleporting too. Both flights are pure functions in `draw.py`; the
> domain did not change beyond the constant.

**The `everything` pool is weighted by pool size**, so `bridge` alone is 144 of
278 facts — 52% of what he sees. *Revisit if* it plays as "just Over the Ten
again": sample a level first, then a fact within it.

**`seconds_per_part = 5.0` for all three multiplication levels is a guess**,
matching `bridge` on the grounds that it is new material. Same instrument as
before: `failures` per level in `progress.json`.

**Ten returns and three points are guesses**, exactly like `PARTS_TO_LAUNCH`.

**One record per level means "3 wins" does not say which mode won them.**
*Revisit if* he asks how many tennis matches he has won — per-mode counters can be
added beside the existing fields and read through `.get`, with no version bump.

---

### Environment and coverage notes

Verified by running, not remembered: **pygame-ce 2.5.8, SDL 2.32.10, Python
3.14.7**; the three current pools really are 24 / 44 / 144. `pytest` and `ruff`
are not installed system-wide — `uv run pytest`. The v1 constraints all still
hold: Hyprland tiles the window, `pygame.display.get_num_video_drivers()` does not
exist in this pygame-ce, and **the user creates commits, branches and anything on
GitHub**.

**Where my reading was partial**, so it is not inherited as coverage: I read
`domain/round.py`, `domain/facts.py`, `storage.py`, `shell/app.py`,
`shell/draw.py`, `shell/audio.py`, `tests/test_round.py`, `tests/test_clock.py`,
`tests/test_facts.py` and `tests/test_scaling.py` in full. I read only the helper
and assertion lines of `tests/test_storage.py`, the first 50 lines of
`README.md`, and `plan.md` in sections rather than end to end.

**Verify before relying on it:** that no call site passes an unknown name to
`Sounds.play` today (grep before the rename, so the new map is exhaustive); and
that `draw_button`'s hover branch is the only place a button's appearance changes,
before adding the dimmed path.

---

### Out of scope, and where it went

Recorded in `ideas.md`, not built here: **Division's content**, **the rule for
what "tricky" means** in the tricky-facts mode (both reserved as dimmed buttons on
the level screen), the parent-facing view of weak facts, two-digit addition with
regrouping, adaptive difficulty, and packaging beyond `uv run mathr`.
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
