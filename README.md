# mathr

A desktop math-fact game built for one specific second grader.

Every fact he gets right bolts another part onto a rocket. Every miss knocks the
top part off and re-queues that fact to be asked again a few questions later.
Ten parts on and it counts down and launches — but an alien saucer is closing in
the whole time, and if the clock runs out first it takes the rocket instead.

The point is fluency: number bonds recalled fast enough to be useful, rather than
counted out on fingers.

```sh
uv run mathr
```

## Playing

**Menu → Rocket Builder → pick a level.** Every level is unlocked from the
start; there is no sequence to grind through.

A question appears with exactly one slot blank:

```
8 + ? = 10        10 - 4 = ?        15 - ? = 8
```

Type the missing number on the on-screen keypad or the real keyboard, then
`OK` / `Enter`. Answers are capped at two digits.

- **Right** → a part bolts on, bottom-up, and the clock is credited.
- **Wrong** → the top part tumbles off, and that fact comes back three questions
  later, so he has to actually retrieve it rather than echo an answer he was
  just shown.
- **Ten parts** → countdown and launch.
- **Clock empties** → the saucer beams the rocket up, the parts scatter, and the
  round ends with *Try again*.

### The levels

| Level | What it drills | Pace |
|---|---|---|
| **Make Five** | bonds of five — `2 + 3`, `5 − 2`, `1 + ? = 5` | 3s a part |
| **Make Ten** | bonds of ten — `7 + 3`, `10 − 6`, `? + 4 = 10` | 3s a part |
| **Over the Ten** | crossing ten within 20 — `8 + 6`, `15 − 7` | 5s a part |

Both question forms are always asked. `3 + ? = 5` matters as much as
`3 + 2 = ?`, because the missing addend *is* the number bond — and that is the
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

## Controls

| | |
|---|---|
| digits | type an answer (keypad or keyboard) |
| `Enter` / `OK` | submit |
| `Backspace` / `<` | delete a digit |
| `Escape` | back one screen; from the menu, quit |
| mouse | everything is clickable |

The window is resizable and tiles happily — everything is laid out on a fixed
1280×800 surface that is scaled and letterboxed into whatever size the window
actually gets, so clicks land where they look like they land at any size.

**Sound** and **Timer** toggle from the menu and are remembered between runs.
Turning the timer off removes the alien and the clock entirely, and those rounds
are recorded separately so practice can never be mistaken for a real launch.

## Progress

Saved to `$XDG_DATA_HOME/mathr/progress.json` (in practice
`~/.local/share/mathr/progress.json`) on every launch, abduction, and quit.
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

`failures` is the number that says whether the pacing is right. If a level shows
one launch against nine failures, the seconds-per-part for that level is wrong —
and nothing else in the file would have told you.

## Development

```sh
uv run mathr      # play
uv run pytest     # 74 tests: facts, round rules, the clock, storage, scaling
```

One runtime dependency, `pygame-ce` (never upstream `pygame` — it has no cp314
wheel and would try to build from source). Sound is synthesized in code from
`array.array`, so there are no asset files and numpy is not needed.

- `plan.md` — why every decision is what it is, including the ones reversed later
- `ideas.md` — what was deliberately left out, and why
- `CLAUDE.md` — the map and the invariants, for making changes
