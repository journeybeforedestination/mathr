# mathr

A desktop math-fact game for one specific second grader. `README.md` describes
how it plays; this file is what you need to change it safely.

- `ideas.md` — what is deliberately out of scope and why, what was built and how
  the original claim about it turned out, and the approaches this program is not
  built on. Read the relevant entry **before** arguing with a design choice; most
  of them were argued once already and the alternatives are recorded there.

There was a `plan.md`. It was the pre-build plan with a section appended per
feature, and it was deleted once its feature sections had been superseded by the
invariants below — which are the maintained copy of the same reasoning, and were
consistently more accurate. Plan a feature in its own scratch file, fold what
survives into this file and `ideas.md`, and let the plan go with the branch.

## Commands

```sh
uv run mathr          # play
uv run mathr --test   # same game, against test-progress.json beside his
uv run pytest         # the whole suite, ~0.5s
uv add <pkg>          # tell the user before adding any dependency
```

`pytest` is not installed system-wide; it comes in through `uv` as a dev
dependency. **`ruff` is not installed at all** — not system-wide and not in the
dev group, so `uv run ruff` fails with `Failed to spawn`. There is no formatter
or linter in this project; match the surrounding style by hand, and note that
lines run past 100 characters throughout `draw.py` already.

## Layering

One direction only: `shell/` → `storage.py` → `domain/`. Never the reverse.

- **`domain/` is pure.** No pygame, no I/O, no module-level `random` —
  randomness arrives as an injected `random.Random` so tests are deterministic.
- **`domain/round.py` knows `parts: int`, a bank of seconds, a span with a
  tolerance on it, and a `Rules` bundle — and nothing about rockets, aliens,
  tennis balls or footballs.** Part names, coordinates and art live in
  `shell/draw.py`. This is the seam that lets every mode reuse every level; the moment the reducer imports a part name, the next
  mode has to fake one or fork it.
- **A mode can differ in its *items* rather than its rules.** Three cabinets are
  three readings of `Rules`; Code Breaker is not. It could run on `ROCKET`'s
  rules unchanged and still be a different game, because a `Sentence` is not a
  `Fact`.
  That is why `Round.queue` holds `Item = Question | Sentence | Target` —
  everything downstream of it touches only `.key`, `.prompt` and the route, so
  one queue serves all three. `Target` is the one with no `.answer`, which is
  why `apply` is not the reducer that resolves it. A *parallel* deck beside the queue is the trap: `tick`
  charges `on_current` to `queue[0]`, so the time he spends on a sentence lands
  in `Tally.seconds` for a fact he was never asked, and the symptom is bad deck
  ordering **in a different cabinet**.
- **A mode is not only a renderer.** `Rules` (`ROCKET`, `TENNIS`, `FOOTBALL`,
  `CODE`, `CURLING`)
  says what the clock does, what a wrong answer costs, what an empty clock
  means, and whether the round stops every so often to ask for a placement.
  Tennis built as a pure renderer over `ROCKET` compiles, draws, and plays as a
  different game — the walk-through with real numbers is in `ideas.md`,
  *A second game mode*.
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
    facts.py      Fact, Question, Strategy, Level, the eight enumerated pools,
                  Side / Sentence / sentences: the code panel's derived deck,
                  SPAN / Target / targets and the six fraction pools
    round.py      Round, Rules, Tally, Aim, Outcome,
                  new_round / apply / tick / dismiss / place
  storage.py      Progress, Settings, LevelRecord; load / save / merge,
                  default_path(testing) — his file, or the one beside it
                  four sections: levels, facts, placements, targets
  shell/
    app.py        App: event loop, Mode, LevelScreen, three screens, the wiring
    draw.py       palette, rocket, alien, court, field, runner, cabinets,
                  the safe and its hoard, the sheet of ice, its house, its
                  sweeper and how stones stack,
                  buttons, number line, Layout, the transform
    audio.py      seventeen synthesized clips, no asset files
