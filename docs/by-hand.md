# Run the program by hand

You can try the program with no agent and no network. Clone this repository first. `/path/to/this/folder` is the folder of the clone, which holds `skills/`. The route below uses one card and `--page-file`, so it needs no network. It ran from an empty folder.

```
SG=/path/to/this/folder/skills/second-guess/scripts/second_guess.py
python3 "$SG" start --idea "a soil sensor" --model example-model
printf '%s' 'FYTA Beam G2 (selectable probe length) Sale price From €39,99' > page.txt
cat > cards.json <<'J'
{"cards":[{"url":"https://example.com/fyta-beam","quote":"FYTA Beam G2 (selectable probe length) Sale price From €39,99","number":"€39,99","sample":"one shop page","population":"A rival sensor","year":"2026"}]}
J
python3 "$SG" check-cards cards.json --page-file 0 page.txt
python3 "$SG" source-context
cat > idea-test-files/assumptions.json <<'J'
{"assumptions":["Garden owners want to know when a plant is dry.","A shop chain would list a new sensor."]}
J
python3 "$SG" assumptions --file assumptions.json
python3 "$SG" stats --no-dataset
cat > idea-test-files/attack.json <<'J'
{"findings":[{"person":"A garden centre buyer","kills":"A new tool gets no shelf space.","ask":"Would you stock it?"}]}
J
python3 "$SG" attack --file attack.json
python3 "$SG" target --text "a chain lists it" --date 2027-06-30 --place "the chain's own website"
python3 "$SG" lean --percent 30 --reason "no record yet"
cat > idea-test-files/text.json <<'J'
{"name":"Soil sensor","paragraphs":["The FYTA Beam G2 costs €39,99."],
 "short":{"target":"A chain lists it","reason":"No record yet","check_at":"The chain's own website",
  "assumptions":["Owners want to know when plants are dry","A chain would list a new sensor"],
  "people":["A garden centre buyer"]}}
J
python3 "$SG" report --file text.json
```

Then open `second-guess-runs/NAME/report.html` in a browser. `NAME` is the `name` that `start` printed, such as `2026-11-05-a-soil-sensor`. If you give no `--run`, each command uses the newest run.

By hand, you write four files: the cards file, the assumptions file, the attack file and the report text. `report` refuses until the assumptions are saved, or until `assumptions --none --reason TEXT` says the idea needs none. The report then counts the assumptions that hold a passing card (add `"assumption": 1` to a card to point it at the first one). The block above shows the smallest working contents.

`source-context` writes one file per passing card in `second-guess-runs/NAME/source-context/`. In an agent run, a second AI reads each file, and `drop-card --index N --reason TEXT` drops a card it doubts. By hand, read those files yourself.

Every command prints JSON and exits non-zero when it refuses. A card that fails its check is different: `check-cards` reports it in the JSON and still exits 0.

## When `stats` says "I don't know"

`stats` is the part that reads a dataset. A feature is one column the formula may use. The outcome column is the column it tries to predict. It answers `I don't know` in cases such as these, and there are others:

- The dataset has more than 500 features or more than 5,000 raw columns. A raw column is any column in the file.
- The dataset has fewer than about 1,000 rows. It will often answer `I don't know` there, even when a real effect exists.
- An outcome has fewer than 20 cases in the later part of the data. This was seen with 200 rows.
- The run takes longer than 90 seconds. This was seen with 499 features at 3,000 rows.
- The outcome column or one of its values looks like a purchase, such as `winLoss`, `retained` or `closed`.
- No dataset that fits the idea was found.

