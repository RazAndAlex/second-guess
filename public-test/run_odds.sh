#!/bin/bash
# Resumable. Needs resolved.jsonl (run_resolve.sh), arm1_preds.json (run_arm1.sh) and cards_pass/ (run_cards.sh). Builds batches once, runs arms 2 and 3 on both models,
# then arm 4 (exploratory) only if the ledger is under $15. EFFORT is the preregistered setting. Any nonzero exit stops the run: 3 budget, 4 kill or refusal, 5 error.
# A kill or error in one model stops the other. More than 5 batches with router errors in one model and arm stops the run (exit 4). Arm 4 stops still score.
cd "$(dirname "$0")" || exit 1
set -o pipefail
# a plain kill of this script stops both models and their children
trap 'pkill -P ${po:-0} 2>/dev/null; pkill -P ${ps:-0} 2>/dev/null; kill ${po:-0} ${ps:-0} 2>/dev/null; pkill -P $$ 2>/dev/null; exit 130' INT TERM
EFFORT=$(cat EFFORT)
[ -f arm1_preds.json ] && [ arm1_preds.json -nt resolved.jsonl ] || { echo "REFUSED: arm1_preds.json missing or older than resolved.jsonl; run ./run_arm1.sh"; exit 4; }
rm -f scores.json  # a crashed score.py must never leave an old verdict behind
[ -f batches.json ] || python3 odds.py --build || exit 4
for arm in 2 3; do
  [ $arm -eq 3 ] && [ ! -d cards_pass ] && { echo "REFUSED: cards_pass/ missing; run ./run_cards.sh"; exit 4; }
  python3 odds.py --model opus --arm $arm --effort $EFFORT > odds_opus_$arm.out 2>&1 & po=$!
  python3 odds.py --model sol --arm $arm --effort $EFFORT > odds_sol_$arm.out 2>&1 & ps=$!
  # poll both; when one ends nonzero, signal the other
  ro=; rs=; fr=
  while [ -z "$ro" ] || [ -z "$rs" ]; do
    sleep 2
    if [ -z "$ro" ] && ! kill -0 $po 2>/dev/null; then wait $po; ro=$?; if [ $ro -ne 0 ] && [ -z "$rs" ]; then fr=${fr:-$ro}; pkill -P $ps 2>/dev/null; kill $ps 2>/dev/null; fi; fi
    if [ -z "$rs" ] && ! kill -0 $ps 2>/dev/null; then wait $ps; rs=$?; if [ $rs -ne 0 ] && [ -z "$ro" ]; then fr=${fr:-$rs}; pkill -P $po 2>/dev/null; kill $po 2>/dev/null; fi; fi
  done
  for m in opus sol; do tail -1 odds_${m}_$arm.out; done
  [ -n "$fr" ] && exit $fr
  [ $ro -ne 0 ] && exit $ro
  [ $rs -ne 0 ] && exit $rs
  python3 odds.py --router || exit $?
done
rc4=0
for m in opus sol; do python3 odds.py --model $m --arm 4 --effort $EFFORT 2>&1 | tail -1; rc=${PIPESTATUS[0]}; [ $rc -ne 0 ] && { rc4=$rc; break; }; done
python3 -I score.py | tail -6 || exit $?
echo "RUN_ODDS ledger=$(python3 -c 'from odds import ledger_total as l;print(round(l(),2))') batches=$(ls odds/*.json | wc -l) router_error_batches=$(python3 -c 'import json;from odds import router_summary as r;print(json.dumps(r()))') arm4_rc=$rc4"
exit $rc4