tests/
  test_facts.py   pool contents, key stability, both orientations, and where
                  the addition split falls
  test_round.py   parts, re-queue, both win conditions
  test_clock.py   the time bank and the rally deadline
  test_place.py   the placement: when it is due, what it costs, what it stops
  test_storage.py round-trip, corruption, merge, backward compatibility
  test_scaling.py the design-surface transform, threat closeness, court and
                  field geometry, the cabinet at any height
  test_select.py  the deck weighting, and that an unweighted deck never moved
  test_sentences.py  what a line is, and that every pool can build a deck
  test_crack.py   locks, the panel, and alarms a wrong answer trips
  test_curl.py    the stone: one reducer, the tolerance, and what ends an end
```

`Fact.strategy` is the route to the answer as numbers — a start and a list of
signed jumps — and `blank` is deliberately not an input, because the picture
shows the whole true equation. `shell/draw.draw_number_line` owns the span and
every degenerate shape those numbers really produce: a jump of zero (`0 + 5`),
an empty jump list (`2 × 0`), and the ten equal jumps of `10 × 10`.

**The two addition levels split on the two numbers *as written*, never on the
answer.** `7 + 7 = 14` is two small numbers and belongs to `small`; `14 − 7 = 7`
is a big number meeting a small one and belongs to `big`. So one number bond
sends its addition forms to one level and its subtraction forms to the other the
moment its total passes ten — which is exactly why `_add_pair` and `_sub_pair`
are two functions and not one `_from_pair` yielding four. Merge them back and
`big` silently acquires `4 + 9` or `small` acquires `13 − 4`, and the only
symptom is a card asking questions the card below it is for. `big` holds
*exactly one* number past ten (`(a > 10) != (b > 10)`, not `or`): two of them is
regrouping, which is a different skill and is in `ideas.md`.

A times pair yields two questions (`a×b=?`, `a×?=c`); the other two are
division, and they live in their own column via `_divide_pair`, which `_divided`
draws from `range(1, 11)` rather than `range(11)` — `0 ÷ ? = 0` is true of every
divisor, so the zero pair would sit in the deck being marked wrong forever.
`_SMALL` leaves out `(0, 0)` for the same reason in the same spirit: `0 + 0 = ?`
is a free mark that measures nothing and inflates the record. Zero *addends*
stay. Pools are enumerated, not generated — 372 / 440 / 22 / 22 / 22 / 20 / 20 /
20, and `everything` is their concatenation (938), pinned by `test_pool_sizes`.

The fraction pools are enumerated the same way — 4 / 7 / 13 / 18 / 14, and
`fractions` is their concatenation (56) — and they live in `FRACTION_LEVELS`,
not in `LEVELS`. `LEVELS_BY_ID` holds both: the shell looks a level up by the id
on a card and never asks which family it came from, while a test that walks
every fact pool does not walk a pool with no facts in it. A `Level` has facts or
targets, never both.

**Division's answer is the hop count, not where the line ends.** Every other
operation's route lands on its own answer, so the highlighted last dot *is* the
answer; `12 ÷ 2` draws six hops of two and lands on 12, which is the number he
was already given. `test_every_strategy_lands_on_the_answer` asserts this per
operation rather than universally, and `draw_number_line`'s `caption` — composed
by `app.hint_caption`, the shell's only look at `Fact.op` — says the count out
loud. Forcing the invariant instead yields `Strategy(0, (4,))` for `12 ÷ 3`: one
hop to the answer, a green test, and a hint that mentions neither 12 nor 3.

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
| `LOCKS` | `domain/round.py` | 4, 5, 6 | lines per lock, and how many locks |
| `ALARMS` | `domain/round.py` | 3 | wrong answers before the vault locks down |
| `SENTENCE_DECK` | `domain/facts.py` | 40 | lines drawn per code round |
| `_SHAPES` | `domain/facts.py` | 5/3/3/1 | both-sides, commuted, split, bare |
| `UNLOCK_HOLD` | `shell/app.py` | 1.1s | how long a swung vault is held |
| `SWING_DELAY` | `shell/app.py` | 0.5s | bolts back on a full combination before the door moves |
| `SWING_TIME` | `shell/app.py` | 1.5s | and how long the leaf takes to swing off the hoard |
| `PLACE_MAX` | `domain/round.py` | 100 | the span of the field, in yards |
| `PLACE_TOLERANCE` | `domain/round.py` | 6 | how far off still completes the pass |
| `PLACE_LIVES` | `domain/round.py` | 3 | placements missed before a turnover |
| `PLACE_GAIN_MIN` | `domain/round.py` | 10 | nearest a called yard can be |
| `PLACE_GAIN_MAX` | `domain/round.py` | 40 | and furthest |
| `CATCH_PARTS` | `domain/round.py` | 1.5 | how long the catch has, in problems |
| `SACK_CHANCE` | `domain/round.py` | 0.25 | how often a play loses ground instead |
| `SACK_MIN` / `SACK_MAX` | `domain/round.py` | 4 / 12 | and how much it costs |
| `SACK_BY` | `domain/round.py` | 50 | past here, one is overdue if none has hit |
| `PLACE_PENALTY` | `domain/round.py` | 10 | ground a wide throw gives up |
| `THROW_HOLD` | `shell/app.py` | 1.3s | how long a finished play is held |
| `RUNNER_HEIGHT` | `shell/draw.py` | 46 | the ball carrier, in design pixels |
| `STRIPE_EVERY` | `shell/draw.py` | `None` | yard stripes, in yards; `None` is the bare line |
| `SPAN` | `domain/facts.py` | 240 | the ice, in units; **see the trap below** |
| `STONES` | `domain/round.py` | 8 | stones in an end |
| `STONE_LIVES` | `domain/round.py` | 3 | wide ones before the end is lost |
| `SHEET` / `SHEET_EDGE` | `shell/draw.py` | rect / 80 | the ice, and the room outside the line for its labels |
| `STONE_RADIUS` / `STONE_ROW` | `shell/draw.py` | 17 / 36 | a stone, and how far above the line the next one on its mark stands |
| `SWEEPER_HEIGHT` | `shell/draw.py` | 76 | the figure at the hack, in design pixels |
| `TEEN_MAX` | `domain/facts.py` | 20 | ceiling on a big number in `big` |
| `Level.seconds_per_part` | `domain/facts.py` | 4 / 5 / 5 | pace, per level |

`seconds_per_part` is the only per-level number; start and cap derive from it
*and from the mode's `Rules`*, so retuning a level is one edit and nothing needs
changing twice. `test_clock.py` asserts the derivation rather than the literals
under both rule sets, so changing a level's pace does not break the suite —
changing `GRACE_PARTS`, `BANK_PARTS` or `BALL_FLIGHT` intentionally will.

Curling has no dial for how forgiving a shot is, and that is deliberate:
`Target.tolerance` is half a tick gap, derived from the partition. Halves are
generous and twelfths are tight without a constant per level, and the rings
drawn at it are the only thing on screen that says the shot got harder. If it
turns out to be the wrong bar for him, the honest fix is the *denominators a
level asks*, not a fudge factor over all of them.

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

**Bridging needs a ten to bridge to.** `Fact.strategy`'s addition branch fired
on `result > 10` alone, which quietly assumed both operands were under ten. They
are not since `big` arrived: `12 + 3` drew `Strategy(12, (-2, 5))` — a hop
*back* to ten and five forward. It lands on 15, so nothing raises and
`draw_number_line` scales to it and draws a perfectly tidy picture; it just
tells him to go backwards for a problem that crosses nothing. The guard is
`max(a, b) > 10` **first**, counting on from the bigger number, which is what
subtraction below it already does and which for `3 + 12` is the commuting said
out loud rather than a bridge from 3.

**Test mode is a flag, not an environment variable.** `--test` picks
`default_path(testing=True)`, a sibling `test-progress.json`. An exported
variable outlives the session, and a real round written to the test file is
invisible: the game looks identical, and what you conclude is that his progress
was lost. It writes a real file rather than none, because `save` is the one
place a bug stops the record being written with nothing on screen to say so — so
a test session must exercise it, just not against his. `App.testing` says so on
the menu and nowhere else, because during play the two are indistinguishable.

**Layout is design space.** Everything is laid out in 1280×800 and scaled into
whatever the window actually is, because Hyprland tiles it to whatever the layout
gives. Mouse positions convert once, through `draw.to_design`, at the event
boundary — nothing downstream may see window coordinates. Symptom if this is
ever bypassed: clicks are accurate near the top-left and drift further out,
which reads as "sloppy hitboxes" and never as a scaling bug.

The concrete failure, because it is worth being able to recognise: lay the
keypad out at absolute coordinates with the "7" key at `(980, 520)`; Hyprland
tiles the window to 960×1040 instead; the keypad's bottom row is off-screen
entirely; he clicks where "7" *appears* to be, `pygame.mouse.get_pos()` returns
window coordinates, the hit-test compares them against 1280×800 rectangles, and
he hits "4" — or nothing. It presents as "the buttons are wrong", which names
nothing, and it cannot be fixed by nudging coordinates because the offset
changes with every window size. This is why the transform landed before any
rocket art: retrofitting it means touching every draw call and every click
site.

**The target is an *item*, not a position on the line.** `Rules.targets_from_deck`
picks between the two, and getting it wrong is arithmetic rather than taste.
Football's `placing` derives its call from the marker — `parts + gains[...]` —
so on a fraction level it would ask for `23/100` on a line ticked in sixths, and
the number called would be a function of the stones already thrown rather than
of the level. `parts` therefore means *stones in the house* in curling, and the
`new_round` guard that pins `target == PLACE_MAX` fires only where the marker
names the target. It must keep firing for football; a test pins that it does.

**`place` is curling's `apply`, and it must do everything `apply` does.**
Advance the queue, write the `Tally` against `Target.key`, credit the part, zero
`on_current`. `apply` is never called in this mode — there is nothing to type —
so anything it normally does and this branch does not simply never happens.
Miss the zeroing and `on_current` accumulates across the whole end, so the last
stone is recorded as having taken ninety seconds; nothing raises, and the lie is
in the record a parent view would read. A fourth reducer beside `apply`, `tick`
and `place` was the alternative: three copies of the tally write, the advance
and the win check, drifting the first time `Tally` changes.

**A wide stone is not re-queued.** `_advance` takes no `retry` here. A missed
*fact* has to come back — retrieval, not echo — but the ghost has just shown him
the true mark, so re-asking the same fraction three stones later is asking him
to reproduce a picture he is still looking at. Symptom otherwise: the end fills
with the one fraction he missed first, and it reads as a broken shuffle.

**`tick` does *not* stop for a placement whose target came from the deck.**
Everywhere else a due placement stops every clock, so aiming time never reaches
`Tally.seconds` and cannot corrupt the deck weighting. In curling one is always
due, so the same early return would stop the round's only clock forever and
record every stone as instant — and nothing weights that deck, so there is
nothing to protect. This is the one exception, and it is why `place` zeroing
`on_current` is load-bearing rather than tidy.

**Target rows must not go into `placements`.** `save` sorts that section with
`key=lambda item: int(item[0])` — it is keyed by decade of the line. A key of
`"2/3|6"` raises `ValueError` *inside `save`*, so `os.replace` never runs and
**the whole file silently stops being written**. `merge` routes by
`rules.targets_from_deck`, never by sniffing the shape of the key.

**`Target` has no `.answer`, deliberately.** `apply` compares
`given == question.answer`. Give `Target` one for symmetry and a stray keypad
path in some future mode compares a typed integer against a span value and marks
`160` correct for `2/3`. Leave the attribute absent so that path raises.

**The house is drawn only once the stone has come to rest.** The rings are
centred on the mark that was called and are exactly as wide as the tolerance, so
a house on the ice while he is still aiming is the answer, printed — and the one
thing he must not be able to read off the ice before he throws. `draw_sheet`
gates them on `ghost`.

**Stones on one mark stack, they do not overlap.** `1/2` and `2/4` are the same
place, and two stones drawn on top of each other are one stone — which reads as
a stone having gone missing rather than as two agreeing. `stone_rows` packs them
upward from the line, capped at what fits under the top of the ice. Sideways is
what a real stone would do and what this one must not: sideways is the answer.
The ghost's gap line is drawn to the row the last stone actually stands in, or
it points at bare ice below a stone that has been lifted out of the way.

**The sheet keeps the *called* target's partition while a miss is being read.**
`place` has already advanced the queue, so `round.current` is the next fraction
and its ticks are a different partition. `Play.ghost` holds the `Target` and not
just the two numbers, or the picture explaining the miss is drawn in the
denominator of a question he has not been asked yet.

**The Timer toggle is dead here**, as it is in Code Breaker: `start` forces
`timed=False`. `CURLING.lives` is `None` and its `locks` are empty, so without
that branch it falls through to the setting, and a round would drain a bank
nothing can spend until `tick` ended a game nobody was racing.

**A click on the ice must not dismiss the held miss**, and a keystroke must not
throw a stone. Both are the rules the field already has, for the same reasons:
`press` returns early while `placing` is set, and `NEXT_UP` is the only way out
of the ghost.

**`0/b` and `b/b` are not questions.** Both are the labelled ends of the line —
free marks that measure nothing and inflate the record, the same failure
`_divided` avoids by drawing from `range(1, 11)`.

**A denominator added later must be re-checked against `SPAN`.** Every one in
scope must divide 240 *and* leave an even quotient, or half a tick gap is not a
whole number and `place`, `Aim` and the click conversion all learn floats for
one denominator. 120 fails: `120 // 8` is 15. Sevenths and ninths fit no span
that keeps the existing set whole. `test_the_span_keeps_every_tolerance_whole`
runs the enumeration.

