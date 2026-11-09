#!/bin/bash
# Resumable. 15 Codex search runs (3 at once), then check_cards.py on both routes. Exit nonzero on any failure.
cd "$(dirname "$0")" || exit 1
python3 gather_cards.py; rc=$?; [ $rc -ne 0 ] && { echo "RUN_CARDS stopped rc=$rc"; exit $rc; }
python3 check_cards.py; rc=$?
echo "RUN_CARDS rc=$rc ledger=$(python3 -c 'from odds import ledger_total as l;print(round(l(),2))')"; exit $rc
