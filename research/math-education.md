# Research: mastery, and what to practice after number bonds

Written to feed future game modes. The question behind it: for a second grader
who is *ahead*, not behind, what does the evidence say about (a) how mastery is
obtained and measured, and (b) what kinds of practice actually move a student
forward — given that repetition and memorization alone will not.

Everything here is sourced. Where the evidence is contested, it says so, because
the contested parts are exactly the ones this game already has an opinion about
(there is a clock, and it is on by default).

---

## 1. What "mastery" means, and how to measure it

### 1.1 Fluency is not speed, but it is not speed-free either

The consensus definition of procedural fluency has three parts — **accuracy,
efficiency, and flexibility** — not one. A student who gets `8 + 6` right by
counting up six is accurate and not fluent; a student who answers instantly but
cannot say why is efficient and not flexible. NCTM and the fact-fluency
literature converge on a developmental sequence: *counting → reasoning
strategies → mastery*, and mastery is only meaningful once the middle phase has
happened ([LD@School][ld], [Solution Tree][st]).

The operational bar most commonly cited for a mastered single-digit fact is
**an answer within ~3 seconds, by recall or by a highly efficient strategy** —
the strategy explicitly counts ([Understood][und], [MathFactLab][mfl]). That is
the same 3s this game already uses as `seconds_per_part`, which is a lucky
coincidence worth keeping rather than retuning by feel.

**Implication for the game:** a per-fact mastery flag should require *both* a
run of correct answers *and* response times under the level's threshold. The
repo already records `answered`, `right`, `wrong` and total `seconds` per fact,
so the slow-but-correct fact — the one a right/wrong count cannot see — is
already visible in the data. It is the single most valuable signal in
`progress.json` and nothing reads it yet.

### 1.2 Measure with a rate, not a percentage

The established practice for progress monitoring in arithmetic is
**curriculum-based measurement (CBM)**: short, fixed-length, mixed probes scored
as **digits correct per minute (DCPM)** rather than problems correct, so partial
credit and finer gradations survive. Two-minute probes are typical; a widely
cited benchmark is that students computing at ~30–40 problems/min (≈70–80 DCPM)
keep accelerating as the curriculum gets harder ([Wright, CBM manual][cbm],
[Peltier][pelt]).

Two flavours matter here:

- **Specific Subskill Mastery** — probe one skill, watch it top out. This is what
  a level in this game is.
- **General Outcome Measurement** — probe a fixed mixed set repeatedly over
  months, watch the trend line. This is what the game currently has *no*
  equivalent of, and it is the measurement that answers "is he actually getting
  better?" rather than "did he win this round?"

**Implication:** a periodic, fixed, mixed probe — same items every time, untimed
UI but timed internally, no rocket — would give a real trend line. It is the
only honest answer to "is the pacing right for him", which `CLAUDE.md` currently
lists as unanswerable in code.

### 1.3 Mastery as a probability, not a streak

Intelligent tutoring systems solved this problem properly. **Bayesian Knowledge
Tracing** (Corbett & Anderson, 1995) models each skill with four parameters —
prior, learn rate, guess, slip — and updates a posterior probability of mastery
after every response. Cognitive Tutor's "adaptive mastery" retires a skill when
P(mastery) ≥ **0.95** and keeps assigning problems otherwise ([BKT
overview][bkt], [Baker et al.][baker]).

This is a small amount of arithmetic — a handful of lines in a pure function —
and it is a much better retirement rule than "three in a row". Guess and slip
matter here specifically: with a two-digit typed answer the guess rate is near
zero, but the *slip* rate for an excited seven-year-old on a keypad is not, and
a streak rule punishes a typo as if it were ignorance.

**Implication:** `domain/` is the right home for a `mastery(fact_history) ->
float`. It is pure, testable, and it turns the existing per-fact counts into a
selection policy without any new storage shape.

### 1.4 For a gifted student, measure above level

The single most robust finding in gifted education is Julian Stanley's:
**identify with above-level testing, then accelerate.** Grade-level instruments
hit the ceiling and tell you nothing; a test aimed two or more years up
discriminates. SMPY built five decades of longitudinal evidence on this, and the
acceleration meta-analyses are unusually clean: accelerated students outperform
same-age non-accelerated peers at **g ≈ 0.70**, and perform *no differently* from
older non-accelerated peers (g ≈ 0.09) — i.e. acceleration moves a student to
where they belong without costing them anything ([Steenbergen-Hu, Makel &
Olszewski-Kubilius, 2016][shu]; [SMPY][smpy]; [Davidson Institute][dav]).

