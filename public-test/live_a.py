import json, odds
from common import *
names = ['Moonlit', 'Brass', 'Quiet', 'Pocket', 'Amber', 'Tidal', 'Paper', 'Cobalt', 'Wild', 'Little']
rows = {9000000 + i: dict(id=9000000 + i, name='%s %s Co. (FAKE)' % (names[i % 10], ['Lantern', 'Orchard', 'Tapes', 'Atlas', 'Mugs'][i % 5]), blurb='An invented test project number %d about %s.' % (i, ['candles', 'seed packs', 'zines', 'maps', 'ceramic cups'][i % 5]),
        parent='Fakeland', cat='Fakeland', usd_goal=1000., country='US') for i in range(25)}
b = dict(batch='FAKE-00', parent='Fakeland', ids=sorted(rows))
print(odds.run_batch('sol', 2, b, rows, 'medium', P('live'), '_a'))
