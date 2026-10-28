# TakeMeter

> ### 👋 Start here
>
> **New to this repo? Read [RUNNING.md](RUNNING.md) first** — setup, the
> notebook, the baseline, and what to do when something breaks.
>
> Once `python test.py` passes:
>
> ```bash
> head -5 data/practice_labels.csv     # the shape your labels.csv needs
> ```
>
> Then open `takemeter.ipynb` **in this folder** — in VS Code, or with
> `jupyter notebook` if you prefer. Pick the kernel: the `.venv` inside this
> project. Run section 1, which reports the hardware you'll be training on.
> Everything else waits until you have data.
>
> Nothing to upload, nothing to connect, no accounts and no keys. The notebook
> runs on your machine and writes next to your code.
>
> **The rest of this file is your submission.** Fill it in as you go.

---

<!-- ─────────────────────────────────────────────────────────────────────────
     HOW TO USE THIS FILE

     Unit 5 asks for the first five sections. Unit 6 adds the five below them.

     Everything is pasted as TEXT. No screenshots, no images.

     ⚠️ The confusion matrix especially. The notebook prints one as a markdown
     table, ready to copy. A screenshot of a matrix earns nothing. Paste the
     table.
     ───────────────────────────────────────────────────────────────────────── -->

<!-- ═══════════════════════ UNIT 5 — THE BUILD ═══════════════════════ -->

## What This Does

TakeMeter sorts posts from the Smogon competitive Pokemon forums (mostly tier-shift, tiering-policy, and metagame threads) by how well a post backs up what it says. Each post is labeled `analysis` (an opinion backed by something checkable), `hot_take` (a confident claim with no checkable support), or `chatter` (social or reaction posts that make no claim about the game). The goal is to tell a reasoned argument from a bare opinion regardless of tone. A fine-tuned DistilBERT does the sorting, and I compare it against a zero-shot baseline.


---

## Label Taxonomy

<!-- Each label: a one-sentence definition and two real examples from your
     reading. Then your decision rule for the hardest boundary.

     The decision rule is worth a point on its own and it's the thing most
     people leave out. Every taxonomy has a hardest boundary. Name yours. -->

### `analysis`

**Definition:** an opinion about Pokemon, tiers, or tiering policy backed by something checkable (a usage stat, a named matchup result, a mechanic, a rule or vote outcome); the evidence must support the post's main claim, not merely be its topic

**Example 1:**
> SnackWasTaken said: Now I have proof that Basculegion is overrated Basculegion is overrated Basculegion is overrated Basculegion is overrated Come on, it even fell to UU. That's gotta say something, right? Click to expand... It says that mons with 2 forms which are basically equivalent get hurt by the 4.52% threshold. The sum of their usage is higher than 5% in any case

**Example 2:**
> Power Panpour said: I have no idea how people gaslit themselves into thinking Thwackey was THAT good. At the beginning of the HOME meta I could understand cuz of new toy syndrome, but after the Teal Mask I had no clue why people were still using that awful thing. Click to expand... I think it's a bit disingenuous to say that people gaslit themselves into thinking thwackey was good, given that it was banned to NUBL by suspect . a month and a bit later grassy surge was banned which was the only reason for thwackey's unban and subsequent drop.

### `hot_take`

**Definition:** a confident claim or judgment about the game, its tiers, or its rules and formats with no checkable support; general reasons ("it's stupid", "it's deadweight") don't count as support

**Example 1:**
> Kingambit being top 3 in the current OU meta and top 1 in National dex. I have never doubt our supreme overlord

**Example 2:**
> HydreigonTheChild said: OU is never giving us dondozo, its the arcanine, forretrress, donphan of UU Click to expand... Least Donphan isn't totally terrible in UU and has some applications. Dozo just is mid af and should've dropped ages ago but somehow it's held on by a thread Don't even understand why either. Not exactly a popular Mon like Garchomp in terms of fans, and it isn't exactly flashy since it's a stall staple mostly, and low ladder isn't exactly where you see stall often.

### `chatter`

**Definition:** social or immediate-reaction posts that make no claim about the game, its tiers, or its rules: thanks, jokes, hype, venting, remarks about your own games or ladder run

**Example 1:**
> omg tysm for the noms/votes in these two categories and no other categories as i definitely DID NOT win anything else ok but fr literally all 7 of those ppl contribute more to the discord than me, they were robbed LOL

