"""Step 5. Arm 1: LogisticRegression on parent category, log10(goal x static_usd_rate), country; fit on the train split only. Run: uv run python arm1.py"""
import json, math, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import resolve
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
def feats(r): return {'parent=' + str(r['parent']): 1, 'country=' + str(r['country']): 1, 'log_usd_goal': math.log10(max(r['usd_goal'], 1))}
res = {r['id']: r['state'] for r in jl(P('resolved.jsonl')) if r.get('state')}
tr = [r for r in resolve.train_pool()[:resolve.TRAIN_N] if res.get(r['id']) in ('successful', 'failed')]  # exactly the registered 2,200
assert resolve.TRAIN_N == 2200 and len(tr) >= 2000, 'only %d labelled of the registered 2,200' % len(tr)
te = jl(P('test.jsonl'))
v = DictVectorizer(); X = v.fit_transform([feats(r) for r in tr]); y = [1 if res[r['id']] == 'successful' else 0 for r in tr]
m = LogisticRegression(max_iter=1000).fit(X, y)
p = m.predict_proba(v.transform([feats(r) for r in te]))[:, 1]
json.dump({str(r['id']): float(q) for r, q in zip(te, p)}, open(P('arm1_preds.json'), 'w'))
print('ARM1 train n=%d funded share %.3f, predictions %d' % (len(tr), sum(y) / len(y), len(te)))
