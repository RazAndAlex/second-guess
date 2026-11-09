"""Shared paths and helpers. Run scripts from this folder."""
import json, os, collections, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__))
TEST = os.path.dirname(HERE)  # scratchpad/test
utc = dt.timezone.utc
T = lambda s: dt.datetime.fromisoformat(s).replace(tzinfo=utc).timestamp()
CUTOFF = '2026-07-01'
P = lambda *a: os.path.join(HERE, *a)
def jl(path):
    return [json.loads(l) for l in open(path)] if os.path.exists(path) else []
def jl_append(path, row):
    with open(path, 'a') as o:
        o.write(json.dumps(row) + '\n'); o.flush()
# prices per million tokens (revised.md)
PRICE = {'sol': (2.0, 10.0), 'opus': (4.0, 20.0), 'sonnet': (2.0, 10.0)}
def cost(model, tin, tout):
    pi, po = PRICE[model]; return (tin * pi + tout * po) / 1e6

class Kill(Exception):
    """A tool item or an unexpected error item appeared in a model log. The run stops (finding 7)."""
CODEX = json.load(open(os.path.expanduser('~/.vnext/runtimes/active.json')))['codex']['executable']
CODEX_HOME = os.path.join(TEST, 'codexhome'); EMPTY = os.path.join(TEST, 'empty')  # codexhome holds auth.json (symlink) plus plugin, cache and sqlite files; the sqlite tables are empty, so no memory carries between calls
SOL_FLAGS = [x for f in ('plugins', 'apps', 'shell_tool', 'code_mode_host', 'multi_agent', 'goals', 'image_generation', 'browser_use', 'computer_use', 'hooks') for x in ('--disable', f)]
SOL_EXEC = ['exec', '-m', 'gpt-6.1-sol', '-s', 'read-only', '--ephemeral', '--skip-git-repo-check', '--json']
CODE_MODE_ERR = 'Code Mode is unavailable because code-mode host is disabled'
ODDS_ALLOW = {'agent_message', 'reasoning'}; CARD_ALLOW = ODDS_ALLOW | {'web_search'}
def sol_cmd(prompt, effort, schema, search=False, out=None):
    """The one shared sol command. Absolute paths only, since cwd is the empty folder. Returns (cmd, env, cwd)."""
    flags = SOL_FLAGS if not search else [x for i, x in enumerate(SOL_FLAGS) if 'code_mode_host' not in (x, SOL_FLAGS[i - 1])]  # web search runs through the code mode host (measured 2026-11-05), so card calls leave it on
    cmd = [CODEX] + (['--search'] if search else []) + flags + SOL_EXEC[:1] + ['-c', 'model_reasoning_effort="%s"' % effort] + SOL_EXEC[1:] + ['--output-schema', os.path.abspath(schema)]
    if not search: cmd[cmd.index('exec') + 1:cmd.index('exec') + 1] = ['-c', 'web_search="disabled"']
    if out: cmd += ['-o', os.path.abspath(out)]
    return cmd + [prompt], dict(os.environ, CODEX_HOME=CODEX_HOME), EMPTY
def sol_run(prompt, effort, schema, search=False, out=None, timeout=900):
    import subprocess
    for d in (CODEX_HOME, EMPTY):
        if not os.path.isdir(d): raise SystemExit('KILL: folder missing: %s (create it; codexhome needs auth.json)' % d)
    cmd, env, cwd = sol_cmd(prompt, effort, schema, search, out)
    r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, cwd=cwd, env=env, timeout=timeout)
    return r.stdout, r.stderr, r.returncode
def guard(log, allow):
    """Per-batch guard on a codex --json log. -> dict(types, msg, tin, tout). Raises Kill on any item type outside allow, or any error
    item other than the Code Mode one. The raw log is the caller's to keep."""
    types = []; msg = None; tin = tout = 0
    for l in log.splitlines():
        try: e = json.loads(l)
        except Exception: continue
        if not isinstance(e, dict): continue
        if e.get('type') == 'turn.completed': u = e.get('usage', {}); tin += u.get('input_tokens', 0); tout += u.get('output_tokens', 0)
        it = e.get('item')
        if not isinstance(it, dict): continue
        t = it.get('type'); types.append(t)
        if t == 'error':
            if not str(it.get('message', '')).startswith(CODE_MODE_ERR): raise Kill('KILL: error item %r' % it.get('message'))
        elif t not in allow: raise Kill('KILL: item type %r' % t)
        elif t == 'agent_message' and e.get('type') == 'item.completed': msg = it.get('text')
    return dict(types=dict(collections.Counter(types)), msg=msg, tin=tin, tout=tout)
