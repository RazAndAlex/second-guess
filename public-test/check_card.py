#!/usr/bin/env python3
"""Check that a card's quote is on the page it cites.  Standalone: python3 check_card.py card.json [--live]
card.json: one card or a list. Fields: url, quote, number, sample, population, year.
Results: pass | fail | unchecked | throttled (429, 5xx or network error that stayed after 3 backoffs; rerun later, never a defeat) | no_dated_capture (archive route only: no capture before 2026-07-14).
Default route: Wayback capture dated before 2026-07-14 (CDX, status 200, fetched raw with id_).
--live: fetch the current page directly. --local: read a local path or file:// url (tests only; the archive route never reads local files).
Archive route date rule: the capture timestamp is 14 digits and at most 20260713, and the final URL after redirects holds such a timestamp too.
A quote that is not on the page fails, including a quote only a search summary had. Exit 0 only if all pass."""
import html, json, re, sys, unicodedata, urllib.request, urllib.parse, urllib.error, os, time, hashlib
TO = '20260713'; UA = 'Mozilla/5.0 (compatible; card-checker)'
GAP = 3.0; BACKOFF = (30, 120, 300); DEADLINE = None  # DEADLINE: time.monotonic() value after which no request is sent (status 599, not cached)
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache'); _last = [0.0]
def raw_get(url, timeout=30):
    """-> (status, bytes, final url). status 0 = network error."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=timeout) as r:
            return r.status, r.read(6_000_000), r.geturl()
    except urllib.error.HTTPError as e: return e.code, b'', url
    except Exception: return 0, b'', url
def retryable(c): return c == 0 or c == 429 or c >= 500
def fetch(url, timeout=30, raw=raw_get, sleep=time.sleep, clock=time.monotonic, cache=True):
    """Disk cache, one request at a time at least GAP s apart, backoff BACKOFF on 0/429/5xx. -> (status, bytes, final). Only final answers are cached; a still-throttled answer is returned uncached."""
    key = os.path.join(CACHE, hashlib.sha256(url.encode()).hexdigest())
    if cache and os.path.exists(key + '.json'):
        m = json.load(open(key + '.json')); return m['status'], open(key + '.body', 'rb').read(), m['final']
    for wait in (0,) + BACKOFF:
        if wait: sleep(wait)
        if DEADLINE is not None and clock() > DEADLINE: return 599, b'', url
        gap = _last[0] + GAP - clock()
        if gap > 0: sleep(gap)
        r = raw(url, timeout); _last[0] = clock()
        if not retryable(r[0]): break
    if retryable(r[0]): return r
    if cache:
        os.makedirs(CACHE, exist_ok=True); open(key + '.body', 'wb').write(r[1]); json.dump(dict(url=url, status=r[0], final=r[2]), open(key + '.json', 'w'))
    return r
def page_text(b):
    """PDF bytes -> text through pypdf, line-break hyphen joins applied to the page only; else utf-8."""
    if b[:4] != b'%PDF': return b.decode('utf-8', 'replace')
    import pypdf, io
    try: t = '\n'.join(p.extract_text() or '' for p in pypdf.PdfReader(io.BytesIO(b)).pages)
    except Exception: return ''
    return re.sub(r'([^\W\d_])-\s*\n\s*(?=[^\W\d_])', r'\1', t)  # letters only: '10-\n20%' stays
def http_get(url, timeout=30):
    c, b, f = fetch(url, timeout); return c, page_text(b), f
def norm(s):
    s = html.unescape(re.sub(r'(?is)<(script|style)\b.*?</\1>', ' ', s)); s = re.sub(r'(?s)<[^>]+>', ' ', s)
    s = html.unescape(s).replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"').replace('–', '-').replace('—', '-').replace('\xa0', ' ')
    s = re.sub(r'\s+', ' ', s).strip().lower()
    return re.sub(r'(?<=\d) %', '%', re.sub(r'\$ (?=\d)', '$', s))  # tags split '41.5' from '%' and '$' from the digits
def digits(s): return re.sub(r'[^0-9.%]', '', s.replace(',', ''))
MIN_QUOTE = 40
def number_in(num, q):
    """Whole-token match: '12' does not match inside '112' or '12.5'."""
    return re.search(r'(?<![\d.,])' + re.escape(num) + r'(?![\d]|[.,]\d)', q) is not None
NUM_OK = re.compile(r'[$0-9][0-9.,%$ a-z-]{0,19}'); URL_OK = re.compile(r'https?://[^\s<>"#]+')
def judge(card, page, local=False):
    # whitelist: every model-written field that reaches a prompt (number, url, quote) must pass a strict rule here
    if not NUM_OK.fullmatch(str(card.get('number') or '').lower()): return 'fail', 'number outside whitelist'
    if not local and not URL_OK.fullmatch(card.get('url') or ''): return 'fail', 'url outside whitelist'
    raw = card.get('quote') or ''
    if '<' in raw or '>' in raw: return 'fail', 'quote holds < or >'  # prompts.py prints the quote as written, so markup could hide text
    q = norm(raw)
    if '<' in q or '>' in q: return 'fail', 'quote holds < or > after decoding'  # '&amp;lt;' decodes twice in norm()
    if any((unicodedata.category(c) == 'Cc' and c not in '\n\r\t') or unicodedata.category(c) == 'Cf' for c in raw + q): return 'fail', 'quote holds a control, zero-width or bidi character'
    if len(q) < MIN_QUOTE: return 'fail', 'quote shorter than %d characters' % MIN_QUOTE
    if q not in norm(page): return 'fail', 'quote not on page'
    num = norm(str(card.get('number') or ''))
    if not num: return 'fail', 'number missing'
    if not number_in(num, q): return 'fail', 'number not in quote'
    return 'pass', 'quote on page'
def bad_status(c): return retryable(c)
def ok_ts(ts): return bool(re.fullmatch(r'\d{14}', ts or '')) and ts[:8] <= TO
def check(card, live=False, get=http_get, local=False):
    url = card.get('url') or ''
    if local:
        p = url[7:] if url.startswith('file://') else url
        try: return judge(card, open(p, encoding='utf-8', errors='replace').read(), local=True)
        except OSError: return 'unchecked', 'cannot read file'
    if not re.match(r'https?://', url): return 'unchecked', 'not a url'
    if live:
        c, body = get(url)[:2]
        if bad_status(c): return 'throttled', 'http %d' % c
        if c != 200 or not body.strip(): return 'unchecked', 'http %d' % c
        return judge(card, body)
    c, body = get('https://web.archive.org/cdx/search/cdx?url=%s&filter=statuscode:200&to=%s&limit=-1' % (urllib.parse.quote(url, safe=''), TO))[:2]
    if bad_status(c): return 'throttled', 'cdx http %d' % c
    if c != 200: return 'unchecked', 'cdx http %d' % c
    rows = [l.split() for l in body.strip().splitlines() if l.strip()]
    if not rows or len(rows[-1]) < 2: return 'no_dated_capture', 'no 200 capture before 2026-07-14'
    ts = rows[-1][1]
    if not ok_ts(ts): return 'no_dated_capture', 'capture timestamp %r is not a 14-digit date up to %s' % (ts, TO)
    res = get('https://web.archive.org/web/%sid_/%s' % (ts, url)); c, body = res[:2]
    if bad_status(c): return 'throttled', 'capture http %d' % c
    if c != 200 or not body.strip(): return 'unchecked', 'capture http %d' % c
    m = re.search(r'/web/(\d{14})', res[2]) if len(res) > 2 and res[2] else None
    if len(res) > 2 and not (m and ok_ts(m.group(1))): return 'no_dated_capture', 'final url after redirects has no capture up to %s: %s' % (TO, res[2])
    s, d = judge(card, body); return s, '%s (capture %s)' % (d, m.group(1) if m else ts)
if __name__ == '__main__':
    live = '--live' in sys.argv; local = '--local' in sys.argv; args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args: sys.exit(__doc__)
    cards = json.load(open(args[0])); cards = cards if isinstance(cards, list) else [cards]
    ok = True
    for c in cards:
        s, d = check(c, live, local=local); ok &= s == 'pass'; print(json.dumps(dict(url=c.get('url'), result=s, detail=d)))
    sys.exit(0 if ok else 1)