Stanley's own instructional protocol, **DT–PI (Diagnostic Testing followed by
Prescriptive Instruction)**, is directly implementable in software: test broadly
above level, find the specific gaps, teach *only* those, re-test. The
anti-pattern it exists to prevent is making a fast student sit through the 80%
they already know.

**Implication:** the strongest thing this game could do for this particular child
is not a better rocket. It is to stop re-asking mastered facts, and to let
content run ahead of second grade. `ideas.md` already lists two-digit work and
multiplication; the evidence says that is the right direction and that the
worry about "going too fast" is the empirically weaker position.

---

## 2. What practice works

Ranked by strength of evidence for *this* age and this kind of content.

### 2.1 Interleaving — strongest, and cheapest to build

Practice is *interleaved* when consecutive problems cannot be solved by the same
method, so the student must first decide **which** method applies. Blocked
practice removes that decision, which is most of the difficulty and most of the
learning.

Taylor & Rohrer (2010), fourth graders: interleaved practice scored **77% vs 38%**
on a next-day test, *d ≈ 1.21*. Rohrer et al.'s later randomized classroom trial
replicated the effect at scale ([Rohrer, practice guide][rohrer-guide];
[Rohrer et al., RCT][rohrer-rct]).

Two caveats that matter for design:

- **It feels worse while it is happening.** Performance during interleaved
  practice is lower than during blocked practice; the advantage appears on the
  delayed test. A game that rewards in-session performance will make interleaving
  look like a bug.
- Every study provided **feedback and error correction**. Interleaving without
  feedback is not the tested intervention.

**Implication:** this is nearly free here. `domain/round.py` draws from one
level's pool. A mixed pool drawing across levels — and, later, across operations
— is a question-selection change, not a new mode. Expect scores to dip.

### 2.2 Spacing — solid, smaller in math than elsewhere

The 2025 meta-analysis of spacing and retrieval practice *specifically in
mathematics* found spaced > massed at **g = 0.28** (27 studies) — real, but
smaller than the general-psychology numbers usually quoted. Notably, the same
review found the **testing effect was not robust in math**: the confidence
interval crossed zero, on a thinner literature ([meta-analysis][meta],
[summary][meta-sum]).

This is a useful corrective. "Retrieval practice" is the mechanism this game
already leans on (the `RETRY_GAP` re-queue is textbook spaced retrieval), and it
is worth knowing that in math the evidence for it is thinner than the internet
suggests, while the evidence for *spacing across sessions* is decent.

**Implication:** `RETRY_GAP = 3` spaces within a round. Nothing spaces across
days. A "facts due today" selection — pulling facts last seen 2, 5, 12 days ago —
is where the g = 0.28 lives, and it needs only a `last_seen` timestamp beside
each fact (an additive field, so no `version` bump; see `CLAUDE.md`).

### 2.3 Worked examples and self-explanation — for anything new

For content the student has not met, the worked-example effect is well
established, and **faded** worked examples (full example → partial → solo) beat
both pure examples and pure problem solving: comparable procedural skill in
*less* time, plus deeper conceptual knowledge ([Booth et al.][booth];
[worked-example effect][we]).

Layered on top, **self-explanation** ("why does that step work?") yields its
largest gains on *conceptual* outcomes rather than procedural ones
([meta-analysis][selfexp]). And in computer-based learning, **elaborated**
feedback (an explanation) is worth *d ≈ 0.49* against *d ≈ 0.05* for
correct/incorrect alone and *0.32* for revealing the right answer ([Van der Kleij
et al., 2015][vdk]).

**Implication, and it is a sharp one:** the game's current feedback is the
*0.05* kind — a part falls off. Showing, on a miss, the *strategy* rather than
the answer (`8 + 6` → `8 + 2 + 4`) moves it toward the *0.49* kind. That is the
highest-value change per line of code in this whole document, and it is a
`shell/draw.py` change plus a strategy annotation on `Fact`.

