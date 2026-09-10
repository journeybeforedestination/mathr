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

## Learning feedback: a number line on a miss, and a deck that knows what is slow

### What changes

A wrong answer stops being a red flash and becomes a picture. When he misses —
or, in tennis, when the ball gets past him — the clock stops, and a number line
draws the route to the answer over the left half of the screen: `8 + 6` as a
jump of 2 to ten and a jump of 4 past it, `5 × 7` as seven jumps of five. It
clears when he types the next digit. Separately, the deck stops being a uniform
shuffle: facts he answers slowly are ordered early, so a ten-part round spends
its questions where his time is actually going. No new screen, no new mode, no
new file in `progress.json`.

Both changes are argued from `research/math-education.md` (on branch
`worktree/rapid-meadow-32ee`, commit `79c74c3` — **not on `main`**, and
`research/` is an empty directory here). §2.3 of that document is the case for
the first: elaborated feedback measures *d ≈ 0.49* against *d ≈ 0.05* for
correct/incorrect alone. §1.1 and §1.3 are the case for the second.

### The load-bearing decision: the pause is a rule, so `hint` lives in `Round`

The hint has to stop the clock, and stopping the clock is not a shell concern.
`CLAUDE.md` already states the general form of this — *"Pacing is a rule, so the
clock is in the domain"* — but the concrete failure is worth walking, because
the shell-side alternative looks obviously simpler and is wrong.

Suppose the hint were a `Play` field in `shell/app.py` with `App.update`
skipping `tick` while it shows, the way it already skips `tick` during a volley.
Play a `bridge` round in the rocket:

1. `seconds_per_part = 5.0`, so the round opens at `5.0 × GRACE_PARTS` = 25s
   (`round.py:19`, `round.py:53`).
2. He misses `13 − 6`. The hint draws. He reads it for four seconds — which is
   the point of showing it.
3. `App.update` skipped `tick`, so `seconds_left` is untouched. Good so far.
4. But `tick` is also what accumulates `on_current` (`round.py:163`), and
   `apply` folds `on_current` into the per-fact `Tally` (`round.py:209`).
   Skipping `tick` in the shell keeps the reading time out of the record only by
   accident of where the skip was written.
5. Now the next person adds a second reason to pause — a "well done" hold, a
   parent-view overlay — and puts the skip somewhere else, or pauses only the
   clock and not the timer. Reading time lands in `Tally.seconds`.
6. `Tally.seconds` is what the new deck weighting reads. Hint-reading time
   inflates the weight of the fact he was just shown, which pushes that fact to
   the front of the next deck, which shows the hint again.

The failure is a feedback loop between two features that never mention each
other, and its symptom is "he keeps getting the same questions", which names
nothing. Putting `hint: Question | None` on `Round` and having `tick` return
early while it is set makes all three clocks — `seconds_left`, `on_current`,
`elapsed` — stop together by construction, and makes it testable without
opening a window.

It also pays for itself twice: `App.ball` derives the ball's height from
`seconds_left` (`app.py:401`), so a frozen clock holds the tennis ball in
mid-air with no extra code.

### The evidence that chose the signal

From the user's live `~/.local/share/mathr/progress.json` at the time of the
dig — 105 answers over 76 distinct facts, 45 of them seen exactly once:

- **Four facts have ever been answered wrong.** Two of those (`5 − ? = 5` and
  `9 + 1 = ?`) were wrong in under three seconds, with the same facts right on
  other attempts. Slips, not ignorance — exactly the case §1.3 of the research
  says a streak rule punishes.
- **The slow facts are all bridging facts**: `6+9` 23.6s, `13−6` 18.6s, `13−8`
  13.6s, against `seconds_per_part = 5.0` for that level. One fact eating the
  entire 25s grace bank is why `bridge` reads `launches: 0, failures: 2`.

So the weighting is on **mean response time**, not on wrong counts, which would
barely fire. A wrong answer's thinking time is already folded into
`Tally.seconds` regardless of correctness (`round.py:209` records `on_current`
on both paths), so slow-and-wrong floats up without a separate term.

The same file shows `everything`, `fives_times` and `tens_times` have **never
been played** — the interleaved pool the research ranks highest already exists
and he has never picked the card. Deliberately no change; see *Accepted with
known risk*.

### The steps

Steps 1 and 2 are independent of each other and both must land before step 3,
which needs data to draw and a stopped clock to draw it against. Step 4 touches
neither and can land in any order; it is last because it is the one that changes
what he sees on screen the least.

---

**Step 1 — `Fact.strategy` in `domain/facts.py`.**

Add a frozen `Strategy(start: int, jumps: tuple[int, ...])` and a `strategy`
property on `Fact`, beside the existing `sides` (`facts.py:37`) and `prompt`
(`facts.py:44`). Pure numbers: no coordinates, no colours, no span. The span the
line is drawn across is the shell's business.

Derivation, from `(a, op, b, result)` only:

| case | start | jumps |
|---|---|---|
| `+`, `result ≤ 10` | `0` | `(a, b)` |
| `+`, `result > 10` | `a` | `(10 - a, result - 10)` |
| `−` , `a > 10 ≥ result` | `a` | `(-(a - 10), -(10 - result))` |
| `−`, otherwise | `a` | `(-b,)` |
| `×` | `0` | `(a,) * b` |

Worked: `8 + 6 = 14` → `start 8, jumps (2, 4)`. `15 − 7 = 8` → `start 15,
jumps (-5, -2)` (`_from_pair` stores the total in `Fact.a`, so `a` is the
minuend — `facts.py:81`). `6 + 4 = 10` → `start 0, jumps (6, 4)`, the whole
bond, which is what Make Five and Make Ten are for. `5 × 7 = 35` →
`start 0, jumps (5,)*7`.

**`blank` is not an input.** The picture always shows the complete true
equation; showing the route *and* the answer is the intervention. This also
disposes of a latent hazard: `Fact` permits `blank == "a"` but `_from_pair` and
`_times_pair` only ever produce `"b"` and `"result"` — verified across all 278
facts — so a `strategy` that ignored `blank` cannot be wrong about a case that
does not exist.

Tests, in `tests/test_facts.py`: every fact in `EVERYTHING` produces a strategy
whose jumps sum from `start` to the correct endpoint (`result` for `+`/`×`,
`result` for `−` counting back from `a`); bridging facts produce exactly two
jumps with the first landing on 10; times facts produce `b` equal jumps.

Falsifies no documentation.

---

**Step 2 — `hint` in `domain/round.py`.**

`Round` gains `hint: Question | None` (`Round` is at `round.py:79`). One field
carries both "the clock is stopped" and "this is the question being drawn", so
the two can never disagree.

- `new_round` (`round.py:113`) sets it to `None`.
- `tick` (`round.py:150`) returns `(round, None)` unchanged when `hint` is set —
  place this beside the existing `if round.over` guard so all three clocks stop
  together. On the `Outcome.POINT` path (`round.py:180`) it sets
  `hint=round.current`, the ball he never answered. On `Outcome.LOST` it does
  **not**: the round is over and the failure screen owns the display.
- `apply` (`round.py:202`) sets `hint=question` when the answer is wrong and
  `None` when it is right — on both the early tennis return (`round.py:212`) and
  the main path. Because `apply` always writes the field, a stale hint cannot
  survive an answer.
- A `dismiss(round)` reducer clears it. The shell calls it; the domain never
  clears it on its own.

Gate: `uv run pytest`. **`tests/test_clock.py:201`
(`test_three_points_lose_the_match`) will fail** — it calls `tick` three times
in a row, and the second call now no-ops against the hint the first one set.
Fix it by calling `dismiss` between ticks, which is what the game does. Verify
the rest of the suite: `test_a_wrong_answer_costs_a_part_but_no_extra_time`
(`test_clock.py:84`) and `test_a_wrong_answer_leaves_the_ball_in_the_air`
(`test_clock.py:209`) do not tick after the miss and should pass untouched.

New tests in `test_clock.py`: the clock does not drain while a hint is set;
`on_current` does not grow while a hint is set; `dismiss` resumes both; a
timeout in tennis sets the hint to the question that timed out; an abduction
does not set one.

Falsifies `CLAUDE.md`, *Invariants that break silently*: **"`tick` accumulates
per-question time even when untimed"** — still true, but now "except while a
hint is showing, which is the whole reason the hint is in the domain." Update it
in this step.

---

**Step 3 — the widget in `shell/draw.py`, wired in `shell/app.py`.**

`draw.draw_number_line(surface, font, strategy, prompt, rect)`: a horizontal
line, a dot at `start` and at each cumulative position, an arc and a signed
label (`+2`, `−5`) above each jump, and the question's own prompt above the
whole thing — the hint carries its prompt because in the rocket `apply` has
already advanced the queue, so `round.current` is no longer the fact being
explained.

Placement: over the left half, roughly x 60–660, y 220–640. Free in both modes —
`ROCKET_ORIGIN = (110, 130)` (`draw.py:34`) and the court spans x 75–625
(`COURT_CENTRE = 350` ± `COURT_NEAR_HALF = 275`, `draw.py:342`/`draw.py:344`) —
and it leaves the keypad (x ≥ 700, `app.py:128`) untouched, which matters
because in tennis he retypes the same question while the hint is up. Design
surface is 1280×800 (`draw.py:13`); everything here is design space.

The renderer owns the span and must handle three degenerate shapes: a jump of
length 0 (18 of the 278 facts — `0 + 5`, `5 − 0`, `2 × 0` in both blank forms),
which draws as a dot with a `+0` label rather than being special-cased away; an
empty `jumps` tuple (`2 × 0` and its siblings), which draws a single dot at the
start; and ten equal jumps (`10 × 10`), which sets the widest span it must fit.

Wiring in `app.py`:

- `render_play` (`app.py:541`) draws the hint after the mode renderer and before
  `render_entry` (`app.py:607`), and skips `render_entry`'s prompt line while a
  hint is up — otherwise two different questions are on screen at once.
- `press` (`app.py:361`) calls `dismiss` first when `round.hint` is set, then
  proceeds; the digit that dismisses also counts as entry, so no keystroke is
  lost. Both the keyboard path (`app.py:260`) and the keypad-click path
  (`app.py:271`) already funnel through `press`, so this is one place.
- `update` (`app.py:436`) must skip `warn` while a hint is set. `tick` now
  returns `seconds_left` unchanged, so the low-bank pulse (`app.py:469`) would
  otherwise keep beeping at a fixed rate under a stopped clock.

Gate: `uv run mathr`, miss a `bridge` fact in the rocket and let a ball past in
tennis. Watch for: the line reads at a glance, the ball is frozen rather than
falling, the keypad is not covered, and the first digit both clears the hint and
lands in the entry box.

Falsifies `README.md:39–40` (rocket, "**Wrong** → the top part tumbles off…")
and `README.md:51` ("**Wrong** → nothing. The ball is still in the air…"), and
the clock description around `README.md:87–109`. Update all three in this step.

---

**Step 4 — the weighted deck.**

`shuffled` (`facts.py:74`) gains an optional third parameter,
`weights: Mapping[str, float] | None = None`. When it is `None` the function
must behave *byte-identically* to today — same `rng.sample`, same interleaved
`rng.random() < 0.5` orientation flip — or every seeded test moves. When it is
given, order by the standard weighted sample without replacement: key each fact
`rng.random() ** (1 / w)` and sort descending.

The weights are computed in `domain/round.py`, not in `facts.py`. `Tally` lives
in `round.py` (`round.py:61`) and `round.py` already imports `facts`
(`round.py:14`); computing weights in `facts.py` would need `Tally` and close
the cycle. `new_round` (`round.py:113`) gains
`history: Mapping[str, Tally] | None = None`, turns it into a plain
`key -> float` map, and hands that to `shuffled`. `facts.py` never learns what a
`Tally` is.

The weight of a fact with `answered > 0` is
`clamp(tally.seconds / tally.answered / level.seconds_per_part, FLOOR, CEILING)`;
an unseen fact weighs `1.0`, so it still appears rather than being crowded out —
45 of 76 facts have `answered == 1`, so there is not enough history to trust a
verdict on any of them. Start at `WEIGHT_FLOOR = 0.5`, `WEIGHT_CEILING = 4.0`.

The full pool stays in the deck; only its order is biased. A ten-part round
draws from the front, so ordering *is* selection, and no level can ever empty
its deck — which is what keeps this from needing a "mastered" state on the level
screen.

`App.start` (`app.py:344`) passes `self.progress.facts` through. No storage
change at all: no new field, no `version` bump, nothing to migrate.

Tests, in a new `tests/test_select.py`: a fact with a slow mean sorts ahead of a
fast one across seeds; an unseen fact is not starved; the clamp bounds a single
outlier (the real 23.6s `6+9` would otherwise weigh 4.7× against `bridge`'s 5.0s
pace); `shuffled` with no weights is unchanged for a given seed — assert against
`tests/test_round.py:93` (`test_shuffle_is_deterministic_per_seed`) and
`tests/test_facts.py:38`.

Falsifies `ideas.md`, *Adaptive difficulty* — currently "**Rejected for v1** as
complexity without evidence — the per-fact data will show whether it is needed."
The data did show it. Rewrite that entry as built, keeping what remains: spacing
across days, mastery as a probability, and retirement of known facts.

Also falsifies the `CLAUDE.md` *Tuning* table (`CLAUDE.md:81–89`), which must
gain `WEIGHT_FLOOR` and `WEIGHT_CEILING` — they are dials meant to be turned
after watching him, exactly like `RETRY_GAP`.

### Traps

**A hint set on the `LOST` path strands the round.** `tick` returns early while
`hint` is set, and `App.update` only advances `since_failure` outside that
branch. Set a hint on an abduction and the failure animation is driven by a
clock that has stopped. The failure screen owns the display; `LOST` sets no
hint. Symptom: the beam freezes half-drawn and *Try again* never appears.

**The `warn` pulse must be skipped while a hint shows.** `warn` (`app.py:469`)
sets its own interval from `seconds_left / threshold`. Under a stopped clock
that ratio is constant, so it degenerates into a metronome at a fixed rate
while he reads — and its own docstring says the pulse exists to *quicken*.
Nothing raises.

**`shuffled(facts, rng)` with no weights must consume the rng exactly as it does
today.** Two tests pin shuffle determinism per seed (`test_round.py:93`,
`test_facts.py:38`), and the function interleaves the orientation flip with the
sample (`facts.py:74–78`), so a "harmless" restructuring of the unweighted path
changes which questions are flipped as well as their order. Add the weighted
path as a branch; do not rewrite the existing one.

**Weights must not be computed in `facts.py`.** `round.py` imports `facts`
(`round.py:14`). Reaching back for `Tally` closes an import cycle that Python
reports as a partially-initialised module from whichever side imported first —
a message that names neither the cycle nor the design mistake.

**Hint-reading time must never reach `Tally.seconds`.** It is the input to the
deck weighting, and inflating it for the fact just explained creates the loop
described in the load-bearing decision. This is guaranteed only by `tick`
returning before it touches `on_current` (`round.py:163`) — not by anything in
the shell.

**`Fact.key` is untouched by all of this,** and must stay that way.
`CLAUDE.md`: *"Changing its shape orphans every count already recorded and
needs a `version` bump plus a migration."* Nothing in this plan writes a new
field to `progress.json`; the weighting reads what is already there.

### Considered and rejected

- **A line of text instead of a drawing** (`8 + 6 → 8 + 2 + 4`). This was my
  recommendation during the dig, on the grounds that a string crosses the domain
  seam cleanly and needs one `draw.text` call. The user chose the drawing, and
  the reason it is the better call is that it costs almost nothing extra: the
  domain still hands over numbers, and one renderer covers all three pools. It
  also lands Siegler's number line (§3.2 — number-line estimation is the
  strongest longitudinal predictor in the research) for free. Recorded because a
  fresh context will feel the same pull toward the string.
- **A bar model for the bond levels, a line for the rest.** More natural for
  Make Five and Make Ten, but it means two renderers and a kind tag on the
  domain shape for the shell to switch on. One widget, one seam.
- **Ten frames.** The manipulative he most likely sees at school, and excellent
  for bridging — but `5 × 10` needs ten of them and the widget stops scaling.
- **A fixed hint duration, or a tap-to-continue button.** A duration is one more
  number to tune and cuts off a slow reader mid-sentence; a button adds a press
  to a screen made only of keypad. Typing the next digit is self-paced and
  already the thing he was going to do.