**Example 2:**
> TheMantyke said: So when do I get my prize money for being the last one on the Orange Islands? This is like Survivor, right? I never did get to use my immunity Amulet Coin. Click to expand... nah this is hunger games and now that u have ur sponsors the fun part is about to begin

### The hardest boundary

**Which two labels:** `analysis` and `hot_take`

**The decision rule I used every time:**
If the post names something specific that someone else could check (a stat, a rule or mechanic, a named matchup, a vote result) and the argument depends on it, it is `analysis`, even if the tone is heated. Otherwise it is `hot_take`, even if the tone is calm.

**Calm but `hot_take`:**
> boulder being ass is really not what i expected. i guess all its offensive traits couldn't make up for it effectively being deadweight into bulkier teams and having very, VERY little defensive utility

It gives reasons, but none can be checked against a number, a mechanic, or a named matchup.

**Heated but `analysis`:**
> How are people still saying Treads should be in UU, home made it a lot better since it can 1v1 the common heatwaveless Zapdos and spin on it which Tusk cannot do for example. It's better speed tier also helps it find a niche on HO as a decent spinner as well as still carrying the utility of knock off that Tusk has. The time for Treads slander has to stop, it is no longer the OU equivalent of UU holding on to Forretress.

The tone is annoyed, but the argument rests on a named matchup (Treads vs. heatwaveless Zapdos), a speed-tier comparison, and a specific move (Knock Off).



---

## The Dataset

<!-- Where you collected from, how you labelled, your counts, and three hard
     cases. -->

**Where the posts came from:** 225 public posts from 18 threads on the Smogon competitive Pokemon forums, collected with a script (Playwright plus BeautifulSoup) in [`data_collection/`](data_collection/). A filter ([`inscope.py`](data_collection/inscope.py)) keeps only posts that can take one of the three labels. The first 200 came from 12 threads, mostly tier-update threads, so the set leans toward tier-shift discussion. I added 25 posts from 6 other thread types (viability rankings, metagame discussion, suspect tests, council) to widen it. [`labels_ids.csv`](labels_ids.csv) records the post ID and permalink for every row of [`labels.csv`](labels.csv).

**How the 225 were assembled:** The final set isn't the output of one scraper run. I scraped Smogon threads in several rounds, changing the plan between rounds. The scripts and [`sampling_plan.md`](data_collection/sampling_plan.md) in `data_collection/` show the tooling and the intended design, and `sample_manifest.json` records only one of those runs (it covers 54 of the final 225 posts). Each round gave a pool of posts that passed the `inscope.py` filter. Claude Code then suggested candidates from those pools, and I kept the ones that gave variety across threads, tiers, years, and the three labels. Because the selection was partly AI-suggested rather than random, the dataset isn't a random sample of Smogon posts, and the per-label counts reflect which posts were chosen.

**How I labelled them:** I labelled in an interactive session with Claude Code, and `labels_ids.csv` records how each row was labelled:

- **20 posts cold.** I labelled these myself before seeing any AI suggestion.
- **205 posts pre-labelled by Claude Code.** I reviewed only the calls Claude flagged as unsure (see How I Used AI). I changed the label on 13 (`corrected` in `labels_ids.csv`): the AI had said `hot_take` for 6, `analysis` for 4 and `chatter` for 3. The other 192 keep the AI's label.

Because 192 labels are the AI's judgment that I kept, most of them unreviewed, the model is partly learning Claude's reading of my label definitions.

**Counts per label:**

| Label | Count | Share |
|---|---|---|
| `analysis` | 66 | 29.3% |
| `hot_take` | 68 | 30.2% |
| `chatter` | 91 | 40.4% |
| **Total** | 225 | 100% |

**Three hard cases**

**1.**
> *The post:* "So... taking pokemon from a tier because it has high usage in the tier above is not allowed because it would impact the former, i get it. But the same happens if pokemon are allowed to drop from the tier above. Not letting, lets say, Latios rise to OU because it would shake UU makes sense, but letting Heatran and Tyranitar drop from OU affects UU in a similar way, it changes the meta. I dont get this tiering decision."
>
> *Could have been:* `analysis` or `hot_take`
>
> *I chose* `hot_take`*, because:* it is a calm, structured argument and Claude Code labelled it `analysis`, but nothing in it can be checked. It names Pokemon and a tiering rule, but gives no usage figure, vote result or matchup. The argument is a comparison between two policies, and the conclusion is "I don't get this tiering decision".

