# Research: the i-Ready curriculum above him, and what of it this game can hold

A companion to `math-education.md` (which lives on branch
`worktree/rapid-meadow-32ee`, commit `79c74c3` — **not on `main`**; it is the
source for every "§" reference below). That document asked *how* to practise.
This one asks *what*, using the curriculum he is actually tested against.

The student is in second grade and places high on the i-Ready Diagnostic. So the
question is not "what is second-grade math" but "what is the next year of it,
and which parts of that can a keypad-and-number-line game hold honestly".

---

## 1. What i-Ready actually measures, and what "placing high" means

The Diagnostic is an adaptive, computer-administered test given two or three
times a year. It reports a scale score plus a **criterion-referenced grade-level
placement**, per domain, in four domains that are constant across K–8
([Curriculum Associates][ca]; [NYSED description][nysed]):

| i-Ready domain | CCSS strands it draws on at grade 3 |
|---|---|
| Number and Operations | 3.NBT (place value, rounding, add/sub within 1000), 3.NF (fractions) |
| Algebra and Algebraic Thinking | 3.OA (multiplication, division, properties, patterns, two-step problems) |
| Measurement and Data | 3.MD (time, volume/mass, scaled graphs, line plots, area, perimeter) |
| Geometry | 3.G (attributes of shapes, quadrilaterals, partitioning into equal areas) |

Two consequences worth stating plainly:

- **The Diagnostic is a placement instrument, not a mastery instrument.** It is
  adaptive, so a student sees perhaps 40 items spanning several grade levels; it
  can tell you he is "Mid Grade 4" in Algebra and Algebraic Thinking and it
  cannot tell you whether he knows `7 × 8`. It is measured in months and reported
  twice a year. `progress.json` already measures in seconds and reports
  continuously. **They answer different questions and neither replaces the
  other** — the Diagnostic tells you *which shelf to reach for*, this game tells
  you *whether the thing on the shelf has stuck*.
- **Placement is per domain.** A student can place a year ahead in one and at
  grade level in another, and for a strong arithmetic student the usual profile
  is Number/Algebra high and Measurement & Data lagging — those are the topics
  with the most vocabulary and the least computation. Worth asking to see the
  domain breakdown before choosing what to build; §1.4 makes the case for
  measuring above level, and the Diagnostic already does it for free.

## 2. The grade 2 list, for review

From Curriculum Associates' own year-long pacing for grade 2
([Ready Mathematics pacing][pace2]) — the content the Diagnostic samples as
"on grade level" for him now:

- **Mental-math strategies**: fact families, make-a-ten, even and odd, arrays as
  repeated addition.
- **One-step and two-step word problems** (2.OA.A.1) — the two-step ones arrive
  in grade 2, not 3.
- **Two- and three-digit addition and subtraction**, place value to 1000,
  reading/writing/comparing three-digit numbers, adding several two-digit
  numbers.
- **Measurement**: length with tools and with different units, *estimating*
  length, comparing lengths, adding and subtracting lengths.
- **Data**: line plots, bar graphs and pictographs.
- **Time and money**; **shapes**, tiling rectangles, halves/thirds/fourths.

What mathr covers of this: the mental-math strategies and fact families,
thoroughly and at speed. Nothing else. The two-digit work is already logged in
`ideas.md` under *More levels* and is the cheapest content extension that exists
— `_ADDITION` takes a new pair list and `_pool` does the rest.

## 3. The grade 3 list, which is the interesting one

Same source, grade 3 ([pacing][pace3]), in teaching order. I have marked each
against this game: **✔ fits the existing machinery**, **~ fits with one new
seam**, **✘ wants a different program**.

**Unit 1 — multiplication and division concepts** (3.OA)
1. Understand the meaning of multiplication ✔
2. Use order and grouping to multiply (commutative, associative) ~
3. Split numbers to multiply (distributive: `7 × 8` as `7 × 5 + 7 × 3`) ~
4. Understand the meaning of division ✔
5. Understand how multiplication and division are connected ✔
6. Multiplication and division facts — **fluency within 100 by year end** ✔
7. Understand patterns ~

**Unit 2 — place value** (3.NBT)
8. Use place value to round numbers ~ (this is estimation on a line)
9. Use place value to add and subtract (within 1000) ✔
10. Use place value to multiply (multiples of 10) ✔

