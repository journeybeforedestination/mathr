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
- **Doubles as its own level.** `1+1` through `10+10` and their subtractions.
  There is a free slot in the addition column waiting for it, and the content is
  a one-line pair list. Deferred because it is a third addition level proposed
  before anyone has watched him play the two that replaced the three — and
  because `small` and `big` between them already ask every double up to
  `10 + 10`. What a Doubles card would add is *grouping* them, so the pattern is
  visible; whether that is worth a card is a question for `facts` in
  `progress.json` once there are enough answers under `7+7=14@result` and its
  neighbours to compare.
- **Bridging to the next ten.** `Fact.strategy` counts on from the bigger number
  for anything with an operand past ten, so `17 + 5` draws one hop of five.
  Drawing it as `17 +3 +2` is arguably the better strategy at that range, but it
  is a new mental move to teach and `12 + 3` needs the single-hop picture
  regardless. Watch him read one first.
- **The rest of the times tables** — 3s, 4s, 6s, 7s, 8s, 9s, and their divisions.
  `_times` and `_divided` already generate them from a single number, so the
  content is free; the cost is entirely the level screen, which is full at twelve
  cards. `3.OA.C.7` names fluency within 100 by the end of grade 3 and three of
  the nine tables are lit, so this is the largest curricular gap that costs no
  new mechanic at all — only a layout decision.
- Two-digit addition/subtraction without regrouping (34+25, 68−43).
- Two-digit **with** regrouping (37+28, 62−45) — the genuinely hard one. Typed
  answers plus mental carrying may need scratch paper; watch him before building.
- Multiplication via skip counting by fives and tens. **Built** — `twos`,
  `fives_times` and `tens_times`, plus an `everything` pool derived from every
  other level's facts.
- **Division.** **Built** — `divide_two`, `divide_five`, `divide_ten`, and the
  column is lit. The original entry called it "a content decision (how far the
  tables go, whether remainders exist) and not a code one", and it was wrong
  about the second half in one specific way worth keeping: every fact until now
  landed on its own answer, and a division fact does not. `12 ÷ 2` draws six
  hops of two and ends on 12, so `test_every_strategy_lands_on_the_answer`
  became per-operation and `draw_number_line` grew a caption. The content half
  was as cheap as promised — tables to ten, no remainders, and one rule about
  nought, since `0 ÷ ? = 0` is true of every divisor.

## A second game mode
**Built** — Tennis Match. Worth keeping the original entry's claim next to what
actually happened, because the claim was wrong in the interesting way.

It said any mode that consumes a stream of correct/wrong outcomes reuses the
levels unchanged, so a mode is only a renderer. Tennis is not: its clock is a
per-rally deadline rather than a shared bank, a wrong answer costs it nothing,
and a missed ball is a point rather than the end. Built as a pure renderer over
the rocket's rules it would still compile, still draw, and play as a different
game. That is worth walking with real numbers, because it is the argument the
next mode will want to re-run. Take `small` at 4.0 seconds a part, so a round
opens with `seconds_left = 20.0` against a `cap` of 16.0, and drive the ball's
position from `seconds_left / cap` the way `draw.closing` drives the saucer:

1. **The serve does not move for four seconds.** `20.0 / 16.0` is above 1.0, so
   the ball sits pinned at the opponent's baseline until the bank falls under
   the cap. `closing` clamps that deliberately — a saucer that starts
   off-screen is fine, a ball that hangs motionless is not.
2. **A correct answer does not reset the rally.** Answer at t=5.0 with 15.0
   left and `_credit` returns `max(15.0, min(15.0 + 4.0, 16.0))` — 16.0. The
   ball retreats one sixteenth of the court and keeps coming. It never flies
   back, so there is no rally, just a ball creeping inexorably closer.
3. **A wrong answer removes a return he already hit.** `apply` does
   `max(parts - 1, 0)`, so his score drops while the ball is still in the air.
   Nothing in tennis does that.
4. **The first ball he misses ends the match.** The bank empties, `tick` sets
   `failed`, and there is no such thing as an opponent point — the three-point
   cushion cannot exist.

What makes it load-bearing is that **nothing fails**. It compiles, it draws,
every existing test passes, and it plays as a different game than the one
specified. No error says "your clock model is wrong". What the seam actually
bought was `parts: int`: the reducer took a `Rules` bundle and gained a
`points` counter, and neither pools, storage, nor the coordinate transform moved
at all.

The remaining candidates — a growing city, a rescue climb, a race — each want
their own read of that bundle. A mode with no threat can still simply run
untimed.

