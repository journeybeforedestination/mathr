# mathr

A desktop math-fact game built for one specific second grader.

Five games. In **Rocket Builder**, every fact he gets right
bolts another part onto a rocket; every miss knocks the top part off. Ten parts
on and it counts down and launches — but an alien saucer is closing in the whole
time, and if the clock runs out first it takes the rocket instead. In **Tennis
Match**, an opponent serves and the ball falls down the court; solving the
problem before it lands swats it back. Ten returns wins, three balls past him
loses. In **Touchdown Drive**, every play is a throw and a catch: a yard
downfield is called, he clicks where that number goes on the field, and then has
to answer a math fact before the ball lands to secure the catch. In **Code
Breaker** the questions are number sentences and the numbers he works out spell
out a safe's combination. In **Curling Club** he is shown a fraction and slides
a stone to where it goes on a sheet of ice ticked into equal parts.

The point is fluency: number bonds recalled fast enough to be useful, rather than
counted out on fingers. Three of them are deliberately not that. Where a number
sits on a line cannot be answered from a memorised table, and neither is
`7 + 6 = ? + 5`, which is about what `=` *means* rather than what `7 + 6` is.
The last two cabinets have no clock in them at all, and Curling Club has no
keypad either — the only thing it ever asks for is a click.

Four cabinets share one pool of arithmetic facts; the fifth has its own pool of
fractions, so it has its own level cards.

```sh
uv run mathr
```

## Playing

**Arcade → a cabinet → pick a level.** The four arithmetic cabinets lead to the
same level grid; Curling Club has its own, because a fraction is not a fact.
Every level is unlocked from the start; there is no sequence to grind through.

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
  threw to stay on the field side by side. **Wider** and it is a holding call as
  well — the ball goes **back ten yards** — and it stops for INCOMPLETE:
  the yard he threw to and how far off it was on which side — *you threw to the
  53, 24 past the 29* — over a number line showing the window the pass had to
  land in, with *Next pass* to move on when he has read it. Nothing is on a
  clock while it is up. The ball does not move, a fresh yard is called from the
  same spot, and one of three attempts is gone. **Three incompletions is a
  turnover.**
- **The catch.** With the ball up, a fact appears and a football grows in the
  corner as its time runs out. Answer it in time and the catch is secured — the
  ball is **spotted on the yard he threw to**, exactly: a pass to the 27 puts
  the ball on the 27, so a short pass gains a little and a deep one gains a lot.
  A wrong answer costs nothing while the ball is up: the number line shows the
  route and everything, the ball included, freezes until he types again.
- **Too slow** → DROPPED. Nothing gained and nothing lost but the seconds. The
  next call comes from the same spot with a **new fact** under it: the one that
  got away goes back into the deck to be asked again later, and the answer box is
  emptied so half of one answer cannot be submitted against the next question.
- **The sack.** About one play in four is not a pass at all — and one is
  guaranteed once he crosses the 50 if none has hit him yet: *SACKED! back 8
  yards — click where that leaves you*. The yardage is stated and the new spot
  is not, so placing it is a subtraction on the line rather than a number to be
  read off. The ball goes back either way — a near-miss cannot buy yards — and
  the field draws the move as a labelled hop backwards, the same picture a
  missed fact gets. It exists so the ball does not only ever march forward:
  without it he estimates ahead of a marker halfway up the field all game and
  the low numbers come up once.
- **A hundred yards** → touchdown. Once he is close enough that no honest target
  is left ahead of him the call is the end zone itself — the one easy placement
  in a round, and the one that wins it.
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

**Code Breaker**

No clock anywhere. What this mode measures is whether he *sees* a relation
rather than computing his way to it, and that shows up as answering faster than
his own arithmetic — which a clock ticking at him would suppress.

The whole left of the screen is a safe: hinges down one side, bolts down the
other, three alarm lamps along the top rail, and a dial beside the combination.
The intercepted lines are behind its glass, each with one number missing:

