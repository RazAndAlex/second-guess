"""Step 8. Run check_card on every saved card by BOTH routes: archive (capture before 2026-07-14) and --live.
Run with the project venv: .venv/bin/python check_cards.py [budget seconds, default 1500]. One request at a time, 3 s apart, backoff 30 s/2 min/5 min, every answer cached under cache/ (a rerun refetches nothing).
A card still throttled after the backoffs (or when the budget ends) gets `throttled`: it is not a defeat and is retried on the next run.
Writes checker_log.json (both counts, every non-pass) and cards_pass/<parent>.json (archive passes, used by arm 3).
no_dated_capture keeps a card out of arm 3 and out of the defeat count. 'Defeats the checker' = unchecked only. The toolkit's real-page count is the live route."""
import json, os, re, sys, time, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import check_card
from check_card import check
from odds import url_key
if __name__ == '__main__':
    check_card.DEADLINE = time.monotonic() + float(sys.argv[1] if len(sys.argv) > 1 else 1500)
    cards = []
    for f in sorted(os.listdir(P('cards'))):
        if f.endswith('.json'):
            for c in json.load(open(P('cards', f))): cards.append((f[:-5], c))
    res = {(live, k): check(c, live=live) for live in (False, True) for k, (par, c) in enumerate(cards)}
    count = lambda live: dict(collections.Counter(res[(live, k)][0] for k in range(len(cards))))
    os.makedirs(P('cards_pass'), exist_ok=True); keep = collections.defaultdict(list)
    for k, (par, c) in enumerate(cards):
        if res[(False, k)][0] == 'pass':
            m = re.search(r'capture (\d{4})(\d{2})(\d{2})', res[(False, k)][1]); keep[par].append(dict(c, capture='%s-%s-%s' % m.groups()))  # date the checker verified
    for par in {p for p, _ in cards}: json.dump(keep[par], open(P('cards_pass', par + '.json'), 'w'))
    pages = {par: len({url_key(c['url']) for c in v}) for par, v in keep.items()}
    log = dict(cards=len(cards), archive_route=count(False), live_route=count(True),
               defeats_checker=dict(archive=count(False).get('unchecked', 0), live=count(True).get('unchecked', 0)),
               throttled=dict(archive=count(False).get('throttled', 0), live=count(True).get('throttled', 0)),
               passing_pages_per_parent=pages,
               failures=[dict(parent=p, url=c['url'], archive=res[(False, k)], live=res[(True, k)]) for k, (p, c) in enumerate(cards) if res[(False, k)][0] != 'pass' or res[(True, k)][0] != 'pass'])
    json.dump(log, open(P('checker_log.json'), 'w'), indent=1)
    print('CHECK cards %d archive %s live %s parents_with_3_passing_pages %d' % (len(cards), log['archive_route'], log['live_route'], sum(1 for v in pages.values() if v >= 3)))
