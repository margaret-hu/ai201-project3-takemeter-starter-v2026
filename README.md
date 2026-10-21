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

**Base model:**

**Settings:** <!-- epochs, learning rate, batch size, seed -->

**Anything I changed from the defaults, and why:**

**Split sizes:** <!-- train / val / test, and per-label counts in the test
split. If a label had fewer than about 8 in test, say so — it explains a lot
of next unit's variance. -->



---

## How I Used AI

<!-- Two specific moments — what you asked, what came back, what you changed.

     ⚠️ Plus disclosure of any pre-labelling. If you had a model pre-label a
     batch and then read and corrected every one, say that. It's an allowed
     workflow and disclosing it costs you nothing. Not disclosing it is the
     problem. -->

**Moment 1: checking the scraped data against my sampling plan**

- *What I asked for:* Whether my scraped pool covered my sampling plan, checked again after I revised the plan and re-scraped.
- *What came back:* No, both times. The first pool had 564 posts from 12 threads (plan: 25–35), no RMT threads because my `inscope.py` filter drops them, and only 28% recent posts. After the revised plan and a first re-scrape, a leftover post limit in Claude's scraper edit stopped the scrape at 14 of 28 threads. After my second re-scrape, the pool has 752 posts from 19 threads and subsamples to 175 posts, with 49% recent but no Doubles/VGC threads.
- *What I changed:* I dropped the RMT quota and rewrote the plan around opinion-bearing threads, then approved the scraper and `subsample.py` changes (10 posts per thread max). Still to do: add Doubles/VGC and viability threads to reach 28 threads and 200 posts.

**Moment 2**

- *What I asked for:*
- *What came back:*
- *What I changed:*

**Pre-labelling disclosure:**

<!-- ═══════════════════════ UNIT 6 — THE TEST ═══════════════════════

     Don't fill these in during unit 5.
     ═══════════════════════════════════════════════════════════════════ -->

---

## Baseline vs. Trained

<!-- Both models on the same posts. `python baseline.py --trained results.json`
     prints this table for you. -->

| Measure | Baseline | Trained | Difference |
|---|---|---|---|
| Overall accuracy |  |  |  |
| Macro F1 |  |  |  |
| F1 — `label_one` |  |  |  |
| F1 — `label_two` |  |  |  |

**What I predicted before I looked:**
<!-- Milestone 1 asks you to write this BEFORE seeing the trained numbers. A
     prediction made afterwards isn't one. -->

**What the gap actually means:**
<!-- If the baseline matched your trained model, your fine-tuning added
     nothing — and that is a real finding, not a failure. Say it plainly. -->



---

## Run Log — Before

<!-- Five criteria across three seeds. The notebook's section 6 prints the
     spread table; the Target and Verdict columns are yours. -->

| Criterion | Target | Seed 42 | Seed 7 | Seed 2024 | Verdict |
|---|---|---|---|---|---|
| 1.  |  |  |  |  |  |
| 2.  |  |  |  |  |  |
| 3.  |  |  |  |  |  |
| 4.  |  |  |  |  |  |
| 5.  |  |  |  |  |  |

### Confusion matrix

<!-- ⚠️ TYPED AS A MARKDOWN TABLE. The notebook prints one ready to paste.
     An image of a matrix earns nothing. -->

| true \ predicted |  |  |  |
|---|---|---|---|
| **** |  |  |  |
| **** |  |  |  |
| **** |  |  |  |

**My biggest off-diagonal number, and what it means:**
<!-- Not "the model made mistakes" — WHICH boundary it didn't learn, and which
     direction. "7 real analysis posts were called hot_take and only 3 went the
     other way" is a direction, not just an error rate. -->



---

## Verdicts and Diagnoses

<!-- MET or MISSED against LAST UNIT's target. The target has to hold across
     all three seeds, not turn up sometimes. -->

| # | Criterion | Target | Verdict | How I decided |
|---|---|---|---|---|
| 1 |  |  |  |  |
| 2 |  |  |  |  |
| 3 |  |  |  |  |
| 4 |  |  |  |  |
| 5 |  |  |  |  |

**Diagnoses**

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

**Agreement rate:** ___ / 30 = ___%

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

**1.**
> *The post:*
>
> *Staff said / I said:*
>
> *My call, and why:*
>
> *Which pile:*

**2.**
> *The post:*
>
> *Staff said / I said:*
>
> *My call, and why:*
>
> *Which pile:*

**What the pattern in my disagreements tells me:**



---

## The Improvement

**What I changed:**

**Which diagnosis pointed at it:**

### Run Log — After

| Criterion | Target | Seed 42 | Seed 7 | Seed 2024 | Verdict |
|---|---|---|---|---|---|
| 1.  |  |  |  |  |  |
| 2.  |  |  |  |  |  |
| 3.  |  |  |  |  |  |
| 4.  |  |  |  |  |  |
| 5.  |  |  |  |  |  |

**Did it help, and how do I know:**

<!-- If it didn't, say so. Relabelling that didn't help is a genuinely
     interesting result and earns full credit. -->



---

## What's Still Broken

<!-- For each criterion still missed: what you'd do, and why you stopped. -->



**The gap between what I meant my labels to capture and what the model
learned:**
<!-- Two sentences. Your confusion matrix is the evidence. -->



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