**Built again** — the relational `=` cabinet, and it broke the frame this entry
was arguing inside. Tennis proved a mode differs in *rules* rather than rendering; the booth
differs in neither. It could run on `ROCKET`'s rules and still be a different
game, because what changed is what a question **is**. That was the third seam,
deferred twice as a heterogeneous queue and reopened here: `Round.queue` now
holds `Question | Sentence`, and `_advance`, `Tally` and `apply` did not move,
because they only ever touched `.key` and `.answer`. What it did cost was two
`Rules` dials (`judges`, `wrong_costs_life`), a `judge` reducer beside `apply`
and `place`, and one overturned invariant — `storage._fold` had to start asking
whether a round was *losable* rather than whether it was *timed*.

It shipped first as **Replay Booth**: a sentence shown whole, judged
Same/Different, and repaired if overturned. It worked, it was tested, and it was
not a game — a static panel with a pip counter, no object on screen that ever
changed, and the feedback backwards, since a wrong answer got a number line and
a right one got nothing. The clock had been removed for a good reason and
nothing replaced the tension it was carrying.

It is now **Code Breaker**: every line is an open sentence, the answers *are*
the combination, and a round is three locks of four, five and six lines. What
the rebuild cost is the true/false half of the lesson — `8 = 8` and
`3 + 5 = 5 + 3` cannot be asked as a blank — and what it bought is that the
maths is the reward rather than a score kept beside it. `judge`, `repairing` and
four outcomes were deleted rather than left unused. Worth keeping the two
side by side, because the first was the design the research argued for and the
second is the one a seven-year-old will play.

The grid is three across by two down and holds five cabinets and one dark
slot. A *seventh* is a layout decision before it is anything else.

## Adaptive difficulty
**Built.** The data answered the question
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
**Built.** A shared bank of seconds per round,
an alien that grows as it drains, and an off switch in the menu.

What remains is the softer end. Per-fact response times are now recorded, so a
personal best *per fact*, or a "beat your own time" mode racing `best_seconds`,
needs no new data — only a UI. Both were left out because the first question is
whether the pressure that exists is already too much, and a second scoreboard
would confound the answer.

## Choosing timed or untimed per level
Raised while designing the clock and set aside: a timed/untimed choice on each
level button, so he could drill `big` untimed while racing on `small`. It
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

## More of the fraction line
Curling ships two level families: four plain ones where the ticks match the
denominator, and `same_as`, where they are a multiple of it and the line ticked
in sixths is asked for `1/3`. Two more were designed and deferred.

- **Past one.** A 0–2 line, and `5/4` or `1 1/2` on it. `3.NF.A.2b` allows it and
  grade 4 needs it. The cost is one honest thing: the span stops being "the
  whole", so the labels have to say what the line runs to, and `SPAN` stops being
  the denominator of everything.
- **A bare line, no ticks.** Pure magnitude estimation of a fraction, which is
  what the longitudinal evidence in `research/iready-grade3.md` is actually
  about — and the only family where the tolerance cannot be half a tick gap,
  because there are no ticks. It needs a generous constant chosen by watching
  him, which is the thing the half-gap rule was picked to avoid.

Both are content plus one decision each, not new mechanics. Neither should land
before there is a round of real play behind the six families that exist.

## Weighting the target deck by error
The stone he places worst would come up more often, exactly as the fact he
answers slowest already does. Deferred, and the reason is the same one that has
now been given three times: `_weights` in `domain/round.py` reads mean seconds
against the level's pace, which means nothing for an estimate. Weighting by error
is a *second* weighting function, and two reasons a deck is ordered is two
mastery models. The data is being written either way — `Progress.targets` holds
a `Tally` per exact fraction, right and wrong and time — so this stays possible
without costing anything to defer. Note what it does *not* hold: the summed
distance, the way `placements` does for football. A `Tally` is the type
`attempts` already carries and reusing it cost nothing; recording error too
means a second map keyed the same way, and it should be added when something is
actually going to read it.

## A parent-facing readout of estimation
Sibling of the parent view of weak facts above, and it wants the same screen.
Two sections now have data and no reader:

- `placements` — football's aims, bucketed by decade of the field. The plot worth
  drawing is *signed* error by bucket, not mean absolute error: the classic
  finding is a logarithmic pattern, overestimating low on the line and
  compressing high, and that is invisible in a mean and obvious in a plot. It is
  also the only thing that would say whether the yard stripes are helping or
  doing the estimating for him.
- `targets` — curling's, per exact fraction, right and wrong. With four to
  eighteen targets in a level this answers "which fractions does he miss", which
  is far more actionable than a bucket. It is the section that would want the
  summed error added above.

## Rounding, as a second question over the same line
`3.NBT.A.1`. Rounding is taught as a rule about the digit to the right, which
leaves no magnitude understanding behind; on a line, *which ten is 47 nearer to*
is the whole of it. Mechanically it is the placement already built, with a coarse
tolerance and a different prompt. Deliberately held back rather than built beside
the fractions: two question types arriving in one mechanic at once is how a
placement mode grows a rule per question type, and the fraction line should be
watched being played before anything else is hung off it.