**Unit 3 — word problems** (3.OA.D.8)
11. One-step problems with × and ÷ ~
12–13. Model and solve **two-step** problems with all four operations ~

**Unit 4 — fractions** (3.NF) — the heart of grade 3
14. Understand what a fraction is ~
15. **Understand fractions on a number line** ✔ *(see §5.1)*
16–17. Understand and find equivalent fractions ~
18–19. Understand and use symbols to compare fractions ~

**Unit 5 — measurement, data, area** (3.MD)
20–21. Tell/write time; solve problems about elapsed time ~
22–23. Liquid volume; mass ✘
24–25. Solve problems using, and draw, scaled graphs ~
26. Measure length and plot data on line plots ✘
27–30. Understand area; multiply to find area; add areas; connect area and
perimeter ~

**Unit 6 — geometry** (3.G)
31–33. Properties of shapes; classify quadrilaterals; divide shapes into equal
areas ✘

And, because he may already be past some of grade 3, the grade 4 spine
([pacing][pace4]) is: place value and rounding to a million, multi-digit
multiplication and division, **multiples and factors**, number and shape
patterns, multi-step problems, fraction equivalence/comparison/addition,
decimals as tenths and hundredths, angles. Of these, *multiples and factors* and
*number patterns* are the two that need no new content model here.

### The short version

Three grade-3 strands are reachable from what mathr already is:

1. **Division and the ×/÷ connection** — the explicit year-end fluency target
   (3.OA.C.7), and the pools already stop one form short of it.
2. **Fractions on a number line** — 3.NF.A.2 is, mechanically, the placement
   already built for Touchdown Drive.
3. **Rounding and estimation** (3.NBT.A.1) — also the placement, with a coarser
   tolerance and a different question.

Everything else is either a different program (mass, geometry, line plots) or a
content-authoring job rather than a code one (word problems).

---

## 4. Measuring mastery of these, honestly

`progress.json` currently holds, per fact key: right, wrong, answered, seconds;
and per `<mode>/<level>`: launches, failures, best_seconds; and raw `placements`.
That is a good instrument for exactly one shape of skill, and the grade-3 list
contains three shapes. Taking them in turn.

### 4.1 Facts, including the new ones — a rate, and it already works

§1.1 and §1.2 settled this: fluency is accuracy *and* rate, measured as a rate
rather than a percentage, and the operational threshold in the literature is on
the order of three seconds per fact for a fact that is *known* rather than
figured out. The CBM tradition measures digits correct per minute and sets the
expectation at roughly two-thirds of the child's own writing speed
([Wright][cbm]; [Peltier][pelt]) — which for a game with a keypad translates to
*median seconds per fact*, which is what the deck weighting already computes.

So for multiplication and division facts, **nothing new is needed to measure
mastery**: median response time over the last *k* attempts, against the level's
`seconds_per_part`, with a recent-error gate. What is missing is only the *readout*
— `ideas.md` already defers the parent view of weak facts, and that view is what
turns the existing data into an answer to "has he got the times tables".

One caution specific to division: `12 ÷ 3` answered in 4s by a child who
recalled `3 × 4 = 12` and one answered in 4s by a child who counted up are
indistinguishable in the data, and both are fine. Do not read the ×/÷ connection
out of timings; read it out of whether `? × 3 = 12` and `12 ÷ 3 = ?` have
converged to the same speed. That comparison is available today because
`Fact.key` distinguishes the forms.

### 4.2 Estimation — a distance, and a bias, not a score

Number-line placement produces a magnitude of error, not a boolean, and the
literature measures it as **percent absolute error**: |estimate − target| ÷ span.
This is the metric behind the longitudinal results in §3.2 and behind the
fraction interventions that move it — Fuchs' *Fraction Face-Off!* and its
relatives report number-line effect sizes around *d ≈ 0.8–1.1* and, notably,
that number-line training transfers to fraction comparison better than area-model
training does ([Fraction Face-Off!][ffo]; [WWC][wwc]; [number line review][nlr]).

Two things follow for measurement here:

- **Mean PAE is the mastery number**, and `placements` already stores what it
  needs. A reasonable target for whole-number placement on 0–100 is single-digit
  PAE; the honest move is to look at his own curve rather than import a
  threshold, since `PLACE_TOLERANCE = 6` was chosen for playability.
