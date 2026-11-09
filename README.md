<h1>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/images/logo-ondark.svg">
    <img src="docs/images/logo-onlight.svg" width="300" alt="second-guess">
  </picture>
</h1>

**An idea validation skill for Claude Code and Codex.** Your agent searches the web for evidence. A small Python program checks every quote and number the agent reports. You get one HTML report.

VIDEO_URL

One example run: the garden centre idea. The percentage is the AI's opinion. Code computed the counts.

[Open the example report](https://razandalex.github.io/second-guess/report.html) · [How it works](https://razandalex.github.io/second-guess/) · [Install](#install)

## Install

```
npx skills add RazAndAlex/second-guess
```

You need Python 3.9 or later, and Node.js for `npx`. `uv` is optional and only helps read PDF pages. To install into one agent only, add `-a claude-code` or `-a codex`.

The skill installs into any agent that the installer supports. It has run end to end in Claude Code and Codex only, and the Claude Code run was on the author's machine.

## Try one idea

Ask your agent to test an idea in plain words, for example: "Use the second-guess skill on this idea: refill tablets for cleaning spray, sold in Italian supermarkets."

Codex needs network access for the commands the agent runs:

```
codex --search exec -s workspace-write --skip-git-repo-check -c 'sandbox_workspace_write.network_access=true' "<idea>"
```

Claude Code:

```
claude -p "<idea>" --allowedTools "Bash,Read,Write,Edit,WebSearch,WebFetch,Agent,Skill"
```

In four test runs, a run took 5 to 14 minutes. The tokens cost $0.54 to $3.19 at API prices. One run also used helper agents that left no cost record. You pay from your own plan or API account.

The run writes to `second-guess-runs/<date>-<idea>/` in the folder where you started it. At the end the agent shows you the path of `report.html`. Open it in a browser. The file holds its own font and needs no network.

Each user picks the model. second-guess ships no data, no model, no API key and no purchase number. Opening a source link tells that site your address.

If a card check prints `network_blocked`, the program reached neither `web.archive.org` nor `github.com`. Turn on network access for your agent.

To try the program with no agent and no network, see [docs/by-hand.md](docs/by-hand.md).

## What gets checked

1. The agent writes the idea's assumptions.
2. It searches the web and saves each source as a card: a link, the exact quote, the number in the quote, the sample, the group it covers and the year.
3. The program opens each link, or a web archive copy, and refuses a card when the quote or the number is not on the page.
4. A fresh helper agent reads each passing card against its page and flags faults, such as a figure from another country or year.
5. If the agent finds a public dataset of earlier cases, the program's `stats` command computes from it and a blind reviewer judges whether the data matches the idea. Otherwise the report says "I don't know".
6. The agent simulates hostile people, buyers among them, who argue against the idea.
7. The agent gives its lean: a percent chance that a named target happens by a named date.
8. The program builds the report and refuses any number that no checked card or saved statistic backs.

A passing card means only that its words are on the page. The words can still say something other than what the card claims. Read the source before you rely on a card.

The lean is an AI's opinion. No test score sits beside it, and it is unproven on real launches.

## What it refuses

- A purchase number. The program refuses purchase phrases, money tied to purchases and numbers with no source.
- A number in the report text that no saved statistic or passing card backs.
- A quote that is not on the page.
- A link that points to a private or local address.

## Known limits

The ones that matter most. The full list of 32 is in [docs/limits.md](docs/limits.md).

- The number check is a word list. It has misses and false refusals.
- A number that a card backs can still be used for a different claim.
- The source reader is an AI's reading. It can miss a fault or flag a sound card. In small tests it caught some faults and missed others, so there is no rate.
- An outside reviewer tried to sneak sentences past the program on 2026-11-05. It refused 82 of 82 written before the reviewer read the code, and let 33 of 62 through that were written after. The program had more repairs since. Nobody has measured it again.
- The report text refuses digits, so years drop out. An old figure can then read as current.
- A sentence with no number can carry a claim with no saved source.
- `stats` answers "I don't know" below about 1,000 rows, above 500 features, or when the run takes longer than 90 seconds.
- The program reads files from one folder only, `idea-test-files/`. That rule binds the program. It does not bind the agent.

## Help

Open an issue at [github.com/RazAndAlex/second-guess/issues](https://github.com/RazAndAlex/second-guess/issues). Say which agent and model you used, the command you ran and what it printed. Leave out private run data and API keys.

To run the tests, clone the repository and run this from its root. One test skips in a clone, because its sample file is not published.

```
python3 -B -I -m unittest discover -s tests
```

## Credit and licence

MIT. See `LICENSE`. Some prompt wording is adapted from Althing; the notice is in `skills/second-guess/references/hostile.md`. The Unicode folding in the source check is adapted from grounded (MIT); the notice is at the top of `skills/second-guess/scripts/second_guess.py`.