Feedback *timing* turns out not to matter much on average — a recent meta-analysis
finds no reliable difference between immediate and delayed ([Educational
Psychology Review][fbtiming]) — so keeping it immediate, which suits a game, costs
nothing.

### 2.4 Problem-solving instruction — what the IES guide actually says

The WWC/IES practice guide *Improving Mathematical Problem Solving in Grades 4
Through 8* makes five recommendations, with graded evidence ([WWC][ies]):

| # | Recommendation | Evidence |
|---|---|---|
| 1 | Prepare problems and use them in whole-class instruction | Minimal |
| 2 | **Assist students in monitoring and reflecting on the problem-solving process** | **Strong** |
| 3 | **Teach students how to use visual representations** | **Strong** |
| 4 | Expose students to multiple problem-solving strategies | Moderate |
| 5 | Help students recognize and articulate concepts and notation | Moderate |

The two *strong* ones are both about metacognition and representation, and both
are buildable: #3 is a bar model or number line drawn on screen; #2 is a prompt
between problems ("which of these was hardest? why?") or a mode where the student
predicts their own answer before solving.

Recommendation #4 is the interesting one for a gifted student: **multiple
strategies for the same problem**, which is the "flexibility" leg of fluency and
the thing pure fact drill never touches.

### 2.5 Non-routine problems and productive struggle

For gifted elementary students specifically, the literature is consistent that
**non-routine problems** — no immediately obvious method, multiple entry points,
sometimes multiple answers — are where their characteristics get exercised.
Studies of gifted fourth graders find success comes with **strategic
flexibility**: making systematic lists, building tables, working backwards,
estimating and checking — and that flexibility, not raw speed, is what separates
levels of success ([Frontiers, 2025][front]; [non-routine case study][nonr]).

"Productive struggle" is the design constraint: slightly above comfort, solvable
with resources or a hint, not solvable instantly.

**Implication:** a mode where the answer is *not* a single number — build a total
from given pieces, find every pair that makes 12, order operations to hit a
target — is qualitatively different from anything the game does now and is the
most defensible "advanced" mode.

---

## 3. What to practice next (content, not mechanics)

Four strands with real evidence behind them, all reachable from where the game
already is.

### 3.1 Relational thinking and the equal sign

The best-documented misconception in elementary arithmetic: children read `=` as
**"write the answer here"** rather than **"the same as"**. Carpenter's
true/false and open number sentence tasks (`3 + 5 = 8`, `8 = 3 + 5`, `8 = 8`,
`3 + 5 = 5 + 3`, `7 + 6 = ? + 5`) directly dismantle it and are the standard
gateway from arithmetic into algebra ([Carpenter et al. via review][rel];
[equal sign research][eqsign]).

This is the **highest-leverage content extension available**, because the game is
already 80% of the way there: `8 + ? = 10` puts the unknown in a non-final
position, which is exactly the move. What is missing is:

- **true/false judging** — show a sentence, answer *yes* or *no*. A different
  input (two buttons, no keypad) and a different `Outcome` source, nothing more.
- **both-sides sentences** — `7 + 6 = ? + 5`. Solvable *relationally* (one more
  on the left, so one less needed... ) rather than by computing. A child who
  computes 13 then subtracts 5 gets it right; a child who reasons gets it right
  faster. The response-time data can literally tell these apart.

### 3.2 Magnitude and the number line

Siegler's line of work is unusually strong: accuracy at placing numbers on a
number line predicts later math achievement, and **first-grade whole-number
number-line estimation predicts seventh-grade fraction arithmetic**, mediated by
fraction magnitude understanding ([Siegler & Braithwaite][sieg]; [Bailey et al.
via review][bailey]).

Estimation is also *not* a fact-recall skill, so it cannot be gamed by
memorizing, which is exactly the brief.

**Implication:** a "place the number" mode — drag a marker to where 37 goes on a
0–100 line, scored by distance rather than right/wrong — is a genuinely different
skill, needs no arithmetic pool, and feeds the strongest longitudinal predictor
in the literature. It does require an `Outcome` richer than boolean, which is a
real design question for `domain/round.py`.

### 3.3 Word-problem *structure* (CGI)

