# mathr

A desktop math-fact game built for one specific second grader.

Three games, one question pool. In **Rocket Builder**, every fact he gets right
bolts another part onto a rocket; every miss knocks the top part off. Ten parts
on and it counts down and launches — but an alien saucer is closing in the whole
time, and if the clock runs out first it takes the rocket instead. In **Tennis
Match**, an opponent serves and the ball falls down the court; solving the
problem before it lands swats it back. Ten returns wins, three balls past him
loses. In **Touchdown Drive**, every play is a throw and a catch: a yard
downfield is called, he clicks where that number goes on the field, and then has
to answer a math fact before the ball lands to secure the catch.

The point is fluency: number bonds recalled fast enough to be useful, rather than
counted out on fingers. The pass is the exception, and deliberately so — where
a number sits on a line is the one thing here that cannot be answered from a
memorised table.

```sh
uv run mathr
```

## Playing

**Arcade → a cabinet → pick a level.** Every cabinet leads to the same level
grid, and every level is unlocked from the start; there is no sequence to grind
through.

A question appears with exactly one slot blank, and the `=` lands on either
side — the same fact is asked both ways round:

```
8 + ? = 10        10 - 4 = ?        ? = 15 - 7        6 = 2 × ?
```

Type the missing number on the on-screen keypad or the real keyboard, then
`OK` / `Enter`. Answers are capped at two digits.

**Rocket Builder**

- **Right** → a part bolts on, bottom-up, and the clock is credited.
- **Wrong** → the top part tumbles off, the clock stops, and a number line draws
  the route to the answer. That fact comes back three questions later, so he has
  to actually retrieve it rather than echo an answer he was just shown.
- **Ten parts** → countdown and launch.
- **Clock empties** → the saucer beams the rocket up, the parts scatter, and the
  round ends with *Try again*.

**Tennis Match**

- **Right** → he swings, and the ball flies back over the net before the
  opponent serves a new one. The clock waits for it: a rally that resets the
  instant the answer lands never looks *hit*.
- **Wrong** → the ball hangs where it was and the number line shows the route.
  He can retype as soon as he has read it; a mistype on a two-digit keypad is
  cheap and common, and punishing it would make the game about typing. The
  question is not re-asked and the queue does not move — it is still on screen.
- **Ten returns** → the trophy.
- **A ball gets past him** → a point to the opponent, the number line for the
  fact he never answered, and that fact comes back three questions later.
  **Three points** loses the match.

**Touchdown Drive**

The clock is the rocket's: one bank, drained in real time, credited by a right
answer. The field runs the full width of the top of the screen and everything he
types is below it, which buys the line ten pixels a yard.

Each play is a throw and then a catch:

- **The throw.** A yard is called — *throw to the 37* — always between ten and
  forty yards ahead of the ball, and there is no keypad. **Click where that
  number goes.** Every clock stops while he aims, so the estimate is never a
  race.
- **Within six yards** the ball is in the air, and the called yard and the one he
  threw to stay on the field side by side. **Wider** and it says INCOMPLETE: the
  ball does not move, a fresh yard is called from the same spot, and one of three
  attempts is gone. **Three incompletions is a turnover.**
- **The catch.** With the ball up, a fact appears and a football grows in the
  corner as its time runs out. Answer it in time and the catch is secured — the
  ball is **spotted where the pass was caught**, so a short pass gains a little
  and a deep one gains a lot. A wrong answer costs nothing while the ball is up:
  the number line shows the route and everything, the ball included, freezes
  until he types again.
- **Too slow** → DROPPED. Nothing gained and nothing lost but the seconds. The
  next call comes from the same spot with a **new fact** under it: the one that
  got away goes back into the deck to be asked again later, and the answer box is
  emptied so half of one answer cannot be submitted against the next question.
- **A hundred yards** → touchdown. The last ten have to be run in with an
  answer: the goal line is a labelled end of the number line, so a pass that
  could reach it would be a free win.
- **Clock empties, or three incompletions** → turnover, and *Try again*.

