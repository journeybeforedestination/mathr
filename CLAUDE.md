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
- **`domain/round.py` knows `parts: int`, a bank of seconds, a span with a
  tolerance on it, and a `Rules` bundle — and nothing about rockets, aliens,
  tennis balls or footballs.** Part names, coordinates and art live in
  `shell/draw.py`. This is the seam that lets every mode reuse every level; the moment the reducer imports a part name, the next
  mode has to fake one or fork it.
- **A mode is not only a renderer.** `Rules` (`ROCKET`, `TENNIS`, `FOOTBALL`)
  says what the clock does, what a wrong answer costs, what an empty clock
  means, and whether the round stops every so often to ask for a placement.
  Tennis built as a pure renderer over `ROCKET` compiles, draws, and plays as a
  different game — the walk-through with real numbers is in `plan.md`, *The
  load-bearing decision*.
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
    facts.py      Fact, Question, Strategy, Level, the seven enumerated pools
    round.py      Round, Rules, Tally, Aim, Outcome,
                  new_round / apply / tick / dismiss / place
  storage.py      Progress, Settings, LevelRecord; load / save / merge
  shell/
    app.py        App: event loop, Mode, three screens, all the wiring
    draw.py       palette, rocket, alien, court, field, runner, cabinets,
                  buttons, number line, Layout, the transform
    audio.py      eleven synthesized clips, no asset files
tests/
  test_facts.py   pool contents, key stability, both orientations
  test_round.py   parts, re-queue, both win conditions
  test_clock.py   the time bank and the rally deadline
  test_place.py   the placement: when it is due, what it costs, what it stops
  test_storage.py round-trip, corruption, merge, backward compatibility
  test_scaling.py the design-surface transform, threat closeness, court and
                  field geometry, the cabinet at any height
  test_select.py  the deck weighting, and that an unweighted deck never moved