- **Bias matters more than error.** The classic finding is a *logarithmic*
  pattern — small numbers spread out, large numbers compressed — which shows up
  as systematic overestimation low on the line and underestimation high. That is
  invisible in a mean and obvious in a plot of signed error by decade bucket.
  `ideas.md` already names this as the analysis `placements` exists for. It is
  also the only measurement in this document that would tell you whether the
  yard stripes are helping or doing the estimating for him.

### 4.3 Relational and structural understanding — measure the *time*, not the answer

For true/false number sentences (§3.1) and for word-problem structure (§3.3),
accuracy saturates fast in a strong student and tells you very little. What
separates "computed it" from "saw it" is response time: a child who answers
`7 + 6 = ? + 5` relationally answers faster than his own arithmetic speed for
13 − 5, and a child who computes does not. The game already records per-item
seconds, so **the discriminating measurement is comparing an item's time against
the same child's baseline for its arithmetic** — no new field, but a new
comparison, and one worth stating before building either mode.

For word problems, the measurement that matters is **accuracy by problem
structure** (join/separate/compare × result/change/start unknown), not overall
accuracy, because difficulty varies by structure independent of number size.
That needs a structure tag on the item, which is a content-model change, not a
storage one.

### 4.4 The thing to avoid

Three shapes of skill invite three mastery models, and `ideas.md` has already
rejected a second one ("one model too many for now") when it looked at thinning
the yard stripes. That judgement should hold. If a second content type lands, the
argument to make first is that **one record shape covers all three**: an item
key, an attempt count, a mean time, and an *error magnitude* that happens to be
0-or-1 for a fact and a PAE for a placement. That is one selection policy, one
weighting, one parent view. Two is where this gets complicated.

---

## 5. Ideas, ranked by what they buy against what they cost

### 5.1 Fractions on the field — the placement, with a fractional line

**The one I would build.** 3.NF.A.2 asks the student to place a fraction on a
number line partitioned into equal parts. `place()` already takes a click on a
line, thresholds the distance, and stores the raw error. What changes is the
*question* ("throw to ⅔") and the *span* — a 0–1 line with the denominator's
tick marks instead of 0–100 yards.

Why it is the strongest idea in this document:

- It is the top item of grade 3's hardest unit, and it is the single strongest
  longitudinal predictor in the whole of `math-education.md` (§3.2 — first-grade
  line estimation predicting seventh-grade fraction arithmetic).
- The intervention evidence is specifically for the number line *over* the area
  model, which is the representation most programs reach for.
- It is not fact recall, so it cannot be gamed, and he cannot have memorised it.
- **The architecture already fits.** `PLACE_MAX`, `PLACE_TOLERANCE`,
  `place_lives` and `Aim` are all span-relative; the marker-is-the-line invariant
  holds; `placements` records error the same way.

The design question to settle before building — and it is a real one — is
whether the fractional line is a **new level inside Touchdown Drive** (the pools
gain fraction targets, the field gains tick marks) or a **fourth cabinet**. My
reading: a level, not a mode. `Rules` already says what a placement costs and how
often it is due; nothing about fractions changes any of that, and the fourth
cabinet is the last one in the grid (`CLAUDE.md`, *Making the two likely
changes*), so it should be spent on a mode that needs different *rules*, not a
different *span*. But the level screen's four-columns-of-three is full too, which
makes this a layout decision either way.

The trap, stated in advance: the football metaphor breaks. Nobody throws to the
⅔ yard line. Either the fractional line gets its own art on the same mechanic
(a high-jump bar, a zip line, a tightrope), or the mode is honest that the field
is a number line and drops the yards. Given how much of this project's design
is spent on mechanic-and-metaphor agreement, this deserves the same treatment.

### 5.2 Division, and the fact-family flip

The cheapest real content on the list. `_MULTIPLY` levels deliberately yield only
`a × b = ?` and `a × ? = c`; the missing two forms are division, and 3.OA.C.7
names fluency with both by the end of grade 3. `ideas.md` already reserves the
dimmed column for it, so this is the content decision it says it is: how far the
tables go, and whether the game ever shows `12 ÷ 3` as a symbol or only ever as
`3 × ? = 12`.

The learning argument for doing both forms: showing the same triple in both
directions *is* the ×/÷ connection (grade 3 lesson 5), and interleaving them —
the strongest single effect in §2.1, *d ≈ 1.21* — is a selection change and not a
new mode. The measurement in §4.1 comes free.