## The scaled pictograph scoreboard
`3.MD.B.3` is scaled bar graphs and pictographs, where each symbol stands for 5
or 10 and the skill is multiplying to read it. `draw_progress` already draws a
row of pips and already divides — football's pip is ten yards. Drawing them with
a key ("each ball = 5 yards") puts a Measurement & Data skill on a screen he
looks at twenty times a round, costs one renderer change, and teaches nothing
wrong if he ignores it. Not a mode, and it should not become one. This is the
cheapest curricular contact in `research/iready-grade3.md` and it is unbuilt only
because nothing has needed the scoreboard opened up yet.

## Guess my rule
A function machine: three rows shown, predict the fourth. It reuses the number
pools, it is generalisation rather than drill, and it is the only idea on the
list that produces a question he cannot answer by computing faster. It hooks
grade 3 lesson 7 and grade 4 lesson 8. The cost is a new question shape — a
machine row is not a `Fact` — which is the *same* cost as word problems and as
true/false sentences. That is the argument for picking one of the three and
letting it define the seam, rather than paying it three times.

## The curriculum this program should not hold
From `research/iready-grade3.md` §5.6, kept here so it is not re-proposed. Grade
3 content that is real, is tested, and wants an interaction a keypad and a line
do not have:

- **Area and perimeter** (lessons 27–30). Genuinely important and genuinely
  multiplicative. A rectangle-building interaction is a different program; worth
  its own dig one day, not a variation on anything that exists.
- **Geometry** (`3.G` entire) — attributes of shapes, quadrilaterals, dividing
  shapes into equal areas. Faked on a keypad it becomes multiple-choice
  vocabulary, which is the worst kind of drill.
- **Mass, liquid volume, line plots.**
- **Word problems**, one-step and two-step. The evidence is strong and the
  content-authoring cost is real, but the honest objection is that a keypad game
  with a two-line problem is a worksheet with sound effects. If it is ever built,
  build it for *structure* — the same numbers with the unknown in the start
  position — and not for reading.

The general shape of the argument: two of i-Ready's four domains are covered
here, and the other two are missing because the input device is a keypad and a
line. Closing that gap means a new interaction, not a new cabinet.

## Packaging
Currently `uv run mathr` from the source directory. A desktop entry, or a
standalone build, only if he wants to launch it himself.

## The approaches this program is not built on

Rejected before the first line was written, and kept here because they are what
a fresh reader proposes first. Nothing below is a feature that was deferred —
each one is a road not taken, and the reason it was not.

- **A web app (React + Vite + Tailwind).** *This was the first recommendation
  made, and it was reversed — the most likely path for a fresh context to
  re-walk.* The argument for it is real: in a browser a part tumbling off is a
  CSS transform and the art is resolution-independent SVG, where pygame means
  integrating rotation per frame by hand. It loses because the choice was a
  desktop app with local-file storage, which removes the browser's decisive
  advantage — playing on a tablet with no dev server. What remains is
  `node_modules` against one dependency. **Revisit only if it has to run on a
  tablet.**
- **Upstream `pygame`.** No cp314 wheel; it would build from source and fail.
  Decided by a fact, not a preference. Both packages import as `pygame`, so a
  stray one in the lockfile is invisible in the source.
- **`tkinter`.** Present, zero dependencies, and `Canvas` + `after()` can
  animate this. Rejected: no game loop, no sound, and manual easing anyway — the
  dependency saved is one package.
- **Kivy / PyQt.** Install weight and licensing complexity far beyond a
  single-screen kid's game.
- **numpy for sound synthesis.** Proven unnecessary: `array.array` feeds
  `Sound(buffer=...)` directly, and the probe ran with numpy absent.
- **A Hyprland window rule instead of design-surface scaling.** It edits the
  user's desktop config to work around an application bug, does not survive
  fullscreen or a different machine, and does nothing for the coordinate
  mapping — which is the half that actually breaks silently. See *Layout is
  design space* in `CLAUDE.md`.
- **Sequential level unlocking.** *More* code than open access, and it would
  make a kid who already owns bonds of five grind past them.
- **Random fact generation.** The pools are small enough to enumerate, and
  enumeration is both simpler and testable by assertion.
- **Multiple-choice answers.** Trains recognition, and a smart kid
  reverse-engineers the distractors. Typed answers force recall, which is the
  whole point of a fluency drill.
- **No timer at all.** Rejected for v1 on the grounds that timers cause anxiety,
  then **overturned** once he asked for urgency. The original reasoning was not
  wrong, which is why the clock ships with an off switch in the menu.
