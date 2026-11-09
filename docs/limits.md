# Known limits

The full list. The README keeps the ones that matter most.

- The program reads files from one fixed folder only. That folder is `idea-test-files/`. `start` creates it in the folder where you ran it, next to `second-guess-runs/`, and `attack` also reads a file from the run folder. The folder binds the program only. It does not bind the agent.
- Locking needs `fcntl`, and is skipped where absent. The hard-link refusal needs a filesystem with link counts.
- The number check is a word list. It has misses and false refusals, and the list is open ended.
- A number that a card backs can still be used for a different claim. The program lets "40 buyers came." pass when a card holds the number 40 for something else. It also lets "25% of customers bought it." pass when a card holds 25.
- A card's population text (the field that names the group the card covers) is refused when it counts buyers or customers, even when the number counts something else, such as "Retail customers of 40 European chains".
- The source reader is an AI's reading. It can miss a fault or flag a sound card. In one test on 10 cards it caught 4 of 4 known faults and flagged 1 of 6 sound cards. The test was small and used the same cards that had shown the faults.
- One outside reviewer, who did not build the program, measured it on 2026-11-05. The reviewer wrote a list of sentences before reading the code. The program refused 82 of 82. The reviewer then wrote a second list after reading the code. 33 of 62 got through.
- The program had one more round of repairs after that measurement. Nobody measured the rates again, so treat both figures as old.
- Examples checked on 2026-11-05 with the current program: "Nothing here says anyone will pay." and "A third party could copy the sensor." are refused by mistake. Money slang such as "The sensor costs a grand." passes.
- The target check is a word list too (a list of words the program looks for). It misses words outside the list and look-alike letters from other alphabets. A target such as "we interview 5 customers and 500 buy" passes.
- `stats` checks the outcome column by its name and values only. It misses neutral names such as `y`, `target`, `label_1` and `outcome`, names in other languages (`kaufte`, `resultado_compra`), and some English names (`upgraded`, `signed_up`). It refuses some harmless names (`winLoss`, `retained`).
- A quote that says a product is "not available for purchase" fails the card even when it also holds a plain shelf price, such as "Price: $39.99 Discontinued - not available for purchase".
- A true quote can fail in some markup. A wrong page charset ends in one of two ways. If the bytes are not UTF-8 and no header or tag names a charset, the card ends `unchecked` ("page charset is unknown"). If the page names a wrong charset that still decodes, the card ends `fail` ("quote not on page"). In both cases the card does not pass.
- If you pass a saved block page ("Just a moment...", "access denied") by hand with `--page-file`, it counts as a failed card, because the quote is not on it.
- The assumption count only shows coverage. Which assumption a card speaks to is the AI's reading, so a card can point to an assumption it does not support. The code counts the pointing and does not judge it. A report with no card pointing anywhere counts 0 and says so.
- `report` refuses in the command line when no assumption list is saved. Code that calls `report_cmd` directly gets no such refusal (`need_list` is off by default), because older tests call it that way.
- When the live page answers 429 and the archive index times out or errors, the card ends `throttled`. The detail then says "the live page refused (http 429) and the archive copy was not read (...)". When the archive has no capture of the page, the detail is only "http 429". Run it again later, or give the page with `--page-file`.
- When the archive answers 429 too, the program makes three runs, the first plus two reruns, of about 45 seconds of waiting each. The card then ends `throttled` with the vague detail "still pending after 3 runs".
- The check on a count written in words catches only a plural "assumptions" named with a source and a quantity word. Other wordings pass. The quantity words include "no", "some", "one" and "any", so a sentence with no count can be refused too, such as "No source covers these assumptions." Rewrite it to name the single assumption.
- If the page itself answers 404 and the web archive then fails, the card shows only "http 404". The archive failure stays hidden.
- A page that answers 429 (too many requests) gets one more try after 10 seconds. Then the program reads the web archive copy. If the copy holds the quote, the card passes. If the copy lacks the quote, the card ends `throttled`, because the live page may hold it. Give the page with `--page-file`.
- A page that answers 5xx makes the program wait 30, 120 and 300 seconds. The card can stay `pending` for the whole time limit. Each card gets an equal share of the time limit.
- The report text refuses digits, so years drop out. An old figure can then read as current.
- A card can lose a limit of its source, such as "US only". The source reader can miss it.
- A sentence with no number can carry a claim with no saved source. The footer speaks for numbers only.
- `pages-opened.txt` is written by the agent. It can leave pages out.
- The source reader misses faults. In one run on each of two ideas it caught 2 of 5 faults that a second agent found, with 1 false flag. This gives no rate.
- The filing question (question 5 of the source reader) ran once on 10 pairs from one run, with one reader seeing all ten. It caught 3 of 3 misfiled cards and wrongly refused 0 of 7, on cards that showed the fault. This gives no rate.
- A wrong `--page-file` writes no CARD file for that call. A rerun without the bad file writes it.
- If the assumption list changes after the cards, a card keeps its number and then points at the new item with that number.
- `source-context` writes the page text in lowercase. The date "May 28" then looks like the verb "may".
- `attack` (the step where the AI argues against the idea) refuses every money amount, even "A $20 tool will not win shelf space."
