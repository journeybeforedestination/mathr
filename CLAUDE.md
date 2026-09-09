# mathr

A desktop math-fact game for one specific second grader. `README.md` describes
how it plays; this file is what you need to change it safely.

- `plan.md` — the reasoning behind every decision, including the ones later
  reversed. Read the relevant section **before** arguing with a design choice;
  most of them were argued once already and the alternatives are recorded.
- `ideas.md` — what is deliberately out of scope, and why.

## Commands

```sh
uv run mathr      # play
uv run pytest     # the whole suite, ~0.1s
uv add <pkg>      # tell the user before adding any dependency
```

`pytest` and `ruff` are not installed system-wide; they come in through `uv`.

## Layering

One direction only: `shell/` → `storage.py` → `domain/`. Never the reverse.

- **`domain/` is pure.** No pygame, no I/O, no module-level `random` —
  randomness arrives as an injected `random.Random` so tests are deterministic.
- **`domain/round.py` knows `parts: int` and a bank of seconds, and nothing
  about rockets or aliens.** Part names, coordinates and art live in
  `shell/draw.py`. This is the seam that lets a second game mode reuse all three
  levels; the moment the reducer imports a part name, the next mode has to fake
  one or fork it.
- **Pacing is a rule, so the clock is in the domain** — a pure
  `tick(round, dt)`, not a timer in the event loop. That is what makes "the bank
  cannot exceed the cap" and "zero ends the round" testable without opening a
  window.
- **`storage.py` is the only file that touches the filesystem.**
- **`shell/` is imperative and draws.** It holds no rules. If you find yourself
  writing a game rule in `app.py`, it belongs one layer down.

## The map

```
src/mathr/
  __init__.py     main(): mixer pre_init, pygame.init, App(...).run()
  domain/
    facts.py      Fact, Level, the three enumerated pools
    round.py      Round, Tally, Outcome, new_round / apply / tick
  storage.py      Progress, Settings, LevelRecord; load / save / merge
  shell/
    app.py        App: event loop, three screens, all the wiring
    draw.py       palette, rocket parts, alien, starfield, buttons, the transform
    audio.py      five synthesized clips, no asset files
tests/
  test_facts.py   pool contents, key stability
  test_round.py   parts, re-queue, launch
  test_clock.py   the time bank
  test_storage.py round-trip, corruption, merge, backward compatibility
  test_scaling.py the design-surface transform, alien scale
```

`domain/facts.py` builds every level from one rule: each number-bond pair yields
four questions (`a+b=?`, `a+?=c`, `c−a=?`, `c−?=b`). Pools are enumerated, not
generated — 24 / 44 / 144 facts, pinned by `test_pool_sizes`.

## Tuning

These are the dials, and they are meant to be turned after watching him play.

| Constant | Where | Now | Effect |
|---|---|---|---|
| `PARTS_TO_LAUNCH` | `domain/round.py` | 10 | length of a round |
| `RETRY_GAP` | `domain/round.py` | 3 | how long before a missed fact returns |
| `GRACE_PARTS` | `domain/round.py` | 5 | opening head start, in problems |
| `BANK_PARTS` | `domain/round.py` | 4 | ceiling on banked time, in problems |
| `Level.seconds_per_part` | `domain/facts.py` | 3 / 3 / 5 | pace, per level |

`seconds_per_part` is the only per-level number; start and cap derive from it, so
retuning a level is one edit and nothing needs changing twice. `test_clock.py`
asserts the derivation rather than the literals, so changing a level's pace does
not break the suite — changing `GRACE_PARTS` or `BANK_PARTS` intentionally will.

## Invariants that break silently

**Layout is design space.** Everything is laid out in 1280×800 and scaled into
whatever the window actually is, because Hyprland tiles it to whatever the layout
gives. Mouse positions convert once, through `draw.to_design`, at the event
boundary — nothing downstream may see window coordinates. Symptom if this is
ever bypassed: clicks are accurate near the top-left and drift further out,
which reads as "sloppy hitboxes" and never as a scaling bug.

**`Fact.key` is a storage format.** It keys accumulated per-fact data in a file
that outlives the code. Changing its shape orphans every count already recorded
and needs a `version` bump plus a migration. Adding *fields beside it* is fine —
everything after `right`/`wrong` is read through `.get` with a default, which is
why adding the clock needed no version bump. `test_a_file_from_before_the_clock_still_loads`
pins that.

**Time credit must never push the bank down.** A round opens *above* its own cap,
so the obvious `min(left + per_part, cap)` would cut a 15s grace bank to 12s as a
reward for a correct answer. It is `max(left, min(left + per_part, cap))` — see
`_credit` in `domain/round.py`.

**`tick` accumulates per-question time even when untimed.** Response times are
worth having either way, and practice mode is where the slowest facts surface.
Skipping it there would give a mastery record blind to the mode he uses when
struggling.

**Untimed launches must not touch `launches`.** They go to `practice`, or the
number that means "I beat it" is farmable from the menu toggle.

**Floor `parts` at zero in the reducer, not the renderer.** Negative parts index
the part list from the end and draw a nose cone floating alone.

**Re-queue must not drop the retry.** Inserting at `RETRY_GAP` past the end of a
short queue relies on slice semantics appending; a fact missed near the end of
the deck must still come back.

**`mixer.pre_init()` runs before `pygame.init()`**, and buffers handed to
`Sound(buffer=...)` must match `mixer.get_init()` exactly — 16-bit signed mono.
A mismatch does not raise; it plays as static or at the wrong pitch. `audio._tone`
reads the rate back rather than hardcoding it.

**`pygame.display.get_num_video_drivers()` does not exist** in pygame-ce 2.5.8.
`WINDOWFOCUSLOST` / `WINDOWFOCUSGAINED` do — the clock pauses on focus loss.

## Making the two likely changes

**A new level.** Add a `Level` to `LEVELS` in `domain/facts.py` with its pair
list and `seconds_per_part`; `_pool` does the rest. `LEVEL_BUTTONS` in `app.py`
is generated from `LEVELS`, so the level-select screen picks it up — but check
it still fits: three buttons at `240 + index * 130` reach y=604 of 800. Update
`test_pool_sizes`.

**A second game mode.** It consumes the stream of `Outcome`s and renders progress
its own way; `domain/` needs no changes at all, which is the entire reason
`round.py` counts parts instead of naming them. The menu currently hardcodes one
mode button.

## Testing, and what testing cannot reach

The suite covers the domain, storage, and the coordinate transform — everything
with a rule in it. It does not open a window, and three things can only be
checked by a human at `uv run mathr`:

1. **Windowing under Hyprland** — that the window opens, resizes, and that clicks
   land on the right key at several window sizes including a tall narrow tile.
2. **Audible sound** — clip construction is proven in tests; output through
   PipeWire is not.
3. **Whether the pacing is right for him.** Unanswerable in code. `failures` per
   level in `progress.json` is what tells you.

Do not add a validation step to a change unless asked; give the user the command
and what to look for instead.

## Conventions

- The user creates commits, branches and anything on GitHub. Do not commit or
  push without asking.
- Comments answer *why*, never restate *what*. Most of this codebase's comments
  exist because the obvious alternative is wrong in a way that fails silently.
- Prefer the smaller solution. When a feature suggests a new abstraction, say so
  and make the case; do not future-proof one that is not needed yet.
- One runtime dependency, `pygame-ce` — never upstream `pygame`, which has no
  cp314 wheel and would try to build from source. Both import as `pygame`, so a
  stray one in the lockfile is invisible in the source.
