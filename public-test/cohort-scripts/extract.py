# Compact each monthly file: one dict per unique id, all outcomes + text, plus collection metadata.
import gzip, json, sys, collections, pickle, datetime as dt, os
utc = dt.timezone.utc
for p in sys.argv[2:]:
    out = {}; lines = 0; bad = 0; topkeys = collections.Counter(); srcs = collections.Counter()
    bymonth = collections.defaultdict(collections.Counter); states = collections.Counter()
    for line in gzip.open(p, 'rt', encoding='utf-8'):
        try: j = json.loads(line); d = j['data']
        except Exception: bad += 1; continue
        lines += 1
        for k in j:
            if k != 'data': topkeys[k] += 1
        srcs[str(j.get('source_url'))[:80]] += 1
        if lines == 1:
            first = {k: (v if not isinstance(v,(dict,list)) else '{..}') for k, v in j.items() if k != 'data'}
            dkeys = sorted(d)
        c = d.get('category') or {}
        out[d['id']] = dict(id=d['id'], state=d.get('state'), la=d.get('launched_at'), dl=d.get('deadline'),
            sc=d.get('state_changed_at'), cr=d.get('created_at'), name=d.get('name'), blurb=d.get('blurb'),
            goal=d.get('goal'), rate=d.get('static_usd_rate'), country=d.get('country'),
            cat=c.get('name'), parent=c.get('parent_name'), up=d.get('usd_pledged'), bk=d.get('backers_count'), pf=d.get('percent_funded'),
            slug=d.get('slug'), spot=d.get('spotlight'), staff=d.get('staff_pick'))
    for r in out.values():
        states[r['state']] += 1
        m = dt.datetime.fromtimestamp(r['la'], utc).strftime('%Y-%m') if r['la'] else 'none'
        bymonth[m][r['state']] += 1
    name = os.path.basename(p)[:30]
    pickle.dump(out, open(os.path.join(sys.argv[1], name + '.pkl'), 'wb'))
    print(name, 'lines', lines, 'bad', bad, 'unique', len(out), dict(states), 'first', first, 'keys', dkeys if lines else None, 'srcs', len(srcs), srcs.most_common(4), flush=True)
