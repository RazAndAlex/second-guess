#!/bin/bash
# Resumable. Fetches stats.json outcomes (test ids, then 2,200 train ids), then runs the split kill checks. Exit nonzero on throttle stop or a kill check.
cd "$(dirname "$0")" || exit 1
python3 resolve.py --set test; rc=$?; [ $rc -ne 0 ] && { echo "RUN_RESOLVE stopped rc=$rc"; exit $rc; }
python3 resolve.py --set train; rc=$?; [ $rc -ne 0 ] && { echo "RUN_RESOLVE stopped rc=$rc"; exit $rc; }
python3 -I split.py --check; rc=$?
echo "RUN_RESOLVE rows=$(wc -l < resolved.jsonl) split_check_rc=$rc"; exit $rc
