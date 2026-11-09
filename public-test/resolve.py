"""Step 3. Fetch project.state from stats.json for each id in test.jsonl then train.jsonl. Resumable.
Skips ids saved in resolved.jsonl, 1.1 s between requests, generic User-Agent, stops after 2 throttle codes in a row.
Usage: python3 resolve.py [--set test|train|all] (train = first 2,200 of a seeded shuffle) [--limit N]    exit 2 if stopped by throttle"""
import json, subprocess, sys, time, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
THROTTLE = ('429', '403', '503'); UA = 'Mozilla/5.0'
TRAIN_N = 2200  # arm 1 trains on a seeded random 2,200 of the train ids (plan: ~2,150 more requests)
def train_pool():
    import random; rows = jl(P('train.jsonl')); random.Random(7).shuffle(rows); return rows
def pending(rows, done):
    return [r for r in rows if r['id'] not in done]
def fetch(url):
    r = subprocess.run(['curl', '-s', '-m', '20', '-A', UA, '-w', '\n%{http_code}', url + '/stats.json?v=1'], capture_output=True, text=True)
    body, _, code = r.stdout.rpartition('\n'); st = None
    try: st = json.loads(body)['project']
    except Exception: pass
    return code, st
def run(rows, done, out, fetch=fetch, sleep=time.sleep, gap=1.1, backoff=60):
    n = bad = 0; stopped = False
    for r in pending(rows, done):
        code, st = fetch(r['url'])
        jl_append(out, dict(id=r['id'], code=code, state=st and st['state'], pledged=st and st.get('pledged'), sc=st and st.get('state_changed_at')))
        done.add(r['id']); n += 1
        if code in THROTTLE:
            bad += 1
            if bad >= 2: stopped = True; break
            sleep(backoff)
        else: bad = 0
        sleep(gap)
    return n, stopped
if __name__ == '__main__':
    a = sys.argv; which = a[a.index('--set') + 1] if '--set' in a else 'all'; lim = int(a[a.index('--limit') + 1]) if '--limit' in a else 10**9
    rows = (jl(P('test.jsonl')) if which in ('test', 'all') else []) + (train_pool()[:TRAIN_N] if which in ('train', 'all') else [])
    out = P('resolved.jsonl'); done = {r['id'] for r in jl(out) if r.get('state')}
    todo = pending(rows, done)[:lim]
    n, stopped = run(todo, done, out)
    left = len(pending(rows, {r['id'] for r in jl(out) if r.get('state')}))
    print('RESOLVE fetched %d, left %d, throttled_stop %s' % (n, left, stopped)); sys.exit(2 if stopped else 0)
