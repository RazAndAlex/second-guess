#!/bin/bash
# Arm 1 fit on the registered 2,200 train ids. Run after run_resolve.sh finished (exit 0). Writes arm1_preds.json.
cd "$(dirname "$0")" || exit 1
uv run python arm1.py
