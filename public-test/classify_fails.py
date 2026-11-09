"""Classify archive 'quote not on page' fails from the cache. A paraphrase/absent, B on page but norm() missed, C stub/JS shell. No network."""
import json, os, re, sys, hashlib, urllib.parse, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_card as cc
def cached(url):
    k = os.path.join(cc.CACHE, hashlib.sha256(url.encode()).hexdigest())
    return (json.load(open(k + '.json')), open(k + '.body', 'rb').read()) if os.path.exists(k + '.json') else None
def alnum(s): return re.sub(r'[^a-z0-9]', '', s.lower())
def classify(card, page_html):
    page = cc.norm(page_html); q = cc.norm(card['quote'])
    if len(page) < 1500 or re.search(r'enable javascript|javascript is (disabled|required)|just a moment|access denied|captcha', page[:3000]): return 'C', 'page text %d chars' % len(page)
    if alnum(q) in alnum(page):
        a = [c for c in set(q) if not c.isalnum() and c != ' ']; return 'B', 'differs only in non-alphanumerics; quote has %r' % sorted(a)
    return 'A', 'page text %d chars' % len(page)
if __name__ == '__main__':
    log = json.load(open('checker_log.json')); out = []
    for f in log['failures']:
        s, d = f['archive']
        if s != 'fail' or not d.startswith('quote not on page'): continue
        card = next(c for c in json.load(open('cards/%s.json' % f['parent'])) if c['url'] == f['url'])
        cdx = cached('https://web.archive.org/cdx/search/cdx?url=%s&filter=statuscode:200&to=%s&limit=-1' % (urllib.parse.quote(card['url'], safe=''), cc.TO))
        ts = cdx[1].decode().strip().splitlines()[-1].split()[1]; cap = cached('https://web.archive.org/web/%sid_/%s' % (ts, card['url']))
        out.append(dict(parent=f['parent'], url=card['url'], cls=classify(card, cc.page_text(cap[1])), pdf=cap[1][:4] == b'%PDF'))
    print(collections.Counter(o['cls'][0] for o in out)); json.dump(out, open('classify_fails.json', 'w'), indent=1)
    for o in out: print(o['cls'][0], o['pdf'], o['url'][:90], o['cls'][1][:80])