**2.**
> *The post:* "I'm sorta going back on the entire "we should ban Regidrago" right now... I don't think that time is now, when we have Pokemon that I see as broken running around. Iron Crown's finally getting more use than just the Weakness Policy set... Booster Energy: Special Attack sets are incredibly good right now... there's just not that much in terms of reliable counterplay to Iron Crown, especially since setguessing can be a bit challenging due to how many matchups each set can just win with Tachyon Cutter... a look at the VR can probably tell you how many matchups this Pokemon can cover with juts a few sets."
>
> *Could have been:* `hot_take` or `analysis`
>
> *I chose* `analysis`*, because:* Claude Code labelled it `hot_take` because it opens with a confident opinion and the writer says they won't go into detail. The argument is built on named sets and a named move (Tachyon Cutter), and the viability rankings are cited as a place to check it. That is support someone else could check, and it backs the main claim that Iron Crown is the more urgent problem.

**3.**
> *The post:* "What are your thoughts on the inevitable return of blaziken and serperior? I know serperior has always had issues with coverage and blaziken has always had severe 4mss and got walled hard by the bulky waters, but blaziken to me feels like its just going to be chi-yu/ogerpon-hearthstone v2.0, but stronger thanks to tera and much harder to revenge kill thanks to speed boost and the fact that most of the bulky waters got nerfed hard this gen too, oh and serperior just nukes everything with its multiple viable tera sets... Is there any preemptive talk right now in the council about whether or not a vote will need to be held..."
>
> *Could have been:* `analysis` or `hot_take`
>
> *I chose* `hot_take`*, because:* Claude Code labelled it `analysis` because it is full of specifics (4MSS, Speed Boost, Tera sets, nerfed bulky waters). Those specifics describe the mechanics, but they support a prediction ("inevitable return", "v2.0, but stronger"). No usage result or tested matchup backs the claim that these two will be broken. The mechanics are only the topic, which my rule says is not enough.

---

## The Training Run

<!-- Your starting model, your settings, and anything you changed and why. -->

**Base model:** `distilbert-base-uncased`, fine-tuned for 3-way classification (`analysis`, `hot_take`, `chatter`) with the training notebook [`takemeter.ipynb`](takemeter.ipynb).

**Settings:** 3 epochs, learning rate 2e-5, batch size 16, max length 128 tokens, seed 42. I trained on CPU (torch 2.14.1+cpu), and `results.json` records this.

**Anything I changed from the defaults, and why:** Nothing. I kept the notebook's defaults for every setting. I had no evidence yet to justify changing any of them, and I wanted the first run to be a baseline I could improve against later.

**Split sizes:** a stratified 70/15/15 split of the 225 posts, which gives 157 train, 34 validation and 34 test. Per-label counts in the test split:

| Label | Test count |
|---|---|
| `analysis` | 10 |
| `hot_take` | 10 |
| `chatter` | 14 |
| **Total** | 34 |

No label falls below 8 in the test split, but 10 posts per label is still small. One post moves a per-label score by 10 points (for `analysis` or `hot_take`), so I expect the numbers to move between seeds.

**Result of this run (seed 42):** accuracy 0.588, macro F1 0.483. `chatter` did best (F1 0.757, recall 1.00). `hot_take` did worst (F1 0.167, 1 of 10 correct). The model's confidence barely separated right answers from wrong ones (mean 0.39 when right, 0.38 when wrong). I haven't interpreted these numbers yet. That is for the baseline comparison and the three-seed run.


---

## How I Used AI

<!-- Two specific moments — what you asked, what came back, what you changed.

     ⚠️ Plus disclosure of any pre-labelling. If you had a model pre-label a
     batch and then read and corrected every one, say that. It's an allowed
     workflow and disclosing it costs you nothing. Not disclosing it is the
     problem. -->

**Moment 1: checking the scraped data against my sampling plan**

- *What I asked for:* Whether my scraped pool covered my sampling plan, checked again after I revised the plan and re-scraped.
- *What came back:* No, both times. The first pool had 564 posts from only 12 threads (plan: 25–35), no RMT threads because my `inscope.py` filter drops them, and few recent posts. After my revised plan, a leftover post limit in Claude's scraper edit stopped the re-scrape at 14 of 28 threads. The final pool has 752 posts from 19 threads, but no Doubles/VGC threads.
- *What I changed:* I dropped the RMT quota, rewrote the plan around opinion-bearing threads, and approved the scraper and `subsample.py` changes (10 posts per thread max). I never reached the plan's 28 threads or any Doubles/VGC threads. Instead I added 25 posts from 6 other thread types (viability rankings, metagame discussion, suspect tests, council), which brought the final set to 225 posts from 18 threads.

