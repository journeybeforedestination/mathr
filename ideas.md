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
Weight question selection toward facts he misses. Rejected for v1 as complexity
without evidence — the per-fact data will show whether it is needed. Response
times sharpen this: mean seconds per fact separates "does not know it" from
"knows it slowly", which want different treatment.

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

## Packaging
Currently `uv run mathr` from the source directory. A desktop entry, or a
standalone build, only if he wants to launch it himself.
