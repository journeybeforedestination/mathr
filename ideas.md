# ideas

Deliberately out of scope. Kept so the reasons are not re-derived — including
for the one entry that has since been built, because *what remains* of it is
easier to see next to what it started as.

## Parent view of weak facts
The data is already being written (`facts` in `progress.json`: per-fact
right/wrong counts, answer counts and total seconds; `failures` and
`best_seconds` per level). No UI reads it. A screen ranking his weakest facts
would be genuinely useful — deferred only because it is a second UI to design
and a menu entry a kid will poke at.

## A "tricky facts" practice mode
**Reserved** — a dimmed button in the Everything column of the level screen, so
the spot is visible and the rule is not invented yet.

Draw the question pool from the lowest-scoring facts in `progress.json` instead of
a level. The stored per-fact counts exist precisely so this is possible later —
and each one now carries `answered` and `seconds` too, so "tricky" can mean slow
rather than only wrong. The slow-but-correct fact is the one worth drilling and
the one a right/wrong count cannot see.

## More levels
- Two-digit addition/subtraction without regrouping (34+25, 68−43).
- Two-digit **with** regrouping (37+28, 62−45) — the genuinely hard one. Typed
  answers plus mental carrying may need scratch paper; watch him before building.
- Multiplication via skip counting by fives and tens. **Built** — `twos`,
  `fives_times` and `tens_times`, plus an `everything` pool derived from every
  other level's facts.
- **Division.** Reserved as a dimmed column on the level screen. The
  multiplication pools deliberately stop at `a × b = ?` and `a × ? = c`; the
  missing two forms *are* division, so this is a content decision (how far the
  tables go, whether remainders exist) and not a code one.

## A second game mode
**Built** — Tennis Match. Worth keeping the original entry's claim next to what
actually happened, because the claim was wrong in the interesting way.

It said any mode that consumes a stream of correct/wrong outcomes reuses the
levels unchanged, so a mode is only a renderer. Tennis is not: its clock is a
per-rally deadline rather than a shared bank, a wrong answer costs it nothing,
and a missed ball is a point rather than the end. Built as a pure renderer over
the rocket's rules it would still compile, still draw, and play as a different
game — see *The load-bearing decision* in `plan.md`. What the seam actually
bought was `parts: int`: the reducer took a `Rules` bundle and gained a
`points` counter, and neither pools, storage, nor the coordinate transform moved
at all.

The remaining candidates — a growing city, a rescue climb, a race — each want
their own read of that bundle. A mode with no threat can still simply run
untimed.

## Adaptive difficulty
**Built** — see *Learning feedback* in `plan.md`. The data answered the question
it was rejected on: not the misses (four in 105 answers, half of them typos) but
the times. The deck is ordered by mean seconds per fact against the level's pace,
clamped between `WEIGHT_FLOOR` and `WEIGHT_CEILING`, with an unseen fact at 1.0.
The whole pool stays in the deck; only its order is biased.

What remains is everything that needs more than one session's history:

- **Spacing across days.** A `last_seen` date, so a fact he has not met in a week
  comes back. It needs a date injected into the domain, and it is the weakest of
  the ideas on the evidence (*g* ≈ 0.28) — and with most facts seen exactly once
  there is nothing to space on yet.
- **Mastery as a probability** rather than a mean, which is what knowledge
  tracing buys. Four parameters to fit against a hundred observations is fitting
  noise. Revisit at thousands.
- **Retiring a mastered fact** from the pool outright. Sharper practice, but a
  fully mastered level then has an empty deck, and the level screen needs a
  "done" state to explain it — a UI decision, not a policy change.

## Timed / speed modes
**Built** — see *Time pressure* in `plan.md`. A shared bank of seconds per round,
an alien that grows as it drains, and an off switch in the menu.

What remains is the softer end. Per-fact response times are now recorded, so a
personal best *per fact*, or a "beat your own time" mode racing `best_seconds`,
needs no new data — only a UI. Both were left out because the first question is
whether the pressure that exists is already too much, and a second scoreboard
would confound the answer.

## Choosing timed or untimed per level
Raised while designing the clock and set aside: a timed/untimed choice on each
level button, so he could drill `bridge` untimed while racing on `fives`. It
doubles the level-select UI and adds a decision before every single round, and
the menu toggle already covers the case that matters (the clock is too much
today). Revisit if he starts using the menu toggle *between* levels rather than
between sessions — that is the signal that the setting belongs to the level and
not to the session.

## A number-line placement mode
**Built** — Touchdown Drive, as a deep pass rather than a mode of its own. The
original entry's guess is worth keeping beside what it cost: it said the
non-boolean outcome was "a `Rules` dial at best and a second reducer at worst".
It landed between the two — three `Rules` dials (`places`,
`confirm_parts`, `place_lives`), a second *reducer function* beside `apply`, a
branch inside `apply` for the answer that confirms a placement, and no second
`Round`. What it did not
predict is where the cost actually fell: the outcome is thresholded into
`PLACED` / `ADRIFT` at the boundary, so `Outcome` stayed a flat enum, and the
raw distance survives in `placements` — but splitting `LevelRecord` by mode and
making `draw_cabinet` work at half its height were both larger jobs than the
placement itself.

The unbuilt half is the scaffolding. The field has fixed marks now — yard
stripes every five, added after watching it played, against this plan's own
advice that a mark is something to count to. What is still missing is the part
that made marks defensible in the research: *thinning them out as he improves*.
That needs a progression rule and a stored level — a second mastery model beside
the deck weighting, which is one model too many for now. Until then
`STRIPE_EVERY` is a constant and the honest position is that the stripes are a
readability trade, not a teaching one. `placements` is the data that would tell you whether it
is needed: mean error per decade bucket, once there are enough attempts in each
to plot. A parent-facing view of it is the same deferral, and belongs with the
parent view of weak facts above.

## Packaging
Currently `uv run mathr` from the source directory. A desktop entry, or a
standalone build, only if he wants to launch it himself.