**Moment 2: pre-labelling the posts with Claude Code**

- *What I asked for:* To label every post using my Label Taxonomy, with the note set to `pre-labeled` (the first 20 were my own `cold` labels).
- *What came back:* A label for each post. Claude flagged 35 as `pre-labeled; unsure`, "my least confident calls."
- *What I changed:* I reviewed only those 35. I removed `; unsure` where I agreed. Where I disagreed, I changed the label and noted `corrected pre-label (was hot_take)`. I didn't check the rest because of time.

**Pre-labelling disclosure:** 20 labels are mine (`cold`). Claude pre-labelled the other 205. I reviewed only its `unsure` calls and corrected 13 labels. The other 192 are unreviewed or confirmed `unsure` posts, so many labels reflect Claude's reading of my definitions.

<!-- ═══════════════════════ UNIT 6 — THE TEST ═══════════════════════

     Don't fill these in during unit 5.
     ═══════════════════════════════════════════════════════════════════ -->

---

## Baseline vs. Trained

<!-- Both models on the same posts. `python baseline.py --trained results.json`
     prints this table for you. -->

| Measure | Baseline | Trained | Difference |
|---|---|---|---|
| Overall accuracy | 0.324 | 0.588 | +0.265 |
| Macro F1 | 0.225 | 0.483 | +0.258 |
| F1 — `analysis` | 0.439 | 0.526 | +0.087 |
| F1 — `hot_take` | 0.000 | 0.167 | +0.167 |
| F1 — `chatter` | 0.235 | 0.757 | +0.521 |

Both models were scored on the same 34 posts in `test_split.csv`, seed 42.

**What I predicted before I looked:**
<!-- Milestone 1 asks you to write this BEFORE seeing the trained numbers. A
     prediction made afterwards isn't one. -->
I had seen the trained results (accuracy 0.588, macro F1 0.483) but no baseline numbers. I predict the baseline scores 0.45–0.55 accuracy. It should beat the trained model on `hot_take` (1 of 10 correct), since zero-shot reads my definition directly instead of learning from 157 noisy examples. I expect the trained model to keep its edge on `chatter`. I expect the baseline's weakest spot to be `analysis` vs. `hot_take`, the boundary I called noisiest.

**What the gap actually means:**
<!-- If the baseline matched your trained model, your fine-tuning added
     nothing — and that is a real finding, not a failure. Say it plainly. -->
My prediction was mostly wrong. The baseline scored 0.324 accuracy, below my 0.45–0.55 range and below the 0.404 you get by always guessing `chatter`. The trained model beat it on every measure, including `hot_take`, where I expected the baseline to win. The baseline predicted `analysis` for about 31 of 34 posts and never predicted `hot_take`, so zero-shot with my definitions can't separate my labels, and fine-tuning added real signal (+0.26 accuracy). The one gap I wouldn't trust is `analysis` (+0.087), which is less than one post's worth of F1 on 34 posts.



---

## Run Log — Before

<!-- Five criteria across three seeds. The notebook's section 6 prints the
     spread table; the Target and Verdict columns are yours. -->

| Criterion | Target | Seed 42 | Seed 7 | Seed 2024 | Verdict |
|---|---|---|---|---|---|
| 1. `analysis` F1 | ≥ 0.55 on all three seeds | 0.526 | 0.692 | 0.750 | MISSED (seed 42) |
| 2. `hot_take` F1 | ≥ 0.55 on all three seeds | 0.167 | 0.400 | 0.000 | MISSED (all three) |
| 3. `chatter` F1 | ≥ 0.75 on all three seeds | 0.757 | 0.889 | 0.765 | MET |
| 4. Overall accuracy | ≥ 0.65 on all three seeds | 0.588 | 0.706 | 0.647 | MISSED (seeds 42 and 2024) |
| 5. Agreement with staff set | ≥ 23 of 30 (77%) | 30 / 30 (100%) | n/a | n/a | MET |