```

`Fact.strategy` is the route to the answer as numbers — a start and a list of
signed jumps — and `blank` is deliberately not an input, because the picture
shows the whole true equation. `shell/draw.draw_number_line` owns the span and
every degenerate shape those numbers really produce: a jump of zero (`0 + 5`),
an empty jump list (`2 × 0`), and the ten equal jumps of `10 × 10`.

`domain/facts.py` builds each addition level from one rule: each number-bond
pair yields four questions (`a+b=?`, `a+?=c`, `c−a=?`, `c−?=b`). A times pair
yields two (`a×b=?`, `a×?=c`) — the other two would be division, which is not
built. Pools are enumerated, not generated — 24 / 44 / 144 / 22 / 22 / 22, and
`everything` is their concatenation (278), pinned by `test_pool_sizes`.

A `Question` is a `Fact` plus `flipped`, which puts the `=` on either side. It
delegates `.answer` and `.key`, so orientation never reaches storage.

## Tuning

These are the dials, and they are meant to be turned after watching him play.

| Constant | Where | Now | Effect |
|---|---|---|---|
| `PARTS_TO_LAUNCH` | `domain/round.py` | 10 | length of a rocket round |
| `RETRY_GAP` | `domain/round.py` | 3 | how long before a missed fact returns |
| `GRACE_PARTS` | `domain/round.py` | 5 | rocket head start, in problems |
| `BANK_PARTS` | `domain/round.py` | 4 | ceiling on banked time, in problems |
| `BALL_FLIGHT` | `domain/round.py` | 1.5 | one ball's flight, in problems |
| `RETURN_FLIGHT` | `shell/app.py` | 0.34s | how long his return takes to land |
| `TENNIS.lives` | `domain/round.py` | 3 | balls past him before the match is lost |
| `TENNIS.target` | `domain/round.py` | 10 | returns needed to win |
| `WEIGHT_FLOOR` | `domain/round.py` | 0.5 | how far a fast fact sinks in the deck |
| `WEIGHT_CEILING` | `domain/round.py` | 4.0 | and how far one slow fact can rise |
| `PLACE_MAX` | `domain/round.py` | 100 | the span of the field, in yards |
| `PLACE_TOLERANCE` | `domain/round.py` | 6 | how far off still completes the pass |
| `PLACE_LIVES` | `domain/round.py` | 3 | wide throws before a turnover |
| `PLACE_GAIN_MIN` | `domain/round.py` | 10 | nearest a called yard can be |
| `PLACE_GAIN_MAX` | `domain/round.py` | 40 | and furthest |
| `CATCH_PARTS` | `domain/round.py` | 1.5 | how long the catch has, in problems |
| `THROW_HOLD` | `shell/app.py` | 1.3s | how long a finished play is held |
| `RUNNER_HEIGHT` | `shell/draw.py` | 46 | the ball carrier, in design pixels |
| `STRIPE_EVERY` | `shell/draw.py` | `None` | yard stripes, in yards; `None` is the bare line |
| `Level.seconds_per_part` | `domain/facts.py` | 3 / 3 / 5 / 5 | pace, per level |

`seconds_per_part` is the only per-level number; start and cap derive from it
*and from the mode's `Rules`*, so retuning a level is one edit and nothing needs
changing twice. `test_clock.py` asserts the derivation rather than the literals
under both rule sets, so changing a level's pace does not break the suite —
changing `GRACE_PARTS`, `BANK_PARTS` or `BALL_FLIGHT` intentionally will.

Tennis is harder than the rocket at the same level: no grace bank, no banking
ahead. Raise `BALL_FLIGHT` before touching `seconds_per_part`, which would
change the rocket too.

**The clock waits for the ball.** A correct answer resets the rally in the
domain immediately, but `Play.volley` holds the outgoing shot for
`RETURN_FLIGHT` and `App.update` skips `tick` while it flies — otherwise the
next ball is already falling before this one has been hit, and the rally reads
as a countdown rather than a rally. `App.ball` is the single source of truth for
where the ball is; seed a new volley from it, never from the clock, or a shot
struck mid-flight jumps.

## Invariants that break silently

**Layout is design space.** Everything is laid out in 1280×800 and scaled into
whatever the window actually is, because Hyprland tiles it to whatever the layout
gives. Mouse positions convert once, through `draw.to_design`, at the event
boundary — nothing downstream may see window coordinates. Symptom if this is
ever bypassed: clicks are accurate near the top-left and drift further out,
which reads as "sloppy hitboxes" and never as a scaling bug.

**A pending placement stops every clock, the way a hint does.** `Round.placing`
is *derived*, never stored. A stored one would have to be written on every path
that could clear it — both branches of `apply`, `place`, the lapse in `tick` —
and a single missed path is a throw that never appears or one that appears
twice, with nothing raising. `tick` returns early while it is set, so
`seconds_left`, `on_current` and `elapsed` stop together and aiming time never
reaches `Tally.seconds` — which is the deck weighting's input. `warn` needs the
same gate as it does for `hint`, for the identical reason.

**A placement is a claim, not a gain.** `place` puts a good one in
`Round.pending` and moves nothing; the next answer either confirms it (`apply` →
`SECURED`, and the marker jumps to where it was called) or fails to before
`pending_left` runs out (`tick` → `LAPSED`, and it comes to nothing). Two skills
per play, and neither can be traded for the other: a placement he could confirm
by guessing is not an estimate, and a fact with no placement under it is the
mode he already has two of.

**A placement is due whenever none is in the air.** `placing` reads nothing but
`rules.places`, `over`, `hint`, `pending` and the room left ahead of the marker —
not `asked`, and not how many have been taken. A wide one comes straight back as
another attempt from the same spot; a good one is followed by the answer that
confirms it and then by the next call. The only question the shell ever asks is
"is one due", and the only questions he answers are the ones under a placement —
except inside the last part, where there is nowhere ahead to aim and the rest is
run in.

**A lapse takes the question with it, and the shell clears the box.** `tick`
advances the queue on the frame a placement lapses and re-queues the fact at
`RETRY_GAP`, exactly as a ball past him does in tennis — otherwise the next
placement is confirmed by the fact he was halfway through typing, and the digits
he had already entered are still sitting in the box waiting to be submitted
against a question that has moved on. `App.update` clears `play.entry` on the
same frame for the second half of that.

**A lapse carries no hint**, unlike every other way of running out of time here.
The next thing it asks for is a click on the field, and a hint can only be put
away by typing; a click that dismissed one would also be a throw, aimed wherever
he happened to be reading. The verdict banner is the feedback instead.

**A wide placement costs an attempt, and `place_lives` of them end the round.**
`place` returns LOST on the third, not ADRIFT, and sets `failed` — the shell's
`throw` hands that straight to `lose`, which owns the failure screen and its
clip. Without the attempt counter the line can be clicked at idly until
something sticks, which is the one way to play this mode without estimating.

**A wrong answer under a pending placement plays by the rally's rules, not the
mode's.** No part lost, the queue untouched, the question still up — even though
`FOOTBALL` sets `wrong_costs_part` and `wrong_advances`. The hint it raises
stops every clock including `pending_left`, so he reads the number line with the
ball held exactly where it was, which is the same bargain tennis makes.

**A placement target is always ahead of the marker, and a good one moves the
marker to it.** In a placement mode the line and the parts bar are the same
axis: one part covers `PLACE_MAX // rules.target` of the line. `placing` adds a
drawn offset to `parts * spot`, so it can never call a yard behind the ball —
which played as a pass thrown backwards down the field, a mechanic that works
while the metaphor around it is a lie. Inside the last part there is nowhere
ahead to aim and `placing` is None: the goal line is a *labelled* end of the
line, so a placement that could reach it would be a free win every time.

**The hint wins over a due placement.** A wrong answer raises both at once; the `hint is not None` clause in `placing` settles it in
the domain, and `dismiss` then makes the throw live with no extra code. If the
shell arbitrated instead, that would be a rule in the shell.

**A keystroke must not resolve or dismiss a placement.** `press` returns early
while `placing` is set. Elsewhere a keystroke dismissing a hint is deliberate —
losing the first digit of an answer reads as a dropped key — but here the click
*is* the estimate, and a placement resolved by the keyboard records an aim he
never made.