**A mode's level cards are a field on `Mode`, with no default.** `LevelScreen`
has no fallback for the same reason `render_play` dispatches through a dict: a
fifth cabinet behind the arithmetic cards is a wrong game one click deep, and it
would compile and draw. `fail_action` reads `self.game.levels.first`, or *Try
again* on a curling failure starts a rocket level.

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

**A miss is read, not glimpsed.** A wide placement sets `Play.review` and holds
`render_miss` — the two numbers, the window it had to land in, and a *Next pass*
button — until he dismisses it, where CAUGHT and DROPPED get `THROW_HOLD` and a
banner. The shell may pace this without breaking the "no rules in the shell"
line because the domain has already stopped every clock: a placement is due, so
`tick` returns early. The button is what makes it safe — a click on the *field*
must never double as a dismissal, or reading the panel throws the next pass at
whatever yard he happened to be looking at. `press` clears it too, so the
keyboard is not dead in front of a screen the mouse can leave.

**A lapse carries no hint**, unlike every other way of running out of time here.
The next thing it asks for is a click on the field, and a hint can only be put
away by typing; a click that dismissed one would also be a throw, aimed wherever
he happened to be reading. The verdict banner is the feedback instead.

**A placement missed by more than the tolerance costs an attempt — a thrown one
and a sack alike — and `place_lives` of them end the round.** `place` returns
LOST on the third, not ADRIFT, and sets `failed`; the shell's `throw` hands that
straight to `lose`, which owns the failure screen and its clip. Without the
attempt counter the line can be clicked at idly until something sticks, which is
the one way to play this mode without estimating.