Accuracy spread across seeds was 0.118, over the 10-point line, so the stability note flags the dataset as too small or lopsided for a stable measure. Device: CPU, torch 2.14.1+cpu.

### Confusion matrix

Seed 42, 34 test posts.

| true \ predicted | analysis | hot_take | chatter |
|---|---|---|---|
| **analysis** | 5 | 1 | 4 |
| **hot_take** | 4 | 1 | 5 |
| **chatter** | 0 | 0 | 14 |

**My biggest off-diagonal number, and what it means:**
5 real `hot_take` posts were called `chatter` and 0 went the other way, so the model never learned to separate a hot take from a post with no claim and defaults to `chatter`, its biggest class.


---

## Verdicts and Diagnoses

<!-- MET or MISSED against LAST UNIT's target. The target has to hold across
     all three seeds, not turn up sometimes. -->

| # | Criterion | Target | Verdict | How I decided |
|---|---|---|---|---|
| 1 | `analysis` F1 | ≥ 0.55 on all three seeds | MISSED | 0.526, 0.692, 0.750. Seed 42 is under by 0.024. |
| 2 | `hot_take` F1 | ≥ 0.55 on all three seeds | MISSED | 0.167, 0.400, 0.000. Under on every seed. |
| 3 | `chatter` F1 | ≥ 0.75 on all three seeds | MET | 0.757, 0.889, 0.765. Lowest seed clears it by 0.007. |
| 4 | Overall accuracy | ≥ 0.65 on all three seeds | MISSED | 0.588, 0.706, 0.647. Seed 2024 is 22 of 34 right, 0.647, just under. |
| 5 | Agreement with staff set | ≥ 23 of 30 | MET | 30 / 30. |

**Diagnoses**

**Criterion 2 (`hot_take`): a hard label pair plus too little data.** Recall was 0.1, 0.3 and 0.0, and the misses go to `chatter` or `analysis` depending on the seed, so the model hasn't learned a stable boundary. `hot_take` is defined by what is absent (no checkable support), and 48 training posts isn't enough to learn that. The agreement report makes a labelling problem less likely: 30 of 30 with staff, including 7 borderline posts. It can't rule one out: my `hot_take` wording is looser than staff's decorative-fact rule, 192 of my 225 labels are Claude's judgment that I accepted, and two of the four seed 42 misses called `analysis` were posts where I changed Claude's pre-label.

**Criterion 1 (`analysis`): test-set noise.** Only seed 42 failed, by one post. I'm not lowering the target.

**Criterion 4 (accuracy):** the miss is `hot_take` dragging accuracy down. The 0.118 spread says 34 test posts is too few for a stable measure.

**Criteria 3 and 5 (met).** `chatter` holding tells me little: it is my largest label, and staff's `reaction` is not my `chatter`, so the agreement check can't vouch for it.

<!-- For each miss: the cause, and how you know. The four common causes are:
     too few examples for a label, a boundary you applied inconsistently, a
     genuinely hard label pair, and a task the model can't reach from this
     much data.

     ⚠️ Use your agreement report as evidence. It is the only instrument you
     have that can tell a LABELLING problem from a MODEL problem, and this
     section is graded on whether you used it that way. -->



---

## Agreement Report

<!-- Your rate against the staff set, and every disagreement adjudicated.

     Remember you labelled these 30 under the STAFF taxonomy in
     data/staff_taxonomy.md, not your own — so every argument below is made
     from those definitions and those decision rules. -->

**Agreement rate:** 30 / 30 = 100%

<!-- Nobody grades this number. A 60% who argues every disagreement from the
     stated rules beats a 95% who wrote "staff was right" nine times. Several
     of the 30 were chosen because they're genuinely ambiguous — you should be
     winning some of these. -->

**Disagreements**

<!-- Three lines each: the post, both labels, and who you think is right and
     why — grounded in the staff definitions you were both applying.

     Then sort each into one of three piles:
       (a) the rule covered it and I applied it loosely → a consistency problem
       (b) the rule genuinely doesn't say               → a gap in the definitions
       (c) the rule is ambiguous here and my reading is defensible → argue it.
           This is a legitimate win.

     Pile (a) is the one that matters most for your diagnosis: if you applied a
     written rule two different ways on 30 posts, that is direct evidence about
     what you did across your own 200. -->

There were none: all 30 labels matched, including the 7 posts staff marked as borderline on purpose. My labels are in `data/my_staff_labels.csv`, so the check ran as `python agreement.py --mine data/my_staff_labels.csv`.

