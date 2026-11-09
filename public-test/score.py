"""Step 11. Score arms per model. Pass rule (fixed in PREREGISTRATION.md): per model, arm 3 Brier at least 10% below arm 1. Arm 4 is exploratory, outside the rule.
Brier: failed 0, funded 1. Writes scores.json."""
import glob, json, os, random, statistics as st, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
MIN_N = 1000  # fewer shared scored ids than this: INCOMPLETE, no verdict
def brier(preds, outs):
    return st.fmean((p - o) ** 2 for p, o in zip(preds, outs))
def boot(d, reps=2000, seed=1):
    r = random.Random(seed); m = sorted(st.fmean(r.choices(d, k=len(d))) for _ in range(reps)); return m[int(.025 * reps)], m[int(.975 * reps)]
def bins(preds, outs, k=10):
    b = collections.defaultdict(list)
    for p, o in zip(preds, outs): b[min(k - 1, int(p * k))].append((p, o))
    return [dict(bin=i, n=len(v), mean_p=round(st.fmean(x[0] for x in v), 3), funded=round(st.fmean(x[1] for x in v), 3)) for i, v in sorted(b.items())]
def split_brier(ids, covered, pr, y):
    """Descriptive only, outside the pass rule: Brier of arms 1, 2, 3 and n on covered ids and on the rest. An arm missing an id leaves it out of that arm's n."""
    out = {}
    for name, grp in (('covered', [i for i in ids if i in covered]), ('rest', [i for i in ids if i not in covered])):
        out[name] = {'n': len(grp)}
        for a in (1, 2, 3):
            g = [i for i in grp if i in pr(a)]
            out[name]['arm%d' % a] = dict(n=len(g), brier=round(brier([pr(a)[i] for i in g], [y[i] for i in g]), 4)) if g else dict(n=0, brier=None)
    return out
def main():
    res = {r['id']: r['state'] for r in jl(P('resolved.jsonl')) if r.get('state')}
    test = {t['id'] for t in jl(P('test.jsonl'))}
    y = {i: 1 if s == 'successful' else 0 for i, s in res.items() if i in test and s in ('successful', 'failed')}
    arm1 = {int(k): v for k, v in json.load(open(P('arm1_preds.json'))).items()} if os.path.exists(P('arm1_preds.json')) else {}
    out = dict(canceled_or_suspended=sum(1 for i, s in res.items() if i in test and s not in ('successful', 'failed')), unresolved=len(test - set(res)), models={})
    for model in ('opus', 'sol'):
        arms = {2: {}, 3: {}, 4: {}}; no_cards = set(); covered = set()
        for f in glob.glob(P('odds', '%s_arm*.json' % model)):
            j = json.load(open(f))
            arms[j['arm']].update({int(k): v for k, v in j['odds'].items()})
            if j['arm'] == 3: (covered if j['cards_used'] else no_cards).update(int(k) for k in j['odds'])
        pr = lambda a: (arm1 if a == 1 else arms[a])
        ids = sorted(set(arm1) & set(arms[3]) & set(y))  # pass rule: arm 1 & arm 3 & outcome
        if not ids: out['models'][model] = 'no shared ids'; continue
        yy = [y[i] for i in ids]; B = {a: brier([pr(a)[i] for i in ids], yy) for a in (1, 3)}
        sq = lambda a: [(pr(a)[i] - y[i]) ** 2 for i in ids]
        gap = [x - z for x, z in zip(sq(3), sq(1))]; share = st.fmean(yy)
        m = dict(n=len(ids), funded_share=round(share, 4), constant_brier=round(share * (1 - share), 4), brier={str(a): round(B[a], 4) for a in B},
                 gap_arm3_minus_arm1=round(st.fmean(gap), 4), gap_ci95=[round(x, 4) for x in boot(gap)],
                 relative_change_arm3_vs_arm1=round(B[3] / B[1] - 1, 4), PASS=(B[3] <= 0.9 * B[1]) if len(ids) >= MIN_N else None,
                 status='COMPLETE' if len(ids) >= MIN_N else 'INCOMPLETE: n=%d under %d, no verdict' % (len(ids), MIN_N),
                 projects_arm3_without_cards=len(no_cards & set(ids)), calibration={str(a): bins([pr(a)[i] for i in ids], yy) for a in (1, 3)})
        for a in (2, 4):  # own subsets, n printed
            ia = sorted(set(arm1) & set(arms[a]) & set(y))
            if ia: m['arm%d%s' % (a, '_exploratory' if a == 4 else '')] = dict(n=len(ia), brier=round(brier([arms[a][i] for i in ia], [y[i] for i in ia]), 4), arm1_same_ids=round(brier([arm1[i] for i in ia], [y[i] for i in ia]), 4))
        m['descriptive_covered_vs_rest'] = split_brier(ids, covered, pr, y)  # outside the pass rule
        out['models'][model] = m
    import odds; out['router_error_batches'] = odds.router_summary()
    json.dump(out, open(P('scores.json'), 'w'), indent=1)
    for k, m in out['models'].items(): print(json.dumps(m) if isinstance(m, str) else '%s n=%d brier=%s PASS(arm3 <= 0.9*arm1)=%s %s' % (k, m['n'], m['brier'], m['PASS'], m['status']) + ''.join(' %s(n=%d)=%s' % (x, m[x]['n'], m[x]['brier']) for x in m if x.startswith('arm')))
    for k, m in out['models'].items():
        if not isinstance(m, str): print('DESCRIPTIVE (outside the pass rule) %s covered vs rest: %s' % (k, json.dumps(m['descriptive_covered_vs_rest'])))
    print('canceled/suspended excluded', out['canceled_or_suspended'], 'unresolved', out['unresolved'], 'router_error_batches', json.dumps(out['router_error_batches']))
if __name__ == '__main__': main()