Neither half of a play can be traded for the other. A placement he could confirm
by guessing is not an estimate, and a fact he could answer without placing
anything is the game he already has two cabinets of. The three attempts are what
stops the line being clicked at idly until something sticks — and, unlike the
clock, they are a cost he can see coming.

Every finished play is held for a beat on the words CAUGHT / INCOMPLETE /
DROPPED with both pennants still on the field, before the next yard is called.

The field is bare: two goal lines, the 50, and nothing else. Yard stripes were
tried and taken out — they are what a real field looks like, and they are also a
benchmark to count along instead of a distance to judge. `STRIPE_EVERY = 5` in
`shell/draw.py` puts them back.

### The levels

| Level | What it drills | Pace |
|---|---|---|
| **Make Five** | bonds of five — `2 + 3`, `5 − 2`, `1 + ? = 5` | 3s a part |
| **Make Ten** | bonds of ten — `7 + 3`, `10 − 6`, `? + 4 = 10` | 3s a part |
| **Over the Ten** | crossing ten within 20 — `8 + 6`, `15 − 7` | 5s a part |
| **Times Two** | `2 × 0` through `2 × 10`, both ways round | 5s a part |
| **Times Five** | `5 × 0` through `5 × 10` | 5s a part |
| **Times Ten** | `10 × 0` through `10 × 10` | 5s a part |
| **Everything** | every fact above, 278 of them, shuffled together | 5s a part |

Division has a dimmed column on the level screen, and *Tricky Facts* a dimmed
button — both reserved, neither built. The multiplication levels ask only
`a × b = ?` and `a × ? = c`; the two forms that would complete the set are
division, which is exactly what is not built yet.

Both question forms are always asked, in both orientations. `3 + ? = 5` matters
as much as `3 + 2 = ?`, because the missing addend *is* the number bond — and that is the
mental move the third level runs on: `8 + 6` is `8 + 2 + 4`, which is a bond of
ten. The third level is the payoff of the first two, not a separate topic.

Bridging ten gets five seconds instead of three because it is a two-step move —
`15 − 7` is `15 − 5 − 2`. Three seconds is a fluency bar for a fact he already
owns, not for one he is still assembling.

### The clock and the alien

The timer is **a shared bank of seconds, not a stopwatch per problem.** It
drains in real time, and every correct answer credits that level's pace back
into it. So the bar to clear is three seconds per *correct answer* on average —
one slow problem is paid for by a fast one, and stopping to think is allowed as
long as it is not every time.

A round opens with five problems' worth of time as a one-time head start, then
the bank tops out at four problems' worth. Being fast buys safety up to a
ceiling; it cannot be hoarded.

The saucer is the readout. Its size tracks the time **remaining**, so it looms
as the bank drains and visibly retreats when he earns seconds back. A slim bar
under the parts row gives the precision the saucer lacks. There is deliberately
no number counting down — a ticking decimal is the most stressful thing that
could share a screen with an equation he is trying to solve.

A wrong answer costs a part and the seconds it burned. It carries no extra time
penalty on top of that.

### The number line

A miss is worth more than a red flash. When he gets one wrong — or lets a ball
past — every clock stops and the left half of the screen draws the route to the
answer: `8 + 6` as a hop of 2 up to ten and a hop of 4 past it, `15 − 7` as 5
back to ten and 2 more, `5 × 7` as seven hops of five. It shows the whole true
equation, answer included; the route *and* the answer together are the point.

It clears the moment he types the next digit, and that digit still lands in the
entry box — no button, no fixed duration, nothing to wait out. Reading time
counts against nothing: the round clock, the per-question timer and the
elapsed-time record all stop together, so a long read never lands in his
response times.

### Which questions come up

A round is still a shuffle of the whole pool, but not a flat one. Facts he has
been slow on are ordered towards the front, weighted by his mean response time
against the pace that level asks for, so a ten-part round spends its questions
where his time is actually going. A fact he has never answered sits at the
middle weight rather than being crowded out — one answer is not a verdict.