The clearest of the hard calls was Rule 1. "Times are down about 3% since the shoe rules changed, so obviously..." is `hot_take`, because "so obviously" does the work and the 3% is decoration. "My times dropped 2% in the shoes and another 2% in the same pair..." is `analysis`, because the numbers are the reason for the conclusion.

**What the pattern in my disagreements tells me:**
No disagreements, so no pile (a) evidence of applying a rule inconsistently. That covers only 30 posts under staff's taxonomy, and staff's `reaction` is not my `chatter`, so it says nothing about my `chatter` boundary. It makes a labelling problem a weaker explanation for the `hot_take` misses than too few examples or a boundary the model can't learn from this much data.



---

## The Improvement

**What I changed:**
I added 14 `hot_take` posts to `labels.csv` (rows 227–240, `added` in `labels_ids.csv`), taking it from 225 rows to 239 and `hot_take` from 68 to 82. I had planned 30. I labelled 89 candidates from unused posts in `pool_inscope.jsonl` under my existing definitions and kept only the 14 `hot_take`. Nothing else changed: same definitions, training settings and seeds, on CPU.

**Which diagnosis pointed at it:**
Criterion 2: "a hard label pair plus too little data". `hot_take` had 48 training posts and F1 of 0.167, 0.400 and 0.000.

### Run Log — After