Cognitively Guided Instruction classifies addition/subtraction situations into
**join, separate, part-part-whole, and compare**, each with the unknown in
different positions (result / change / start; whole / part; difference /
quantity / referent). Difficulty varies enormously by structure — *start
unknown* and *compare* problems are far harder than *result unknown* at the same
numbers — and students taught to recognize structure outperform students taught
keyword tricks ([CGI problem types][cgi]; [overview][cgiwiki]).

**Implication:** this is a real difficulty axis that is *independent of number
size*, which is precisely what an advanced student needs — harder thinking, not
bigger numbers. A `bridge`-level child who can do `15 − 7` instantly may still
be stopped cold by "Sam had some marbles, gave away 7, and has 8 left."

### 3.4 Functional thinking — "guess my rule"

Early algebra research (Blanton & Kaput and successors) frames four practices:
generalizing relationships, representing them, reasoning with them, justifying
them. **Function machines / "guess my rule"** is the classic elementary vehicle
([functional thinking assessment][ft]; [developmental progression][ftprog]).

**Implication:** the cleanest possible new mode. Input goes in, output comes out,
three examples shown, the child predicts the fourth and then names the rule. It
reuses the number pools, it is not drill in any form, and generalization is the
defining move of mathematical thinking.

### 3.5 A note on spatial reasoning

Fifty years of SMPY data show spatial ability is a strong, **routinely
unmeasured** predictor of STEM accomplishment, and talent searches that ignore it
underserve exactly the students who have it ([Wai & Lubinski][wai]; [neglected
talent][spatial]). Spatial skills are trainable (meta-analysed as malleable), but
**transfer from spatial training to mathematics achievement is mixed** — some
broad transfer, some narrow, some none ([transfer study][sptransfer]).

So: worth including for its own sake and as a signal, not defensible as a way to
improve arithmetic.

---

## 4. The timed-clock question, honestly

This game has a clock and an alien, so the fairest possible summary:

- **NCTM's position statement (2023)** holds that timed tests do not assess
  fluency and can harm students. The most-repeated supporting claim — that about
  a third of students develop math anxiety from timed testing — traces to a
  practitioner article, not a controlled study ([Fluency Without Fear][fwf];
  [critique][som]).
- **The first direct empirical test** (Journal of School Psychology, 2024; 113
  fourth and fifth graders, timed and untimed tasks, anxiety measured before and
  after) found **no statistically significant effect of timing on self-reported
  anxiety**. Students with math difficulties *and* high initial anxiety actually
  performed better and rated the task *easier* under overt timing ([study][jsp];
  [coverage][edweek]).

The honest reading: the strong claim that timing causes anxiety is not
established, and the mechanism most likely runs through *stakes and public
comparison* rather than the presence of a clock. This game has no class ranking,
no grade, and an off switch. That is roughly the configuration the evidence is
least worried about.

Two design cautions survive regardless:

1. A clock that is tight enough to punish a *correct but slow* answer will
   suppress the strategy use that the 3-second definition explicitly allows.
   Pace by level, which the game already does.
2. Time pressure and **interleaving** fight each other, because interleaving
   deliberately depresses in-session performance. If a mixed-pool mode is added,
   it probably wants a longer `seconds_per_part` or no clock at all — otherwise
   the mode that teaches best is the mode he loses at.

---

## 5. Candidate game modes, ranked

Ranked by (evidence strength × distance from what already exists) ÷ build cost.
Every one of these consumes the same `Outcome` stream unless noted.

| # | Mode | What it trains | Evidence | Cost |
|---|---|---|---|---|
| 1 | **Strategy feedback on a miss** (not a mode — a change) | reasoning phase of fluency | elaborated feedback *d ≈ 0.49* | small: annotate `Fact`, draw it |
| 2 | **True / false number sentences** | relational `=`, the algebra gateway | strong, well-replicated misconception work | small: new input, same pools |
| 3 | **Mixed pool across levels** | discrimination, strategy selection | interleaving *d ≈ 1.21* | small: selection change |
| 4 | **Guess my rule / function machine** | generalization | early-algebra research base | medium: new screen, no new domain |
| 5 | **Spaced review across days** | retention | spacing *g = 0.28* | small: `last_seen` field + selection |
| 6 | **Number-line placement** | magnitude — the long-range predictor | Siegler, longitudinal, strong | medium: needs non-boolean `Outcome` |
| 7 | **CGI-structured word problems** | problem structure, non-keyword reading | strong; hardest axis to fake | medium: content authoring |
| 8 | **Target / open-middle puzzles** | non-routine, productive struggle | good for gifted specifically | medium-large: new scoring |
| 9 | **Fixed mixed probe (measurement, not a game)** | *measuring* the trend | CBM, decades of use | small, but needs a parent UI |

