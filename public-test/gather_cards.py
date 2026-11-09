"""Step 7. One Codex web-search run per parent category (up to 3 at once), skipping parents already saved in cards/.
Exit 0 all saved, 5 some failed, 3 budget stop, 4 kill (a tool item other than web_search in a log). Final line prints counts."""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import prompts
from odds import CODEX, ledger_total
BUDGET = 19.0; RES = 0.6; KILLED = []
def slug(p): return p.replace(' ', '_').replace('&', 'and')
def todo(parents, have): return [p for p in parents if slug(p) not in have]
def one(parent):
    out = P('cards', slug(parent) + '.json'); key = 'cards:' + slug(parent)
    if KILLED: return parent, 'skipped after kill'
    if ledger_total() + RES > BUDGET: return parent, 'budget'
    jl_append(P('ledger.jsonl'), dict(key=key, status='reserved', usd=RES))
    try: stdout, stderr, rc = sol_run(prompts.CARD_PROMPT.format(parent=parent), 'medium', P('card.schema.json'), search=True, out=out + '.tmp', timeout=1200)
    except subprocess.TimeoutExpired: return parent, 'timeout'
    open(P('cards', slug(parent) + '.raw'), 'w').write(stdout + '\nSTDERR\n' + stderr)
    try: g = guard(stdout, CARD_ALLOW)
    except Kill as e:
        KILLED.append(parent); print('CARDS KILL', parent, e)  # batch discarded, raw log kept
        if os.path.exists(out + '.tmp'): os.rename(out + '.tmp', out + '.killed')
        return parent, 'kill'
    tin, tout = g['tin'], g['tout']
    jl_append(P('ledger.jsonl'), dict(key=key, status='done', usd=cost('sol', tin, tout), tin=tin, tout=tout))
    open(P('cards', slug(parent) + '.log'), 'w').write(json.dumps(g['types']))
    try: cards = json.loads(open(out + '.tmp').read())['cards']
    except Exception: return parent, 'no output'
    json.dump(cards, open(out, 'w')); os.remove(out + '.tmp'); return parent, 'ok'
if __name__ == '__main__':
    os.makedirs(P('cards'), exist_ok=True)
    parents = sorted({t['parent'] for t in jl(P('test.jsonl'))})
    have = {f[:-5] for f in os.listdir(P('cards')) if f.endswith('.json')}
    work = todo(parents, have)
    with ThreadPoolExecutor(3) as ex: res = list(ex.map(one, work))
    bad = [r for r in res if r[1] != 'ok']
    print('CARDS parents %d, saved before %d, fetched now %d, failed %s, ledger=%.2f' % (len(parents), len(have), len(res) - len(bad), bad, ledger_total()))
    sys.exit(4 if KILLED else 3 if any(b[1] == 'budget' for b in bad) else 5 if bad else 0)
