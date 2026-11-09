"""Step 2: funded share per monthly file and launch quarter. Diagnostic only; no step takes a base rate from it.
Run: python3 -I filter.py   (reads parsed pickles, one record per id, first per file)"""
import pickle, glob, collections, datetime as dt, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import TEST, utc
for p in sorted(glob.glob(os.path.join(TEST, 'work', 'Kickstarter_*.pkl')) + [os.path.join(TEST, 'work', 'raw.json.gz.pkl')]):
    D = pickle.load(open(p, 'rb')); c = collections.defaultdict(collections.Counter)
    for r in D.values():
        if r['la']:
            q = dt.datetime.fromtimestamp(r['la'], utc); c['%dQ%d' % (q.year, (q.month - 1) // 3 + 1)][r['state']] += 1
    print(os.path.basename(p), 'ids', len(D))
    for q in sorted(c)[-6:]:
        s, f = c[q]['successful'], c[q]['failed']
        print('  %s funded/(f+s) %.2f n=%d  (diagnostic only)' % (q, s / max(1, s + f), s + f))
