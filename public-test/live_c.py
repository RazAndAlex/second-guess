import json
from common import *
pr = "Search the web for the population of Iceland. Give exactly 1 card: url (the page), quote (copied exactly from that page), number (the figure in the quote), sample '1', population 'Iceland', year (publication year)."
out, err, rc = sol_run(pr, 'medium', P('card.schema.json'), search=True, out=P('live', 'card_c.json'), timeout=600)
open(P('live', 'sol_card_c.raw'), 'w').write(out + '\nSTDERR\n' + err)
g = guard(out, CARD_ALLOW); print('rc', rc, 'GUARD PASSED', {k: v for k, v in g.items() if k != 'msg'}, 'usd', round(cost('sol', g['tin'], g['tout']), 4), 'router errors', err.count('tools::router'))
print(g['msg'][:400])
try: guard(out, ODDS_ALLOW); print('odds guard would pass')
except Kill as e: print('odds guard on same log:', e)
