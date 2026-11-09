#!/usr/bin/env python3 -I
"""Independent recompute of scores.json from raw odds logs, arm1_preds.json and resolved.jsonl. Own arithmetic, no imports from KS.
Usage: python3 -I verify_scores.py [page.html]. Exit 0 only if all Briers equal scores.json to 4 decimals, n>=1000, unresolved<2%."""
import json, glob, os, sys, re
KS = os.path.dirname(os.path.abspath(__file__))
def parse_raw(path):
    """-> dict id->p taken from the raw log only (opus: StructuredOutput tool_use input; sol: the agent_message text)."""
    odds = None
    for l in open(path):
        if not l.startswith('{'): continue
        e = json.loads(l)
        if e.get('type') == 'assistant':
            for c in e['message']['content']:
                if c.get('type') == 'tool_use' and c.get('name') == 'StructuredOutput': odds = c['input']['odds']
        elif e.get('type') == 'result' and e.get('structured_output'):
            so = e['structured_output']['odds']
            assert odds is None or odds == so, 'opus tool_use input differs from result'; odds = so
        elif e.get('type') == 'item.completed' and e['item'].get('type') == 'agent_message':
            odds = json.loads(e['item']['text'])['odds']
    assert odds is not None, path
    d = {x['id']: x['p'] for x in odds}; assert len(d) == len(odds), 'duplicate id ' + path
    return d
def load_preds():
    pr = {}  # (model, arm) -> {id: p}
    cov = {}  # model -> set of ids in arm-3 batches that used cards
    for f in sorted(glob.glob(KS + '/odds/*_arm[23]_*.raw')):
        b = os.path.basename(f)
        if '.fail' in b or b.startswith(('sol_arm2_FAKE',)): continue
        m = re.match(r'(opus|sol)_arm(\d)_(.+)\.raw$', b)
        if not m: continue
        model, arm, batch = m.group(1), int(m.group(2)), m.group(3)
        d = parse_raw(f); jf = json.load(open(f[:-4] + '.json'))
        assert {int(k): v for k, v in jf['odds'].items()} == d, 'json odds != raw for ' + b
        t = pr.setdefault((model, arm), {})
        assert not set(t) & set(d), 'id twice ' + b
        t.update(d)
        if arm == 3 and jf['cards_used']: cov.setdefault(model, set()).update(d)
    return pr, cov
def brier(p, y): return sum((a - b) ** 2 for a, b in zip(p, y)) / len(y)
def main(page=None):
    pr, cov = load_preds()
    arm1 = {int(k): v for k, v in json.load(open(KS + '/arm1_preds.json')).items()}
    st = {}
    for l in open(KS + '/resolved.jsonl'):
        r = json.loads(l)
        if r.get('state'): st[r['id']] = r['state']  # last good row wins
    sc = json.load(open(KS + '/scores.json')); ok = True; rep = []
    def chk(name, mine, theirs):
        nonlocal ok
        good = round(mine, 4) == theirs; ok &= good
        rep.append('%-34s mine %.6f -> %.4f   scores.json %s   %s' % (name, mine, round(mine, 4), theirs, 'OK' if good else 'MISMATCH'))
    heads = []
    for model in ('opus', 'sol'):
        ids_all = set(pr[(model, 3)])
        assert ids_all == set(pr[(model, 2)]), 'arm2/arm3 id lists differ'
        unres = [i for i in ids_all if st.get(i) not in ('successful', 'failed')]
        ids = sorted(ids_all - set(unres)); y = {i: 1 if st[i] == 'successful' else 0 for i in ids}
        yy = [y[i] for i in ids]; s = sc['models'][model]
        share = sum(yy) / len(yy)
        rep.append('%s n=%d (raw ids %d, unresolved/canceled among them %d = %.2f%%) funded share %.4f (scores %s)' % (model, len(ids), len(ids_all), len(unres), 100 * len(unres) / len(ids_all), share, s['funded_share']))
        ok &= len(ids) >= 1000 and len(unres) / len(ids_all) < 0.02 and len(ids) == s['n'] and round(share, 4) == s['funded_share']
        b = {1: brier([arm1[i] for i in ids], yy), 2: brier([pr[(model, 2)][i] for i in ids], yy), 3: brier([pr[(model, 3)][i] for i in ids], yy)}
        chk(model + ' constant', share * (1 - share), s['constant_brier'])
        chk(model + ' arm1', b[1], s['brier']['1']); chk(model + ' arm2', b[2], s['arm2']['brier']); chk(model + ' arm3', b[3], s['brier']['3'])
        chk(model + ' arm2 arm1_same_ids', b[1], s['arm2']['arm1_same_ids'])
        pas = b[3] <= 0.9 * b[1]; ok &= pas == s['PASS']; rep.append('%s pass rule arm3 %.4f <= 0.9*arm1 %.4f -> %s (scores %s)' % (model, b[3], .9 * b[1], pas, s['PASS']))
        ok &= round(b[3] - b[1], 4) == s['gap_arm3_minus_arm1']; rep.append('%s gap %.4f (scores %s)' % (model, b[3] - b[1], s['gap_arm3_minus_arm1']))
        c = [i for i in ids if i in cov.get(model, set())]; r = [i for i in ids if i not in cov.get(model, set())]
        d = s['descriptive_covered_vs_rest']; ok &= len(c) == d['covered']['n'] and len(r) == d['rest']['n']
        rep.append('%s covered n=%d rest n=%d (scores %d/%d)' % (model, len(c), len(r), d['covered']['n'], d['rest']['n']))
        for nm, g in (('covered', c), ('rest', r)):
            for a in (1, 2, 3):
                p = arm1 if a == 1 else pr[(model, a)]
                chk('%s %s arm%d' % (model, nm, a), brier([p[i] for i in g], [y[i] for i in g]), d[nm]['arm%d' % a]['brier'])
        heads += [b[1], b[2], b[3], share * (1 - share)]
    out = '\n'.join(rep); print(out)
    if page:
        h = open(page).read()
        for v in sorted(set('%.4f' % x for x in heads)):
            hit = v in h; ok &= hit; print('page has %s: %s' % (v, hit))
    print('VERDICT', 'PASS exit 0' if ok else 'FAIL exit 1'); return 0 if ok else 1
if __name__ == '__main__': sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