**A wrong answer under a pending placement plays by the rally's rules, not the
mode's.** No part lost, the queue untouched, the question still up — even though
`FOOTBALL` sets `wrong_costs_part` and `wrong_advances`. The hint it raises
stops every clock including `pending_left`, so he reads the number line with the
ball held exactly where it was, which is the same bargain tennis makes.

**The marker is the line.** `rules.target == PLACE_MAX` in a placement mode, so
`parts` is a position on the line and a catch on the 27 spots the ball on the
27. Anything coarser — parts as tens of yards, which is how this first shipped —
rounds every catch down to the nearest part, and the number he estimated stops
being the number he gets, which is the whole mode. `new_round` raises rather
than letting a placement mode disagree, and `draw_progress` shows a tenth per
pip rather than a hundred pips.

**A placement target is ahead of the marker, except a sack, which is behind it
and is the one he is not told.** An ordinary call is a drawn offset added to
`parts`, so it can never name a yard behind the ball — that played as a pass
thrown backwards down the field, a mechanic that works while the metaphor around
it is a lie. Close to the end the call is `PLACE_MAX` itself: the goal line is a
*labelled* end, so it is the one easy placement in a round, and it is the one
that wins it.

**A drive that never goes backwards is the one with least in it.** Three long
catches walk the length of the line, and every estimate in the second half of
that drive lives in the top quarter of it. Two rules stop it: past `SACK_BY` a
sack is due whatever the draw said if none has happened yet (`sacks_taken == 0`,
which is why that count is a field and not derived from `placed`), and a wide
throw gives up `PLACE_PENALTY` of ground on top of the attempt. A missed *sack*
spot is not penalised again — the play has already taken its ground, and
charging twice for one mistake is what makes a mode feel arbitrary.