```
┌──────────────────────────────────────┐
│◉  LOCK 1 OF 3        ALARMS ● ○ ○    │
│   ┌──────────────────────────────┐   │
│   │ 4 + 8 = 5 + 7            ●   │   │▐▌ bolt
│   │ 10 - 7 = 15 ÷ 5          ●   │   │
│   │ 2 + 3 = 5 + ?                │   │▐▌
│   │ ▬▬ ▬▬ ▬▬ ▬▬                  │   │
│◉  └──────────────────────────────┘   │▐▌
│  CODE  5   15  __  __    (◍) dial    │
└──────────────────────────────────────┘
```

- **Every number he works out drops into the combination**, and the dial turns a
  notch as it lands. That is the whole mapping: the maths *is* the code, rather
  than a score being kept next to it.
- **Lines below the one he is on stay encrypted** — a row of blocks, so he can
  see how much is left without reading ahead. A lock he could scan in advance is
  a worksheet.
- **A round is three locks, of four, five and six lines.** Filling a
  combination spins the dial, throws the three bolts, and holds the whole lock
  open in green — his lines and his numbers, still there to look at — before the
  next one loads. Three wins in a round rather than one, and the last lock is
  meant to feel longer than the first.
- **A wrong answer lights one of the three alarm lamps** and the line stays put
  — he still has to open it. The number line comes up showing both sides, which
  is how he gets it next rather than guessing again. Reading it and then typing
  costs nothing more. **Three alarms and the vault locks down.**
- **The third lock is the door itself.** It swings open on its hinges and the
  safe is full of gold — bars, coins and gems on two shelves — under
  *VAULT OPEN!*

The lines are built from the level's own facts, so every arithmetic cabinet
still leads to the same cards. Four shapes, in rough order of how much relation they
need: `7 + 6 = ? + 5` (two expressions, neither readable on its own),
`3 + 5 = ? + 3` (commuted), `12 ÷ 2 = ? + 4` (the value split in two), and
plain `7 + 6 = ?`, which is the question the other three cabinets already ask
and is deliberately the rarest.

*Everything* makes the best panel, because it can put `10 - 7` and `15 ÷ 5` on
opposite sides of the same `=`. The division levels lean entirely on splitting —
they have no two expressions sharing a value and nothing to commute — which is
the reason that shape exists at all.

**A miss shows both sides at once**, over one shared span, with a line under it
saying whether they landed together. One span on purpose: two lines each scaled
to their own numbers would put both endpoints in the same place, which is the
opposite of the point.

**Curling Club**

No clock and no keypad. A fraction is called, and the whole answer is where he
clicks on a sheet of ice marked 0 at one end and 1 at the other and ticked into
equal parts:

```
  misses ● ○ ○                                    3 / 8 stones

 ┌────────────────────────────────────────────────────────────┐
 │  │                                                       │ │
 │  ├────┬────┬────●────┬────┬────●────┬────┬────┬────●────┤   │
 │  0                                                      1   │
 └────────────────────────────────────────────────────────────┘

                        slide the stone to
                               3/4
                           click the ice
```

- **The ticks are the denominator.** `2/3` is called on a line cut into thirds,
  so the mark is there to be found rather than guessed at — this is the whole of
  what the mode teaches.
- **The stone stops exactly where he clicked.** There is no power meter and no
  wobble: an error that is partly motor would corrupt the one thing being
  measured.
- **Near enough is half a tick gap** — near enough that no other tick is nearer.
  So halves are forgiving and twelfths are tight, and nothing needs tuning per
  level.
- **A stone in the house counts and stays on the ice.** Eight of them win the
  end. The stones piling up along the line are what carries the round, in place
  of the clock the other cabinets have. Two that land on the same mark — `1/2`
  and `2/4` are the same place — stand one above the other rather than on top of
  each other, because sideways is the answer and cannot be nudged.
- **Someone is standing at nought with a broom**, sweeping, drawn in the same
  blocks as the ball carrier in Touchdown Drive.
- **A wide stone brings out the house** — rings exactly as wide as the shot was
  forgiving, centred on the true mark, with his stone sitting outside them and a
  line saying where it should have gone: *1/3 is 2 ticks along a line cut into
  6*. It is held until he presses *Next stone*; a click on the ice cannot
  dismiss it, or reading the miss would throw the next stone at whatever he
  happened to be looking at.
