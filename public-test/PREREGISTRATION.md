# Pre-registration: Kickstarter public test (written 2026-11-05, before any scored odds run)

Population: 1,000 test projects (funded or failed, outcome from stats.json), first live capture from the 2026-07-24 file (519 ids) or the 2026-08-12 file (1,025 ids) among the 1,544 test ids, launched 2026-07-14 to 2026-08-09, ran 29.5 days or more.
Outcome: funded = 1, failed = 0. Canceled and suspended projects are excluded and counted.

## Arms
1. Logistic regression (scikit-learn `LogisticRegression`, default C) on parent category, log10(goal x static_usd_rate), country. Fitted on the train split only (live before 2026-07-01, deadline before 2026-07-14, exactly `resolve.train_pool()[:2200]`, the first 2,200 of a seeded shuffle, with at least 2,000 labelled funded or failed).
2. Model sees project id, name and blurb from the first live capture. Output: one odds number per id, 0 to 1, by schema, no free text.
3. Arm 2 plus the passing cards for that project's parent category, only when the parent has 3 or more passing cards. Below 3 the project gets none; scoring records how many projects hit that.
4. EXPLORATORY, outside the pass rule: arm 3 plus category, goal in USD and country. Runs only after arms 2 and 3 are complete and only if the ledger is under $15.