**A sack lands where it lands, whatever he clicks.** `_take_the_loss` spots the
ball at `parts - loss` on both paths. Spotting it at his click would make a sack
the cheapest way up the field — a few yards forward of the truth, every time,
inside the tolerance. What his click buys is only whether it cost an attempt.

**A sack records nothing in `aims`.** That record is how far off he is when he
is *shown* a number; an error on a sack is as much the subtraction as the line,
and folding the two together would read later as estimation drift that never
happened.

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

**`rules.lives` alone is three lives nothing can spend.** `points` is
incremented in `tick` when the bank empties and nowhere else, so lives mean
"empty-clock events survived" unless `wrong_costs_life` says otherwise. That is
why `new_round` raises for an untimed round with lives and no such dial — an
untimed tennis match can be neither won nor lost, and nothing else would say so.
It is read in `apply`, not `tick`: the alarm is tripped by a wrong *answer*.

**A wrong answer that trips an alarm must be handled in `submit`.** `apply` can
now end a round — it is the only reducer a `wrong_costs_life` mode goes through
— and every other mode's loss arrives from `tick` or from `throw`. Without the
`Outcome.LOST` branch in `submit` the domain is over while the shell sits there
with a dead keypad and no failure screen, and nothing raises.

**A swung lock must be held with its own lines and its own digits.** `apply`
clears `cracked` and `Round.lock` derives the *next* lock on the same frame, so
the one moving reward in this mode was the panel resetting and the combination
emptying — the code being erased. `Play.opened` holds the lock the shell has
just finished for as long as it is shown, and `App.opening` returns `None`
rather than `0.0` when nothing is swinging: a swing *starts* at zero, and a
renderer gating on the number alone spends that first frame drawing the next
lock, empty.