- **Three wide stones** end the end, and *Try again*.

The rings are only ever drawn *after* the stone has come to rest. They are
centred on the mark that was called, so a house on the ice while he is still
aiming is the answer, printed.

*Same As* is the level where the two numbers disagree on purpose: `1/3` called
on a line ticked in sixths, `1/2` on a line ticked in twelfths. Same place, a
different name for it.

### The levels

| Level | What it drills | Pace |
|---|---|---|
| **Ten and Below** | both numbers ten or less — `2 + 2`, `7 + 7`, `10 − 6`, `1 + ? = 5` | 4s a part |
| **Above Ten** | one number past ten, up to 20 — `12 + 3`, `13 − 4`, `20 − 7` | 5s a part |
| **Times Two** | `2 × 0` through `2 × 10`, both ways round | 5s a part |
| **Times Five** | `5 × 0` through `5 × 10` | 5s a part |
| **Times Ten** | `10 × 0` through `10 × 10` | 5s a part |
| **Divide by Two** | `2 ÷ 2` through `20 ÷ 2`, both ways round | 5s a part |
| **Divide by Five** | `5 ÷ 5` through `50 ÷ 5` | 5s a part |
| **Divide by Ten** | `10 ÷ 10` through `100 ÷ 10` | 5s a part |
| **Everything** | every fact above, 938 of them, shuffled together | 5s a part |

The multiplication levels ask only `a × b = ?` and `a × ? = c`; the two forms
that would complete the set are division, and they are their own column rather
than two more questions inside *Times Two* — so a division level asks
`12 ÷ 2 = ?` and `12 ÷ ? = 6` and nothing else. The tables stop at ten and there
are no remainders. Nothing divides by nought: `0 ÷ ? = 0` is true of every
divisor, so that pair is not askable and the division levels hold twenty facts
where the times levels hold twenty-two.

Division is also the one operation whose answer is *not* where its number line
ends. `12 ÷ 2` draws six hops of two and lands on 12 — the number already in the
question — so the hint captions the hop count, and the picture is exactly the
one `2 × 6 = 12` draws.

The two addition levels split on **the two numbers as written**, never on the
answer. `7 + 7 = 14` is two small numbers, so it is in *Ten and Below*; `14 − 7`
is a big number meeting a small one, so it is in *Above Ten*. One number bond
therefore sends its addition forms to one level and its subtraction forms to the
other the moment its total passes ten. *Above Ten* has exactly one number past
ten — `18 − 13` is regrouping, which is a different skill and is not here.

Nothing adds nought to nought: `0 + 0 = ?` measures nothing and would only
inflate the record, the same reason nothing divides by nought. Zero *addends*
stay, because `0 + 5` is a real thing to get wrong.

*Tricky Facts* keeps its dimmed button in the Everything column: reserved, not
built.

Curling Club has its own six, and no pace at all — nothing there is timed:

| Level | What it drills |
|---|---|
| **Halves & Fourths** | `1/2`, and the fourths, each on its own ticks |
| **Thirds & Sixths** | thirds and sixths |
| **Fifths & Tenths** | fifths and tenths |
| **Eighths & Twelfths** | the tight ones |
| **Same As** | `1/3` on sixths, `1/2` on twelfths — equivalence |
| **Every Fraction** | all 56, shuffled together |

`0/b` and `b/b` are left out of every one of them: both are the labelled ends of
the line, so they are marks he gets for free.

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
  "rocket/big": { "launches": 3, "practice": 1, "failures": 9, "best_seconds": 47.2 }
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
uv run pytest     # 240 tests: facts, round rules, both clocks, storage, scaling
```

One runtime dependency, `pygame-ce` (never upstream `pygame` — it has no cp314
wheel and would try to build from source). Sound is synthesized in code from
`array.array`, so there are no asset files and numpy is not needed.

- `plan.md` — why every decision is what it is, including the ones reversed later
- `ideas.md` — what was deliberately left out, and why
- `CLAUDE.md` — the map and the invariants, for making changes