**Placement targets are drawn in `new_round`, never in a reducer.** `tick`,
`apply` and `place` take no rng, and two tests pin shuffle determinism per seed.
A mode without placements draws none, so its consumption of the rng is exactly
what it was.

**`render_play` dispatches through a dict, not an `if`.** It used to be
`if rocket: … else: court`, so a mode added to `MODES` without a renderer drew
as tennis — it compiled, it drew, and nothing raised. The remaining
`self.mode == "rocket"` checks are rocket art (parts falling, the beam, the
countdown) and fail safe: a mode that is not the rocket simply does not take
them.

**A dimmed cabinet must not be clickable.** The `click` loop skips the `"soon"`
entry in `CABINETS`; without that it would set `self.mode` to a mode that does
not exist and `App.game` would raise a `KeyError` on the next frame.

**`draw_cabinet`'s offsets scale with `rect.height`.** They were absolute, and
below about 380 the control panel got a negative height, which pygame draws
inverted or not at all — which is what the 2x2 grid would have done. `cabinet_parts`
divides by `CABINET_HEIGHT`, and a test pins that h=440 is unchanged.

**`Fact.key` is a storage format.** It keys accumulated per-fact data in a file
that outlives the code. Changing its shape orphans every count already recorded
and needs a `version` bump plus a migration. `VERSION` is 2 for a different
format — the `levels` key, now `<mode>/<level>` — which `Fact.key` is unaffected
by. Adding *fields beside it* is fine —
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
struggling. The one exception is `Round.hint` — see below.

**A hint stops every clock, and that is why it is in the domain.** `tick`
returns early while `Round.hint` is set, so `seconds_left`, `on_current` and
`elapsed` stop *together*, by construction. The obvious alternative — a field on
`Play` and a skip in `App.update`, the way a volley already works — stops
`seconds_left` and leaves `on_current` running. Hint-reading time then lands in
`Tally.seconds`, which is the input to the deck weighting, which pushes the fact
he was just shown to the front of the next deck, which shows the hint again. The
symptom is "he keeps getting the same questions", which names nothing. The shell
only ever calls `dismiss`.

**No hint on the `LOST` path.** The failure screen owns the display, and
`App.update` drives its animation from the clock a hint would stop. Symptom: the
abduction beam freezes half-drawn and *Try again* never appears.

**`warn` must be skipped while a hint shows.** It sets its own interval from
`seconds_left / threshold`, and under a stopped clock that ratio is constant —
the pulse that exists to *quicken* becomes a metronome while he reads. Nothing
raises.

**`shuffled` with no weights must consume the rng exactly as it always did.**
Two tests pin shuffle determinism per seed, and the flat path interleaves the
orientation flip with `rng.sample`, so restructuring it changes which questions
are flipped as well as their order. The weighted path is a separate branch on
purpose; do not merge them.

**Deck weights are computed in `round.py`, never in `facts.py`.** `round`
imports `facts`; reaching back for `Tally` closes an import cycle that Python
reports as a partially-initialised module from whichever side imported first — a
message naming neither the cycle nor the mistake.

**Untimed launches must not touch `launches`.** They go to `practice`, or the
number that means "I beat it" is farmable from the menu toggle. Tennis is always
timed for the same reason it has no untimed form, and `new_round` raises rather
than building a round with lives and no clock.

**`Sounds.play` fails silently on an unknown name.** It is
`self._clips.get(name)` — a missing clip plays nothing and raises nothing. That
is why `Mode.clips` maps outcomes to clip names explicitly instead of using
`outcome.value`: keyed by the enum, renaming an outcome turns a sound off with
no error anywhere.

**Dimmed buttons must not hover.** `draw_card` takes `dimmed` and ignores
`hovered` when set, and the click handlers never see `SOON_BUTTONS`. A
coming-soon row that lights up under the cursor and does nothing reads as
broken, not as unfinished.

**A wrong answer in tennis must not touch the queue.** Not advance it, not
re-queue the fact — the question is still on screen, so re-queuing would put it
in the deck twice. The re-queue lives on the timeout path in `tick` instead.

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

**A new level.** Add a `Level` to `_ADDITION` or `_MULTIPLY` in
`domain/facts.py` with its pair list and `seconds_per_part`; `_pool` does the
rest, and `everything` picks it up because it is derived. Then place it: the
level screen is four fixed columns of three (`COLUMN_X`, `ROW_Y`, `CARD` in
`app.py`), so a fourth row needs a layout decision, not just an id in a tuple.
Update `test_pool_sizes` — the `everything` total moves too.

**A fourth game mode.** Add a `Rules` to `domain/round.py` and a `Mode` to
`MODES` in `app.py` (title, clip map, a `draw.Layout`, noun and what a part is
worth in it, hold times, `rally` / `warns`), a renderer in the `render_play` dispatch, its clips
in `audio.py`, and take the `"soon"` cabinet's rect in `CABINETS` — the grid is
full at four, so a fifth is a layout decision, not an entry in a tuple. Ask
first whether its clock is a bank or a deadline, and whether it interrupts
itself: if none of `ROCKET`, `TENNIS` or `FOOTBALL` fits, `Rules` gains a dial
rather than the shell gaining a rule.

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