### 5.3 Round the ball — estimation as a different question on the same line

3.NBT.A.1 is rounding to the nearest 10 and 100, and rounding is taught as a
computational rule ("look at the digit to the right") in a way that leaves no
magnitude understanding behind. On a number line it is the opposite: *which ten
is 47 nearer to* is the whole of it.

Cost is nearly zero against 5.1 — same placement, same span, a different prompt
and a coarser tolerance. Worth holding until the fractional line exists, then
adding as a second question type over one mechanic, because building both at once
is what makes the placement mode grow a rule for each.

### 5.4 Guess my rule, as a scoreboard

§3.4 ranked the function machine highly and it has now gained a curricular hook
at both ends: grade 3 lesson 7 (understand patterns, 3.OA.D.9) and grade 4
lesson 8 (number and shape patterns). It reuses the number pools, it is
generalisation rather than drill, and it is the only idea here that produces a
question the child cannot answer by computing faster.

It does need a new question shape (three rows shown, predict the fourth), which
is the seam `math-education.md` §6 flagged: a question is currently a `Fact`, and
a function-machine row is not one. That is the honest cost, and it is the same
cost for word problems and true/false sentences — which is an argument for
picking *one* of the three and letting it define the seam.

### 5.5 The scaled scoreboard — a free one

3.MD.B.3 is scaled bar graphs and pictographs, where each symbol stands for 5 or
10, and the skill is multiplying to read it. `draw_progress` currently draws pips.
Drawing them as a pictograph with a key ("each ball = 5 yards") puts a grade-3
Measurement & Data skill into a screen he already looks at twenty times a round,
costs one renderer change, and teaches nothing wrong if he ignores it. This is
not a mode and should not become one; it is the cheapest curricular contact in
the document.

### 5.6 What I would leave alone

- **Word problems** (units 3, and grade 4's multi-step). The evidence in §3.3 is
  strong and the content-authoring cost is real, but the bigger problem is that
  a keypad game with a two-line problem is a worksheet with sound effects. If it
  is ever built, build it for *structure* — the same numbers with the unknown in
  the start position — not for reading.
- **Area and perimeter** (lessons 27–30). Genuinely important, genuinely
  multiplicative, and a rectangle-building interaction is a different program
  from a keypad and a line. Worth its own dig later; not a variation on anything
  that exists.
- **Mass, liquid volume, line plots, quadrilaterals.** Grade-3 content that this
  game should not pretend to hold.

---

## 6. Recommendation

If one thing: **5.2, division and the flipped fact family**, because it finishes
a level family that is half-built, it is the named year-end fluency target, and
its mastery measurement already exists.

If two: add **5.1, the fractional number line**, and accept that it comes with a
metaphor decision. It is the highest-value item on the grade-3 list by the
evidence, and this codebase has already paid for the mechanic.

Before either, the thing that costs nothing: **look at the domain breakdown on
his actual i-Ready report**. Number and Operations high with Measurement & Data
lagging argues for something quite different from an even profile, and it is the
one input to this document I do not have.

---

## Sources

[ca]: https://www.curriculumassociates.com/programs/i-ready-learning/i-ready-classroom-mathematics-2024
[nysed]: https://www.nysed.gov/sites/default/files/iready-supplemental-assessment.pdf
[pace2]: https://s3.amazonaws.com/scschoolfiles/1912/readymathpacing2.pdf
[pace3]: https://s3.amazonaws.com/scschoolfiles/1912/readymathpacing3.pdf
[pace4]: https://s3.amazonaws.com/scschoolfiles/1912/readymathpacing4.pdf
[ss]: https://resources.finalsite.net/images/v1740428051/bethany/lkef1fhmorjocrym29cz/K-6iready-classroom-math-scope-sequence-k-8-ccss-2024.pdf
[ffo]: https://files.eric.ed.gov/fulltext/ED603592.pdf
[wwc]: https://ies.ed.gov/ncee/wwc/Intervention/1209
[nlr]: https://onlinelibrary.wiley.com/doi/am-pdf/10.1111/ldrp.12169
[cbm]: https://www.jimwrightonline.com/pdfdocs/cbaManual.pdf
[pelt]: https://coreypeltier.substack.com/p/curriculum-based-measures-in-math
[im]: https://illustrativemathematics.blog/2021/01/25/by-the-end-of-grade-3-developing-fluency-with-multiplication/