- **Holding the rocket's queue until the hint is dismissed** so the missed
  question stays current. Coherent, but it makes `Rules.wrong_advances`
  conditional on the hint, and that dial is load-bearing for tennis
  (`CLAUDE.md`, *A wrong answer in tennis must not touch the queue*). The hint
  carries its own prompt instead.
- **Weighting on right/wrong, or on a streak.** His data has four wrong answers
  in 105, two of which are typos. The signal is not there, and a streak rule
  punishes a slip.
- **Bayesian knowledge tracing** (§1.3). Four parameters to fit against 105
  observations. Revisit when there are thousands.
- **Weighted sampling with replacement**, so a mastered fact may not appear for
  many rounds. Sharper, but the deck stops being the pool and `_advance`'s
  replay-when-low rule (`round.py:145`) needs rethinking.
- **Retiring mastered facts outright** (true DT–PI, §1.4). A fully mastered
  `fives` empties its deck, and the level screen then needs a "done" state — a
  UI decision, not a policy change.
- **`last_seen` and spaced review across days** (§2.2, *g* ≈ 0.28). It is the
  weakest of the four ideas, needs a date injected into the domain, and 45 of 76
  facts have been seen exactly once — there is nothing to space on yet.

### Accepted with known risk

- **Hints are always on, with no menu toggle.** The concern is that his
  response-time record now mixes two regimes and nothing in `progress.json` says
  which. Accepted because a third toggle beside Sound and Timer
  (`app.py:90`) is one more thing for a seven-year-old to poke, and because
  every study in §2.3 provided feedback — none made it optional. Revisit if the
  per-fact means visibly shift after this lands and you need to compare against
  the pre-hint history.
- **Nothing is done about `Everything` never being played.** The interleaved
  pool is the best-evidenced practice in the research (*d ≈ 1.21*) and he has
  never chosen the card. The concern is that the best mode goes unused
  indefinitely. Accepted because deciding now means guessing why a seven-year-old
  skips a card. **Trigger to revisit: `launches` for `everything` still 0 after
  the next few sessions** — the counter already records this, at no cost.
- **The hint panel covers the rocket, the alien and any falling parts.**
  Accepted: the rocket is static and the clock is stopped, so nothing live is
  hidden. Revisit if he reports losing track of how many parts he has.

### Environment and coverage notes

- The research document is **not on `main`**. It is at
  `research/math-education.md` on `worktree/rapid-meadow-32ee`, commit
  `79c74c3`; `research/` on `main` is an empty directory. Read it with
  `git show 79c74c3:research/math-education.md`. Whether it should be merged to
  `main` is the user's call.
- The evidence in *The evidence that chose the signal* came from the user's live
  `~/.local/share/mathr/progress.json`, which is outside the repository and will
  have moved on. Re-read it before tuning `WEIGHT_FLOOR` / `WEIGHT_CEILING`.
- **Partial reading.** `shell/draw.py` was read by structure and grep, not in
  full — the drawing primitives available for the number line (arcs, dashed
  lines, font sizes beyond `draw.text` at `draw.py:223`) still need reading
  before step 3. `shell/audio.py`, `tests/test_scaling.py` and
  `tests/test_storage.py` were not read at all; `tests/test_round.py` and
  `tests/test_clock.py` were read in the regions cited above, not end to end.
- Whether the hint should make a sound is undecided and unexamined; `audio.py`
  was not read. `Sounds.play` fails silently on an unknown name
  (`CLAUDE.md`), so a clip added carelessly here is silent with no error.
- `pytest` is not installed system-wide; the suite is `uv run pytest` and takes
  about 0.1s. The suite opens no window — the three things it cannot reach are
  listed in `CLAUDE.md`, *Testing, and what testing cannot reach*.
- The user creates commits and anything on GitHub. Do not commit or push without
  asking.

### Out of scope, and where it went