Items 1, 2, 3 and 5 are all small, and between them they cover elaborated
feedback, relational thinking, interleaving and spacing — the four
best-supported ideas in this document.

---

## 6. Where this bumps into the current architecture

Noted, not proposed. Each is a real design question, and `plan.md` conventions
say make the case before building the abstraction.

- **`Outcome` is boolean.** Modes 6 and 8 produce a *degree* of correctness
  (distance from the true position; number of valid solutions found). Either they
  threshold it into a boolean at the mode boundary — cheapest, probably right —
  or `Outcome` grows, which touches every mode.
- **A question is currently a `Fact`.** A true/false sentence, a function-machine
  row and a number-line target are not facts with a missing operand. The
  question-generation seam, not `Round`, is what needs to generalize — `Round`
  already only counts parts.
- **Selection is uniform-random within a level.** Modes 3 and 5 and the whole of
  §1.3 want a *policy* — mastery-weighted, due-date-weighted, mixed-pool. That
  policy is pure, testable, and belongs in `domain/`. It is the one new
  abstraction this research actually argues for.
- **`progress.json` already holds what mastery estimation needs** except a
  `last_seen` timestamp. Adding it is an additive field read through `.get`, so
  no `version` bump — the same reason adding the clock needed none.

---

## Sources

[ld]: https://www.ldatschool.ca/the-importance-of-math-fact-fluency-evidence-informed-classroom-practices/
[st]: https://www.solutiontree.com/blog/beyond-fact-fluency-making-the-most-of-instruction-with-basic-facts/
[und]: https://www.understood.org/en/articles/fact-fluency-an-evidence-based-math-strategy
[mfl]: https://mathfactlab.helpscoutdocs.com/article/68-the-foundational-research-behind-mathfactlab
[cbm]: https://www.jimwrightonline.com/pdfdocs/cbaManual.pdf
[pelt]: https://coreypeltier.substack.com/p/curriculum-based-measures-in-math
[bkt]: https://www.emergentmind.com/topics/bayesian-knowledge-tracing-bkt
[baker]: https://learninganalytics.upenn.edu/ryanbaker/BCA2008W.pdf
[shu]: https://journals.sagepub.com/doi/abs/10.3102/0034654316675417
[smpy]: https://my.vanderbilt.edu/smpy/researchers/julian-c-stanley/
[dav]: https://www.davidsongifted.org/gifted-blog/eight-considerations-for-mathematically-talented-youth/
[rohrer-guide]: https://files.eric.ed.gov/fulltext/ED595322.pdf
[rohrer-rct]: https://gwern.net/doc/psychology/spaced-repetition/2019-rohrer.pdf
[meta]: https://eprints.whiterose.ac.uk/id/eprint/229807/
[meta-sum]: https://tipsforteachers.co.uk/research-a-meta-analytic-review-of-the-effectiveness-of-spacing-and-retrieval-practice-for-mathematics-learning/
[booth]: https://files.eric.ed.gov/fulltext/ED566953.pdf
[we]: https://www.sciencedirect.com/science/article/abs/pii/S0747563208002161
[selfexp]: https://www.researchgate.net/publication/313794629_Promoting_self-explanation_to_improve_mathematics_learning_A_meta-analysis_and_instructional_design_principles
[vdk]: https://journals.sagepub.com/doi/abs/10.3102/0034654314564881
[fbtiming]: https://link.springer.com/article/10.1007/s10648-026-10117-8
[ies]: https://ies.ed.gov/ncee/wwc/PracticeGuide/16
[front]: https://pmc.ncbi.nlm.nih.gov/articles/PMC12394163/
[nonr]: https://nasenjournals.onlinelibrary.wiley.com/doi/10.1111/1471-3802.12695
[rel]: https://files.eric.ed.gov/fulltext/EJ1184961.pdf
[eqsign]: https://files.eric.ed.gov/fulltext/ED514405.pdf
[sieg]: https://siegler.tc.columbia.edu/wp-content/uploads/2019/11/2017-Siegler-Braithwaite-NumDev.pdf
[bailey]: https://siegler.tc.columbia.edu/wp-content/uploads/2019/02/2014-FazioBaileyThompSiegler-fac.pdf
[cgi]: https://lor2.gadoe.org/gadoe/file/89ebbb03-20aa-4980-ba78-c908bfcb2b60/1/CGI-Problem-Types.pdf
[cgiwiki]: https://en.wikipedia.org/wiki/Cognitively_Guided_Instruction
[ft]: https://cdn.vanderbilt.edu/vu-sub/wp-content/uploads/sites/280/2023/08/04182337/ATME_McEldoonandRittle-JohnsonPME-NApaper_2010-1.pdf
[ftprog]: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10744471/
[wai]: https://www.semanticscholar.org/paper/Spatial-ability-for-STEM-domains:-Aligning-over-50-Wai-Lubinski/ca3d6205ffb8cab6724fb0828634826e2e87ead7
[spatial]: https://www.tandfonline.com/doi/abs/10.1080/02783193.2013.829896
[sptransfer]: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9035498/
[fwf]: https://www.youcubed.org/evidence/fluency-without-fear/
[som]: https://www.thescienceofmath.com/timed-tests-cause-math-anxiety
[jsp]: https://www.sciencedirect.com/science/article/abs/pii/S0022440524000360
[edweek]: https://www.edweek.org/teaching-learning/do-timed-tasks-really-worsen-math-anxiety/2024/08

