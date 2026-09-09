# mathr

A desktop math-fact game built for one specific second grader.

Two games, one question pool. In **Rocket Builder**, every fact he gets right
bolts another part onto a rocket; every miss knocks the top part off. Ten parts
on and it counts down and launches — but an alien saucer is closing in the whole
time, and if the clock runs out first it takes the rocket instead. In **Tennis
Match**, an opponent serves and the ball falls down the court; solving the
problem before it lands swats it back. Ten returns wins, three balls past him
loses.

The point is fluency: number bonds recalled fast enough to be useful, rather than
counted out on fingers.

```sh
uv run mathr
```

## Playing

**Arcade → a cabinet → pick a level.** Both cabinets lead to the same level
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
- **Wrong** → the top part tumbles off, and that fact comes back three questions
  later, so he has to actually retrieve it rather than echo an answer he was
  just shown.
- **Ten parts** → countdown and launch.
- **Clock empties** → the saucer beams the rocket up, the parts scatter, and the
  round ends with *Try again*.

**Tennis Match**

- **Right** → he swings, and the ball flies back over the net before the
  opponent serves a new one. The clock waits for it: a rally that resets the
  instant the answer lands never looks *hit*.
- **Wrong** → nothing. The ball is still in the air and he can retype while it
  falls; a mistype on a two-digit keypad is cheap and common, and punishing it
  would make the game about typing.
- **Ten returns** → the trophy.
- **A ball gets past him** → a point to the opponent, that fact comes back three
  questions later, and the next one is served. **Three points** loses the match.

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

### The rally clock

Tennis reads the same clock a different way, which is why the rule lives in the
domain rather than in the drawing: the bank is one ball's flight, a problem and
a half's worth of time, and a correct answer refills it rather than topping it
up. The
ball's position on the court *is* the clock — it retreats to the opponent's
baseline on a return, the same way the saucer retreats when the bank is
credited. There is no head start and no banking ahead, so tennis is the harder
of the two at the same level. The **Timer** toggle belongs to the rocket; a
rally has no untimed form, because without a deadline the ball has nowhere to
be.

## Controls

| | |
|---|---|
| digits | type an answer (keypad or keyboard) |
| `Enter` / `OK` | submit |
| `Backspace` / `<` | delete a digit |
| `Escape` | back one screen; from the arcade, quit |
| mouse | everything is clickable |

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
 "version": 1,
 "settings": { "sound": true, "timer": true },
 "levels": {
  "bridge": { "launches": 3, "practice": 1, "failures": 9, "best_seconds": 47.2 }
 },
 "facts": {
  "15-7=8@result": { "right": 4, "wrong": 3, "answered": 7, "seconds": 31.2 }
 }
}
```

Nothing in the game reads the per-fact numbers back yet. They are written
because they cost almost nothing and cannot be reconstructed later: a mean of
4.5 seconds on a fact he mostly gets right identifies the *slow but correct*
fact, which is exactly what a practice mode should surface first and exactly
what a right/wrong count cannot see.

One record per level, shared by both modes: `launches` counts a launch and a
won match alike, and `best_seconds` is the fastest of either. The per-fact
tallies were always mode-agnostic, and splitting the record would need a
`version` bump for a number nobody has asked for yet.

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