Models: `claude-opus-5-5` via `claude -p` (Claude login, ANTHROPIC_BASE_URL and ANTHROPIC_AUTH_TOKEN removed for the subprocess) and `gpt-6.1-sol` via the vNext Codex binary 0.163.0. Claude has no tools; the only entry in its list is the built-in StructuredOutput that returns the schema answer. Sol runs through one shared command (CODEX_HOME holding a clean folder with a symlinked auth.json and codex's own cache files (no AGENTS.md, no memories, no plugins enabled), empty working folder, plugins, apps, shell_tool, code_mode_host, multi_agent, goals, image_generation, browser_use, computer_use and hooks disabled (card calls leave code_mode_host on, because web search runs through it; measured 2026-11-05), read-only sandbox, web search disabled for odds, `--search` for cards). Sol still has tool names offered by the client; a per-batch guard reads the `--json` log and stops the whole run on any item other than agent_message, reasoning, or the Code Mode error (card calls also allow web_search).
**Effort for all odds calls on both models: medium** (same in every arm). Chosen after the stage-1 preflight, from measured cost; this file is written after the preflight and before any scored run. The preflight (one arm-2 batch per model) is not scored.

## Batches
Seed 20261105. Eligible ids = test ids resolved funded or failed, sorted by id, `random.Random(20261105).shuffle`, first 1000; grouped by parent category (sorted), 25 per batch. Same batches for every arm and both models. Cards: up to 5 per parent, from Codex web search (gpt-6.1-sol), kept only if `check_card.py` finds the exact quote (at least 40 normalised characters) and the number (whole token) in a Wayback capture whose 14-digit timestamp, and whose final URL after redirects, are 20260713 or earlier. The prompt shows each card as number, quote, url and the checker's capture date; sample, population and year are never sent. Every model-written field that reaches the prompt passes a strict whitelist in `judge()`: the number must fully match `[$0-9][0-9.,%$ a-z-]{0,19}` (lower-cased), the url must fully match `https?://[^\s<>"#]+` (no fragment, no space, no quote mark), and the quote must hold no < or > and is printed normalised (tags removed, lower case). A card that fails any rule never reaches `cards_pass/`. The capture date is the checker's own.

## Pass rule (per model, scored separately, not changed after seeing results)
A model passes when arm 3 Brier is at least 10% below arm 1 Brier on the shared ids: Brier(arm 3) <= 0.9 x Brier(arm 1). Brier = mean squared error, funded 1, failed 0. Also reported: arm 2, constant-answer Brier, paired bootstrap 95% interval of the arm 3 minus arm 1 gap, calibration bins, canceled count, excluded ids, projects that got no cards. Arm 4 is exploratory and reported under that label. Arm 2 and arm 4 are scored on their own subsets with n printed. Fewer than 1,000 shared arm 1, arm 3 and outcome ids: the report says INCOMPLETE and gives no verdict.

## Budget
Ledger for odds and cards stops at $19 (token cost at: sol $2/$10 per million, opus $4/$20; opus billed cost taken when larger). N is not cut by the runner.

## Changelog
- 2026-11-05 (after code review, before any scored run): parent fix (top-level categories keep their own name, no more `none`); card line now shows only number, exact quote, url and the checker's capture date; checker date rule (14-digit timestamp at most 20260713, final URL after redirects also dated, local files only with --local); arm 1 pool fixed to `resolve.train_pool()[:2200]` (at least 2,000 labelled); per-batch guard on every sol log; up to 2 retries per batch with their own ledger keys; quote floor 40 characters and whole-token number match; prompt says "ran about 30 days or more"; cost projection uses 48 batches per arm (49 after the second recheck). Sol ran with tool names still offered by the client; the code mode host was off so shell calls fail, and each batch log records that no tool item appeared. Card calls keep the code mode host on for web search; in a test it still could not run `ls /`.
- 2026-11-05 (after recheck, before any scored run): the checker fails any quote holding < or >, and the prompt prints the normalised quote; `scores.json` is deleted at the start of each run; arm 3 refuses to start without `cards_pass/`; a kill or error in one model stops the other; the retry loop checks the budget; one page counts once toward the 3 passing cards (compared on lower-case host without www., no scheme, no trailing slash, no /index.html, no query, no fragment; an archive-prefixed URL is unwrapped); **router-error limit: more than 5 batches with router errors in one model and arm stops the run (exit 4); the count is printed and written to scores.json**; the cost projection uses 49 batches per arm; population wording corrected to the first live capture date.
- 2026-11-05 (after the second recheck, before any scored run): the whitelist above covers the number, the url and the quote; the 3-card dedupe counts one page once on a normalised key; a kill in one model exits with that model's own code (4) and also stops the sibling's in-flight child; a plain kill of `run_odds.sh` stops both models and their children.
- 2026-11-05 (checker rerun on saved cards, before any scored run): archive requests go one at a time, at least 3 s apart, with backoff of 30 s, 2 min and 5 min on 429, 5xx or a network error; a request still throttled after that gets the new status `throttled`, which stays apart from `unchecked` and from the defeat count and is rerun next time; every CDX row and capture is cached on disk under `cache/`; PDF pages are read as text with pypdf (line-break hyphen joins only in the page text), on the archive and the live route; `norm()` closes the gap page markup leaves in `42.74 %` and `$ 2.85`. The date rule, the quote floor and the whitelist are unchanged.
- 2026-11-05 (four small fixes, before any scored run; no Brier seen): the checker also fails a quote holding < or > after entity decoding (double-escaped `&amp;lt;`), and a quote holding a control character other than newline, return and tab, or a zero-width or bidi (format) character; the PDF line-break hyphen join runs only between letters (`10-<newline>20%` stays); score.py adds a block labelled descriptive, outside the pass rule: arm 1, 2 and 3 Brier with n on covered parents (arm 3 batches with cards used) and on the rest, on the same shared ids. The pass rule and verdict are unchanged.
- 2026-11-05 (coverage fixed before any scored run; no Brier seen): no second card search. Arm 3 cards go to the 4 of 15 parents with 3 or more different passing pages on the archive route: Comics, Games, Music, Publishing (742 of the 1,544 test projects, 48%). Every other project gets the arm 2 prompt in arm 3. The pass rule stays on all shared ids, as registered. Also reported, descriptive only and outside the pass rule: arm 1, arm 2 and arm 3 Brier on the covered parents and on the rest, with n.

## Prompts, verbatim
### Odds prompt (all arms)
```
You forecast Kickstarter campaigns. Every project below launched between 14 July 2026 and 9 August 2026 and ran about 30 days or more. For each project give the probability, between 0 and 1, that it reached its funding goal. Use only the text below and what you already know. Do not use any tool. Return one number for every project id, and nothing else.

```
Cards block (arms 3 and 4, only with 3 or more passing cards), header then one line per card:
```

Evidence cards for the parent category "{parent}". Each card quotes a page published before 14 July 2026:

- {number} | "{quote}" ({url}, archived {capture})

```
Project list header and line. Arms 2 and 3: `Projects (id | name | blurb{extra}):` with `id | name | blurb`. Arm 4 adds ` | category: <cat> | goal: <USD> USD | country: <country>` to each line and ` | category | goal | country` to the header.
```

Projects (id | name | blurb{extra}):

<id> | <name> | <blurb>
```
### Output schema (odds)
```
{
 "type": "object",
 "additionalProperties": false,
 "required": [
  "odds"
 ],
 "properties": {
  "odds": {
   "type": "array",
   "items": {
    "type": "object",
    "additionalProperties": false,
    "required": [
     "id",
     "p"
    ],
    "properties": {
     "id": {
      "type": "integer"
     },
     "p": {
      "type": "number",
      "minimum": 0,
      "maximum": 1
     }
    }
   }
  }
 }
}
```
### Card search prompt
```
Search the web for published statistics about how often Kickstarter projects in the parent category "{parent}" reach their funding goal. Use only pages dated before 14 July 2026. Give up to 5 cards. Each card has: url (the page), quote (copied exactly from that page), number (the figure in the quote), sample (how many projects the figure covers), population (which projects, which period), year (publication year). Do not invent a quote. If you find fewer than 5, give fewer.
```
### Card schema
```
{
 "type": "object",
 "additionalProperties": false,
 "required": [
  "cards"
 ],
 "properties": {
  "cards": {
   "type": "array",
   "maxItems": 5,
   "items": {
    "type": "object",
    "additionalProperties": false,
    "required": [
     "url",
     "quote",
     "number",
     "sample",
     "population",
     "year"
    ],
    "properties": {
     "url": {
      "type": "string"
     },
     "quote": {
      "type": "string"
     },
     "number": {
      "type": "string"
     },
     "sample": {
      "type": "string"
     },
     "population": {
      "type": "string"
     },
     "year": {
      "type": "string"
     }
    }
   }
  }
 }
}
```