| Criterion | Target | Seed 42 | Seed 7 | Seed 2024 | Verdict |
|---|---|---|---|---|---|
| 1. `analysis` F1 | ≥ 0.55 on all three seeds | 0.167 | 0.500 | 0.333 | MISSED (all three; before: seed 42 only) |
| 2. `hot_take` F1 | ≥ 0.55 on all three seeds | 0.645 | 0.562 | 0.562 | MET (before: MISSED) |
| 3. `chatter` F1 | ≥ 0.75 on all three seeds | 0.759 | 0.750 | 0.714 | MISSED (seed 2024; before: MET) |
| 4. Overall accuracy | ≥ 0.65 on all three seeds | 0.611 | 0.611 | 0.583 | MISSED (all three; before: seeds 42 and 2024) |
| 5. Agreement with staff set | ≥ 23 of 30 (77%) | 30 / 30 | n/a | n/a | MET (carried over, not re-run: this change doesn't touch the staff set) |

Accuracy spread across seeds fell from 0.118 to 0.028. Test set is now 36 posts, not 34.

**Did it help, and how do I know:**
It fixed the criterion I aimed at and made the model worse overall. `hot_take` F1 clears 0.55 on all three seeds, but by only 0.012 on two of them, about one post. `analysis` F1 fell on every seed (0.526 → 0.167, 0.692 → 0.500, 0.750 → 0.333), `chatter` slipped under its target on seed 2024, and mean accuracy went down (0.647 → 0.602) while mean macro F1 stayed flat (0.549 → 0.555). One criterion gained, two lost.

The seed 42 confusion matrix shows why: 6 of 10 `analysis` posts were called `hot_take`. The model learned to say `hot_take` more often, which raised `hot_take` recall to 10 of 12 and cost the other labels.

Two limits on the comparison. Adding rows reshuffles every split, so the after-numbers are on different test posts (36, with 12 `hot_take`), not the same 34. And I picked the 14 because they looked like hot takes, so they are probably easier than a typical `hot_take`, and 14 is half of what I planned.



---

## What's Still Broken

<!-- For each criterion still missed: what you'd do, and why you stopped. -->

`hot_take` is rare in this forum under my definition: only 14 of 89 candidates I reviewed for the improvement qualified, and most of the rest were `analysis`. Collecting the other 16 would need a different method than a keyword shortlist.

**Criteria 1, 3 and 4 (`analysis` F1, `chatter` F1, accuracy) are missed, and I caused it.** The extra `hot_take` rows taught the model to call opinionated `analysis` posts `hot_take` (6 of 10 on seed 42), which pulled down `analysis`, then `chatter` on seed 2024, then accuracy (0.611, 0.611, 0.583). I would add `analysis` rows that cite numbers but still read as opinion, so the model sees both sides of the Rule 1 boundary. I stopped because every added row reshuffles the 36-post test set, and I can't tell a real gain from noise without a fixed one.

**Criterion 2 (`hot_take` F1) is met but fragile.** It clears 0.55 by about one post on two seeds, and the 14 added posts were hand-picked, so a fresh `hot_take` set would be the fair test.

**The gap between what I meant my labels to capture and what the model
learned:**
I meant `hot_take` to be a claim with no checkable support, and `analysis` a claim whose numbers or reasons carry the conclusion. The model learned something closer to "opinionated tone means `hot_take`": the seed 42 matrix shows 10 of 12 `hot_take` right but 6 of 10 `analysis` called `hot_take`.


---

## Stretch Items

I am attempting one stretch item: **a per-label error write-up**. I wrote this declaration after running the script that produced its numbers, so it is not a before-the-build declaration.

### Stretch: a per-label error write-up (`hot_take`)

**What this item is and what it changed:** a written analysis of the worst label in the Run Log — Before matrix. It changes no data, labels, settings or results. It adds [`error_analysis.py`](error_analysis.py) and its output [`error_analysis_before_predictions.csv`](error_analysis_before_predictions.csv), because the notebook saves only counts. The script retrains the 225-row "before" model on all three seeds and saves each test post's guess and confidence. It reproduces the logged numbers, and this covers the "before" model, not the one trained on the 14 added posts.

`hot_take` is the worst label on all three seeds (F1 0.167, 0.400, 0.000). On seed 42 it got 1 of 10 right, and I read the 9 misses: 5 went to `chatter` and 4 to `analysis`.

**Called `chatter` (5).** These read like banter: three open with a quoted reply, and the rest have slang or exclamations ("idk why...", "Yikes", "the OU goat of all time"). Each still claims something about the game, but casually. My `chatter` definition includes jokes and hype, so the model is reading tone while my `hot_take` rule is about content.

**Called `analysis` (4).** These look like arguments: they name Pokemon and tiers, use numbers ("2 of the fastest relevant pokemon") and connectives ("that means", "mostly because"), and two run 119 and 133 words. By my rule none has support someone else could check.

**What they have in common.** All 9 are opinions with no checkable support, and the model goes by how they sound. It had 48 `hot_take` training posts to learn a label defined by something absent. That is my hypothesis, not something this analysis tests. Confidence on the misses was 0.34 to 0.43, close to the 0.33 of a three-way guess.

**Which label it is confused with.** Not one label. Over the three seeds, 26 of 30 test `hot_take` posts were missed: 14 went to `analysis` and 12 to `chatter`. The direction changes with the split (to `analysis`/`chatter`: 4/5 on seed 42, 6/1 on seed 7, 4/6 on seed 2024).

**Caveat.** Two of the four `analysis` misses are posts where I changed Claude's pre-label ("If Ceruledge ... that means Iron Threads can also drop" was `analysis`). A tier-update outcome could count as checkable under my own definition, so some of the "confusion" may be label noise.


<!-- ═════════════════════════════════════════════════════════════════════

     SUBMISSION CHECKLIST — unit 5

       [ ] criteria.md has five numbered criteria, each naming a NUMBER
       [ ] Each has a reason underneath tied to your data or taxonomy
       [ ] labels.csv: at least 150 rows, text/label/note, ONE file not split
       [ ] No label above 70%
       [ ] All five unit 5 sections have real content
       [ ] Label Taxonomy includes the decision rule for your hardest boundary
       [ ] The Dataset includes three hard cases
       [ ] results.json and test_split.csv committed (the notebook does this)
       [ ] At least four new commits
       [ ] Repository URL submitted — WRITE IT DOWN

     SUBMISSION CHECKLIST — unit 6

       [ ] Baseline vs. Trained table, with your prediction written beforehand
       [ ] Run Log — Before, five criteria across three seeds
       [ ] Confusion matrix TYPED AS A MARKDOWN TABLE
       [ ] A verdict on every criterion
       [ ] A diagnosis for every miss, using the agreement report as evidence
       [ ] Agreement Report with every disagreement adjudicated
       [ ] One improvement, with Run Log — After
       [ ] What's Still Broken
       [ ] results_three_seeds_before.json, results_three_seeds_after.json,
           baseline_results.json and
           agreement_results.json committed
       [ ] At least four new commits
       [ ] The SAME repository URL as last unit

     Do not delete and recreate this repository.
     ═════════════════════════════════════════════════════════════════════ -->

---

📖 **How to run this project: [RUNNING.md](RUNNING.md)**
