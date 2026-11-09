import json, subprocess, sys, os
from common import *
pr = "Use web search to find the current population of Iceland and tell me the figure and the URL in one line."
def run(name, pre, post=[]):
    cmd = [CODEX] + pre + SOL_EXEC[:1] + post + ['-c', 'model_reasoning_effort="low"'] + SOL_EXEC[1:] + [pr]
    r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, cwd=EMPTY, env=dict(os.environ, CODEX_HOME=CODEX_HOME), timeout=300)
    open(P('live', 'c2_%s.raw' % name), 'w').write(r.stdout + '\nSTDERR\n' + r.stderr)
    ts = [(json.loads(l).get('item') or {}).get('type') for l in r.stdout.splitlines() if l.startswith('{')]
    g = guard_loose(r.stdout) if False else None
    print(name, [t for t in ts if t], 'router_err', r.stderr.count('tools::router'))
which = sys.argv[1]
if which == 'a': run('a_live_cfg', SOL_FLAGS, ['-c', 'web_search="live"'])
if which == 'b': run('b_search_nodisable', ['--search'])
if which == 'c': run('c_search_only_code_mode_on', ['--search'] + [x for f in ('plugins', 'apps', 'shell_tool', 'multi_agent', 'goals', 'image_generation', 'browser_use', 'computer_use', 'hooks') for x in ('--disable', f)])
