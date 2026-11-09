"""Step 4. Writes test.jsonl (1,544 outcome-blind ids) and train.jsonl; --check runs the kill checks on resolved.jsonl.
Run: python3 -I split.py            build id lists (train urls need a pass over 4 gz files, a few minutes)
     python3 -I split.py --check    kill checks, exits nonzero"""
import pickle, gzip, json, os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
W = lambda n: os.path.join(TEST, 'work', n)
FILES = ['Kickstarter_2025-07-14T06_25_27_218Z', 'Kickstarter_2026-01-12T09_37_51_016Z', 'Kickstarter_2026-05-12T07_26_57_886Z', 'Kickstarter_2026-06-11T03_20_11_324Z']
def row(r, url):
    g = r['goal'] or 0; rt = r['rate'] or 1
    return dict(id=r['id'], url=url, name=r['name'], blurb=r['blurb'], goal=g, rate=rt, usd_goal=round(g * rt, 2), country=r['country'], cat=r['cat'], parent=r['parent'] or r['cat'])
def build():
    fate = pickle.load(open(W('fate.pkl'), 'rb')); urls = pickle.load(open(W('urls.pkl'), 'rb'))
    ids = pickle.load(open(W('aug_ids.pkl'), 'rb'))
    with open(P('test.jsonl'), 'w') as o:
        for i in sorted(ids): o.write(json.dumps(row(fate[i]['live'], urls[i])) + '\n')  # fate live = first live capture
    print('test', len(ids), flush=True)
    train = {}
    for n in FILES:  # first file where the project is live
        D = pickle.load(open(W(n[:30] + '.pkl'), 'rb'))
        for i, r in D.items():
            if i in train or r['state'] != 'live' or not r['la'] or not r['dl']: continue
            if r['la'] < T(CUTOFF) and (r['dl'] - r['la']) / 86400 >= 29.5 and r['dl'] < T('2026-07-14'): train[i] = r
    print('train ids', len(train), flush=True)
    urlmap = {}
    for n in FILES:  # urls only exist in the gz files
        for line in gzip.open(os.path.join(TEST, 'data', n + '.json.gz'), 'rt', encoding='utf-8'):
            if '"state":"live"' not in line: continue
            d = json.loads(line)['data']
            if d['id'] in train and d['id'] not in urlmap: urlmap[d['id']] = d['urls']['web']['project']
        print('urls', n[11:21], len(urlmap), flush=True)
    with open(P('train.jsonl'), 'w') as o:
        for i, r in sorted(train.items()):
            if i in urlmap: o.write(json.dumps(row(r, urlmap[i])) + '\n')
    print('train written', sum(1 for i in train if i in urlmap))
def check():
    res = {r['id']: r for r in jl(P('resolved.jsonl')) if r.get('state')}
    test = jl(P('test.jsonl')); st = collections.Counter(res[t['id']]['state'] for t in test if t['id'] in res)
    unres = sum(1 for t in test if t['id'] not in res)
    v = collections.Counter(r['state'] for r in jl(P('val25_import.jsonl')))
    print('test states', dict(st), 'unresolved', unres, 'of', len(test))
    print('2025-07-14 live sample funded/all ended %.3f vs site 0.563 (n=%d)' % (v['successful'] / max(1, sum(v.values()) - v['live']), sum(v.values())))
    bad = []
    if st['failed'] < 100: bad.append('KILL: fewer than 100 failed in test (%d)' % st['failed'])
    if unres > 0.02 * len(test): bad.append('KILL: %d unresolved test ids is more than 2%%' % unres)
    print('\n'.join(bad) or 'split checks ok'); sys.exit(1 if bad else 0)
if __name__ == '__main__': check() if '--check' in sys.argv else build()