**`UNLOCK_HOLD` means nothing unless `submit` sets it.** `submit` sets
`flash_left = FLASH_TIME` for every outcome, and the bolt animation divides by
`UNLOCK_HOLD`. Without the `CRACKED` branch the bolts start 59% drawn back and
finish in 0.45s, and the constant in the table above describes nothing that
happens.

**The rail, the combination and the dial are *on* the door.** `draw_treasure`
repaints `CODE_DOOR`'s face before it draws the chamber, because `render_code`
has already drawn all three on this frame and a door that has swung away cannot
still be showing them. Symptom otherwise: "LOCK 3 OF 3" and the alarm lamps
floating over the open safe.

**A line below the one he is on must stay encrypted.** `draw_panel` draws a row
of blocks for anything past `active`. Drawing the real sentences is the
yard-stripe trap again: he reads ahead, works the easy ones first in his head,
and the lock stops being a sequence.

**`cracked` is cleared as each vault swings.** It holds only the lines of the
lock he is on, because the panel draws all of them and three locks' worth would
run off the bottom of the screen. `Round.lock` is derived from `parts` alone for
the reason `placing` is derived — a stored lock index has to be written on every
path that moves `parts`, and one missed path is a vault that opens twice.

**`Rules.locks` must add up to `Rules.target`.** `new_round` raises otherwise:
a mismatch means the last vault never swings, or the round is won partway
through a lock with lines still showing on the panel.

**A dimmed cabinet must not be clickable.** The `click` loop skips the `"soon"`
entry in `CABINETS`; without that it would set `self.mode` to a mode that does
not exist and `App.game` would raise a `KeyError` on the next frame. The grid is
three across by two down now — five cabinets and one dark — and the height
stayed 220 on purpose, so `cabinet_parts` and the test pinning `h = 440` are
untouched.

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

