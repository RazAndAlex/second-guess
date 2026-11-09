"""Step 10. Odds batches for arms 2/3/4 on opus (claude -p) and sol (codex), no tools.
  python3 odds.py --build                      write batches.json (1,000 funded/failed test ids, 25 per batch, seeded)
  python3 odds.py --model opus|sol --arm 2|3|4 [--effort low|medium] [--budget 19] [--only-first N]
  python3 odds.py --preflight --model M [--effort E]   one arm-2 batch, tool-free proof, writes preflight/
Skips batches whose file exists; writes a worst-case reservation to ledger.jsonl before each call and the measured cost after.
Exit: 0 ok, 3 budget reached, 4 KILL (tool use, wrong model, bad output)."""
import json, os, random, subprocess, sys, collections, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import prompts
SEED = 20261105; BATCH = 25; N = 1000; PASSING = 3
RESERVE = {'sol': 0.6, 'opus': 1.0}; BUDGET = 19.0; MAX_ROUTER_BATCHES = 5
class Budget(Exception): pass
def eligible():
    res = {r['id']: r['state'] for r in jl(P('resolved.jsonl')) if r.get('state')}
    return [t for t in jl(P('test.jsonl')) if res.get(t['id']) in ('successful', 'failed')]
def make_batches(rows, seed=SEED, n=N, size=BATCH):
    rows = sorted(rows, key=lambda r: r['id']); random.Random(seed).shuffle(rows); rows = rows[:n]
    by = collections.defaultdict(list)
    for r in rows: by[r['parent']].append(r['id'])
    out = []
    for p in sorted(by):
        for k in range(0, len(by[p]), size): out.append(dict(batch='%s-%02d' % (p.replace(' ', '_').replace('&', 'and'), k // size), parent=p, ids=by[p][k:k + size]))
    return out
def ledger_total():
    last = {}
    for r in jl(P('ledger.jsonl')): last[r['key']] = r['usd']
    return sum(last.values())
def router_summary():
    """-> {'model_armN': batches with router_errors > 0}, over the finished batch files."""
    import glob
    c = collections.Counter()
    for f in glob.glob(P('odds', '*.json')):
        j = json.load(open(f))
        if (j.get('router_errors') or 0) > 0: c['%s_arm%d' % (j['model'], j['arm'])] += 1
    return dict(c)
def url_key(u):
    """One page, one key: archive prefix unwrapped, no scheme, lower-case host without www., no query, fragment, /index.html or trailing slash."""
    import re, urllib.parse
    u = (u or '').strip(); m = re.match(r'https?://web\.archive\.org/web/[0-9a-z_]*/(https?://.*)', u, re.I)
    if m: u = m.group(1)
    p = urllib.parse.urlsplit(u); host = p.netloc.lower(); host = host[4:] if host.startswith('www.') else host
    path = re.sub(r'/index\.html?$', '', p.path, flags=re.I).rstrip('/')
    return host + path
def passing_cards(parent):
    f = P('cards_pass', parent.replace(' ', '_').replace('&', 'and') + '.json')
    seen = set(); out = []
    for c in (json.load(open(f)) if os.path.exists(f) else []):
        k = url_key(c.get('url'))
        if k not in seen: seen.add(k); out.append(c)  # 3 passing cards = 3 different pages
    return out
def parse(model, out):
    """-> (odds dict, tin, tout, tool_items). Raises ValueError on a kill."""
    if model == 'sol':
        g = guard(out, ODDS_ALLOW)  # raises Kill on any tool item
        if g['msg'] is None: raise ValueError('BAD: no agent_message')
        return json.loads(g['msg']), g['tin'], g['tout'], [], g['types']
    ev = [json.loads(l) for l in out.splitlines() if l.startswith('{')]
    j = [e for e in ev if e.get('type') == 'result'][-1]; u = j.get('usage', {}); tools = []
    listed = next((e.get('tools') for e in ev if e.get('type') == 'system' and e.get('subtype') == 'init'), None)
    used = [c.get('name') for e in ev if e.get('type') == 'assistant' for c in e['message']['content'] if c.get('type') == 'tool_use']
    # StructuredOutput is the built-in call that returns the schema answer (num_turns=2 is that call); anything else is a kill
    tools = [t for t in (listed or []) if t != 'StructuredOutput'] + [t for t in used if t != 'StructuredOutput']
    mu = j.get('modelUsage') or {}; models = list(mu)
    o = mu.get('claude-opus-5-5')
    if not o: raise Kill('KILL: model not claude-opus-5-5: %s' % models)
    if any(v.get('provider') != 'firstParty' for v in mu.values()): raise Kill('KILL: not a first-party login: %s' % {k: v.get('provider') for k, v in mu.items()})
    tin = o['inputTokens'] + o['cacheCreationInputTokens'] + o['cacheReadInputTokens']; tout = o['outputTokens']  # haiku side call (~$0.0001) not counted
    return j.get('structured_output') or json.loads(j['result']), tin, tout, tools, dict(models=models, tools_listed=listed, tool_calls=used, total_cost_usd=j.get('total_cost_usd'))
def call(model, prompt, effort):
    if model == 'sol': return sol_run(prompt, effort, P('odds.schema.json'))
    env = {k: v for k, v in os.environ.items() if k not in ('ANTHROPIC_BASE_URL', 'ANTHROPIC_AUTH_TOKEN')}
    cmd = ['claude', '-p', '--model', 'opus', '--tools', '', '--setting-sources', 'project', '--output-format', 'stream-json', '--verbose', '--json-schema', json.dumps(prompts.ODDS_SCHEMA),
           '--no-session-persistence', '--strict-mcp-config', '--max-budget-usd', '1', '--effort', effort]
    r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=tempfile.mkdtemp(prefix='ks-empty-'), env=env, timeout=900)
    return r.stdout, r.stderr, r.returncode
def validate(o, ids):
    got = {x['id']: x['p'] for x in o['odds']}
    if sorted(got) != sorted(ids) or len(o['odds']) != len(ids): raise ValueError('BAD: ids mismatch')
    if any(not (0 <= p <= 1) for p in got.values()): raise ValueError('BAD: p out of range')
    return got
RETRIES = 2  # at most 2 retries per batch; each attempt has its own ledger key
def usage_cost(model, stdout):
    """Best-effort cost of a failed attempt from its log; 0 if unreadable (the reservation then stays in the ledger)."""
    try:
        if model == 'sol': g = guard_loose(stdout); return cost('sol', g[0], g[1])
        j = [json.loads(l) for l in stdout.splitlines() if l.startswith('{')]; return [e for e in j if e.get('type') == 'result'][-1].get('total_cost_usd') or 0
    except Exception: return 0
def guard_loose(log):
    tin = tout = 0
    for l in log.splitlines():
        try: e = json.loads(l)
        except Exception: continue
        if isinstance(e, dict) and e.get('type') == 'turn.completed': u = e.get('usage', {}); tin += u.get('input_tokens', 0); tout += u.get('output_tokens', 0)
    return tin, tout
def run_batch(model, arm, b, rows_by_id, effort, outdir, tag='', key=None):
    rows = [rows_by_id[i] for i in b['ids']]; cards = passing_cards(b['parent']) if arm in (3, 4) else None
    prompt = prompts.build(arm, rows, cards); base = os.path.join(outdir, '%s_arm%d_%s%s' % (model, arm, b['batch'], tag)); last = None
    for n in range(RETRIES + 1):
        k = '%s.retry%d' % (key, n) if key and n else key
        if n and ledger_total() + RESERVE[model] > BUDGET: raise Budget()
        if n and k: jl_append(P('ledger.jsonl'), dict(key=k, status='reserved', usd=RESERVE[model]))
        stdout, stderr, rc = call(model, prompt, effort); fail = '%s.fail%d.raw' % (base, n)
        try:
            p = parse(model, stdout); o, tin, tout, tools = p[:4]
            got = validate(o, b['ids'])
            if tools: raise Kill('KILL: tool items %s' % tools)
        except Kill:
            open(fail, 'w').write(stdout + '\nSTDERR\n' + stderr)
            if k: jl_append(P('ledger.jsonl'), dict(key=k, status='done', usd=usage_cost(model, stdout)))
            raise
        except (ValueError, KeyError, TypeError, IndexError, json.JSONDecodeError) as e:
            open(fail, 'w').write(stdout + '\nSTDERR\n' + stderr); last = e
            if k: jl_append(P('ledger.jsonl'), dict(key=k, status='done', usd=usage_cost(model, stdout)))
            continue
        usd = cost('opus' if model == 'opus' else 'sol', tin, tout)
        if model == 'opus': usd = max(usd, p[4].get('total_cost_usd') or 0)  # cache writes bill above list input price; take the larger
        extra = p[4:] if model == 'opus' else None
        json.dump(dict(batch=b['batch'], model=model, arm=arm, effort=effort, odds=got, tin=tin, tout=tout, usd=usd, attempts=n + 1, cards_used=len(cards or []) >= PASSING, n_cards=len(cards or []), extra=extra,
                       item_types=p[4] if model == 'sol' else None, router_errors=stderr.count('codex_core::tools::router') if model == 'sol' else None), open(base + '.json', 'w'))  # router_errors: tool calls the model tried that failed with no log item
        open(base + '.raw', 'w').write(stdout)
        return usd, tin, tout, tools, (k or key)
    raise ValueError('no valid answer after %d attempts: %s' % (RETRIES + 1, last))
if __name__ == '__main__':
    a = sys.argv; arg = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    if '--build' in a:
        res = {r['id'] for r in jl(P('resolved.jsonl')) if r.get('state')}; unres = sum(1 for t in jl(P('test.jsonl')) if t['id'] not in res)
        if unres > 0.02 * 1544: print('KILL: %d test ids unresolved; batches.json not written' % unres); sys.exit(4)
        b = make_batches(eligible()); json.dump(b, open(P('batches.json'), 'w')); print('BATCHES', len(b), 'projects', sum(len(x['ids']) for x in b)); sys.exit(0)
    if '--router' in a:
        s = router_summary(); print('ROUTER_ERROR_BATCHES', json.dumps(s)); sys.exit(4 if any(v > MAX_ROUTER_BATCHES for v in s.values()) else 0)
    model = arg('--model'); effort = arg('--effort', 'medium'); budget = float(arg('--budget', 19)); BUDGET = budget; rows_by_id = {t['id']: t for t in jl(P('test.jsonl'))}
    if '--preflight' in a:
        os.makedirs(P('preflight'), exist_ok=True); b = make_batches(eligible())[0]
        try: usd, tin, tout, tools, _ = run_batch(model, 2, b, rows_by_id, effort, P('preflight'), '_' + effort)
        except (ValueError, Kill) as e: print('PREFLIGHT STOP', e); sys.exit(4)
        print('PREFLIGHT %s effort=%s ok tin=%d tout=%d usd=%.4f tools=%s' % (model, effort, tin, tout, usd, tools)); sys.exit(0)
    arm = int(arg('--arm')); os.makedirs(P('odds'), exist_ok=True); batches = json.load(open(P('batches.json'))); done = ex = 0
    if arm == 4 and ledger_total() >= 15: print('ODDS arm4 skipped: ledger %.2f >= 15' % ledger_total()); sys.exit(0)
    for b in batches[:int(arg('--only-first', 10**6))]:
        key = '%s_arm%d_%s' % (model, arm, b['batch'])
        if os.path.exists(P('odds', key + '.json')): ex += 1; continue
        if ledger_total() + RESERVE[model] > budget: print('ODDS budget stop ledger=%.2f done=%d existing=%d' % (ledger_total(), done, ex)); sys.exit(3)
        jl_append(P('ledger.jsonl'), dict(key=key, status='reserved', usd=RESERVE[model]))
        try: usd, tin, tout, tools, lk = run_batch(model, arm, b, rows_by_id, effort, P('odds'), key=key)
        except Budget: print('ODDS budget stop in retry', key, 'ledger=%.2f' % ledger_total()); sys.exit(3)
        except Kill as e: print('ODDS KILL', key, e); sys.exit(4)
        except (ValueError, subprocess.TimeoutExpired) as e: print('ODDS ERR', key, e); sys.exit(5)
        jl_append(P('ledger.jsonl'), dict(key=lk, status='done', usd=usd, tin=tin, tout=tout)); done += 1
    print('ODDS %s arm%d done=%d existing=%d ledger=%.2f' % (model, arm, done, ex, ledger_total()))
