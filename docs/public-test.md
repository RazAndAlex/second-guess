# Public test on 1,000 Kickstarter projects: GPT-6.1 Sol 0.1620, statistics 0.1976

Run on 2026-11-05 on GPT-6.1 Sol and Claude Opus 5.5. The rules were written before the run (`public-test/PREREGISTRATION.md`). A separate verifier recomputed all 22 scores and they match to 4 decimals (`public-test/verify-report.md`, which also sources the numbers below). That file, the data and the model outputs stay on the author's machine and are not in this repository.

## The question

Can a model predict which new Kickstarter projects get funded, from the project's name and blurb, better than plain statistics? Do evidence cards improve it?

## The result

Brier score: the mean squared gap between the forecast and what happened, with funded as 1 and failed as 0. Lower is better. Always guessing the average gives 0.2448. 57.2% of the 1,000 got funded.

| Who | Plain | With cards | Gain over statistics (with cards) |
|---|---|---|---|
| Statistics (category, goal, country) | 0.1976 | | |
| Pass line | 0.1779 | | |
| Opus 5.5 | 0.1760 | 0.1781 | 9.87%, misses by 0.0002, rerun noise about 0.004 |
| GPT-6.1 Sol | 0.1622 | 0.1620 | 18.03%, passes |

- The rule: a model passes when its score with cards is at least 10% below the statistics score, which gives the pass line. Opus is undecided, because it missed by less than the noise.
- Cards changed nothing that we can see. Their effect spans zero on both models.
- 128 of the 1,000 had $0 pledged at first capture, and all failed. On the other 872, Opus ties statistics and Sol wins by 0.0247 (0.0103 to 0.0386). The models never saw the pledged amount, so this is no leak.
- Cards covered 491 projects in 4 of 15 categories: Comics, Games, Music, Publishing.
- Leak hunt: 17 projects flagged. Removing them moves the win over statistics by 0.0007 on Opus and 0.0009 on Sol.
- Fixing the models' calibration after the fact takes the plain scores to Opus 0.1656 and Sol 0.1610. This step was not in the rules, so treat it as a hint.
- The test had four arms. Arm 1: statistics. Arm 2: model, plain. Arm 3: model with cards. Arm 4: arm 3 plus category, goal and country. Arm 4 was exploratory and stayed unrun, because spending had reached the $15 limit set for it.

## The checker

On 71 cards from 15 searches, one per Kickstarter category (`public-test/cards/`):

| Route | Pass | Fail | Unchecked | Other |
|---|---|---|---|---|
| Web archive | 27 | 28 | 1 | 15 no dated capture |
| Live page | 26 | 19 | 14 (HTTP 403) | 12 throttled |

Run it: `.venv/bin/python check_card.py card.json [--live] [--local]`. Results: `pass`, `fail`, `unchecked`, `throttled`, `no_dated_capture`. It needs network access, and it keeps a cache in `cache/` beside the script.

## What we can claim

- On this population, on these two models, on this date, reading a name and a blurb beats a simple statistical formula by a clear margin on Sol.
- The checker catches cards whose quote is missing from the page. 28 of 71 failed on the archive route.
- Correction found on 2026-11-05: at least 4 of those 28 failures are false. The web archive sent those 4 pages compressed, `check_card.py` never decompressed them, and the first 60 characters of each quote are on the page after decompressing. The 4 cards are in Comics, Dance and Journalism. So the archive route is at least 31 pass and at most 24 fail. Those 4 cards never reached the models, and he decided against a rerun ("1 no"), so the effect on the scores in this file is unmeasured.

## What we cannot claim

- That the result holds for other kinds of product. Kickstarter is one market.
- That cards improve a prediction.
- That a model can predict buying. The target was funding.
- That the search recipe in the skill works. The test used one plain search prompt per category.
- That the models had no knowledge of these projects from training. All launched in July and August 2026, after Opus's stated cutoff, and no test can settle this from our files.

## Who the projects were

Webrobots publishes monthly scrapes of Kickstarter. 1,544 projects were first seen live in its file of 2026-08-12, launched 2026-07-14 to 2026-08-09, each run at least 29.5 days. Outcomes came from Kickstarter's own `https://www.kickstarter.com/projects/<creator>/<slug>/stats.json?v=1`, which is undocumented, at 1.1 seconds per call with a generic User-Agent. Result: 810 funded, 644 failed, 86 canceled, 3 suspended, 1 unresolved. The 1,000 were drawn from the 1,454 funded or failed, seed 20261105. The statistics arm trained on 2,074 other labelled projects.

Why the live route: for projects with the same deadlines, Webrobots' June file shows 67.0% funded, its October file 82.0%, and Kickstarter itself 56.3% (`plan-revised.md`, line 186). The later the file, the more it favours funded projects.

## What it cost

Sources: `ledger.jsonl` for model calls, the run log of the helper agents for the workers. Model calls $15.72: 15 searches $8.38 ($0.56 each), Opus $4.38, Sol $2.88, preflight $0.08. Workers that built and checked it $19.68. Probes $0.86. All in, about $36.

## Rerun it

From `public-test/` in a clone. Run `uv sync` first to create `.venv`.

```
.venv/bin/python -m unittest test_ks                # 58 tests pass
shasum -a 256 PREREGISTRATION.md                    # 94f135c2dd42...
```

`score.py` and `verify_scores.py` need the model outputs (`odds/`, `arm1_preds.json`, `resolved.jsonl`). These files are not in this repository, so the scores can only be recomputed after a full rerun.

A full rerun with new model calls needs more:

1. Download the raw files from https://webrobots.io/kickstarter-datasets/ into `data/` at the project root. `split.py` lists the file names. They take about 2.3 GB.
2. Create `empty/` and `codexhome/` at the project root, with an `auth.json` in `codexhome/`.
3. Run `run_resolve.sh`, `run_arm1.sh`, `run_cards.sh`, `run_odds.sh`, then `score.py`. Budget about $16 in model calls.

`common.py` reads the Codex location from `~/.vnext/runtimes/active.json`, a file from the author's own agent manager. The file is frozen with the test, so to rerun on your machine, change that line to the path of your `codex` program.