Recorded in `ideas.md`, not built here: spacing across days, mastery as a
probability, retirement of mastered facts, and the parent-facing trend probe
(§1.2's fixed mixed measurement) — all of them waiting on more than 105 answers.
The `everything` card's visibility is left to the `launches` counter. The
number-line widget from step 3 is most of a number-line *placement* mode (§3.2),
but that is a new mode with a non-boolean outcome and belongs in `ideas.md`, not
here.

---

## Football: a drive, and a pass placed on the field

A third cabinet, **Touchdown Drive** (working title — the mode id is
`football`; do not call it anything with *field goal* in it, for the reason
below). Most downs are ordinary keypad facts from the same level pools,
scored exactly as the rocket scores them: correct advances the ball ten yards,
wrong loses ten. Every fourth down is different — no keypad. A number appears
("throw to the 37"), the field is drawn as a bare 0–100 line with the goal lines
and the 50 marked and nothing else, and he **clicks where that number goes**. A
throw within tolerance completes for a thirty-yard gain; a wide one falls
incomplete and costs nothing. A hundred yards is a touchdown and wins the round.
The clock is the rocket's draining bank, and it stops dead while a throw is
pending.

The mode exists for the throw. Number-line estimation is the strongest
longitudinal predictor in `research/math-education.md` §3.2 — first-grade
whole-number line estimation predicting seventh-grade fraction arithmetic — and
it is the only thing in this game that cannot be gamed by memorising a table.
The drive is the wrapper that gets him to take twenty of them a week.

### The load-bearing decision: the placement is a pass, not a field goal

The obvious framing is a field goal. It is wrong, and the failure is not a
matter of taste.

Walk it with real numbers. `Rules.target` counts `parts`, and `parts` is the
ball's position: 0 at his own goal line, 10 at the opponent's. A field goal
worth three parts, attempted every fourth down, plays out as:

1. Downs 1–3: three correct answers, `parts` 0 → 3. Ball on the 30.
2. Down 4: a good kick. `parts` 3 → 6. **Ball on the 60.**
3. Downs 5–7: three more correct. `parts` 9. Ball on the 90.
4. Down 8: a good kick. `parts` 10 → touchdown.

Step 2 is the problem. A field goal in football *ends the possession* — the ball
goes back to the other team on a kickoff. A kick that moves your own offence
thirty yards downfield and lets you keep playing is not a rule of any football
code. The mode would compile, draw, and play correctly while teaching him
something false about the sport it is named after; the symptom is a seven-year-old
who is confused the first time he watches a real game, which never gets reported
as a bug.

The alternative that keeps the kick is to make `parts` *points on a scoreboard*
and add a separate yards counter to `Round` so the domain knows when he is in
range. That is two counters and at least three new `Rules` dials, for a mode
whose whole reason to exist is the number line.

A deep pass has none of this. A completed pass advances the drive — that is
exactly what a completed pass does — so mechanic and metaphor agree, `parts`
stays yards-in-tens, `Rules.target` stays 10, and the whole rule set is
`ROCKET` plus two dials.

Everything below is downstream of that. The domain names it a *placement*, never
a pass: `domain/round.py` is not allowed to know about footballs any more than it
knows about rockets or tennis balls, and the next placement mode should not have
to fake a receiver.

### What changes, file by file

| File | Change |
|---|---|
| `src/mathr/storage.py` | `VERSION` 1 → 2; `LevelRecord` keyed by `"<mode>/<level>"`; migration; new `placements` section |
| `src/mathr/domain/round.py` | two `Rules` dials, `PLACE_MAX`, `PLACE_TOLERANCE`, `Aim`, `Round.targets`/`placed`/`placing`, `place()`, two `Outcome` members, `tick` early return |
| `src/mathr/shell/audio.py` | two clips: `catch`, `incomplete` |
| `src/mathr/shell/draw.py` | `draw_cabinet` scaled to `rect.height`; `draw_field`; `draw_gridiron` (cabinet art) |
| `src/mathr/shell/app.py` | `FOOTBALL` mode, 2×2 `CABINETS`, `render_field`, click-to-place, `render_play` dispatch, `press`/`warn` gating |
| `tests/` | new `test_place.py`; additions to `test_clock.py`, `test_storage.py` |
| `README.md`, `CLAUDE.md`, `ideas.md` | see each step |

### The steps

Ordered by what has to exist before what. Storage leads because the migration is
cheaper with two modes in the file than with three, and because a football round
that lands first writes into the shared bucket and then has to be untangled.
Audio precedes the shell so the mode is never silently mute. The cabinet layout
precedes the shell because the mode is unreachable without a cabinet.

---

#### Step 1 — Split `LevelRecord` by mode, and add `placements`

`storage.py:124` `_fold` keys the record by `round.level_id` alone and `Round`
carries no mode, so **a tennis win already increments the same `launches` as a
rocket win on the same level**, and `best_seconds` is already a minimum across
two clocks that are not comparable. `README.md:192–195` records this as a
deliberate choice. It is being overturned: a third mode makes the badge on a
level card the mixture of three different games, and `_badge`
(`shell/app.py:682`) has no way to say so.

- `VERSION = 1` → `2` (`storage.py:18`).
- `Round` gains `mode_id: str`, set by `new_round` from a new argument. The
  alternative — `merge(progress, round, mode_id)` — leaves `Round` unable to
  answer "which game was this", which the placement tallies also need.
- `_fold`/`merge` key `progress.levels` as `f"{round.mode_id}/{round.level_id}"`.
- `load` migrates: when the file's `version` is 1, every `levels` key `k`
  becomes `f"rocket/{k}"`. Rocket is the right guess — it is the default mode
  (`shell/app.py:201`) and, per the dig, `everything`, `fives_times` and
  `tens_times` had never been played at all.
- `Progress.level(level_id)` (`storage.py:41`) takes a mode too. All call sites
  are in `render_levels` (`shell/app.py:540`).
- New top-level `placements` section, read through `.get` like every field added
  since v1: `{"30": {"attempts": 4, "error": 21.5}}` — key is the target's
  decade bucket as a string, `error` is summed absolute yards. Bucketed, not
  keyed by exact yard, because 11 keys fill with usable data in a week and 101
  keys never do.

**Gate:** `uv run pytest`. New tests in `test_storage.py`: a v1 file's `fives`
record loads as `rocket/fives`; a rocket win and a tennis win on the same level
land in separate records; `placements` round-trips; a v2 file missing
`placements` loads as empty.

**Falsifies:** `README.md:192–195` ("One record per level, shared by both
modes…") — rewrite in this step. `plan.md:530–532` ("it keys `LevelRecord` in
`progress.json`") is still true but now under-specified; add the mode prefix.
`CLAUDE.md`'s `Fact.key` invariant explicitly permits *adding fields beside*
`right`/`wrong` without a bump — that is unchanged and unaffected; this bump is
for the `levels` key shape, which is a different format.

---

#### Step 2 — The placement in the domain

No shell in this step. Everything here is testable without opening a window.

New in `domain/round.py`, beside the existing dials at lines 16–28:

```python
PLACE_MAX = 100          # the span of the line, in whatever the mode calls units
PLACE_TOLERANCE = 6      # how far off still counts
PLACE_EVERY = 4          # downs between placements
PLACE_PARTS = 3          # what a good one is worth
```

`Rules` (`round.py:40`) gains two fields, both defaulted so `ROCKET` and
`TENNIS` at lines 59 and 63 need no edit:

```python
place_every: int | None = None   # None: this mode has no placements
place_parts: float = 0.0
```

`Outcome` (`round.py:31`) gains `PLACED = "placed"` and `ADRIFT = "adrift"`.
Domain-neutral names on purpose — `CAUGHT`/`INCOMPLETE` would put a football in
the reducer, which is the seam `CLAUDE.md` says not to cross.

`Round` gains:

```python
targets: tuple[int, ...]   # drawn once, in new_round, from the rng
placed: int                # how many have been resolved
```

and `placing` as a **derived property**, not a stored field:

```python
@property
def placing(self) -> int | None:
    every = self.rules.place_every
    if every is None or self.over or self.hint is not None:
        return None
    if self.asked // every <= self.placed:
        return None
    return self.targets[self.placed]
```

Derived rather than stored because a stored `placing` would have to be written
on every path through `apply` the way `hint` is (`round.py:274` writes `hint` on
both the right and the wrong path precisely so a stale one cannot survive an
answer), and a single missed path is a placement that never appears or one that
appears twice. Derived, only `place()` writes anything, and `placing` cannot
disagree with `asked`.

Note the `hint is not None` clause: **the hint wins.** A wrong answer on the
fourth down sets `hint` and makes a placement due on the same frame; he sees the
number line for the fact he just missed, and the throw appears when he dismisses
it. Without the clause both are live at once and the shell has to arbitrate,
which is a rule in the shell.

`targets` are drawn in `new_round` — `rng.choices(range(PLACE_MAX + 1), k=n)` —
and never during a reduction, because `tick` and `apply` take no rng and the
suite pins shuffle determinism per seed. Draw enough for the longest possible
round; the queue replay in `_advance` (`round.py:185`) means `asked` has no upper
bound, so index with `self.placed % len(self.targets)` or draw generously and
document the cap.

`tick` (`round.py:206`) currently reads:

```python
if round.over or round.hint is not None:
    return round, None
```

It becomes `or round.placing is not None`. This is the whole reason the
placement is in the domain: `seconds_left`, `on_current` and `elapsed` stop
*together*, by construction. It also buys a property for free — the seconds he
spends aiming never reach the next fact's `Tally.seconds`, so aiming time cannot
push a fact up the deck weighting.

New reducer, beside `dismiss` at `round.py:254`:

```python
def place(round: Round, value: int) -> tuple[Round, Outcome]:
```

Thresholds `abs(value - round.placing) <= PLACE_TOLERANCE` into a boolean at
this boundary — research §6 calls this "cheapest, probably right" — records an
`Aim(attempts, error)` under the target's decade bucket in a new
`Round.aims: Mapping[str, Aim]`, increments `placed`, adds `place_parts` on a
good throw and nothing on a wide one, and returns `PLACED` or `ADRIFT`. It must
also set `launched` when `parts >= rules.target`, exactly as `apply` does at
`round.py:280` — a touchdown can be scored by a throw.

A wide throw is **not** re-queued. There is no fact to re-ask; the next target
is drawn fresh. `RETRY_GAP` has nothing to do with this path.

New rules bundle:

```python
FOOTBALL = Rules(GRACE_PARTS, BANK_PARTS, 1.0, True, True, None,
                 PARTS_TO_LAUNCH, PLACE_EVERY, PLACE_PARTS)
```

**Gate:** `uv run pytest`. New `tests/test_place.py`: a placement is due after
`PLACE_EVERY` answers and not before; every clock stops while one is pending
(mirror `test_no_clock_runs_while_a_hint_shows`, `test_clock.py:230`); a hint
suppresses a due placement until dismissed; exactly on tolerance is good and one
past it is not; a wide throw costs no parts and no time; a good throw can win
the round; `place` on a round with `place_every is None` raises; aiming time
never reaches `Tally.seconds` (mirror `test_hint_reading_time_never_reaches_the_record`,
`test_clock.py:250`). Add to `test_clock.py`: the derivation tests at lines 42
and 51 should pass under `FOOTBALL` as they do under both existing rule sets.

**Falsifies:** `CLAUDE.md`'s statement that `domain/round.py` "knows `parts: int`,
a bank of seconds and a `Rules` bundle" — it now also knows a span and a
tolerance. Update in the docs step, and keep the sentence's point: it still
knows no part names.

---

#### Step 3 — Two clips

`audio.py:150` builds eight clips. Add `catch` (a soft thump plus a rising
third — it should feel like a reward, not like `correct`) and `incomplete` (a
short dry hiss, clearly not `wrong`, because a wide throw costs nothing).

Follow `_pock` (`audio.py:110`) for shape: a `wave(t)` closure and `_envelope`,
built through `_tone`, which reads the rate back from `mixer.get_init()` rather
than hardcoding it.

**Gate:** `uv run pytest` — clip *construction* is covered by the suite. Audible
output is not; that is item 2 of the human checklist in `CLAUDE.md`.

---

#### Step 4 — Four cabinets, and `draw_cabinet` at any height

**The 2×2 grid does not fit as `draw_cabinet` is written.** The arithmetic:

`draw_cabinet` (`draw.py:488`) uses fixed offsets — marquee 62 tall at `y+20`,
screen 236 tall below it, and a panel whose height is
`rect.bottom - screen.bottom - 44`. That requires `rect.height > 380` for the
panel to have any height at all; the current cabinets are 440.

The vertical budget on the 800-tall surface: "mathr" at y=96 and "pick a game"
at y=156 (`app.py:518–519`), and `MENU_BUTTONS` at y=666 with height 76
(`app.py:100–104`), so the cabinets get roughly y=186 to y=650 — **464px for two
rows**, or about 220px each. Two rows of 400+ is 800px and does not fit.

So `draw_cabinet` must derive its marquee, screen and panel from `rect.height`.
Scale the existing offsets by `rect.height / 440` rather than inventing new
ratios: that reproduces today's cabinet exactly at h=440, which is a property a
test can assert.

- `CABINETS` (`app.py:95`) becomes four entries at x=160 and x=720, w=400,
  y=186 and y=420, h=220.
- The fourth is **dimmed and not clickable**. `draw_card` (`draw.py:202`)
  already ignores `hovered` when `dimmed`; the click loop at `app.py:283–286`
  must skip it, the same way the handlers never see `SOON_BUTTONS`
  (`app.py:127`). A cabinet that lights up and does nothing reads as broken.
  Give it a marquee reading "Coming soon" and an empty screen.
- `self.thumbnail = draw.rocket_thumbnail(self.parts, 200)` (`app.py:218`) is
  sized for a 236-tall screen. At h=220 the screen is ~118, so the thumbnail
  wants ~100. Derive it from the cabinet height rather than swapping one
  magic number for another.
- `draw_mini_court` (`draw.py:517`) insets by fixed `(-36, -30)`; at half the
  height that is most of the screen. Make the inset proportional.
- New `draw_gridiron(surface, rect, now)` for the football cabinet's screen: the
  field with the 50 marked and a ball arcing across it.

**Gate:** the human checklist. `uv run mathr`, look at the arcade — four
cabinets, three live and one dimmed, nothing clipped, the dimmed one does not
light up under the cursor and does nothing when clicked. Resize to a tall narrow
tile and check the same.

**Falsifies:** `plan.md:534–535` ("two drawn cabinets with marquees and small
live screens").

---

#### Step 5 — The mode, the field, and the click

- `MODES` (`app.py:57`) gains `"football"`: title, `FOOTBALL` rules, a clip map
  covering `CORRECT`/`WRONG`/`WON`/`LOST`/`PLACED`/`ADRIFT`, noun `"yards"`,
  win/lose strings, hold times. `clips[outcome]` indexes directly
  (`app.py:409`), so a missing key raises loudly — unlike `Sounds.play`, which
  goes silent. Rocket and tennis need no new entries: they never produce the new
  outcomes.
- **`render_play` (`app.py:563`) is a two-way branch** — `if self.mode ==
  "rocket": render_rocket() else: render_court()`. A third mode falls into the
  tennis court silently. Replace with a dispatch off `Mode`. There are twelve
  `self.mode ==` sites (`app.py:397, 402, 440, 471, 477, 567, 656, 665, 673`);
  the ones that ask "is this mode's art a rocket" belong on `Mode` as fields or
  hooks. **Make the case in the commit message before doing it** — this is the
  new abstraction the third mode argues for, and `CLAUDE.md` asks for the case,
  not a speculative framework.
- `draw_field(surface, ...)` in `draw.py`: a 0–100 line across the play area,
  goal lines at each end and one mark at the 50, nothing else. Anchoring at the
  midpoint is the estimation strategy the research watches children develop;
  ticks every ten would turn the task into counting to the nearest tick and the
  mode would train nothing. It shares the left half with `HINT_BOX`
  (`draw.py:540`, x 60–660) — the keypad at x ≥ 700 must stay clear, and the
  field must not collide with the hint when both are on screen in sequence.
- Input: while `play.round.placing is not None`, a click inside the field
  converts x → yards and calls `place`. It arrives already in design space —
  `click` is fed `self.to_design(event.pos)` at `app.py:264` — and nothing
  downstream may see window coordinates.
- `press` (`app.py:377`) must **return early while `placing is not None`**. It
  currently calls `dismiss` on any keystroke and then appends digits; left alone,
  he types an answer that is queued against a question hidden behind a pending
  throw. A keystroke must not resolve a placement either — only a click on the
  field can, because the click *is* the estimate.
- `warn` (`app.py:491`) is already gated on `play.round.hint is None` at
  `app.py:477`; it needs the same gate on `placing`, for the identical reason —
  `warn` sets its interval from `seconds_left / threshold`, and under a stopped
  clock that ratio is constant, so the pulse that exists to quicken becomes a
  metronome while he aims.
- `start` (`app.py:354`): football has no `lives`, so the Timer toggle applies
  to it as it does to the rocket. An untimed football round still throws.

**Gate:** the human checklist — `uv run mathr`, play a football round at two
window sizes. Specifically: the clock visibly stops when a throw appears; a
keystroke does nothing while it is up; a click near a goal line and one near the
50 both land where they look like they land in a tall narrow tile.

---

#### Step 6 — Documentation

- `README.md`: the opening paragraph says "Two games, one question pool"
  (line 5) and "Both cabinets" (line 22) — three now. Add a Touchdown Drive
  paragraph beside Rocket Builder (line 36) and Tennis Match (line 46). Rewrite
  the shared-record paragraph (lines 192–195). Note in Controls (line 146) that
  one screen is clicked rather than typed.
- `CLAUDE.md`: add `football` to the map; add `PLACE_MAX`, `PLACE_TOLERANCE`,
  `PLACE_EVERY`, `PLACE_PARTS` to the tuning table; add the traps below to
  *Invariants that break silently*; update *A third game mode* under *Making the
  two likely changes* to describe what a fourth would now cost; correct the
  `domain/round.py` sentence per step 2.
- `ideas.md`: strike *A number-line placement mode* and record what was actually
  built against what it claimed, in the style of the *A second game mode* entry.
  Its claim — "it is a third mode with a non-boolean outcome … a `Rules` dial at
  best and a second reducer at worst" — landed between the two: one dial pair, a
  second *reducer function* beside `apply`, and no second `Round`.

---

### Overturned by the first play-through

Two things were wrong the moment it was played, and both were wrong in the
plan rather than in the code.

**The target was drawn across the whole line, independent of the ball.** From
the 70 it called *throw to the 20*, and sometimes it called the yard the ball
was already on. Every walk-through above checks that the *drive* makes football
sense; none of them checks that the *throw* does. The fix is the same shape as
the field-goal decision: the target is drawn as an offset ahead of the marker
(`PLACE_GAIN_MIN`..`PLACE_GAIN_MAX`), never as an absolute yard, and a
completion **spots the ball where the pass was caught** rather than paying a
flat `PLACE_PARTS`. That deletes a dial: the number he estimates *is* the number
he gets, a short pass is worth a little and a deep one a lot, and the line and
the parts bar become one axis — one part covers `PLACE_MAX // rules.target`.
The cost is that a pass can no longer score: the goal line is a labelled end of
the line, so a target that could reach it would be a free touchdown. Inside the
last part `placing` is None and the ball has to be run in.

**`PLACE_EVERY = 4` bought too few placements.** Three keypad questions per
throw made it a rocket round with an occasional line. It is 1 — a throw after
every answer — because the placement is the thing the mode exists for and the
arithmetic is the thing there is already a mode for. A round is now about five
answers and five throws.

**And the placement became a claim rather than a gain.** The mode as planned
asked one thing per play; it now asks two, and the play is a *throw and a
catch*: a good placement goes to `Round.pending` and moves nothing until an
answer confirms it before `pending_left` runs out. The reason is the one this
plan states for the mode existing at all — the placement is the thing that
cannot be gamed by a memorised table — and a placement that pays out on its own
can be gamed the other way, by clicking near the middle and taking whatever it
gives. Two skills per play, neither tradeable for the other. It cost two `Round`
fields, one `Rules` dial, two `Outcome` members, a branch in `apply` that plays
by the rally's rules rather than football's, and a lapse path in `tick`.

**The marker was tens of yards, so a catch on the 27 spotted the ball on the
20.** `parts` was the position in tens and `Rules.target` stayed at ten, so
`_secure` floor-divided every catch down to the nearest part — which reads at
the table as "it just advances ten yards", and quietly makes the number he
estimated not the number he gets. A placement mode's `target` is now `PLACE_MAX`
and the marker *is* the line, with `new_round` raising rather than letting the
two disagree. Two consequences worth recording: `draw_progress` shows a tenth
per pip instead of a hundred pips, and the run-in disappeared — close to the end
the call is the goal line itself, so the touchdown is a caught pass rather than
a walk-in, which is the better football anyway.

**And the ball only ever went forwards.** With the marker climbing the line, he
estimates ahead of wherever it has got to; the low numbers come up once, at the
start, and by the second half of a drive the whole task lives in the last
quarter of the line. Sacks are the fix: about a play in four loses ground
(`SACK_CHANCE`), and the placement they ask for is the one he is *not* told —
he is told what it cost, and has to say where that leaves him. That makes a
sack a subtraction modelled on the line, which is the same thing
`draw_number_line` draws over a missed fact, and the field draws the move as a
labelled hop backwards for the same reason. The ball lands where it lands
whatever he clicks: spotting it at his click would make a sack the cheapest way
up the field, a few yards forward of the truth every time, inside the tolerance.
Considered and rejected: a real-time pass rush that could fire while the ball is
in the air — a second clock racing the same answer the catch deadline already
races, and indistinguishable from it when you lose.

**And a good drive still never went backwards.** Sacks at one play in four are
a distribution, not a guarantee: three long catches finish a drive having never
been pushed back once, and every estimate after the first then lives in the top
half of the line. Two rules close it — a sack is due past `SACK_BY` if none has
landed yet, and a wide throw is a holding call worth `PLACE_PENALTY` of ground
on top of the attempt it spends. The second is the more important of the two: a
miss at the top of the field used to cost nothing he could see, which made
clicking until one stuck the cheapest way to finish. A missed *sack* spot is
deliberately not penalised again; the play has already taken its ground.

**A miss had no cost, so it became three strikes.** A wide placement used to
leave an ordinary running down behind it, worth ten yards for a right answer —
which made the cheapest way to play the mode "click anywhere, then answer the
question you were going to be asked anyway". It now says INCOMPLETE, moves
nothing, calls a fresh yard from the same spot, and spends one of three
attempts; the third is a turnover, through `Rules.place_lives` and
`Round.adrift`. That also deleted the last of the `asked`-versus-`placed`
bookkeeping: a placement is due whenever none is in the air, which is one
sentence instead of an operator nobody could check by reading it.

**A dropped ball kept its question, and the box kept its digits.** Both were
the same missing step: `tick` cleared `pending` on a lapse and nothing else, so
the fact he had run out of time on was still `queue[0]` for the next catch, with
whatever he had typed against it still in the entry box ready to be submitted.
It now advances the queue and re-queues the fact at `RETRY_GAP` the way a ball
past him does in tennis, and the shell empties `play.entry` on the same frame.
The lapse deliberately raises no hint, which every other timeout here does: the
next thing it asks for is a click on the field, and a hint can only be put away
by typing — a click that dismissed one would also be a throw, aimed wherever he
happened to be reading.

**The screen was re-laid-out around the line.** The field runs the full width of
the top and everything he types sits below it, which takes the line from five
pixels a yard to ten. That needed `Mode` to carry a `draw.Layout` — where the
prompt, the entry box and a hint go — because football's hint lands over the
field's left half while the other two modes keep the original arrangement. The
number line has been rect-relative since it was built, which is the only reason
this was a constant and not a rewrite.

**And the field got its stripes back**, which this plan rejected twice. Every
five yards, unnumbered, in green rather than white. The rejection reasoning
stands and is unchanged — a stripe is something to count to rather than a
distance to judge — but it is a picture of a field to a seven-year-old, and the
trade is his to make from watching him play. `STRIPE_EVERY = None` restores the
bare line, which is why it is a constant and not a literal — and after seeing
them on the field he took them straight back off again, which is the constant
earning itself.

### Traps

**A stored `placing` will drift from `asked`.** Derived from `asked`, `placed`
and `rules.place_every`, it cannot. If a later change makes it a field for
convenience, it must then be written on *every* path through `apply` — both the
correct and the wrong branch, and the early return at `round.py:270` where a
wrong answer in tennis leaves the queue alone — the way `hint` is at
`round.py:274`. A single missed path is a throw that never appears, or one that
appears twice on consecutive downs. Nothing raises.

**`tick` must return early on `placing`, and `warn` must be gated on it.** Both
for the reasons already recorded for `hint`: without the `tick` return,
`seconds_left` stops (or does not) independently of `on_current`, and aiming
time lands in `Tally.seconds`, which feeds the deck weighting, which pushes the
facts around the throw to the front of the next deck. The symptom is "he keeps
getting the same questions", which names nothing. Without the `warn` gate the
alarm pulse becomes a fixed metronome while he aims.

**A keystroke must not resolve or dismiss a placement.** `press`
(`app.py:377`) calls `dismiss` on every keystroke by design — losing the first
digit of an answer reads as a dropped key. That reasoning does not extend here:
the click *is* the estimate, and a placement resolved by the keyboard records an
aim he never made. `press` returns early while `placing is not None`.

**The hint must win over a due placement.** A wrong answer on the fourth down
raises both. If both are live the shell arbitrates, which puts a rule in the
shell; if the placement wins, he never sees the number line for the fact he
missed. The `hint is not None` clause in the `placing` property settles it in the
domain, and `dismiss` (`round.py:254`) then makes the throw live with no extra
code.

**`render_play` is a two-way branch, not a dispatch.** `app.py:567` is
`if self.mode == "rocket": … else: render_court(…)`. A third mode added to
`MODES` without touching this renders as tennis — it compiles, it draws, and
nothing raises. Fix the dispatch in the same step that adds the mode.

**A dimmed cabinet must not be clickable.** `draw_card` (`draw.py:202`) already
refuses to hover a dimmed card; the click loop at `app.py:283–286` iterates
`CABINETS` and would happily set `self.mode` to a mode that does not exist,
raising a `KeyError` from `App.game` (`app.py:342`) on the next frame. Skip it
there, the way the handlers never see `SOON_BUTTONS`.

**`draw_cabinet`'s offsets are absolute.** `rect.height` below about 380 gives
the panel a negative height and pygame draws it inverted or not at all. Scaling
by `rect.height / 440` both fixes it and keeps the current look provably
identical at the current size.

**The `version` bump is for the `levels` key shape, not for `Fact.key`.**
`CLAUDE.md` warns that changing `Fact.key` orphans every recorded count. This
change does not touch it — `facts` keys and their contents are untouched, and
`test_a_file_from_before_the_clock_still_loads` (`test_storage.py:47`) must keep
passing unchanged except for the level key it asserts.

**Placement targets come from `new_round`, never from a reducer.** `tick`,
`apply` and `place` take no rng, and two tests pin shuffle determinism per seed
(`test_round.py:93`, `test_select.py:47`). Drawing a target inside a reduction
would make the round unreproducible from its seed and would break those tests in
a way that reads as a shuffle bug.

**Every fourth *answer*, not every fourth *question*.** `asked` increments on
both the right and the wrong path (`round.py:271`). A wrong answer therefore
advances toward the next throw even though it cost him ten yards. That is
deliberate — the throw is a change of pace, not a reward — but it means the
count is of attempts, and a test should say so.

---

### Considered and rejected

- **A field goal.** Rejected on the walk-through above: it advances a drive it
  should end.
- **`parts` as points, with a separate yards counter.** The honest football
  model. Two counters in `Round` and three or more `Rules` dials, for a mode
  whose reason to exist is the line.
- **A heterogeneous queue, `Question | Placement`.** The research document's own
  read ("the question-generation seam, not `Round`, is what needs to
  generalize"). Rejected as future-proofing: it touches `_advance`, `shuffled`,
  `_weights` and storage, and one mode wants it. Revisit when a second placement
  mode exists.
- **A second reducer, sequenced by the shell.** Cleanest separation, but "when
  does a throw happen" is a rule, and the shell holds no rules.
- **The throw's target as the answer to a fact** ("8 + 5 = ?", place the
  answer). Reuses `Fact.key`, so throws would feed `Tally` and the deck
  weighting for free. Rejected because the span then varies by level — `fives`
  places on 0–10 and `tens_times` on 0–100 — and a line that rescales between
  rounds is exactly what makes the estimate un-learnable.
- **Ticks every ten yards, like a real field.** Faithful and much easier;
  it converts estimating into counting to the nearest tick.
- **Marks that thin out as he improves.** The honest teaching answer, and it
  needs a progression rule and a stored level — a second mastery model beside
  the deck weighting. In `ideas.md`.
- **A graded outcome, distance as the score.** How estimation is actually
  measured, and the richer signal is the one worth having over months. Rejected
  because `Outcome` would grow a payload every mode has to consume; the raw
  distance is preserved in `placements` regardless, so the signal is not lost —
  only the round's *reaction* to it is thresholded.
- **Reusing `CORRECT`/`WRONG` for throws.** No enum change, no clip maps to
  update — but the two events would be indistinguishable by sound, by flash, and
  in any later recorded stream.
- **A moving aim marker he stops with a click.** More game-like, and it measures
  reaction as much as magnitude — it would contaminate the one signal the mode
  exists to collect.
- **Typing the yard number on the keypad.** Zero new input, and it collapses the
  mode back into arithmetic.
- **A play clock, per down.** Truer football and reuses `TENNIS`'s shape, but
  then football and rocket differ only in art, which is the trap `The
  load-bearing decision` of the arcade section already walked through.
- **Four downs and no clock.** Genuinely a third reading and the most football-
  like. `Rules` has no dial for attempts-remaining; this is the case where
  `Rules` grows rather than the shell gaining a rule. Not now.
- **One throw per round, at the end of the drive.** Simplest, and one estimate a
  round is not practice.
- **Three cabinets across, narrower.** Fits without touching `draw_cabinet`.
  Not chosen; see below.
- **My own wrong turn.** During the dig I said the shared `LevelRecord` was
  undocumented and therefore a latent bug. It is documented, at
  `README.md:192–195`, as a deliberate choice with a stated reason. Step 1
  overturns a decision rather than fixing an oversight, and the README passage
  has to be rewritten rather than merely extended. A fresh reader who greps
  `plan.md` alone would make the same mistake — the reasoning was only ever in
  the README.

---

### Accepted with known risk

- **The 2×2 cabinet grid.** Chosen over three across. The cost is real and was
  not visible when the choice was made: `draw_cabinet` has to become
  height-proportional, the rocket thumbnail and `draw_mini_court` have to
  follow, and every cabinet loses about half its height. Three across needed
  none of that. The gain is that the fourth mode has a home and the arcade does
  not have to be re-laid-out again. **Revisit trigger:** if the cabinets at
  h=220 read as cramped on the real display in step 4, three across at w≈340 is
  still available and costs nothing already built.
- **`PLACE_TOLERANCE = 6` is a guess.** Second-graders' mean absolute error on a
  0–100 line runs roughly 5–10% in the literature, so six yards should land near
  a coin flip at the start. It is a dial and `CLAUDE.md` says the dials are meant
  to be turned after watching him. **Revisit trigger:** the mean error in
  `placements` after a week — if he is completing nearly every throw, tighten it;
  if `failures` for football outruns `launches`, loosen it before touching
  anything else.
- **Nothing reads `placements`.** Same deferral as the per-fact tallies, and the
  same justification: the data cannot be reconstructed later and costs almost
  nothing now. **Revisit trigger:** enough attempts per bucket to plot a trend,
  which is also when the parent view in `ideas.md` becomes worth building.
- **A migration guess.** Every v1 level record becomes rocket's. Tennis rounds
  played on a level will have inflated rocket's `launches` and possibly its
  `best_seconds`. Unfixable — the mode was never recorded. The affected numbers
  are a badge on a card.

---

### Environment and coverage notes

- **The research document is not on `main`.** `research/math-education.md` at
  commit `79c74c3` on `worktree/rapid-meadow-32ee`; `research/` on `main` is an
  empty directory. Read it with
  `git show 79c74c3:research/math-education.md`. §3.2 is the case for this mode,
  §5 ranks it sixth, §6 names the `Outcome` problem this plan thresholds around.
- **What was read for this plan, and what was not.** Read in full:
  `domain/round.py`, `storage.py`, `ideas.md`, the research document. Read in
  part: `shell/app.py` (the mode/layout constants, `handle`, `click`, `press`,
  `submit`, `ball`, `update`, `warn`, `start`, `render_menu`, `render_play`,
  `render_rocket`, `_badge` — **not** `render_court`, `render_entry`,
  `render_win`, `render_failure`, or the main loop), `shell/draw.py` (the
  cabinet, card, number-line and court-geometry sections only — **not**
  `draw_rocket`, `draw_alien`, `draw_beam`, or the transform), `domain/facts.py`
  (`Fact`, `Strategy`, the level tuples — **not** `_pool`, `_times` or
  `shuffled`), `shell/audio.py` (the clip table and generator shapes only). Test
  names were read for all six files; only `test_storage.py`'s helpers and
  `test_clock.py`'s hint tests were read in full.
- **To verify in step 5, not assumed here:** whether `draw_field` at
  `HINT_BOX`'s x-range (60–660) collides with anything `render_rocket` draws —
  the comment at `draw.py:537–539` says the rocket sits at x 110–410 and the
  court spans 75–625, but football's own art has not been laid out.
- **To verify in step 2, not assumed here:** how many targets `new_round` must
  draw. `_advance` replays the deck, so `asked` is unbounded; confirm whether
  indexing `targets` modulo its length is acceptable or whether a round can run
  long enough for the repetition to be noticeable.
- Three things the suite cannot reach, unchanged from `CLAUDE.md`: windowing
  under Hyprland, audible output through PipeWire, and whether the pacing suits
  him. `failures` per level in `progress.json` — now under `football/<level>` —
  is what answers the third.

---

### Out of scope, and where it went

Recorded in `ideas.md`, not built here: true/false number sentences (research
§3.1, ranked second — the relational `=`, and the cheapest of the remaining
ideas) — **since built, as Replay Booth; see that section below**, and the entry
is worth reading next to this line, because "cheapest of the remaining ideas"
was wrong: it was the one that reopened the heterogeneous queue. Also
guess-my-rule (§3.4), CGI-structured word problems (§3.3), and a
scaffolded field whose marks thin out as he improves. Spacing across days,
mastery as a probability, and retirement of mastered facts stay where the
previous section left them. A parent-facing view of `placements` is the same
deferral as the parent view of weak facts, and belongs in the same entry.

---

## Division: the third column

### What changes

The Division column on the level screen stops being dimmed. Three new levels —
*Divide by Two*, *Divide by Five*, *Divide by Ten* — ask `12 ÷ 2 = ?` and
`12 ÷ ? = 6`, twenty facts each, and `everything` grows from 278 facts to 338.
The multiplication levels are untouched. The number line learns to draw a
division fact as the skip count it is, and says how many hops that was, because
a division fact is the first one whose answer is not a place on the line.

No new mode, no new `Rules`, no storage version bump. This is the content
decision `ideas.md` said it was, settled: the tables go to ten, there are no
remainders, and `÷` is shown as a symbol rather than hidden behind `2 × ? = 12`.

### The load-bearing decision: the answer is the hop count, not the endpoint

Every fact in the game until now lands on its own answer. `Fact.strategy`
(`facts.py:68`) returns a start and signed jumps, and `test_facts.py`'s
`test_every_strategy_lands_on_the_answer` asserts `strategy.end == fact.result`
for all 278 of them. Division cannot satisfy that, and the failure is quiet
rather than loud.

Walk it with real numbers. `12 ÷ 3 = 4` is `Fact(12, "÷", 3, 4)`. The picture
that teaches it is the skip count: `0 → 3 → 6 → 9 → 12`, four equal hops — which
is pixel-for-pixel the picture `3 × 4 = 12` already draws, and that sameness *is*
grade 3's lesson on how multiplication and division connect. But that line ends
on **12**, and `fact.result` is **4**. The answer is the number of hops.

The three ways this goes wrong if it is not decided up front:

1. Force the invariant and draw `Strategy(12, (-3, -3, -3, -3))`: the line runs
   `12 → 9 → 6 → 3 → 0` and ends on **0**, which is not the answer either. Now
   the test fails on a different number and the picture teaches counting down to
   nothing.
2. Force it the other way and hand back `Strategy(0, (4,))` — a single hop to 4.
   The invariant passes, the test goes green, and the hint for `12 ÷ 3` is a
   number line with a lone hop of four on it that mentions neither 12 nor 3. It
   is wrong and nothing raises.
3. Draw the correct skip count and leave the widget alone. Then the hint for
   `12 ÷ 3 = ?` shows hops labelled `+3 +3 +3 +3` ending at a highlighted **12**
   — and 12 is the number already printed in the question. The picture shows him
   the number he was given and never shows him the number he was asked for.

So the rule is stated per operation instead of universally, and the widget gains
a caption:

- `÷` draws `Strategy(0, (fact.b,) * fact.result)` — `fact.result` hops of
  `fact.b`, ending on `fact.a`.
- The test becomes: `+`, `−` and `×` land on `fact.result`; `÷` lands on
  `fact.a` with `fact.result` jumps.
- `draw_number_line` gains an optional caption, and the booth's own hint (next
  section) will want the same parameter, so it is added once here.

Both division forms of a pair share one `(a, op, b, result)` tuple and therefore
one strategy, exactly as the two subtraction forms of a bond already do.
`Fact(12, "÷", 4, 3)` — `12 ÷ ? = 3` — draws three hops of four and also ends on
12. Correct in both directions with one expression.

### The steps

Order is forced twice: the pool has to exist before the level screen can point
at it, and `Fact.strategy` has to know `÷` before any miss on a division fact
can draw a hint. Step 3 is last because it is the only step that touches files
outside the change.

**Step 1 — the pools.** `domain/facts.py`.

Add `_divide_pair(a, b)` beside `_times_pair` (`facts.py:158`), yielding the two
forms that `_times_pair`'s docstring already names as deliberately absent:

```python
def _divide_pair(a: int, b: int) -> tuple[Fact, ...]:
    total = a * b
    return (
        Fact(total, "÷", a, b, "result"),   # 12 ÷ 2 = ?
        Fact(total, "÷", a, b, "b"),        # 12 ÷ ? = 6
    )
```

Add `_divided(n)` mirroring `_times` (`facts.py:175`) but over `range(1, 11)`,
not `range(11)` — see Traps. Add `_DIVIDE` beside `_MULTIPLY` (`facts.py:206`)
with ids `divide_two`, `divide_five`, `divide_ten`, names *Divide by Two* /
*Divide by Five* / *Divide by Ten*, and `seconds_per_part` 5.0 to match the
multiply column. Extend `EVERYTHING` (`facts.py:214`) and `LEVELS`
(`facts.py:221`) — both are derived, so both pick the new levels up from the one
tuple.

Add the `÷` branch to `Fact.strategy` (`facts.py:68`) **before** the `+`/`−`
branches, alongside the existing `×` early return.

*Gate:* `uv run pytest`. Tests that must be updated in this step, all in
`tests/test_facts.py`: `TIMES` (line 5) gains `"÷": lambda a, b: a // b`;
`test_pool_sizes` gains the three levels at 20 each and `everything` becomes
**338**; `test_each_topic_asks_its_own_operations` gains the division levels
asking `{"÷"}` and `everything` asking `{"+", "-", "×", "÷"}`;
`test_every_strategy_lands_on_the_answer` splits per operation as above. Add
`test_division_hops_count_the_answer` pinning
`strategy(12, "÷", 2, 6) == Strategy(0, (2,) * 6)` — the worked example above
uses `12 ÷ 3`, which is not in any pool, because the divisors are 2, 5 and 10 —
and a division key to
`test_keys_are_unique_and_stable` — `12÷2=6@b` — because that string is now a
storage format.

**Step 2 — the caption.** `shell/draw.py`, `shell/app.py`.

`draw_number_line` (`draw.py:937`) takes `caption: str | None = None` and draws
it under the prompt when set. `render_play` (`app.py:712`) composes it for `÷`
only — `"four hops of three"` — reading `play.round.hint.fact.op`. This is
presentation, not a rule: the shell is choosing words for a number the domain
already returned.

*Gate:* `uv run mathr`, miss a fact on *Divide by Five* on purpose, and check
the line reads `0 3 6 9 12` with the caption under it and the whole thing inside
`HINT_BOX`. `test_scaling.py` covers the transform, not this.

**Step 3 — the column.** `shell/app.py`, `README.md`, `CLAUDE.md`, `ideas.md`.

`LEVEL_COLUMNS` (`app.py:176`) gains the third tuple. `SOON_BUTTONS`
(`app.py:191`) drops its three division entries and keeps only *Tricky Facts* —
which moves it from a generator expression plus a tuple to a one-element tuple.
`app.py:693` loses its `draw.DIM if title == "Division"` conditional entirely;
every column title is now `draw.ACCENT`.

Documentation this step falsifies, all of which must move in the same commit:

- `README.md:125–138`, the level table — three rows, and `everything` becomes
  338.
- `README.md:135–138`, which states division as a deliberate absence: *"Division
  has a dimmed column on the level screen... The multiplication levels ask only
  `a × b = ?` and `a × ? = c`; the two forms that would complete the set are
  division, which is exactly what is not built yet."* That passage is now false
  in every clause and has to be rewritten, not extended.
- `CLAUDE.md`, *The map* and *Making the two likely changes* — the pool sizes
  line (`24 / 44 / 144 / 22 / 22 / 22`, `everything` 278) and the claim that a
  times pair yields two questions *"— the other two would be division, which is
  not built"*.
- `ideas.md`, *More levels* — the **Division** entry becomes **Built**, and the
  pattern the file already uses for built entries applies: keep what it
  predicted next to what it cost.

*Gate:* `uv run pytest`, then `uv run mathr` and confirm the Division column
cards are lit, clickable, and carry badges.

### Traps

**`b = 0` must not be in the division pools.** `_times(n)` (`facts.py:175`)
draws `b` from `range(11)`, which is right for multiplication — `2 × 0 = 0` is a
fact worth asking. Carried into division it produces `Fact(0, "÷", 2, 0, "b")`,
which renders as `0 ÷ ? = 0`, and **every divisor is a correct answer**. He types
5, the game says wrong, and the number line draws zero hops of two. Nothing
raises, and the fact sits in the deck being wrong forever. `_divided` uses
`range(1, 11)`, which is also where the 20-facts-per-level figure comes from.

**The `÷` branch must come before the `+`/`−` branches in `Fact.strategy`.** The
current body (`facts.py:68–83`) early-returns on `×`, then on `+`, and otherwise
falls through to subtraction. A `÷` fact reaching the fall-through is treated as
`a − b`: `12 ÷ 3` draws `Strategy(12, (-3,))`, a single hop from 12 to 9. It is a
valid-looking line, it lands on nothing relevant, and no test outside
`test_every_strategy_lands_on_the_answer` would notice.

**`Fact.key` is unchanged and must stay unchanged.** `12÷2=6@result` is a new
string in an existing format. No `VERSION` bump — `storage.py:18` stays at 2 —
because nothing about the *shape* of a key moved and every existing key still
means what it meant. Adding new level ids is the same: `LevelRecord` is keyed
`<mode>/<level>` and a new level id is simply a key with no record yet.

**Verify `÷` renders.** Fonts come from `pygame.font.SysFont(None, ...)`
(`app.py:277–282`). `×` (U+00D7) already renders in that font, and `÷` (U+00F7)
is its neighbour in Latin-1, so this should be free — but a missing glyph draws
as a blank or a box and raises nothing. Look at it once in step 2's gate.

### Considered and rejected

- **Growing `_times_pair` to four forms**, so *Times Two* teaches `2 × 6` and
  `12 ÷ 2` together. This is the research's own argument — showing a triple in
  both directions *is* the ×/÷ connection, and interleaving is the strongest
  single effect in `research/math-education.md` §2.1. Rejected because it
  deletes the reserved Division column rather than filling it, and changes a
  level he already plays underneath him. The connection is still made in
  `everything`, and both keys exist, so the measurement in
  `research/iready-grade3.md` §4.1 — whether `2 × ? = 12` and `12 ÷ 2 = ?` have
  converged to the same speed — is available either way.
- **Both: full fact families *and* a division column.** The most exposure, and
  it duplicates every division key across two columns, so `everything` needs
  de-duplication or it double-counts and `test_everything_is_every_other_pool`
  changes shape.
- **Division as `a × ? = c` only, with no `÷` symbol.** Already how the game
  asks it. Rejected because the reserved UI names the levels *Divide by 2 / 5 /
  10* and the column title is *Division*; a column that never shows a division
  sign is a worse lie than not having one.
- **A partition picture for the hint** — twelve counters dealt into three rows.
  Closer to how division is first taught, and it is a second representation in a
  game that has exactly one. The skip count reuses the widget and makes the ×/÷
  connection the same image.
- **No hint on division at all.** Zero work, and it removes elaborated feedback
  — the highest-ranked cheap intervention in `research/math-education.md` §5 —
  from the one operation that is new to him.
- **My own wrong turn.** Mid-dig I put `everything` at 318 facts. It is 278 + 60
  = **338**; the 20-per-level figure was right and the addition was not. The
  number appears in `test_pool_sizes`, `README.md:133` and `CLAUDE.md`, so a
  stale one is pinned by a test in one place and printed as prose in two others.

### Accepted with known risk

- **`seconds_per_part = 5.0` for the division levels** is a guess, copied from
  the multiply column. Division is new to him and a first division fact is
  likely slower than a known times fact. It is the one per-level dial and
  `CLAUDE.md` says the dials are turned after watching him. **Revisit trigger:**
  `failures` on `rocket/divide_two` running ahead of `rocket/twos`.

### Environment and coverage notes

The suite does not open a window, so step 2's caption and step 3's lit column
are checked by hand at `uv run mathr` and by nothing else. Everything in step 1
is covered by `tests/test_facts.py`.

---

## Replay Booth: a sentence judged, and repaired

> **Superseded before it was played.** Built as written, then replaced by *Code
> Breaker* below. Everything here about the seam — one queue holding
> `Question | Sentence`, lives a wrong answer spends, `losable` rather than
> `timed` — survived the replacement and is still true. What did not survive is
> the mechanic: judge-then-repair. Kept in full, because the reason it failed is
> not visible from the thing that replaced it.

### What changes

A fourth cabinet takes the *soon* slot. He is the official in the replay booth:
a scoring claim is shown as a number sentence — `7 + 6 = 9 + 5` — and he lets
the call stand or overturns it. Overturning is not enough on its own; one number
is highlighted and he types what it should have been. Three blown calls and he
is off the crew. There is no clock at all.

The lesson is the equal sign. The best-documented misconception in elementary
arithmetic is reading `=` as *"write the answer here"* rather than *"the same
as"* (`research/math-education.md` §3.1), and the sentences that dismantle it —
`8 = 8`, `3 + 5 = 5 + 3`, `7 + 6 = 9 + 5`, `7 + 6 = ? + 5` — are not facts with
a missing operand. They are the first items in this game that a `Fact` cannot
express.

### The load-bearing decision: this mode differs in its *items*, not its *rules*

The arcade section of this plan argued that a mode is not a renderer — that
Rocket, Tennis and Football are three readings of a `Rules` bundle, and a mode
built as a pure renderer over someone else's rules compiles, draws, and plays as
a different game. That argument is intact and it does not apply here. The booth
could run on `ROCKET`'s rules unchanged and still be a different game, because
what changed is what a question **is**.

That makes this the third seam, and it is the one deferred twice — once in the
arcade section, once in the football section, as *"a heterogeneous queue,
`Question | Placement`... rejected as future-proofing: it touches `_advance`,
`shuffled`, `_weights` and storage, and one mode wants it. Revisit when a second
placement mode exists."* This is the other event that reopens it, and
`research/iready-grade3.md` §5.4 says the same thing from the other side: three
candidate modes all pay for this seam, so pick one and let it define it.

The decision is that **`Round.queue` holds items, not questions**, where an item
is anything with `.key`, `.prompt`, `.answer` and `.strategy`. Concretely
`Question | Sentence`. Everything downstream already touches only those four
members: `_advance` (`round.py:365`) slices the queue and never reads inside an
item; `_weights` (`round.py:280`) and `Tally` key off `.key`; `apply`
(`round.py:574`) compares `given == question.answer`.

Walk the alternative to see why it is worse. Give the booth a *parallel* deck —
`Round.sentences` beside `Round.queue`, the way `gains` sits beside the queue for
placements. Now:

1. A booth round has a `queue` of facts it never asks and a `sentences` tuple it
   does. `Round.current` returns a question that is not on screen.
2. `tick` accumulates `on_current` against `queue[0]`, so every second he spends
   judging a sentence is charged to a fact he never saw.
3. `merge` folds that into `Tally.seconds` for that fact, which is the deck
   weighting's only input, which floats a fact he has never been asked to the
   front of every future deck.
4. The symptom is "he keeps getting the same questions in the *rocket*", and
   nothing in the booth is anywhere near the stack trace, because there is no
   stack trace.

The parallel deck is cheaper to write and it corrupts the one data set in this
game that cannot be reconstructed. One queue, mixed items.

### What a sentence is

```python
@dataclass(frozen=True)
class Side:
    """One side of a sentence: a bare number, or a binary expression."""
    a: int
    op: str | None = None
    b: int | None = None
```

```python
@dataclass(frozen=True)
class Sentence:
    """A number sentence with `=` between two sides, judged and then repaired.

    `Fact` is the degenerate case — one expression, one bare number — but it
    stays its own type, because `Fact.key` is a storage format and this is not.
    """
    left: Side
    right: Side
    mark: str      # "left" | "right": which side's `b` is highlighted for repair
    fixed: int     # what that number must be for the sentence to be true
```

- `.true` is derived: `left.value == right.value`. Never stored — a stored truth
  value can disagree with the numbers beside it, and the numbers are what he
  reads.
- `.answer` is `fixed`, so `apply` compares against it with no new branch.
- `.key` is its own string in its own shape — `"7+6=9+5@right"` — sitting beside
  untouched `Fact.key`s in the same `facts` map.
- `.strategy` is not enough: the hint needs both sides. `Sentence` carries
  `.strategies -> tuple[Strategy, Strategy]`, and the shell picks the hint
  renderer per mode, not by an `isinstance` check.

Sentences are generated from a level's own fact pool, so the shared level grid
needs no layout decision and every cabinet still leads to the same twelve cards.
Two facts from the pool with the same result give a true both-sides sentence
(`tens` is every pair making ten, so `3 + 7 = 4 + 6` falls straight out); one
side shifted by one or two gives a false one. `bridge` yields the hard ones.

### The load-bearing decision, second half: judge and repair are one play

A bare true/false item is a coin flip. That is the exact failure the football
attempt counter exists to stop — *"the line can be clicked at idly until
something sticks, which is the one way to play this mode without estimating"* —
and it arrives here at 50%, not at a tolerance.

So a "call overturned" has to be backed: one number is highlighted and he types
what it should be. Two skills in one play, and neither is tradeable for the
other. This is the throw-and-catch bargain the football section already argued
and it reuses that machinery rather than inventing a second copy:

| Football | Booth |
|---|---|
| `place(round, value)` → `PLACED` / `ADRIFT` | `judge(round, said_true)` → `CALLED` / `BLOWN` |
| `Round.pending` — a claim awaiting confirmation | `Round.repairing` — a sentence awaiting its number |
| `Round.placing` — derived, "is one due" | `Round.judging` — derived, "is one due" |
| `apply` confirms it → `SECURED` | `apply` repairs it → `FIXED` |

`repairing` is stored because `pending` is stored; `judging` is derived because
`placing` is derived, and for the identical reason given in that section — a
stored one has to be written on every path that could clear it, and one missed
path is an item that never appears or one that appears twice, with nothing
raising.

### The load-bearing decision, third half: lives without a clock

`rules.lives` today means **empty-clock events survived**. `points` is
incremented in exactly one place — `tick` (`round.py:376`), on the frame the
bank empties — and `apply` can never set `failed` at all. So a mode with lives
and no clock, written naively, has three lives that nothing can ever spend and
no way to lose.

`new_round` guards this (`round.py:310–312`):

```python
if not timed and rules.lives is not None:
    # A rally has nowhere to put the ball without a deadline to fly along.
    raise ValueError("a round with lives cannot be untimed")
```

That reason is true and it is about tennis. The guard's real content is *lives
with no way to spend one*, which is what makes it right for tennis and wrong
here. So `Rules` gains one dial — `wrong_costs_life: bool` — and the guard is
restated as what it actually means:

```python
if not timed and rules.lives is not None and not rules.wrong_costs_life:
    raise ValueError("a round with lives needs something that can spend one")
```

`points` keeps its counter and gains a second thing that increments it. `apply`
gains the power to set `failed`, which `place` (`round.py:485`) already has, so
this is a precedent and not a new capability in the reducer layer.

Why no clock at all: the measurement that separates *saw it* from *computed it*
is response time against his own arithmetic baseline
(`research/iready-grade3.md` §4.3), and a threat clock suppresses the thing being
measured — `research/math-education.md` §4 caution 2 is explicit that time
pressure and this kind of practice fight. `tick` still accumulates `on_current`
in an untimed round, by design and by its own docstring, so the times are still
recorded. And in a replay booth, unhurried is the job: every other cabinet's
clock is diegetic — fuel burning, a ball falling, a play clock — and here the
*absence* of one is too.

### The steps

The order is forced end to end: the item type has to exist before a queue can
hold one, the queue before a reducer can judge one, the reducer before the shell
can draw one, and the recording predicate before the first win is folded into a
file. Steps 1–3 are pure domain and each is landable with tests and no window.

**Step 1 — `Sentence`, and generation.** `domain/facts.py`, new
`tests/test_sentences.py`.

`Side`, `Sentence`, and `sentences(level, rng)` deriving a pool from
`level.facts`. Shape mix per the dig: `8 = 8` and `3 + 5 = 5 + 3` as the easy
openers, `7 + 6 = 9 + 5` as the body, `7 + 6 = ? + 5` — a sentence whose marked
number is blank from the start and needs no judgement — as the hardest.

*Gate:* `uv run pytest`. Pin that a true sentence's sides are equal and a false
one's differ by one or two; that `.answer` makes it true when substituted; that
keys are unique within a pool and stable across runs; and that generation is
deterministic per seed.

**Step 2 — the queue holds items.** `domain/round.py`, `domain/facts.py`.

Widen the `queue` and `deck` types. `shuffled` gains a sentence path — a
separate branch, not a generalisation of the existing one, for the same reason
the weighted path is separate: *"the unweighted one interleaves the orientation
flip with the sample and every seeded test pins the result."*

*Gate:* `uv run pytest` with **no test changes**. This step is a no-op for the
three existing modes, and `test_select.py`'s determinism pins are what prove it.
If a seeded shuffle moved, the widening touched the flat path and must be redone.

**Step 3 — `judge`, and lives that a wrong answer spends.** `domain/round.py`,
`tests/test_judge.py`.

`Rules.wrong_costs_life`, the restated `new_round` guard, `Round.repairing`,
`Round.judging`, the `judge` reducer, `apply` gaining the repair branch and the
power to set `failed`, and a `BOOTH` rule set. New outcomes: `CALLED`, `BLOWN`,
`FIXED`. Add `Round.losable` — `timed or rules.wrong_costs_life` — for step 5.

Two behaviours that follow from the existing sections and are not open
decisions: a wrong judgement **advances** the queue and re-queues at `RETRY_GAP`
(tennis leaves a wrong answer's question up because he can retype it; there is
nothing to retype when the answer was one of two buttons, so leaving it up shows
him the answer), and a wrong **repair** costs nothing — no life, no queue move,
the hint up and the sentence held — exactly as *"a wrong answer under a pending
placement plays by the rally's rules, not the mode's."*

*Gate:* `uv run pytest`. Pin that three blown calls set `failed` and return
`LOST`; that a wrong repair changes neither `points` nor the queue; that
`judging` is None while `hint` is set, and that the hint therefore wins over a
due call the way it wins over a due placement; that `new_round` still raises for
untimed tennis and no longer raises for the booth.

**Step 4 — the booth.** `shell/app.py`, `shell/draw.py`, `shell/audio.py`.

A `Mode` entry, a `Layout`, a renderer in the `render_play` dispatch
(`app.py:712`), the fourth `CABINETS` rect (`app.py:156`), two judgement buttons
as a module constant beside `KEYPAD` (`app.py:201`) — `Layout` does not need a
new field, because `KEYPAD` is already a module constant and not one — and a
whistle clip in `audio.py`, where nothing whistle-like exists today; `wrong` and
`cheer` are reusable.

The two-line hint: `draw_number_line` grew a `caption` parameter in the division
work, and this needs the sibling — both sides' routes over one shared span, so
`7 + 6` lands on 13 and `9 + 5` lands on 14 and the gap is a visible distance.
The renderer is chosen per mode through the same dict dispatch as `render_play`,
never by an `isinstance` on the item.

`start()` (`app.py:428`) computes `timed = True if mode.rules.lives is not None
else self.progress.settings.timer`. The booth has lives and must be untimed, so
this line needs the booth's case; the Timer toggle is inert here and that is
correct.

*Gate:* `uv run mathr`. Play a booth round at two window sizes including a tall
narrow tile; confirm the judgement buttons hit where they are drawn, that the
call does not reveal itself before he answers, and that a blown call shows both
routes inside the hint rect.

**Step 5 — a win counts as a launch.** `storage.py`, `tests/test_storage.py`.

`_fold` (`storage.py:140`) opens `if not round.timed: return replace(record,
practice=...)`. The booth is untimed and losable, so under that predicate a
perfect game records as practice and the level card reads zero launches forever,
next to three cabinets that launch. The predicate becomes `round.losable`.

This overturns a documented invariant rather than extending one. `CLAUDE.md`
says *"Untimed launches must not touch `launches`. They go to `practice`, or the
number that means 'I beat it' is farmable from the menu toggle."* The reason is
right and the test was a proxy: what makes a win farmable is having no way to
lose, not having no clock. Rocket with the timer off is still untimed, still has
no lives, still records to `practice`. Nothing about the anti-farming property
changes.

*Gate:* `uv run pytest`. Pin that a rocket round with the timer off still folds
to `practice`, that a booth win folds to `launches`, and that
`test_a_file_from_before_the_clock_still_loads` is untouched — no `VERSION` bump,
because sentence keys are new strings in the `facts` map and a booth `LevelRecord`
is a new `<mode>/<level>` key.

**Step 6 — documentation.** `README.md`, `CLAUDE.md`, `ideas.md`, and the
football section of this file.

- `README.md` gains a *Replay Booth* section beside the other three, and its
  opening line — *"Three games, one question pool"* — becomes four.
- `CLAUDE.md`: *The map* gains `judge`/`Sentence`; *Making the two likely
  changes* says the grid is now full at four and a fifth cabinet is a layout
  decision; the invariant on untimed launches is restated per step 5; the
  `Rules` dial table gains `wrong_costs_life`.
- `ideas.md`, *A second game mode* — the remaining-candidates paragraph names a
  growing city, a rescue climb and a race, none of which this is.
- **This file, the football section's *Out of scope, and where it went***, which
  reads *"Recorded in `ideas.md`, not built here: true/false number sentences
  (research §3.1, ranked second — the relational `=`, and the cheapest of the
  remaining ideas)"*. That is now built and the entry has to say so.

### Traps

**A stored truth value.** `Sentence.true` is derived from its own sides. Stored,
it can disagree with the numbers printed next to it, and the failure is a
sentence that is visibly true and marked wrong — which reads to a seven-year-old
as the game being broken, and to a reader as a generation bug rather than a
storage one.

**The booth must not reveal the call before he answers.** Whatever the art does
— a monitor, a verdict light, a crowd — it must be identical for a true and a
false sentence until he has committed. This is the yard-stripe trap in another
costume: *"they are what a real field looks like, and they are also a benchmark
to count along instead of a distance to judge."* An indicator that leans before
the judgement removes the entire skill and nothing raises, because the mode still
scores correctly.

**The queue must stay one queue.** Walked through above. The symptom of a
parallel deck is corrupted `Tally.seconds` on facts he was never asked, which
surfaces as bad deck ordering in a *different cabinet*.

**A keystroke must not judge.** `press` (`app.py:452`) already returns early
while `placing` is set, because *"the click is the estimate"*. The same gate is
needed for `judging`: the two buttons are the call, and a digit key that resolved
a call would record a judgement he never made. But note the asymmetry — during
the **repair** the keyboard is the input, and the hint-dismissal rule applies
there exactly as it does everywhere else.

**A wrong judgement must advance; a wrong repair must not.** Getting these the
same way round is the bug. Advance on a wrong repair and the next call is
confirmed by a sentence he was halfway through fixing. Hold on a wrong judgement
and the answer is on screen — there were only two.

**`new_round`'s guard must be restated, not deleted.** Deleting it lets an
untimed tennis round exist: three lives, no clock, nothing that can ever spend
one, and a match that cannot be lost or won. The guard's replacement has to keep
raising for that case.

**Two of four cabinets would be football-flavoured.** The booth is sport-agnostic
by nature — it reviews *calls*, and the monitor never has to show a field. Keep
it visually indoors, or the arcade reads as football twice.

### Considered and rejected

- **A balance beam, a tug of war, a tightrope.** The canonical representations
  for relational `=`, and the beam is what the literature reaches for. Rejected
  by the user in favour of a sports theme; the booth keeps the property that
  mattered — it shows which side is heavy once he has committed, and not before.
- **Long jump** — two jumps measured against one tape, so the mode and the hint
  are drawn in the same representation. The strongest runner-up, and it carries
  the reveal trap in a sharper form: the jumpers have to still be in the air
  while he judges.
- **Rowing** (an unbalanced boat veers) and **tied at the buzzer** (a scoreboard
  is genuinely two sums). Rowing shows *which* side is heavy but not *by how
  much*; the scoreboard is the most honest reading of `=` in any sport and the
  most static picture of the four.
- **True/false over facts only** — `8 + 5 = 14`, true or false. Derived wholly
  from the existing pools, no new type, `Fact.key` reused, the hint unchanged.
  Nearly free, and it teaches *check the arithmetic* rather than what `=` means.
- **Open sentences only** — `7 + 6 = ? + 5` on the existing keypad. No new input
  at all, and it needs the same new type anyway, so it pays the seam cost for
  less of the lesson.
- **Judge only, with no repair.** A coin flip scores 50%.
- **A parallel sentence deck beside the queue.** Walked through above.
- **A generous bank instead of no clock** — `ROCKET`'s rules with the level's
  `seconds_per_part` raised. It needs no new dial and it was my recommendation
  during the dig. Overturned by the user in favour of lives-and-no-clock, and
  the better argument is the user's: a bank that is generous enough not to rush
  a thinker is a clock that does nothing, and it would still have made the
  mode's threat identical to the rocket's.
- **False sentences off by a lot.** A wildly wrong side is spotted without
  reasoning. Off by one or two is the item that separates seeing from computing.
- **Growing `Layout` for the judgement buttons.** `KEYPAD` is a module constant
  and not a `Layout` field; the buttons follow the precedent.

### Accepted with known risk

- **The times levels are thin for this mode.** A both-sides sentence needs two
  facts from the same pool with the same result, and `_times(n)` holds one fact
  per product. *Times Two* can barely make one. Division shipping first thickens
  the multiply half of the grid, which is a second reason for that order, but it
  does not fully fix it. **Revisit trigger:** if the booth is unplayable on the
  multiply and division columns, restrict its level list rather than weakening
  the sentence generator.
- **The 2×2 grid is now full.** The arcade section accepted this when it chose
  the grid over three cabinets across, and this spends the last slot. A fifth
  cabinet is a layout decision, and `ideas.md` still holds guess-my-rule and
  CGI word problems, both of which want one. The user's position, recorded
  during the dig: the grid can grow if needed.
- **`Sentence.key` is a new storage format** and gets the same protection
  `Fact.key` has — changing its shape later orphans everything recorded under
  it. It is not covered by `VERSION`, which describes the `levels` key.

### Environment and coverage notes

Steps 1, 2, 3 and 5 are covered by the suite and open no window. Step 4 is
covered by nothing: the three things `CLAUDE.md` names as unreachable by testing
— windowing under Hyprland, audible sound, and whether the pacing is right for
him — all apply, and the reveal trap above is a fourth. Look at it at
`uv run mathr`.

**Reading this plan is based on.** Fully read: `domain/facts.py`,
`domain/round.py`, `storage.py`, `tests/test_facts.py`, both files in
`research/`, `ideas.md`, `CLAUDE.md`. Read in part: `shell/app.py` — the
constants, `Mode`, `MODES`, `Play`, the event handlers, `submit`, `throw`,
`update`, `render_play` — but **not** the individual renderers below
`app.py:756` (`render_rocket`, `render_court`, `render_field`, `render_miss`,
`render_entry`, `render_win`, `render_failure`); `shell/draw.py` — `Layout`,
`draw_number_line`, and the constants around them, but not the art or the
cabinet geometry; `shell/audio.py` — only the clip names at lines 209–220, not
the synthesis. Not read at all: `tests/test_round.py`, `test_clock.py`,
`test_place.py`, `test_storage.py`, `test_scaling.py`, `test_select.py`. Step 2
in particular claims "no test changes" against `test_select.py`, which has not
been read — verify that claim before relying on it.

### Out of scope, and where it went

Recorded in `ideas.md`, not built here: guess-my-rule / the function machine
(`research/math-education.md` §3.4), CGI-structured word problems (§3.3), and
fractions on a number line (`research/iready-grade3.md` §5.1) — the highest-value
item on the grade-3 list, deferred because it is a different *span* rather than
different *rules* and therefore wants a level, not the last cabinet. Rounding as
a second question over the placement mechanic (§5.3) and the scaled pictograph
scoreboard (§5.5) are the two cheapest remaining and belong beside it. The
parent-facing view that would read `placements` and the per-fact tallies back is
the same deferral it has been in every section of this file.

---
## Code Breaker: the answers are the combination

### What changes

The fourth cabinet stops being a sentence judged one at a time and becomes a
panel of them. Each intercepted line has one number missing — `7 + 6 = ? + 5` —
and every number he works out drops into a combination that opens a lock. A
round is three locks of four, five and six lines. A wrong answer trips one of
three alarms; the line stays put, the number line comes up showing both sides,
and he tries again. Three alarms and the vault locks down.

### The load-bearing decision: the maths has to *be* the reward

Replay Booth was built to this file's own spec, passed 200 tests, and was not a
game. The failure is worth stating precisely, because it is not a failure of the
lesson and re-deriving it from the working code is impossible.

Walk what was on screen. A green rectangle with `7 + 3 = 3 + 9` in it, two
buttons, and a pip in the shared header. Now compare each cabinet by what
*moves*:

1. Rocket: a part bolts on, visibly, every correct answer. Ten of them build an
   object.
2. Tennis: a ball falls at him and he hits it back.
3. Football: a marker walks up a field he can see.
4. Booth: nothing. The only state on screen was `0 / 10 calls`.

And the feedback ran backwards. A *wrong* call raised the two-route number line
— the richest picture in the game. A *right* call played a whistle and advanced.
The punishment was more interesting than the reward, which for a seven-year-old
is the whole problem.

The third thing was structural. Removing the clock was correct — the mode
measures reasoning faster than his own arithmetic, and a clock suppresses what
it is measuring — but the clock was the only thing carrying tension in the other
three cabinets, and nothing replaced it. Ten identical calls in a row; call nine
felt like call one.

So the fix is not art on top of the booth. It is: **make the answers accumulate
into something**, which is what a combination does. The number he works out is
not scored, it is *kept*, in a cell he can see, next to the cells still empty.
That single change gives the mode an object that grows, a reward for being right
that is bigger than the reward for being wrong, and — with locks of four, five
and six — an escalation that the flat run of ten never had.

The cost is stated plainly: **the true/false half of the lesson goes.** `8 = 8`
and `3 + 5 = 5 + 3` cannot be asked as a blank, and those are the two Carpenter
items that confront `=` most directly. What survives is `7 + 6 = ? + 5`, which
is the canonical open number sentence and the gateway item in the same research.
That trade was put to the user with the loss named, and taken.

### What was deleted, and why it is not dead code kept "just in case"

`judge`, `Round.repairing`, `Round.judging`, `Round.asking`, `Sentence.true`,
`Sentence.hidden`, `Sentence.blanked`, `Sentence.repaired`, the false-sentence
generator with its shift-and-check, and the outcomes `UPHELD` / `CALLED` /
`BLOWN` / `FIXED`. With every line open, nothing can fire any of it. Kept, it
would be a second reducer a cold reader has to understand before finding out
that no mode calls it. The history is in git and the reasoning is in the section
above this one.

`Rules.judges` and `Rules.locks` collapsed into one dial for the same reason: a
mode with locks has sentences in them, and there is no useful mode with either
and not the other.

### The steps

Order forced: the item shape before the deck, the deck before the reducer, the
reducer before anything can be drawn, and the panel before it can be looked at.

1. **`Sentence` loses its judged half.** `domain/facts.py`. Sides hold true
   numbers, `prompt` hides the marked one, `filled` shows it. Generation drops
   the shift-and-check entirely — nothing false is ever built, so `_sane` has
   nothing to guard.
2. **A shape for thin pools.** `_decomposed` — `12 ÷ 2 = ? + 4`. Without it a
   division level generated **ten lines, every one of them bare** `12 ÷ 2 = ?`,
   because division cannot commute and no two of its expressions share a value.
   That is the whole cabinet reduced to plain arithmetic on repeat, and it is
   only visible by generating a deck and looking at it. Both parts at least one:
   `18 ÷ 2 = 0 + ?` is the bare fact with a nought on the front.
3. **Locks and alarms.** `domain/round.py`. `Rules.locks`, `Round.cracked`,
   `Round.lock`, `Outcome.CRACKED`, the alarm branch in `apply`, and the guard
   that the locks add up to the target.
4. **The panel.** `shell/draw.py`, `shell/app.py`, `shell/audio.py`.
5. **Documentation.** `README.md`, `CLAUDE.md`, `ideas.md`, and the banner on
   the section above.

### Traps

**`apply` can now end a round, so `submit` must handle `LOST`.** Every other
mode loses in `tick` or in `throw`. Without the branch the domain is over while
the shell sits there with a dead keypad and no failure screen, and nothing
raises. Found by driving a round headless, not by the suite.

**Do not name a rect after a colour.** `PANEL` is a palette entry in `draw.py`;
a module-level `PANEL = pygame.Rect(...)` silently replaced it and every cabinet
on the menu screen died with `invalid color`. It is `CODE_PANEL`.

**The hint box has to be tall enough for two routes.** `draw_two_routes` needs
roughly 470px; given the 230px box it was first handed, the arcs drew through
the prompt and the entry box sat on top of the verdict. Its baselines are now
proportional to the rect, and Code Breaker's hint covers the panel — which is
dead while a hint is up, exactly as the rocket's hint covers the rocket.

**Lines below the active one must stay encrypted.** Drawing the real sentences
lets him read ahead and work the easy ones first, and the lock stops being a
sequence. Same trap as the yard stripes.

**`cracked` clears on each swung vault**, or three locks of lines run off the
bottom of the panel.

### Considered and rejected

- **Adding a reveal animation to the booth** — the two sides weighing after he
  commits. It fixes the backwards feedback and nothing else: still no object
  that accumulates, still no escalation. It was my recommendation and the user
  overrode it with the code-breaking direction, which is the better call:
  a spectacle that happens *and then is gone* is not progress.
- **A game to officiate on the monitor** — a scoreboard advancing as he calls.
  Most art, and it reads as a fourth sport beside the football cabinet.
- **Promotion through a crew** — sideline to head referee. A label changing, not
  a thing moving, which is the problem being fixed.
- **Free choice of which line to attack.** More like a real puzzle and genuine
  agency. Costs a reducer change — `apply` would need to know which line the
  answer is for — and click-to-select state in the shell. Worth revisiting if
  the fixed order reads as a list rather than a panel.
- **Open lines plus one forgery per lock** — keeps true/false as a decoy line to
  flag. It is the way back to the lost half of the lesson, and it costs two
  input modes on one panel. The likeliest next change to this cabinet.
- **Single-digit answers only**, so each cell is one digit. Would cripple
  generation on the times and division levels, where values run to a hundred.
  Cells are sized for two digits instead.
- **Keeping `judge` for a later forgery mode.** Future-proofing a reducer no
  mode calls.

### Accepted with known risk

- **The true/false items are gone**, and with them the two Carpenter shapes that
  most directly attack "`=` means write the answer here". `7 + 6 = ? + 5`
  carries the lesson alone. **Revisit trigger:** if he fills blanks fluently but
  still reads `=` as an instruction — which shows up as him answering
  `7 + 6 = ? + 5` with 13 — the forgery line above is the fix.
- **Three locks of 4/5/6 is fifteen lines**, half again the ten the booth asked
  for, with no clock to bound it. **Revisit trigger:** if a round runs past three
  minutes or he stops before the third lock, shorten `LOCKS` — it is one tuple.
- **Bare lines (`7 + 6 = ?`) are the fallback shape** and are the question the
  other three cabinets already ask. Weighted 1 against 5/3/3 and pinned under a
  third of any deck by test. **Revisit trigger:** if the division levels feel
  like arithmetic, the split shape's weight is the dial.

### Environment and coverage notes

The suite covers items, decks, locks and alarms. It does not open a window. The
panel, the encrypted rows, the combination filling, the bolt animation and the
three new clips are checked by a human at `uv run mathr` — plus, this time, by
driving the app headless under `SDL_VIDEODRIVER=dummy` and saving frames, which
is what caught the `PANEL` collision, the broken hint box and the missing `LOST`
branch. That technique is worth reaching for before asking the user to look.

### Out of scope, and where it went

Unchanged from the section above: guess-my-rule, CGI word problems, and
fractions on a number line stay in `ideas.md`. The forgery line is recorded here
rather than there, because it belongs to this cabinet rather than beside it.


## Code Breaker: the panel becomes a safe

### What changes

Shell only. No `Rules`, no reducer, no storage: the mode plays exactly as the
section above describes. The left column stops being a sci-fi readout and
becomes one safe door — hinges down the left, three bolts down the right, the
alarm lamps in the top rail, the lines behind glass, the combination and a dial
on the face below them. A correct answer turns the dial a notch. A filled
combination spins it, throws the bolts, and holds the finished lock in green.
Winning swings the door off its hinges: inside is gold on two shelves.

### The two things that were already wrong

Both found by driving a round headless and looking at the frames, neither
visible in the suite and neither raising anything.

**The crack was showing him the code being erased.** `apply` clears `cracked` on
the line that opens a lock, and `Round.lock` is derived from `parts`, so on that
same frame `render_code` redrew the panel as the *next* lock — encrypted rows,
empty cells — and animated a bar over the top of it. The one moving reward in
the mode was the safe resetting. The fix is `Play.opened`: the shell keeps the
lock it has just finished for as long as it is shown, which is presentation and
belongs on `Play` beside `throw` and `review`, not in the domain.

**`UNLOCK_HOLD` was not a hold.** `submit` sets `flash_left = FLASH_TIME` (0.45)
for every outcome, and `App.opening` divides by `UNLOCK_HOLD` (1.1). The bolts
therefore started 59% drawn back and finished in 0.45s, and the constant in the
tuning table described nothing. A `CRACKED` branch in `submit` gives it the 1.1s
it has always claimed.

### The load-bearing decision: the safe wraps the maths, it does not sit beside it

The obvious build is a vault door drawn *next to* the panel. The screen says no
before taste does: the only free space is the strip beside the keypad, about
580x120, and a door there is a decoration next to the game rather than the thing
he is playing. More importantly it repeats the failure the section above exists
to fix — the reward would be art that happens near the maths instead of the
maths itself. Wrapping the combination cells in the door makes the numbers he
worked out *be* the safe's face. The dial turning on each answer is the same
argument at one-notch scale: the motion says what he just did.

The door is rectangular, because it has to wrap a 548-wide panel. `draw_vault`,
the round one, stays exactly as it was for the cabinet screen, where a turning
dial reads at 200px and a rectangular box does not.

### The steps

1. **The rects.** `CODE_DOOR`, `CODE_PANEL` and `LOCK_ROW` re-laid inside it,
   `CODE_HINT` split out from `CODE_PANEL`, `CODE_CHAMBER` behind it.
2. **The door.** `draw_door`, `draw_bolts`, `draw_dial`, `_hinges`; `draw_panel`
   loses the lock label to the rail and `draw_alarms` disappears into it.
3. **The hold.** `Play.opened`, the `CRACKED` branch in `submit`, and
   `App.opening` returning `None`.
4. **The hoard.** `draw_treasure` and the `"code"` branch in `render_win`.
5. **Documentation.** `README.md`, `CLAUDE.md`, and this section.

### Traps

**`App.opening` returns `None`, not `0.0`, when nothing is swinging.** A swing
starts at zero, so a renderer gating on `opening > 0` spends the first frame of
the reward drawing the next lock, empty — which is the bug being fixed, surviving
in a single frame where it is just fast enough to read as a flicker.

**Everything on the door goes with the door.** The rail labels, the alarm lamps,
the combination and the dial are drawn by `render_code`, which runs before
`render_win` on the winning frame. `draw_treasure` repaints `CODE_DOOR`'s face
before drawing the chamber, or "LOCK 3 OF 3" floats over the open safe.

**The bolts are drawn after the glass.** They retract *inward*, and the panel is
inward of them; drawn with the frame they disappear behind it at exactly the
moment they are meant to be watched.

**`CODE_HINT` is not `CODE_PANEL` any more.** `draw_two_routes` needs about
470px of height, and the panel is now sized for six lines inside a door. Tying
the hint to the panel means retuning `_LINE_HEIGHT` silently squeezes the number
line.

### Considered and rejected

- **A round door.** It cannot wrap a rectangle of lines, and shrinking the lines
  to fit a circle costs legibility on `12 ÷ 2 = ? + 4`, which is the shape that
  needs it most.
- **Growing the safe to fill the screen before it swings.** A bigger moment, but
  the safe leaving the spot it stood on all round breaks the continuity that
  makes the swing land on the work he did.
- **Coins spilling out of the door**, using the rocket's `FallingPart`
  machinery. Most motion, and a physics pass this mode has no other use for.
- **A hoard that grows across wins.** New stored state beside `launches` and a
  place to show it — a different feature wearing the safe's clothes. Worth doing
  deliberately or not at all.
- **New clips for the bolt throw and the door.** The crack still plays `unlock`,
  the notch `tumbler`, the win `cheer`. Additions to `audio.py`, independent of
  any of this, and easier to judge once the pictures are being watched.

### Accepted with known risk

- **The leaf is blank steel while it swings.** Carrying the rail, the
  combination and the dial on a horizontally compressed leaf is a surface and a
  transform for about a second of screen time. **Revisit trigger:** if the swing
  reads as a slab sliding rather than a door opening.
- **The chamber is large and the hoard sits on two shelves near the bottom.**
  There is empty dark above it, behind the banner. **Revisit trigger:** if it
  reads as an empty safe with something at the bottom rather than a full one.

---


## Curling: a fraction placed on a partitioned line

A fifth cabinet, and the first mode with no keypad in it. He is shown a
fraction, he clicks where it goes on a sheet of ice marked 0 to 1 and ticked
into equal parts, and the stone slides to exactly where he clicked and stays
there. Eight stones an end. A stone within half a tick gap of the true mark is
in the house and counts; three wide ones end the round. There is no clock —
estimation is deliberate, and a stopwatch on it measures the stopwatch. This is
`3.NF.A.2` (locate `a/b` on a number line partitioned into `b` equal parts) and,
in its second level family, `3.NF.A.3` equivalence: the line is ticked in sixths
and the number called is `1/3`. See `research/iready-grade3.md` §5.1 for why this
strand and not another; the short version is that it is the top item of grade 3's
hardest unit and the number line beats the area model in the intervention
evidence.

### The load-bearing decision: the target is an *item*, not a position

The obvious move is to reuse the football placement whole — set `rules.places`,
let `Round.placing` name the target, let `place()` resolve the click. It is
wrong, and the failure is arithmetic rather than taste.

`Round.placing` (`domain/round.py:268`) derives its target from the marker:
`min(PLACE_MAX - 1, parts + gains[placed % len(gains)])`, with `gains` drawn in
`new_round` from `range(PLACE_GAIN_MIN, PLACE_GAIN_MAX + 1)`. Walk an end of
curling on that machinery, on a level whose pool is thirds and sixths:

1. Stone 1. Marker at 0, the drawn gain is 23. The target is 23 of 100. The
   mode must now ask him to place **23/100** on a line ticked into sixths.
   There is no tick there and the number is not in the level.
2. He is near enough, so the marker moves to 23. Stone 2's gain is 31: the
   target is 54/100. Still not a sixth, and now also not a third.
3. By stone 5 the marker is past 80 and every remaining target is in the top
   fifth of the line. `1/2` cannot be asked again this round at all — the
   marker walked past it on stone 2 and `_secure` (`round.py:662`) uses `max`
   precisely so nothing can walk it back.

Three separate failures, and only the third one has a name in this repository
(*a drive that never goes backwards is the one with least in it*). The first two
are fatal: the number called is a function of the previous stones, so a level
cannot control which fractions are asked, and the ticks drawn have nothing to do
with the number called. `new_round`'s guard at `round.py:404` compounds it —
`rules.places` requires `target == PLACE_MAX`, so the span could not be anything
but 100, and 100 is not divisible by 3.

The mode would compile, draw, and play — the stones would slide, the house would
fill — while asking questions from outside its own level. The symptom is "the
fractions are weird", which names nothing.

So the target comes from the **deck**, not from the marker. That makes it an
item, which the codebase already has a seam for: `Item = Question | Sentence`
(`domain/facts.py:218`), where everything downstream of `Round.queue` touches
only `.key`, `.prompt` and the route. It becomes
`Item = Question | Sentence | Target`, and `parts` goes back to meaning what it
means in the rocket — stones in the house, out of eight — rather than a position
on the line.

Everything below is downstream of that.

### The load-bearing decision, second half: `place` becomes this mode's `apply`

`apply` (`round.py:672`) is the only reducer that writes a `Tally`, and — apart
from `tick`'s timeout path — the only one that advances the queue, via `_advance`
(`round.py:463`). `place` (`round.py:583`) deliberately does neither: in football
a wide throw comes straight back as another attempt from the same spot, and the
question under it is untouched because a *later answer* is what confirms it.

A curling stone is thrown once. Wide or not, the next fraction comes up. So
`place` in this mode has to advance the queue, record the attempt against the
item's key, and credit the part. That is not a shell concern and it is not a
second `Round`: it is a branch in `place` on a rules dial, taken before the
football path.

The tempting alternative is a fourth reducer, `slide()`. Rejected: it would
duplicate the tally write, the advance and the win check, and the three copies
would drift the first time `RETRY_GAP` or `Tally` changes. One reducer, two
branches, with the branch named for what the domain knows (the target came from
the deck) and not for curling.

### What a target is

```python
@dataclass(frozen=True)
class Target:
    num: int       # the numerator called
    den: int       # its denominator
    ticks: int     # how many equal parts the line is drawn in; a multiple of den
```

- **`ticks == den`** is the plain family: `2/3` on a line ticked in thirds.
- **`ticks == k * den`** is equivalence: `1/3` on a line ticked in sixths, which
  is grade 3 lessons 16–17 at no mechanical cost.

Derived, all of it:

- `value` — where it truly lies, in span units: `SPAN * num // den`.
- `tolerance` — half a tick gap: `SPAN // (2 * ticks)`. Self-tuning, so halves
  are forgiving and twelfths are tight, and no constant needs retuning per level.
- `route` — a `Strategy` in **tick units**: `Strategy(0, (ticks // den,) * num)`.
  `2/3` on thirds is two hops of one; `1/3` on sixths is one hop of two, which
  is the equivalence said out loud. This is the same shape `12 ÷ 3` already
  produces, so `draw.draw_number_line` (`draw.py:1323`) is the miss picture with
  no new widget.
- `prompt` — `"2/3"`. `key` — `"2/3|6"`, numerator, denominator and the
  partition, because `1/3` on thirds and `1/3` on sixths are different questions
  and must not share a row.
- `answer` — **there is none.** A `Target` deliberately has no `.answer`
  property. Anything that reaches for one is code that thinks this is typed, and
  should fail loudly at the attribute rather than quietly comparing to `None`.

**`SPAN = 240`, and the number is load-bearing.** Every denominator in scope
(2, 3, 4, 5, 6, 8, 10, 12) must divide the span *and* leave an even quotient, or
the half-tick-gap tolerance is not an integer and `place`, `Aim` and the click
conversion all have to learn floats. 120 fails: `120 // 8 = 15`, half of which is
7.5. 240 passes for every one of them. Verified by enumeration; re-run it before
adding a denominator:

```python
[d for d in (2,3,4,5,6,8,10,12) if 240 % d or (240 // d) % 2]  # -> []
```

### What changes, file by file

| File | Change |
|---|---|
| `src/mathr/domain/facts.py` | `Target`; `Item` gains it; `targets()` deck builder; four `_FRACTION` levels plus an equivalence family; a fractions `Everything` |
| `src/mathr/domain/round.py` | `CURLING` rules; a dial for deck-drawn targets; `SPAN`, `STONES`, `STONE_LIVES`; `placing` branch; `place` branch that advances, tallies and credits; `losable` learns `place_lives`; `new_round` guard relaxed |
| `src/mathr/storage.py` | a `targets` section beside `facts` and `placements`; `merge` folds `Round.attempts` for target keys into it |
| `src/mathr/shell/draw.py` | `SHEET`, `draw_sheet`, `sheet_units`, `CURLING` `Layout`, `draw_rink` (cabinet art); `CABINETS` geometry |
| `src/mathr/shell/audio.py` | two clips: `slide`, `inhouse` |
| `src/mathr/shell/app.py` | `CURLING` mode, 3×2 `CABINETS`, per-mode level lists, `render_sheet`, `slide()` beside `throw()`, `render_play` dispatch entry |
| `tests/test_curl.py` | new |
| `tests/test_facts.py`, `test_storage.py`, `test_scaling.py` | additions named per step |
| `README.md`, `CLAUDE.md`, `ideas.md` | named per step |

### The steps

Ordered so that every guard exists before the thing it guards, and so that the
domain is complete and tested before a window is opened. Each step leaves the
suite green and the game playable.

**1. `Target` and the fraction pools** — `domain/facts.py`.
Add `Target`, widen `Item`, add `targets(pool, rng, count)` (a flat shuffle; it
must not go through `shuffled`, which returns `Question`s and whose rng
consumption is pinned by two seeded tests). Add the level families:

| id | name | pairs |
|---|---|---|
| `halves` | Halves & Fourths | `den` 2 and 4, `ticks == den` |
| `thirds` | Thirds & Sixths | `den` 3 and 6, `ticks == den` |
| `fifths` | Fifths & Tenths | `den` 5 and 10, `ticks == den` |
| `eighths` | Eighths & Twelfths | `den` 8 and 12, `ticks == den` |
| `same_as` | Same As | `den` 2/3/4 drawn on `ticks` 4/6/8/12 — equivalence |
| `fractions` | Every Fraction | the concatenation, derived like `EVERYTHING` |

Enumerated, never generated, exactly as the fact pools are. Exclude `0/b` and
`b/b` from every pool: both are the labelled ends of the line, so they are free
marks that measure nothing — the same reason `_divided` drops the zero pair.
**Gate:** `uv run pytest`. **Tests:** pool sizes pinned per level and for the
derived `fractions` total, the way `test_pool_sizes` (`tests/test_facts.py:47`)
pins the fact pools; that `ticks % den == 0` for every target in every pool; that
`tolerance` is an integer for every target in every pool; that `route` in tick
units lands on `num` hops summing to `value`.
**Falsifies:** `CLAUDE.md`'s pool-size list (`24 / 44 / 144 / …`) and its claim
that `Round.queue` holds `Question | Sentence`.

**2. The rules and the reducer** — `domain/round.py`.
`SPAN = 240`, `STONES = 8`, `STONE_LIVES = 3`. Add the dial — one boolean on
`Rules`, `targets_from_deck`, documented as *the placement is the question, not
a function of the marker*. `CURLING = Rules(0.0, 0.0, 0.0, False, False, None,
STONES, places=True, place_lives=STONE_LIVES, targets_from_deck=True)` — the
three timing dials dead, as they are in `CODE` (`round.py:151`).
- `placing` returns `round.current.value` when the dial is set, before any of the
  gains/sack machinery, and still after the `over` and `hint` guards.
- `place` branches first on the dial: no `pending`, no penalty, no sack. It
  advances the queue (no re-queue — see traps), records
  `attempts[target.key]` with `record(good, on_current)`, adds `good` to `parts`,
  zeroes `on_current`, increments `adrift` on a wide one, and returns
  `PLACED` / `ADRIFT`, or `WON` when `parts >= rules.target`, or `LOST` on the
  `place_lives`th wide stone.
- `losable` (`round.py:319`) becomes
  `self.timed or self.rules.wrong_costs_life or self.rules.place_lives is not None`.
  Without it a perfect end folds to `practice` forever and the level card never
  shows a launch.
- `new_round`'s guard at `round.py:404` becomes
  `if rules.places and not rules.targets_from_deck and rules.target != PLACE_MAX`.
  The guard must keep firing for football; add a test that it still does.
- The deck comes from `targets(...)` when the dial is set, and draws no `gains`,
  `sacks` or `sack_at` — so a curling round consumes the rng exactly as its own
  shuffle does and nothing else.
**Gate:** `uv run pytest`. **Tests:** `tests/test_curl.py` — an in-house stone
scores and advances the queue; a wide one advances it too and scores nothing;
three wide ones return `LOST` and set `failed`; eight in the house return `WON`;
the tolerance is exactly half a tick gap at three denominators; `losable` is true
for a curling round and still false for an untimed rocket round; `tick` never
ends a curling round; the queue is never re-queued.
**Falsifies:** `CLAUDE.md`'s *A round that cannot be lost must not touch
`launches`* (it now asks a third thing) and the `Rules` dial list.

**3. Storage** — `storage.py`.
A `targets: Mapping[str, Tally]` section on `Progress`, read through `.get` with
a default so a file written today still loads; `merge` routes a round's
`attempts` into `facts` or `targets` by mode (`round.rules.targets_from_deck`),
never by sniffing the key shape. **No `VERSION` bump** — `Fact.key` is unchanged
and the level key is unchanged; this is a new section, which is exactly the case
the module docstring says is additive.
**Gate:** `uv run pytest`. **Tests:** round-trip with targets present; a file
with no `targets` key loads as empty, beside
`test_a_file_from_before_the_clock_still_loads` (`tests/test_storage.py:60`); a
curling round's attempts land in `targets` and never in `facts`; a football
round's `aims` still land in `placements`.
**Falsifies:** the `storage.py` module docstring's list of sections, and
`CLAUDE.md`'s storage line.

**4. The sheet** — `shell/draw.py`.
`SHEET` rect, `draw_sheet(surface, font, ticks, stones, called, ghost)` — the
ice, the ticks, `0` and `1` labelled at the ends, the house drawn as rings
centred on the called mark at the target's own tolerance radius, and every stone
thrown so far. `sheet_units(position) -> int | None`, the sibling of
`field_yards` (`draw.py:1005`), converting a design-space click to `0..SPAN` and
returning `None` off the sheet, vertically generous for the same reason. A
`CURLING` `Layout` (`draw.py:1218`) — there is no entry box, so `entry` is a
zero rect and `hint` takes the sheet's own area.
**Gate:** `uv run pytest`. **Tests:** in `tests/test_scaling.py` — `sheet_units`
maps the two ends to 0 and `SPAN`, is monotone across the sheet, and returns
`None` above and below it; the house radius shrinks as `ticks` grows.

**5. The cabinet grid** — `shell/app.py`, `shell/draw.py`.
`CABINETS` (`app.py:190`) becomes three across by two down: six slots, five
modes and one `"soon"`. Widths go 400 → 368 with 44 of gap
(`44 + 368 + 44 + 368 + 44 + 368 + 44 == 1280`); **height stays 220**, so
`cabinet_parts` (`draw.py:517`) and the test pinning `h = 440` unchanged are
untouched. The `"soon"` guards are already in `click` (`app.py:402`) and
`draw_card` (`draw.py:217`) — verify both still skip it after the grid changes.
This lands before the mode so the grid is proven with a dimmed slot rather than
with a half-built cabinet in it.
**Gate:** `uv run mathr` — the arcade shows six slots, the sixth is dim, dead
and does not hover. **Falsifies:** `CLAUDE.md`'s *the 2x2 grid is full* and
*Two rows of two, and now full* at `app.py:187`.

**6. Per-mode level lists** — `shell/app.py`.
`Mode` (`app.py:63`) gains `levels: tuple[tuple[str, ...], ...]` and
`titles: tuple[str, ...]`; the level screen builds its buttons from the current
mode instead of the module-level `LEVEL_COLUMNS` (`app.py:210`) and
`COLUMN_TITLES` (`app.py:208`). The four existing modes carry today's four
columns verbatim, so nothing about them changes. `fail_action`'s
`LEVELS[0].id` fallback (`app.py:472`) must become the current mode's first
level, or *Try again* on a curling failure starts a rocket level.
This lands before the mode because a curling cabinet with the arithmetic level
screen behind it is a wrong game one click deep.
**Gate:** `uv run pytest`, then `uv run mathr` — each of the four cabinets still
shows its twelve cards.
**Falsifies:** `CLAUDE.md`'s *every cabinet still leads to the same twelve level
cards* and the comment at `round.py:412`.

**7. The mode** — `shell/app.py`, `shell/audio.py`.
`Play` gains `stones: list[tuple[int, bool]]` (where each landed, and whether it
counted) and `ghost: tuple[int, int] | None` (aimed, called) for the held miss.
`slide(position)` beside `throw` (`app.py:579`): convert with `sheet_units`,
call `place`, append the stone, hold the miss. `click` (`app.py:399`) routes to
it on the dial rather than on `self.mode`. `render_sheet` joins the
`render_play` dispatch (`app.py:796`) — a dict entry, never an `if`. `start`
(`app.py:477`) sets `timed=False` for this mode alongside the `locks` case.
Clips: `slide` and `inhouse`.
**Gate:** `uv run mathr`, and see the section below for what to look at.
**Falsifies:** `CLAUDE.md`'s mode list, `render_play` note and *Making the two
likely changes*.

**8. The documentation.** `README.md` gains the mode; `CLAUDE.md` gains the map
entries, the tuning rows (`SPAN`, `STONES`, `STONE_LIVES`, `SENTENCE_DECK`'s
sibling for the target deck size) and every invariant from the traps below;
`ideas.md` takes the deferred work named at the end of this section. Last,
because the earlier steps each falsify a piece of it and doing this once is
cheaper than eight times.

### Traps

**A wide stone must not be re-queued.** `_advance(round, retry)`
(`round.py:463`) exists because a missed *fact* has to come back — retrieval,
not echo. A missed *estimate* is different: the ghost has just shown him the true
mark, so re-asking the same fraction three throws later is asking him to
reproduce a picture he is still looking at, and the deck weighting is not there
to fix it either. Pass no `retry`. Symptom otherwise: the end fills up with the
one fraction he got wrong first, and it reads as the shuffle being broken.

**`place` must zero `on_current`.** It is `apply` that does this today
(`round.py:685`), and in this mode `apply` is never called. Miss it and
`on_current` accumulates across the whole end, so the last stone is recorded as
having taken ninety seconds. Nothing raises; the number is simply a lie, and it
is a lie in the record that a parent view would read.

**Target rows must not go into `placements`.** `save` sorts that section with
`key=lambda item: int(item[0])` (`storage.py:127`) — it is keyed by decade of the
line. A key of `"2/3|6"` raises `ValueError` *inside `save`*, so the
`os.replace` never happens and **the whole file silently stops being written**;
`load` swallows nothing here because nothing was written. The symptom is progress
that stops accumulating with no error on screen. This is why targets get their
own section, and it is a second reason (beyond the bucket collision with
football's yards) not to reuse `aims`.

**`Target` has no `.answer`, and that is deliberate.** `apply` compares
`given == question.answer`. If `Target` grows an `answer` property for symmetry,
a stray keypad path in a future mode compares a typed integer against a span
value and marks `160` correct for `2/3`. Leave the attribute absent so that path
raises.

**The Timer toggle is dead here**, as it is in Code Breaker. `start`
(`app.py:477`) must force `timed=False`; a curling round built with a clock has
`seconds_left` draining under a mode with nothing to spend it on, and `tick`
would end a round nothing is watching.

**A click on the sheet must not dismiss the held miss.** The same rule the field
already has: `review` is cleared by a button, never by a click on the play area,
or reading the ghost throws the next stone at whatever tick he was reading.
`press` clears it too, so the keyboard is not dead in front of it — and `press`
must otherwise return early for this mode entirely, since there is nothing to
type.

**The house is drawn at the target's own tolerance.** Not at a constant. A fixed
ring under a half-tick-gap rule tells him he is in when he is out; the ring
shrinking as denominators grow is also the only thing on screen that says the
shot got harder.

**`0/b` and `b/b` are not questions.** Both are the labelled ends of the line.
Left in the pool they are free marks that measure nothing and inflate the record
— the same failure `_divided` avoids by drawing from `range(1, 11)`.

**A denominator added later must be re-checked against `SPAN`.** Sevenths and
ninths divide neither 240 nor any span with an even quotient for the whole
existing set; adding one means moving the span *and* re-deriving every
tolerance. Run the enumeration above before adding a level.

### Considered and rejected

- **Reuse football's placement whole.** The load-bearing decision above: the
  target would be a function of the marker, so a level could not control which
  fractions it asks.
- **A fourth reducer, `slide()`.** Duplicates the tally write, the advance and
  the win check; three copies that drift the first time `Tally` changes.
- **A power meter — aim plus weight, as in real curling.** Makes the error partly
  motor, which corrupts the one measurement this mode exists to take. The click
  is the estimate and the stone lands exactly there.
- **A pie or bar splitting into `b` parts on a miss.** The area model. The
  intervention evidence in `research/iready-grade3.md` §5.1 is specifically for
  the number line *over* it, and two representations for one idea is worse than
  either alone.
- **A shot clock per stone.** Cheap, and it would give the mode the tension the
  others get from a clock. Rejected because a stopwatch on a deliberate estimate
  measures the stopwatch; the stones accumulating on the ice are what carries the
  round instead.
- **Weighting the deck by estimation error.** `_weights` (`round.py:363`) reads
  mean seconds against the level's pace, which means nothing for a stone. A
  second weighting function is a second mastery model, which `ideas.md` has now
  refused three times. Recorded in `ideas.md`.
- **A fixed tolerance, like `PLACE_TOLERANCE`.** No single number is right for
  both halves and twelfths.
- **My own wrong turn, worth recording.** I first proposed spanning the line in
  **120** units and asserted the denominators all divided it. They do not:
  `120 // 8 = 15`, so an eighths line has a half-tick gap of 7.5 and the
  tolerance stops being an integer — which would have pushed `place`, `Aim` and
  the click conversion into floats for one denominator, and the failure would
  have shown up as eighths being inexplicably harder than twelfths. Enumerating
  the divisors instead of trusting the round number is what found it. 240.
- **My second wrong turn.** I initially recommended per-target rows go into the
  existing `facts` map, since a `Tally` is a `Tally`. The `int()` sort in `save`
  is a hazard in the same family, and mixing two key shapes in one section makes
  every future reader of that file disambiguate them. A separate section costs
  one dict and no version bump.

### Accepted with known risk

- **The house moves every stone.** In real curling it does not; the house is
  fixed and the *throw* varies. This is target practice on ice wearing curling's
  clothes. Taken knowingly: the accumulating stones and the rings-as-tolerance
  are worth more than the fidelity. **Revisit trigger:** if he says it is not
  curling, or a real game confuses him — the same test the football/field-goal
  argument was decided on.
- **Eight stones can crowd.** Two targets that land near each other put two
  stones nearly on top of each other, and at twelfths the marks are ten span
  units apart. **Revisit trigger:** if stones become hard to tell apart on the
  ice; the fix is stacking them in rows above the line, not shrinking them.
  *Fired on the first play-through, and the named fix is what was built:*
  `stone_rows` in `shell/draw.py`. `halves` guarantees it — `1/2` and `2/4` are
  the same mark, and a deck of four over eight stones puts up to four on it.
- **Both level families ship together.** The equivalence family (`same_as`) is
  strictly harder than the four plain ones and its tolerance is the one most
  likely to need re-arguing. **Revisit trigger:** if the `same_as` record shows a
  wide-stone rate unlike the other five, treat its tolerance — not his
  understanding — as the first suspect.

### Environment and coverage notes

- The suite does not open a window. Three things can only be checked by a human
  at `uv run mathr`, and step 7's gate is all three: that a click on the sheet
  lands on the tick it looks like it lands on **at several window sizes,
  including a tall narrow Hyprland tile**; that the two new clips are audible
  through PipeWire; and whether half a tick gap is the right bar for him at
  eighths and twelfths.
- `pytest` and `ruff` are not installed system-wide; they arrive through `uv`.
- One runtime dependency, `pygame-ce`. This adds none.
- The user creates commits and anything on GitHub. Do not commit or push
  without asking.

### What was read, and what was not

Read closely for this plan: all of `domain/round.py`, all of `storage.py`,
`domain/facts.py` in full, and the parts of `shell/app.py` named by line above
(`Mode`, `MODES`, `CABINETS`, the level-screen constants, `Play`, `click`,
`start`, `press`, `throw`, `lose`, `render_play`). **Not read:** `shell/draw.py`
except the dozen symbols cited — in particular `draw_field`, `draw_number_line`
and `draw_progress` were read only at their docstrings, so step 4 should open
`draw_field` (`draw.py:1024`) in full before writing `draw_sheet`; it is the
closest sibling and the tick-drawing and label placement are likely to be
liftable. `shell/audio.py` and the existing tests were not read at all beyond
their names — step 1 should open `tests/test_facts.py` and step 2
`tests/test_place.py` before writing new ones.

### Out of scope, and where it went

Recorded in `ideas.md`, not built here: fractions past one on a 0–2 line and
mixed numbers; a bare unticked line as the hardest family; weighting the target
deck by estimation error; the parent-facing readout of both `placements` and
`targets`; rounding to the nearest ten as a second question type over the same
mechanic; the scaled pictograph scoreboard; *Guess my rule*; the rest of the
times tables; two-digit addition; and the grade-3 strands this program should
not pretend to hold — area and perimeter, mass, liquid volume, line plots and
geometry. `research/iready-grade3.md` is the argument behind each.

---

## Addition, resplit: ten and below, above ten

The three addition levels were `fives`, `tens` and `bridge` — bonds of five,
bonds of ten, and crossing ten. Enumerating what that actually covered was the
whole of the argument: of the 66 pairs summing to ten or less, exactly 17 were
asked, the ones totalling precisely 5 or 10. `2 + 2` was in no level in the
game. Neither was `1 + 1`, `3 + 4` or `6 + 2`. `bridge` then jumped to sums of
11–18. The gap was not a corner of the content, it was most of it.

### The split is on the operands, not the sum

Two levels replace the three, and the rule is **the two numbers as written**:

| Level | Rule | Facts |
|---|---|---|
| `small` — Ten and Below | both operands ≤ 10 | 372 |
| `big` — Above Ten | exactly one operand 11–20, the other ≤ 10 | 440 |

So `7 + 7 = 14` is small — two small numbers — and `14 − 7 = 7` is big, because
14 is written in it. `12 + 3` and `13 − 4` are big. The answer never decides.

The alternative was splitting on the sum, which is what "over the ten" always
meant, and it was rejected because it puts `7 + 7` and `9 + 8` in the same level
as `12 + 3` while leaving `2 + 2` nowhere: it sorts by how hard the answer is,
when what he is looking at is the question.

**The structural consequence is the thing to remember.** `_from_pair` yielded
four facts from one number bond — two addition, two subtraction — and under this
rule those four no longer belong together. The pair `(7, 7)` sends `7 + 7 = 14`
to `small` and `14 − 7 = 7` to `big`; `(4, 9)` sends `4 + 9 = 13` one way and
`13 − 4 = 9` the other. So it became `_add_pair` and `_sub_pair`, and each level
composes the pairs it wants from each. Merging them back is the silent failure:
`big` acquires `4 + 9`, or `small` acquires `13 − 4`, and the only symptom is a
card asking the questions the card below it is for.

`big` holds *exactly one* number past ten — written `(a > 10) != (b > 10)`, not
`or`. Two of them is `18 − 13`, which is regrouping: a different skill, already
logged in `ideas.md`, and one that would put a picture of two long hops in front
of him for a fact he should be decomposing. `TEEN_MAX` is 20 for the same reason
plus a drawing one: past twenty the number line spans a width a hop of three is
invisible on.

`(0, 0)` is the one pair left out of `small`. `0 + 0 = ?` is a free mark that
measures nothing and inflates the record — the same judgement `_divided` makes
by starting at one, and the same one that keeps `0/b` out of the curling deck.
Zero *addends* stay: `0 + 5` is a real thing to get wrong, and it was already
being asked.

### The bridging picture had a latent bug, and `big` triggered it

`Fact.strategy` bridged whenever `result > 10`, which silently assumed the first
operand was under ten. With `big` in the game it is not:

```
12 + 3 = ?   ->  Strategy(start=12, jumps=(-2, 5))
```

That lands on 15. Nothing raises, `draw_number_line` scales to the range and
draws a tidy two-hop picture — it just tells him to go *backwards* to ten and
then forward five, for a problem that crosses nothing. The guard is
`max(a, b) > 10` tested **before** the bridging branch, returning
`Strategy(bigger, (smaller,))`: hold the big number and count on, which is
exactly what the subtraction branch below it already does. Taking the bigger
number whichever side it is written on also makes `3 + 12` draw as `12 + 3`,
which is the commuting said out loud rather than a bridge from 3.

Rejected: bridging *upward* to the next ten, so `17 + 5` draws `17 +3 +2`. It is
correct and probably the better strategy at this range, but it is a new mental
move to teach, and `12 + 3` — which crosses nothing — still needs the single-hop
fallback anyway. Revisit after watching him read one.

### What was not broken

Nothing. `Fact.key` is derived from the equation, so every bond already drilled
under `fives` and `tens` arrives in `small` with its tallies intact and its deck
weight already earned — the level is smart from the first round rather than the
tenth. Only the `rocket/fives`-shaped rows in `levels` go stale, and they are
left alone: dead rows nothing reads, costing nothing.

Two alternatives were rejected. **Filtering unknown level ids on load** would
tidy the file at the cost of an import of the level table inside `storage.py`
and a new failure mode where a typo'd id silently erases a real record.
**Starting the file fresh** was explicitly on the table and is the worse trade:
the per-fact tallies are the one thing in there that cannot be reconstructed.

`test_a_file_from_before_the_clock_still_loads` deliberately keeps `fives` as
its level id. A v1 file predates this change, so its dead rows are exactly what
that test should be feeding in.

### Pacing

`seconds_per_part` is 4.0 for `small` and 5.0 for `big`. The bond levels were
3.0, but `small` now holds `1 + 1` and `9 + 8` in one pool, so 3.0 was too sharp
at its hard end and 5.0 would have made every level in the game 5.0 — at which
point the per-level dial is a constant and
`test_start_and_cap_scale_with_the_level` stops testing anything. This is a
guess, and the number that answers it is `failures` per level in
`progress.json`.

The cost of merging the levels, stated plainly: one pace now serves a pool
spanning `1 + 1` to `9 + 8`. The deck weighting orders *which* facts come up, not
how long each is worth. If he starts failing `small` while answering most of it
instantly, the honest fix is splitting it again — not shaving the constant.

### The level screen

The addition column holds two cards where the other two hold three, and the
fourth column keeps the tall *Everything* card and the dimmed *Tricky Facts*
slot. `level_screen` enumerates each column independently, so a short column
needed no code. The free slot is left free rather than filled: *Doubles* was
considered for it — `6 + 6` and `8 + 8` exist today only inside `big` as things
to bridge — and deferred, because it is a third addition level proposed before
anyone has watched him play the two.

---

## Test mode

`uv run mathr --test` runs the whole game against `test-progress.json`, a
sibling of his file. `App.__init__` already took a path, so the change is
`default_path(testing)` and a `testing` flag carried for one purpose: a line on
the menu screen.

Three decisions in it.

**A flag, not an environment variable.** `default_path` already reads
`XDG_DATA_HOME`, so `XDG_DATA_HOME=/tmp/x uv run mathr` was a working test mode
with no code at all. Rejected because an exported variable outlives the session,
and that is precisely how a real round gets written to the wrong file.

**It writes a real file rather than nothing.** Saving is the one place a bug
stops the record being written with no sign on screen — a `ValueError` inside
`save` means `os.replace` never runs — so a test session has to exercise it.
Just not against his.

**It says so on the menu and nowhere else.** During play a test round is
indistinguishable from a real one, and the failure is silent in the worst
direction: you conclude his progress was lost. A marker on every screen
including play was rejected as one more thing on screen while he is answering.

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