The signal is time, not wrongness. He is rarely wrong, and half the wrong
answers on record were typed in under three seconds with the same fact right
elsewhere — those are slips, and a rule built on them would punish a slip.

### The rally clock

Tennis reads the same clock a different way, which is why the rule lives in the
domain rather than in the drawing: the bank is one ball's flight, a problem and
a half's worth of time, and a correct answer refills it rather than topping it
up. The
ball's position on the court *is* the clock — it retreats to the opponent's
baseline on a return, the same way the saucer retreats when the bank is
credited. There is no head start and no banking ahead, so tennis is the harder
of the two at the same level. The **Timer** toggle belongs to the modes with a bank
— the rocket and the drive; a rally has no untimed form, because without a
deadline the ball has nowhere to be. An untimed drive still throws.

## Controls

| | |
|---|---|
| digits | type an answer (keypad or keyboard) |
| `Enter` / `OK` | submit |
| `Backspace` / `<` | delete a digit |
| `Escape` | back one screen; from the arcade, quit |
| mouse | everything is clickable — and in Touchdown Drive the throw is *only* a click; the keyboard does nothing while one is called |

The window is resizable and tiles happily — everything is laid out on a fixed
1280×800 surface that is scaled and letterboxed into whatever size the window
actually gets, so clicks land where they look like they land at any size.

**Sound** and **Timer** toggle from the arcade and are remembered between runs.
Turning the timer off removes the alien and the clock entirely, and those rounds
are recorded separately so practice can never be mistaken for a real launch.

## Progress

Saved to `$XDG_DATA_HOME/mathr/progress.json` (in practice
`~/.local/share/mathr/progress.json`) on every win, loss, and quit.
Writes go through a temp file and an atomic replace, and a missing or damaged
file loads as an empty record rather than an error — a seven-year-old will close
the window mid-write, and a truncated file that wipes his progress is the one
bug guaranteed to end use of the program.

```json
{
 "version": 2,
 "settings": { "sound": true, "timer": true },
 "levels": {
  "rocket/bridge": { "launches": 3, "practice": 1, "failures": 9, "best_seconds": 47.2 }
 },
 "facts": {
  "15-7=8@result": { "right": 4, "wrong": 3, "answered": 7, "seconds": 31.2 }
 },
 "placements": {
  "30": { "attempts": 4, "error": 21.5 }
 }
}
```

Nothing in the game reads the per-fact numbers back yet. They are written
because they cost almost nothing and cannot be reconstructed later: a mean of
4.5 seconds on a fact he mostly gets right identifies the *slow but correct*
fact, which is exactly what a practice mode should surface first and exactly
what a right/wrong count cannot see.

One record per level **per mode**, keyed `<mode>/<level>`. It was one record
shared by every mode until a third arrived and made the badge on a level card a
mixture of three different games — `launches` counting launches, won matches and
touchdowns alike, and `best_seconds` a minimum across clocks that are not
comparable. That is the `version` bump from 1 to 2: a v1 file's level records
load under `rocket/`, which is a guess, and any tennis played before the split
has inflated the rocket's numbers unrecoverably. The per-fact tallies were and
remain mode-agnostic, which is right — a fact is a fact.

`placements` accumulates every throw by decade of the called yard: attempts, and
the summed absolute distance he was off. Bucketed because eleven buckets fill
with usable data in a week and a hundred and one never do. Nothing reads it back
yet, for the same reason as the per-fact tallies.

`failures` is the number that says whether the pacing is right. If a level shows
one launch against nine failures, the seconds-per-part for that level is wrong —
and nothing else in the file would have told you.

## Development

```sh
uv run mathr      # play
uv run pytest     # 93 tests: facts, round rules, both clocks, storage, scaling
```

One runtime dependency, `pygame-ce` (never upstream `pygame` — it has no cp314
wheel and would try to build from source). Sound is synthesized in code from
`array.array`, so there are no asset files and numpy is not needed.

- `plan.md` — why every decision is what it is, including the ones reversed later
- `ideas.md` — what was deliberately left out, and why
- `CLAUDE.md` — the map and the invariants, for making changes