**Fluency and mastery**
- [The Importance of Math Fact Fluency — LD@School][ld]
- [Beyond Fact Fluency — Solution Tree][st]
- [Fact fluency: an evidence-based strategy — Understood][und]
- [MathFactLab research foundations][mfl]
- [Curriculum-Based Measurement: A Manual for Teachers — Jim Wright][cbm]
- [Curriculum-Based Measures in Math — Corey Peltier][pelt]
- [Bayesian Knowledge Tracing overview][bkt] · [Baker et al., contextual estimation of guess and slip][baker]

**Gifted / acceleration**
- [Steenbergen-Hu, Makel & Olszewski-Kubilius (2016), 100 years of ability grouping and acceleration][shu]
- [Julian C. Stanley and SMPY — Vanderbilt][smpy]
- [Eight considerations for mathematically talented youth — Davidson][dav]

**Practice design**
- [Rohrer, Interleaved Mathematics Practice guide][rohrer-guide] · [Rohrer et al., randomized controlled trial][rohrer-rct]
- [Meta-analytic review of spacing and retrieval practice for mathematics learning (2025)][meta] · [summary][meta-sum]
- [Booth et al., worked example effect][booth] · [The worked-example effect][we]
- [Promoting self-explanation: meta-analysis][selfexp]
- [Van der Kleij et al. (2015), feedback in computer-based learning][vdk]
- [Meta-analysis of feedback timing in computer-assisted learning][fbtiming]
- [IES/WWC, Improving Mathematical Problem Solving in Grades 4–8][ies]
- [Non-routine problem solving and strategic flexibility in gifted fourth graders][front] · [case study][nonr]

**Content strands**
- [Students' early grade understanding of the equal sign][eqsign] · [relational thinking review][rel]
- [Siegler & Braithwaite, Numerical Development][sieg] · [Fazio, Bailey, Thompson & Siegler][bailey]
- [CGI problem types][cgi] · [CGI overview][cgiwiki]
- [Assessing elementary students' functional thinking][ft] · [developmental progression of early algebraic thinking][ftprog]
- [Wai & Lubinski, spatial ability for STEM][wai] · [Spatial ability: a neglected talent][spatial] · [does spatial training transfer?][sptransfer]

**The timed-test debate**
- [Fluency Without Fear — YouCubed][fwf] (the position) · [The Science of Math critique][som] (the rebuttal)
- [Math anxiety in elementary students: timing and task complexity, J. School Psychology 2024][jsp] · [Education Week coverage][edweek]