**A round that cannot be lost must not touch `launches`.** `storage._fold` asks
`Round.losable`, not `Round.timed`: what makes a win farmable is having no way
to lose, not having no clock. The rocket with the Timer toggle off has neither,
so it still folds to `practice`; Code Breaker has no clock and three alarms a
wrong answer trips, so its win is a launch. Curling has no clock either, and three wide
stones; `losable` asks a third thing, `place_lives is not None`, which also
makes an untimed *football* drive losable — correctly, since three wide throws
end it. Asking `timed` was right until a mode arrived that could be lost without
one. Tennis is always
timed for the same reason it has no untimed form, and `new_round` raises rather
than building a round with lives and no clock.

**`Sounds.play` fails silently on an unknown name.** It is
`self._clips.get(name)` — a missing clip plays nothing and raises nothing. That
is why `Mode.clips` maps outcomes to clip names explicitly instead of using
`outcome.value`: keyed by the enum, renaming an outcome turns a sound off with
no error anywhere.

**Dimmed buttons must not hover.** `draw_card` takes `dimmed` and ignores
`hovered` when set, and the click handlers never see `LevelScreen.soon`. A
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

**A new fraction level.** Add a `Level` to `_FRACTION` in `domain/facts.py` with
its (denominator, partition) pairs; `_targets` does the rest, and `FRACTIONS`
picks it up because it is derived. Check the denominators against `SPAN` first —
see the trap. Then place it: `FRACTIONS` in `app.py` is three columns and a tall
card, and a fifth column is a layout decision. Update `test_fraction_pool_sizes`.

**A new level.** Add a `Level` to `_ADDITION` or `_MULTIPLY` in
`domain/facts.py` with its pair list and `seconds_per_part`; `_pool` does the
rest — pass `_sub_pair` for a pool of subtractions, since the default builds
additions only — and `everything` picks it up because it is derived. Then place
it: the level screen is four fixed columns of three (`COLUMN_X`, `ROW_Y`, `CARD`
in `app.py`), so a fourth row needs a layout decision, not just an id in a
tuple. The addition column has one free slot; the other two are full. Update
`test_pool_sizes` — the `everything` total moves too.

**A sixth game mode. The maths has to *be* the reward.** Replay Booth was built
to spec, passed 200 tests, and was not a game — the one failure here that cost a
rewrite, and one that cannot be re-derived from the working code because the
working code is the fix. Compare the cabinets by what *moves* when he is right:
the rocket bolts on a part, tennis returns a ball, football walks a marker up a
field he can see, and the booth showed `0 / 10 calls`. Worse, the feedback ran
backwards — a *wrong* call raised the two-route number line, the richest picture
in the game, while a *right* call played a whistle and advanced. The punishment
was more interesting than the reward, which for a seven-year-old is the whole
problem. Removing its clock had been correct (the mode measures reasoning faster
than his arithmetic, and a clock suppresses what it measures) but the clock was
the only thing carrying tension, and nothing replaced it. The fix was not art on
top: it was making the answers **accumulate into something** — a combination,
kept in a cell he can see beside the cells still empty. So before the dials
below, ask what grows on screen when he is right, and whether it is more
interesting than what happens when he is wrong.

The 3x2 grid has exactly one slot left, the `"soon"` one
— a *seventh* cabinet is a layout decision before it is anything else.
Otherwise: add a `Rules` to `domain/round.py` and a `Mode` to `MODES` in
`app.py` (title, clip map, a `draw.Layout`, a `LevelScreen`, noun and what a
part is worth in it, hold times, `rally` / `warns`), a renderer in the
`render_play` dispatch, its clips in `audio.py`, and take the `"soon"` rect in
`CABINETS`. Ask first whether its clock is a bank or a deadline, whether it
interrupts itself, and where its questions come from: if none of `ROCKET`,
`TENNIS`, `FOOTBALL`, `CODE` or `CURLING` fits, `Rules` gains a dial rather than
the shell gaining a rule.

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
