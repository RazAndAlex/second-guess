import ast, gzip, http.client, io, json, os, subprocess, sys, tempfile, time, unittest, urllib.request, urllib.response

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, 'skills', 'second-guess', 'scripts')
sys.path.insert(0, SCRIPTS)
import second_guess as sg  # noqa: E402

QUOTE = 'The overall success rate for comics projects came in at 78 percent'
CARD = dict(url='https://example.com/a', quote=QUOTE, number='78 percent', sample='s', population='p', year='2023')
PAGE = b'<html><body><p>' + QUOTE.encode() + b'.</p></body></html>'


def fake(table, enc=''):
    """get(url) for check(): table maps a url prefix to (status, bytes); anything else is status 404.
    enc rides as the 5th field, the way make_raw reports Content-Encoding."""
    def get(url):
        for k, v in table.items():
            if url.startswith(k): return v[0], v[1], url, '', enc
        return 404, b'', url, '', enc
    return get


class Imports(unittest.TestCase):
    def test_module_level_imports_are_standard_library(self):
        with open(os.path.join(SCRIPTS, 'second_guess.py')) as f: tree = ast.parse(f.read())
        names = set()
        for n in tree.body:
            if isinstance(n, ast.Import): names |= {a.name.split('.')[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom): names.add(n.module.split('.')[0])
        self.assertTrue(names and names <= set(sys.stdlib_module_names if hasattr(sys, 'stdlib_module_names') else
            'argparse base64 codecs contextlib csv datetime decimal hashlib html io ipaddress json math os re socket stat sys tempfile threading time unicodedata urllib zlib'.split()), names)


class Results(unittest.TestCase):
    def test_pass(self):
        self.assertEqual(sg.check(CARD, fake({'https://example.com/a': (200, PAGE)}))[0], 'pass')

    def test_fail_quote_absent(self):
        r = sg.check(CARD, fake({'https://example.com/a': (200, b'<p>nothing relevant here at all</p>')}))
        self.assertEqual(r, ('fail', 'quote not on page'))

    def test_unchecked(self):
        r = sg.check(CARD, fake({}))  # live 404, no archive capture
        self.assertEqual(r[0], 'unchecked')

    def test_throttled(self):
        r = sg.check(CARD, fake({'https://example.com/a': (429, b''), 'https://web.archive.org/cdx': (503, b'')}))
        self.assertEqual(r[0], 'throttled')

    def test_archive_route_passes(self):
        t = {'https://example.com/a': (404, b''), 'https://web.archive.org/cdx': (200, b'com,example)/a 20240102030405 http://example.com/a text/html 200 X 1\n'),
             'https://web.archive.org/web/20240102030405id_/https://example.com/a': (200, PAGE)}
        r = sg.check(CARD, fake(t))
        self.assertEqual(r[0], 'pass'); self.assertIn('20240102030405', r[1])

    def test_quote_split_by_tags_passes(self):
        page = b'<p>The overall success rate for <b>comics</b> projects came in at <span>78</span> <i>percent</i></p>'
        self.assertEqual(sg.check(CARD, fake({'https://example.com/a': (200, page)}))[0], 'pass')

    def test_number_absent_from_quote_fails(self):
        c = dict(CARD, number='99 percent')
        self.assertEqual(sg.judge(c, QUOTE), ('fail', 'number not in quote'))

    def test_angle_bracket_in_quote_fails(self):
        c = dict(CARD, quote=QUOTE + ' <b>')
        self.assertEqual(sg.judge(c, QUOTE + ' <b>')[0], 'fail')

    def test_grounded_fold_ligature_and_soft_hyphen(self):
        c = dict(CARD, quote='The overall success rate for comics projects came in at 78 percent, first of all')
        self.assertEqual(sg.judge(c, 'The overall success rate for comics projects came in at 78 percent, \ufb01rst of all')[0], 'pass')
        page = 'The overall success rate for comics projects came in at 78 per\xadcent'.replace('success', 'sucﬁess').encode()
        self.assertEqual(sg.judge(CARD, page.decode())[0], 'fail')  # 'sucfiess' is not 'success'
        page = 'The overall succe\xadss rate for comics projects came in at 78 percent'
        self.assertEqual(sg.judge(CARD, page)[0], 'pass')

    def test_pdf_without_pypdf_is_unchecked_with_command(self):
        if 'pypdf' in sys.modules or __import__('importlib.util').util.find_spec('pypdf'): self.skipTest('pypdf installed')
        r = sg.check(CARD, fake({'https://example.com/a': (200, b'%PDF-1.4 fake')}))
        self.assertEqual(r[0], 'unchecked')
        self.assertIn('UV_CACHE_DIR=second-guess-runs/.uv-cache uv run --no-project --with pypdf python', r[1])

    def test_retry_logic_sits_behind_retry_delay(self):
        calls = []; slept = []
        def raw(url, timeout): calls.append(url); return 429, b'', url, ''
        r = sg.fetch('https://x.test/', raw=raw, sleep=slept.append, clock=lambda: 0.0, cache_dir=None)
        self.assertEqual(r[0], 429); self.assertEqual(len(calls), 4); self.assertEqual([s for s in slept if s >= 30], list(sg.BACKOFF))


class Cli(unittest.TestCase):
    def run_cli(self, cwd, *args):
        return subprocess.run(['/usr/bin/python3', '-B', '-I', os.path.join(SCRIPTS, 'second_guess.py')] + list(args),
                              cwd=cwd, capture_output=True, text=True)

    def test_start_then_check_cards_with_page_file(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_cli(d, 'start', '--idea', 'A smart garden tool', '--model', 'test'); self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(os.path.isdir(os.path.join(d, 'idea-test-files')))
            self.assertTrue(os.path.exists(os.path.join(json.loads(r.stdout)['run'], 'state.json')))
            with open(os.path.join(d, 'cards.json'), 'w') as f: json.dump({'cards': [CARD]}, f)
            with open(os.path.join(d, 'page.txt'), 'wb') as f: f.write(PAGE)
            r = self.run_cli(d, 'check-cards', 'cards.json', '--page-file', '0', 'page.txt'); self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            out = json.loads(r.stdout); self.assertEqual(out['results'][0]['result'], 'pass'); self.assertEqual(out['counts']['pass'], 1)

    def test_schema_error_fails_card_and_report_without_file_exits_2(self):
        with tempfile.TemporaryDirectory() as d:
            self.run_cli(d, 'start', '--idea', 'x', '--model', 'm')
            with open(os.path.join(d, 'c.json'), 'w') as f: json.dump([{'url': 'https://example.com/'}], f)
            out = json.loads(self.run_cli(d, 'check-cards', 'c.json').stdout)
            self.assertEqual(out['results'][0]['result'], 'fail'); self.assertIn('missing a field', out['results'][0]['detail'])
            r = self.run_cli(d, 'report'); self.assertEqual(r.returncode, 2); self.assertIn('--file', json.loads(r.stdout)['error'])

    def test_check_cards_without_run_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_cli(d, 'check-cards', 'c.json'); self.assertNotEqual(r.returncode, 0); self.assertIn('error', json.loads(r.stdout))


B = 'the overall success rate for comics projects '


def jc(quote, number, page, url='https://example.com/a'):
    return sg.judge(dict(CARD, quote=quote, number=number, url=url), page)


class Fooling(unittest.TestCase):
    """Tests that try to fool the normaliser (review of ticket 2)."""
    def test_superscript_and_fraction_do_not_become_digits(self):
        self.assertEqual(jc(B + 'rose to 10 percent in total', '10', B + 'rose to 10\u00b2 percent in total')[0], 'fail')
        self.assertEqual(jc(B + 'rose to 102 percent in total', '102', B + 'rose to 10\u00b2 percent in total')[0], 'fail')
        self.assertEqual(jc(B + 'rose to 11 percent in total', '11', B + 'rose to 1\u00bd percent in total')[0], 'fail')
        self.assertEqual(jc(B + 'rose to 781 percent in total', '781', B + 'rose to 78\u00bd percent in total')[0], 'fail')
        self.assertEqual(jc(B + 'rose to 78 percent in total', '78', B + 'rose to 7\u2078 percent in total')[0], 'fail')
        self.assertEqual(jc(B + 'rose to 10 in total', '10', B + 'rose to 10\u00b2 in total')[0], 'fail')  # quote ends at the digit

    def test_footnote_marker_and_fullwidth_digits(self):
        t = B + 'came in at 78%\u00b9 of all projects'
        self.assertEqual(jc(t, '78%', t), ('pass', 'quote on page'))
        t = B + 'came in at 78\u00b9 of all projects'
        self.assertEqual(jc(t, '78', t)[0], 'pass')
        self.assertEqual(jc(B + 'came in at 78 percent of all', '78', B + 'came in at \uff17\uff18 percent of all')[0], 'pass')
        self.assertEqual(sg.norm('a\ufffcb'), 'a\ufffcb')  # the placeholder survives and trips no guard
        self.assertEqual(sg.judge(dict(CARD, quote=B + 'came in at 78%\u00b9 of all', number='78%'), B + 'came in at 78%\u00b9 of all')[0], 'pass')

    def test_number_cut_from_a_longer_number_on_the_page(self):
        q = '78 percent of comics projects reached their funding goal in 2023'
        self.assertEqual(jc(q, '78', 'In 2023, 178 percent of comics projects reached their funding goal in 2023')[0], 'fail')
        self.assertEqual(jc(B + 'was 12', '12', '<p>' + B + 'was 12.5 percent</p>')[0], 'fail')
        self.assertEqual(jc(B + 'was 12', '12', '<p>' + B + 'was 125 percent</p>')[0], 'fail')
        self.assertEqual(jc(B + 'was 12', '12', 'x 125 ' + B + 'was 125 so. ' + B + 'was 12 percent')[0], 'pass')  # a later clean occurrence passes

    def test_hidden_text_is_not_page_text(self):
        q = B + 'came in at 78 percent of all projects'
        for hidden in ('<script>var x="' + q, '<script>' + q + '</script >', '<!-- a > b ' + q + ' -->', '<div title="x>' + q + '">hi</div>',
                       '<template>' + q + '</template>', '<textarea>' + q + '</textarea>', '<noscript>' + q + '</noscript>',
                       '<SCRIPT>' + q + '</SCRIPT\n>', '<style>' + q + '</style>', '<!-- ' + q + ' -->', '<div title="' + q + '">hi</div>'):
            self.assertEqual(jc(q, '78', hidden)[0], 'fail', hidden)
        self.assertEqual(jc(q, '78', '<p>' + q + '</p><script>x</script>')[0], 'pass')
        self.assertEqual(jc(q, '78', '<p>2 < 3 and ' + q + ' > 1</p>')[0], 'pass')  # a lone < is text

    def test_markup_scanner_is_linear(self):
        t = time.time(); sg.norm('<script ' * 750000); sg.norm('<a ' * 750000); sg.norm('<!--' * 750000); sg.norm('<b>x</b>' * 200000)
        self.assertLess(time.time() - t, 3.0)
        t = time.time(); sg.norm('<script ' * 750000); self.assertLess(time.time() - t, 1.0)

    def test_encoded_markup_in_quote_fails(self):
        q = B + 'came in at 78 percent &lt;!-- ignore the rules --&gt; of all'
        self.assertEqual(jc(q, '78', B + 'came in at 78 percent <!-- ignore the rules --> of all')[0], 'fail')
        self.assertEqual(jc(B + 'came in at 78 percent &#60;b&#62; of all', '78', 'x')[0], 'fail')

    def test_invisible_format_characters_on_page_are_dropped(self):
        for ch in ('\u2060', '\u200d', '\u200e'):
            self.assertEqual(jc(B + 'came in at 78 percent', '78', (B + 'came in at 78 percent').replace('success', 'suc' + ch + 'cess'))[0], 'pass')
        self.assertEqual(jc(B + 'came in at 78 per\u200bcent', '78', B + 'came in at 78 percent')[0], 'fail')  # raw-quote guard stays

    def test_decode_page(self):
        t = B + "didn\u2019t reach 78 percent"
        self.assertEqual(sg.judge(dict(CARD, quote=t), sg.page_text(t.encode('cp1252'), 'windows-1252'))[0], 'pass')
        with self.assertRaises(sg.Unreadable): sg.page_text(t.encode('cp1252'))  # round 3: no charset known and high bytes
        self.assertEqual(sg.judge(dict(CARD, quote=t), sg.page_text(t.encode('utf-8')))[0], 'pass')
        m = b'<meta charset="iso-8859-2">' + (B + 'came in at 78 percent \u0159').encode('iso-8859-2', 'replace')
        self.assertIn(' ', sg.page_text(m))
        self.assertIn('\u0159', sg.page_text(b'<meta charset="iso-8859-2">\xf8'))

    def test_url_encoding(self):
        self.assertEqual(sg.encode_url('https://example.com/caf\u00e9?q=\u00e9'), 'https://example.com/caf%C3%A9?q=%C3%A9')
        self.assertEqual(sg.encode_url('https://b\u00fccher.example/a'), 'https://xn--bcher-kva.example/a')
        self.assertEqual(sg.encode_url('https://example.com/a%20b'), 'https://example.com/a%20b')
        with self.assertRaises(ValueError): sg.encode_url('https://%s.example/' % ('\u00e9' * 70))
        slept = []; seen = []
        def get(u): seen.append(u); return 404, b'', u, ''
        r = sg.check(dict(CARD, url='https://example.com/caf\u00e9'), get)
        self.assertEqual(seen[0], 'https://example.com/caf%C3%A9'); self.assertEqual(r[0], 'unchecked')
        self.assertEqual(sg.check(dict(CARD, url='https://%s.example/' % ('\u00e9' * 70)), get)[0], 'unchecked')


class Files(unittest.TestCase):


    def cli(self, d, *args):
        return subprocess.run(['/usr/bin/python3', '-B', '-I', os.path.join(SCRIPTS, 'second_guess.py')] + list(args), cwd=d, capture_output=True, text=True)

    def setup_run(self, d, cards):
        self.cli(d, 'start', '--idea', 'x', '--model', 'm')
        with open(os.path.join(d, 'c.json'), 'w') as f: json.dump(cards, f)

    def test_pdf_page_file_without_pypdf_is_unchecked(self):
        if __import__('importlib.util').util.find_spec('pypdf'): self.skipTest('pypdf installed')
        with tempfile.TemporaryDirectory() as d:
            self.setup_run(d, [CARD])
            with open(os.path.join(d, 'a.pdf'), 'wb') as f: f.write(b'%PDF-1.4 x')
            out = json.loads(self.cli(d, 'check-cards', 'c.json', '--page-file', '0', 'a.pdf').stdout)
            self.assertEqual(out['results'][0]['result'], 'unchecked'); self.assertIn('pypdf', out['results'][0]['detail'])

    def test_page_file_cp1252(self):
        t = B + "didn\u2019t reach 78 percent"
        with tempfile.TemporaryDirectory() as d:
            self.setup_run(d, [dict(CARD, quote=t)])
            with open(os.path.join(d, 'p.txt'), 'wb') as f: f.write(t.encode('cp1252'))
            out = json.loads(self.cli(d, 'check-cards', 'c.json', '--page-file', '0', 'p.txt').stdout)
            self.assertEqual(out['results'][0]['result'], 'unchecked')  # round 3: no charset known and high bytes

    def test_bad_page_file_index_refused_before_network(self):
        with tempfile.TemporaryDirectory() as d:
            self.setup_run(d, [CARD])
            for idx in ('5', '-1'):
                r = self.cli(d, 'check-cards', 'c.json', '--page-file', idx, 'nofile'); self.assertEqual(r.returncode, 1)
                self.assertIn('no card', json.loads(r.stdout)['error'])

    def test_empty_run_refused_and_deep_json_and_bad_cache(self):
        with tempfile.TemporaryDirectory() as d:
            self.setup_run(d, [CARD])
            r = self.cli(d, 'check-cards', 'c.json', '--run', ''); self.assertEqual(r.returncode, 1); self.assertIn('error', json.loads(r.stdout))
            with open(os.path.join(d, 'deep.json'), 'w') as f: f.write('[' * 200000 + ']' * 200000)
            r = self.cli(d, 'check-cards', 'deep.json'); self.assertEqual(r.returncode, 1); self.assertIn('error', json.loads(r.stdout))
        with tempfile.TemporaryDirectory() as d:
            import hashlib
            k = os.path.join(d, hashlib.sha256(b'https://x.test/').hexdigest())
            with open(k + '.json', 'w') as f: f.write('{"stat')
            with open(k + '.body', 'wb') as f: f.write(b'x')
            r = sg.fetch('https://x.test/', raw=lambda u, t: (200, b'ok', u, ''), sleep=lambda s: None, clock=lambda: 0.0, cache_dir=d)
            self.assertEqual(r[1], b'ok')
            with open(k + '.json') as f: self.assertEqual(json.load(f)['status'], 200)


class FakeClock:
    def __init__(self): self.t = 0.0; self.slept = 0.0
    def __call__(self): return self.t
    def sleep(self, s): self.t += s; self.slept += s


def cards5():
    return [dict(CARD, url='https://example.com/p%d' % i, quote=B + 'came in at %d percent of all projects' % (70 + i), number=str(70 + i)) for i in range(5)]


def run_cards(d, cards, clk, raw, pages=None, limit=90, resolver=None):
    os.makedirs(os.path.join(d, 'run'), exist_ok=True)
    with open(os.path.join(d, 'c.json'), 'w') as f: json.dump(cards, f)
    return sg.check_cards(os.path.join(d, 'c.json'), os.path.join(d, 'run'), pages, time_limit=limit, raw=raw, sleep=clk.sleep, clock=clk, resolver=resolver)


def page_for(c): return ('<p>' + c['quote'] + '.</p>').encode()


class Ticket3(unittest.TestCase):
    def setUp(self): sg._last[0] = -1e9

    def test_dead_network_is_blocked_within_the_limit(self):
        clk = FakeClock(); calls = []
        def raw(url, timeout): calls.append((url, timeout)); clk.t += timeout; return 0, b'', url, 'URLError: <urlopen error [Errno 8] nodename nor servname provided>'
        with tempfile.TemporaryDirectory() as d:
            out = run_cards(d, cards5(), clk, raw)
            self.assertLessEqual(clk.t, 90); self.assertEqual(out['counts']['network_blocked'], 5)
            self.assertTrue(out['error'].startswith('network_blocked: this program reached neither web.archive.org nor github.com (`URLError'))
            self.assertIn("-c 'sandbox_workspace_write.network_access=true'", out['error'])
            self.assertEqual({u for u, t in calls}, {'https://web.archive.org', 'https://github.com'}); self.assertTrue(all(t <= 8 for u, t in calls))
            with open(os.path.join(d, 'run', 'card-results.json')) as f: saved = json.load(f)
            self.assertEqual({v['result'] for v in saved.values()}, {'network_blocked'})
            ok2 = lambda u, t: (200, page_for(cards5()[int(u[-1])]) if u.endswith(tuple('01234')) else b'', u, '')
            out = run_cards(d, cards5(), FakeClock(), ok2)  # rerun tries network_blocked cards again
            self.assertEqual(out['counts']['pass'], 5); self.assertNotIn('error', out)

    def test_page_file_needs_no_network(self):
        clk = FakeClock()
        def raw(url, timeout): raise AssertionError('network used: ' + url)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'p.txt')
            with open(p, 'wb') as f: f.write(page_for(CARD))
            out = run_cards(d, [CARD], clk, raw, pages={0: p})
            self.assertEqual(out['results'][0]['result'], 'pass'); self.assertEqual(out['remaining'], 0)

    def test_settled_cards_skip_network_and_edited_card_is_checked_again(self):
        cs = cards5()[:2]; clk = FakeClock(); n = []
        def raw(url, timeout): n.append(url); return (200, page_for(cs[int(url[-1])]), url, '') if 'example' in url else (200, b'', url, '')
        with tempfile.TemporaryDirectory() as d:
            run_cards(d, cs, clk, raw); self.assertEqual([u for u in n if 'example' in u], ['https://example.com/p0', 'https://example.com/p1'])
            def dead(url, timeout): raise AssertionError('network used')
            out = run_cards(d, cs, FakeClock(), dead); self.assertEqual(out['counts']['pass'], 2)
            cs[0] = dict(cs[0], sample='changed')
            out = run_cards(d, cs, FakeClock(), raw)  # the page comes from the run cache, but the edited card gets its own saved entry
            self.assertEqual(out['counts']['pass'], 2)
            with open(os.path.join(d, 'run', 'card-results.json')) as f: self.assertEqual(len(json.load(f)), 3)

    def test_backoff_only_on_429_and_5xx_and_never_past_the_deadline(self):
        clk = FakeClock()
        r = sg.fetch('https://x.test/', raw=lambda u, t: (0, b'', u, 'e'), sleep=clk.sleep, clock=clk)
        self.assertEqual(r[0], 0); self.assertLess(clk.slept, 5)  # status 0 never backs off
        clk = FakeClock(); calls = []
        def raw(u, t): calls.append(t); return 503, b'', u, ''
        r = sg.fetch('https://x.test/', raw=raw, sleep=clk.sleep, clock=clk, deadline=clk() + 90)
        self.assertEqual(r[0], sg.PENDING); self.assertLessEqual(clk.t, 90); self.assertEqual(len(calls), 2)  # 30 s fits, 120 s does not
        clk = FakeClock()
        r = sg.fetch('https://x.test/', raw=raw, sleep=clk.sleep, clock=clk, deadline=clk() + 2)  # the GAP sleep alone passes it
        self.assertEqual(r[0], sg.PENDING)

    def test_timeout_is_min_30_and_remaining(self):
        clk = FakeClock(); seen = []
        def raw(u, t): seen.append(t); return 200, b'x', u, ''
        sg.fetch('https://x.test/', raw=raw, sleep=clk.sleep, clock=clk, deadline=clk() + 10)
        sg.fetch('https://y.test/', raw=raw, sleep=clk.sleep, clock=clk, deadline=clk() + 100)
        self.assertEqual(seen, [10.0, 30])

    def test_pending_then_throttled_after_three_runs(self):
        with tempfile.TemporaryDirectory() as d:
            for run in (1, 2, 3):
                clk = FakeClock()
                def raw(u, t): return (200, b'<p>x</p>', u, '') if 'archive' in u or 'github' in u else (503, b'', u, '')
                out = run_cards(d, [CARD], clk, raw, limit=40)
                if run < 3: self.assertEqual(out['results'][0]['result'], 'pending'); self.assertEqual(out['remaining'], 1); self.assertLessEqual(clk.t, 40)
            self.assertEqual(out['results'][0]['result'], 'throttled'); self.assertEqual(out['remaining'], 0)

    def test_one_host_up_means_card_unchecked(self):
        clk = FakeClock()
        def raw(u, t): return (200, b'x', u, '') if 'github' in u else (0, b'', u, 'ConnectionResetError')
        with tempfile.TemporaryDirectory() as d:
            out = run_cards(d, [CARD], clk, raw)
            self.assertEqual(out['results'][0]['result'], 'unchecked'); self.assertNotIn('error', out)

    def test_gaierror_on_blocked_network_reads_network_blocked(self):
        import socket
        clk = FakeClock()
        def resolver(h, p): raise socket.gaierror(8, 'nodename nor servname provided')
        with tempfile.TemporaryDirectory() as d:
            out = run_cards(d, [CARD], clk, None, resolver=resolver)
            self.assertEqual(out['results'][0]['result'], 'network_blocked'); self.assertIn('gaierror', out['error'])

    def test_redirect_to_metadata_address_is_refused_with_no_request_sent(self):
        hit = []
        class H(urllib.request.HTTPHandler):
            def http_open(self, req):
                hit.append(req.full_url)
                if '169.254.169.254' in req.full_url: raise AssertionError('request sent to the metadata address')
                h = http.client.HTTPMessage(); h['Location'] = 'http://169.254.169.254/latest/meta-data'
                r = urllib.response.addinfourl(io.BytesIO(b''), h, req.full_url, 302); r.msg = 'Found'; return r
        names = {'a.test': '93.184.216.34', 'meta.test': '169.254.169.254'}
        raw = sg.make_raw(lambda h, p: [names.get(h, h)], handlers=[H()])
        r = raw('http://a.test/x', 5)
        self.assertEqual(r[0], sg.REFUSED); self.assertTrue(r[3].startswith('link refused:')); self.assertEqual(hit, ['http://a.test/x'])
        r = raw('http://meta.test/', 5); self.assertEqual(r[0], sg.REFUSED); self.assertEqual(hit, ['http://a.test/x'])  # before the first request
        for bad in ('file:///etc/passwd', 'ftp://a.test/', 'http://[::ffff:127.0.0.1]/', 'http://10.0.0.1/', 'http://127.0.0.1/', 'http://100.64.0.1/', 'http://224.0.0.1/'):
            self.assertEqual(raw(bad, 5)[0], sg.REFUSED, bad)

    def test_refused_link_is_fail_with_no_archive_or_probe(self):
        calls = []; clk = FakeClock()
        def raw(u, t): calls.append(u); return sg.REFUSED, b'', u, 'link refused: x resolves to 10.0.0.1'
        with tempfile.TemporaryDirectory() as d:
            out = run_cards(d, [CARD], clk, raw)
            self.assertEqual(out['results'][0]['result'], 'fail'); self.assertTrue(out['results'][0]['detail'].startswith('link refused:'))
            self.assertFalse([u for u in calls if 'cdx' in u or 'web/' in u])  # no archive attempt
            self.assertEqual(calls.count('https://example.com/a'), 1)


class Encoding(unittest.TestCase):
    """Ticket 3 part B: gzip bodies, Content-Encoding br/zstd, unreadable bodies, earliest archive capture."""
    LATEST = '20240202030405'; EARLIEST = '20240101000000'

    def test_gzip_body_passes_with_and_without_the_header(self):
        gz = gzip.compress(PAGE)
        self.assertEqual(sg.check(CARD, fake({'https://example.com/a': (200, gz)}))[0], 'pass')
        self.assertEqual(sg.check(CARD, fake({'https://example.com/a': (200, gz)}, enc='gzip'))[0], 'pass')

    def test_gzip_archive_capture_passes(self):
        t = {'https://example.com/a': (404, b''),
             'https://web.archive.org/cdx': (200, b'com,example)/a 20240202030405 http://example.com/a text/html 200 X 1\n'),
             'https://web.archive.org/web/20240202030405id_/https://example.com/a': (200, gzip.compress(PAGE))}
        r = sg.check(CARD, fake(t))
        self.assertEqual(r[0], 'pass')
        self.assertIn('20240202030405', r[1])

    def test_truncated_gzip_is_unchecked(self):
        r = sg.check(CARD, fake({'https://example.com/a': (200, gzip.compress(PAGE)[:-10])}))
        self.assertEqual(r, ('unchecked', 'gzip stream is truncated'))

    def test_corrupt_gzip_is_unchecked(self):
        b = gzip.compress(PAGE)
        m = len(b) // 2
        r = sg.check(CARD, fake({'https://example.com/a': (200, b[:m] + b'\x00' * 8 + b[m + 8:])}))
        self.assertEqual(r, ('unchecked', 'gzip stream is bad or truncated'))

    def test_gzip_over_the_50_mb_cap_is_unchecked(self):
        body = gzip.compress(b'a' * (50 * 1024 * 1024 + 1024))
        r = sg.check(CARD, fake({'https://example.com/a': (200, body)}))
        self.assertEqual(r[0], 'unchecked')
        self.assertIn('50 MB', r[1])

    def test_gzip_pdf_reaches_the_pdf_route(self):
        if 'pypdf' in sys.modules or __import__('importlib.util').util.find_spec('pypdf'):
            self.skipTest('pypdf installed')
        r = sg.check(CARD, fake({'https://example.com/a': (200, gzip.compress(b'%PDF-1.4 fake'))}))
        self.assertEqual(r[0], 'unchecked')
        self.assertIn('uv run --no-project --with pypdf', r[1])

    def test_brotli_and_zstd_are_named_in_the_detail(self):
        for enc in ('br', 'zstd'):
            r = sg.check(CARD, fake({'https://example.com/a': (200, b'\x00' * 100)}, enc=enc))
            self.assertEqual(r[0], 'unchecked')
            self.assertIn(enc, r[1])
            self.assertIn('Content-Encoding', r[1])

    def test_unreadable_body_is_unchecked_and_near_clean_body_passes(self):
        r = sg.check(CARD, fake({'https://example.com/a': (200, b'\x81\x8d\x8f\x90\x9d' * 800)}))
        self.assertEqual(r, ('unchecked', 'page charset is unknown'))  # round 3: no charset known
        r2 = sg.check(CARD, fake({'https://example.com/a': (200, b'<p>' + QUOTE.encode() + b'\x81\x8d</p>')}))
        self.assertEqual(r2[0], 'unchecked')  # round 3: no charset known and high bytes

    def test_earliest_capture_tried_when_latest_lacks_the_quote(self):
        old = b'<p>' + QUOTE.encode() + b'.</p>'
        new = b'<p>The comics section was redesigned in 2024 by a new editorial team.</p>'
        t = {'https://example.com/a': (404, b''),
             'https://web.archive.org/cdx': (200, b'com,example)/a 20240101000000 http://example.com/a text/html 200 X 1\n'
                                                 b'com,example)/a 20240202030405 http://example.com/a text/html 200 X 1\n'),
             'https://web.archive.org/web/20240202030405id_/https://example.com/a': (200, new),
            'https://web.archive.org/web/20240101000000id_/https://example.com/a': (200, old)}
        r = sg.check(CARD, fake(t))
        self.assertEqual(r[0], 'pass')
        self.assertIn('20240101000000', r[1])

    def test_pass_on_latest_capture_fetches_no_earlier_capture(self):
        hits = []
        rows = (b'com,example)/a 20240101000000 http://example.com/a text/html 200 X 1\n'
                b'com,example)/a 20240202030405 http://example.com/a text/html 200 X 1\n')
        def get(u):
            hits.append(u)
            if u.startswith('https://web.archive.org/cdx'):
                return 200, rows, u, ''
            if '/web/20240202030405id_/' in u:
                return 200, PAGE, u, ''
            return 404, b'', u, ''
        r = sg.check(CARD, get)
        self.assertEqual(r[0], 'pass')
        web_hits = [u for u in hits if '/web/' in u]
        self.assertEqual(len(web_hits), 1)
        self.assertIn('20240202030405', web_hits[0])


if __name__ == '__main__':
    unittest.main()


# ---- ticket 4: stats and match ----------------------------------------------------
import random  # noqa: E402


def make_csv(path, n=400, seed=1, signal=True, outcome=None, extra=None, dates=None, header=('when', 'x', 'kind', 'y')):
    """Rows: date, numeric x, text kind, outcome y. With signal, y depends on x and kind. extra: {col: fn(i, y) -> cell}."""
    rng = random.Random(seed); rows = []
    for i in range(n):
        x = rng.gauss(0, 1); kind = rng.choice('abc')
        z = 2.0 * x + {'a': 1.0, 'b': 0.0, 'c': -1.0}[kind] if signal else 0.0
        y = int(rng.random() < 1 / (1 + 2.718281828 ** -z)) if signal else rng.randint(0, 1)
        if outcome is not None: y = outcome(i, y)
        d = dates(i) if dates else '2024-%02d-%02d' % (1 + (i * 12) // n, 1 + i % 28)
        rows.append([d, '%.4f' % x, kind, str(y)])
    cols = list(header)
    for name, fn in (extra or {}).items():
        cols.append(name); [r.append(fn(i, int(r[3]))) for i, r in enumerate(rows)]
    with open(path, 'w', newline='') as f:
        w = csv.writer(f); w.writerow(cols); w.writerows(rows)


import csv  # noqa: E402


class StatsBase(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory(); self.d = self._d.name
        self.run_dir = sg.start('idea', 'm', base=self.d)
        self.files = os.path.join(self.d, 'idea-test-files')

    def tearDown(self): self._d.cleanup()

    def csv(self, name='d.csv', **kw):
        make_csv(os.path.join(self.files, name), **kw); return name

    def stats(self, name='d.csv', **kw):
        kw.setdefault('outcome', 'y'); kw.setdefault('date', 'when')
        return sg.stats_cmd(self.run_dir, name, base=self.d, **kw)

    def idk(self, out, word=None):
        self.assertTrue(out['first_line'].startswith("I don't know"), out['first_line'])
        self.assertEqual(out['quotable'], {}); self.assertFalse(out['counts'])
        if word: self.assertIn(word, out['first_line'])

    def match_yes(self): return sg.match_cmd(self.run_dir, 'Synthetic test group', 'yes', 'Same kind of cases.')

    def saved(self, name):
        with open(os.path.join(self.run_dir, name)) as f: return json.load(f)


class LocalFilePaths(StatsBase):
    def test_good_file_is_read(self):
        self.csv(); self.assertEqual(self.stats()['stats']['status'], 'ok')

    def test_symlink_is_refused(self):
        self.csv('real.csv'); os.symlink(os.path.join(self.files, 'real.csv'), os.path.join(self.files, 'link.csv'))
        with self.assertRaises(sg.Refused): self.stats('link.csv')

    def test_symlink_to_a_file_outside_is_refused(self):
        make_csv(os.path.join(self.d, 'outside.csv')); os.symlink(os.path.join(self.d, 'outside.csv'), os.path.join(self.files, 'o.csv'))
        with self.assertRaises(sg.Refused): self.stats('o.csv')

    def test_folder_that_is_a_symlink_is_refused(self):
        make_csv(os.path.join(self.d, 'elsewhere.csv'))
        os.mkdir(os.path.join(self.d, 'other')); os.replace(os.path.join(self.d, 'elsewhere.csv'), os.path.join(self.d, 'other', 'a.csv'))
        os.rmdir(self.files); os.symlink(os.path.join(self.d, 'other'), self.files)
        with self.assertRaises(sg.Refused): self.stats('a.csv')

    def test_bad_names_are_refused(self):
        make_csv(os.path.join(self.d, 'x.csv')); self.csv('ok.csv')
        os.mkdir(os.path.join(self.files, 'sub')); make_csv(os.path.join(self.files, 'sub', 'y.csv'))
        os.mkdir(os.path.join(self.files, 'dir.csv'))
        with open(os.path.join(self.files, 'x.txt'), 'w') as f: f.write('a,b\n')
        for bad in ('../x.csv', '..', '/etc/passwd.csv', os.path.join(self.files, 'ok.csv'), 'sub/y.csv', 'sub\\y.csv', 'x.txt', 'ok.csv\0', 'dir.csv',
                    '', ' ', ' ok.csv', 'ok.csv ', 'ok.csv/', './ok.csv', 'ok', 'missing.csv', '..csv', 'ok.csv.exe'):
            with self.subTest(bad=bad), self.assertRaises(sg.Refused): self.stats(bad)

    def test_fifo_named_csv_is_refused_without_hanging(self):
        os.mkfifo(os.path.join(self.files, 'f.csv'))
        with self.assertRaises(sg.Refused): self.stats('f.csv')

    def test_refusal_saves_nothing(self):
        with self.assertRaises(sg.Refused): self.stats('../x.csv')
        self.assertFalse(os.path.exists(os.path.join(self.run_dir, 'stats.json')))

    def test_upper_case_extension_is_csv(self):
        self.csv('D.CSV'); self.assertEqual(self.stats('D.CSV')['stats']['status'], 'ok')


class FourChecks(StatsBase):
    def test_built_csv_passes_and_counts_with_a_yes(self):
        self.csv(); self.stats(); out = self.match_yes()
        self.assertTrue(out['counts']); m = out['stats']['measures']
        self.assertLess(m['brier_model'], m['brier_average']); self.assertEqual(m['cases'], 400)
        self.assertEqual(m['earlier_cases'] + m['later_cases'], 400)
        self.assertEqual(sum(m['counts']['earlier'].values()), m['earlier_cases'])
        self.assertEqual(out['quotable']['counts']['cases'], 400)

    def test_one_outcome_value(self):
        self.csv(outcome=lambda i, y: 1); self.idk(self.stats(), 'distinct values')

    def test_three_outcome_values(self):
        self.csv(outcome=lambda i, y: y + (i % 7 == 0)); self.idk(self.stats(), 'distinct values')

    def test_too_few_cases(self):
        self.csv(n=100); self.idk(self.stats(), 'fewer than')

    def test_few_of_one_outcome_in_earlier_part(self):
        self.csv(outcome=lambda i, y: int(i % 20 == 0) if i < 320 else y); self.idk(self.stats(), 'earlier')

    def test_later_part_with_one_outcome_only_cannot_pass_by_a_great_score(self):
        self.csv(outcome=lambda i, y: 1 if i >= 320 else y); self.idk(self.stats(), 'later')

    def test_no_usable_date(self):
        self.csv(dates=lambda i: 'someday'); self.idk(self.stats(), 'unreadable date')

    def test_empty_date_cells(self):
        self.csv(dates=lambda i: ''); self.idk(self.stats())

    def test_formula_no_better_than_average_on_noise(self):
        self.csv(signal=False, seed=5); out = self.stats(); self.idk(out, 'does not beat')
        out = self.match_yes(); self.idk(out, 'does not beat')   # a yes cannot rescue a failed check

    def test_shuffled_noise_over_many_seeds_never_passes_by_luck_of_the_check_itself(self):
        # a pass on noise would have to show a real Brier win; whichever seeds pass must show it, never a tie or a worse score
        for seed in range(3):
            self.csv(signal=False, seed=seed); out = self.stats()
            if out['stats']['status'] == 'ok':
                m = out['stats']['measures']; self.assertLess(m['brier_model'], m['brier_average'])

    def test_failed_check_keeps_numbers_out_even_after_yes(self):
        self.csv(n=100); self.stats(); out = self.match_yes(); self.idk(out); self.assertNotIn('Synthetic test group', out['first_line'])

    def test_passing_stats_without_a_match_is_idk(self):
        self.csv(); out = self.stats(); self.idk(out, 'not judged'); self.assertEqual(out['stats']['status'], 'ok')

    def test_ties_across_the_split_move_the_cut_and_stay_honest(self):
        self.csv(n=500, dates=lambda i: '2024-01-%02d' % (1 + i // 25))   # 25 rows per date: the 80% cut falls inside a date
        out = self.stats(); m = out['stats']['measures']
        self.assertLess(m['earlier_to'][:10], m['later_from'][:10])   # no date on both sides
        self.assertEqual(m['earlier_cases'] + m['later_cases'], 500)

    def test_all_cases_on_one_date(self):
        self.csv(dates=lambda i: '2024-05-05'); self.idk(self.stats(), 'cut')

    def test_rows_in_reverse_date_order_are_sorted_first(self):
        import datetime as dt
        self.csv(dates=lambda i: (dt.date(2024, 1, 1) + dt.timedelta(days=399 - i)).isoformat())
        m = self.stats()['stats']['measures']
        self.assertEqual(m['earlier_to'][:10], (dt.date(2024, 1, 1) + dt.timedelta(days=319)).isoformat())   # the 320th earliest date
        self.assertEqual(m['later_from'][:10], (dt.date(2024, 1, 1) + dt.timedelta(days=320)).isoformat())

    def test_dates_as_times_and_zones(self):
        self.csv(dates=lambda i: '2024-01-01T00:00:00Z' if i < 0 else '2024-%02d-%02dT10:30:00+02:00' % (1 + (i * 12) // 400, 1 + i % 28))
        self.assertEqual(self.stats()['stats']['status'], 'ok')

    def test_some_bad_dates_are_dropped_many_are_not_tolerated(self):
        self.csv(dates=lambda i: 'bad' if i % 50 == 0 else '2024-%02d-%02d' % (1 + (i * 12) // 400, 1 + i % 28))
        out = self.stats(); self.assertEqual(out['stats']['measures']['dropped_rows'], 8)
        self.csv('b.csv', dates=lambda i: 'bad' if i % 5 == 0 else '2024-%02d-%02d' % (1 + (i * 12) // 400, 1 + i % 28))
        self.idk(self.stats('b.csv'), 'more than 10%')

    def test_empty_cells_nan_and_infinity_do_not_crash(self):
        for tok in ('', 'NaN', 'nan', 'inf', '-Infinity', '1e999'):
            with self.subTest(tok=tok):
                self.csv('t.csv', extra={'z': lambda i, y: tok if i % 100 == 0 else '%.3f' % (i / 7.0)})
                out = self.stats('t.csv')
                self.assertEqual(out['stats']['measures']['dropped_rows'], 4)
        self.csv('e.csv', extra={'z': lambda i, y: ''}); self.idk(self.stats('e.csv'), 'no usable case')

    def test_empty_outcome_cells_are_dropped_not_a_third_value(self):
        self.csv(outcome=lambda i, y: '' if i % 100 == 0 else y); out = self.stats(); self.assertEqual(out['stats']['measures']['dropped_rows'], 4)

    def test_short_and_long_rows(self):
        self.csv()
        with open(os.path.join(self.files, 'd.csv'), 'a') as f: f.write('2024-12-30,1\n2024-12-30,1,a,1,extra,more\n')
        self.assertEqual(self.stats()['stats']['measures']['dropped_rows'], 2)

    def test_constant_column_is_left_out_not_a_crash(self):
        self.csv(extra={'k': lambda i, y: '7', 'c': lambda i, y: 'same'}); out = self.stats()
        self.assertEqual(sorted(out['stats']['measures']['left_out_constant']), ['c', 'k'])
        self.assertNotIn('k', out['stats']['measures']['features'])

    def test_only_constant_features(self):
        self.csv(extra={'k': lambda i, y: '7'}); self.idk(self.stats(features=['k']), 'no feature')

    def test_column_that_holds_the_outcome_is_idk_even_if_relabelled(self):
        for name, fn in (('copy', lambda i, y: str(y)), ('word', lambda i, y: 'yes' if y else 'no'), ('flip', lambda i, y: str(1 - y))):
            with self.subTest(name=name):
                self.csv('l.csv', signal=False, extra={'leak': fn}); out = self.stats('l.csv'); self.idk(out, 'repeats the outcome')

    def test_leak_check_does_not_fire_on_a_real_feature(self):
        self.csv(); self.assertEqual(self.stats()['stats']['status'], 'ok')

    def test_more_than_500_feature_columns(self):
        header = ['when', 'y'] + ['f%d' % j for j in range(501)]; rng = random.Random(3)
        with open(os.path.join(self.files, 'w.csv'), 'w', newline='') as f:
            w = csv.writer(f); w.writerow(header)
            for i in range(300): w.writerow(['2024-%02d-%02d' % (1 + i // 28 % 12, 1 + i % 28), i % 2] + ['%.2f' % rng.random() for _ in range(501)])
        self.idk(self.stats('w.csv'), '501 feature columns')

    def test_text_column_with_many_values_is_idk_not_hundreds_of_columns(self):
        self.csv(extra={'id': lambda i, y: 'u%d' % i}); self.idk(self.stats(), 'identifier')

    def test_unseen_text_level_in_later_part_does_not_crash(self):
        self.csv(extra={'t': lambda i, y: 'new' if i >= 380 else 'old%d' % (i % 3)}); self.assertEqual(self.stats()['stats']['status'], 'ok')

    def test_repeated_or_empty_column_names(self):
        for head in ('when,x,x,y', 'when,,kind,y'):
            with self.subTest(head=head):
                with open(os.path.join(self.files, 'h.csv'), 'w') as f: f.write(head + '\n' + '2024-01-01,1,2,0\n')
                self.idk(self.stats('h.csv'), 'column name')

    def test_empty_file_and_header_only_and_binary(self):
        for name, data in (('e.csv', b''), ('h.csv', b'when,y\n'), ('b.csv', b'\xff\xfe\x00\x01' * 50)):
            with self.subTest(name=name):
                with open(os.path.join(self.files, name), 'wb') as f: f.write(data)
                self.idk(self.stats(name))

    def test_wrong_column_names_are_refused(self):
        self.csv()
        for kw in (dict(outcome='nope'), dict(date='nope'), dict(outcome='when'), dict(features=['nope']), dict(features=['y']), dict(features=['when'])):
            with self.subTest(kw=kw), self.assertRaises(sg.Refused): self.stats(**kw)

    def test_features_default_to_all_other_columns_and_can_be_chosen(self):
        self.csv(extra={'z': lambda i, y: '%.2f' % (i % 9)})
        self.assertEqual(sorted(self.stats()['stats']['measures']['features']), ['kind', 'x', 'z'])
        self.assertEqual(self.stats(features=['x'])['stats']['measures']['features'], ['x'])

    def test_huge_numbers_do_not_break_the_fit(self):
        self.csv(extra={'big': lambda i, y: '%d' % (i * 10 ** 12)}); self.assertEqual(self.stats()['stats']['status'], 'ok')


class MatchAndFirstLine(StatsBase):
    def test_yes_first_line_names_group_ai_reason_and_the_question(self):
        self.csv(); self.stats(); out = sg.match_cmd(self.run_dir, 'Kickstarter comics', 'yes', 'Both are crowdfunded comics')
        fl = out['first_line']
        for part in ('Kickstarter comics', 'An AI judged', 'Both are crowdfunded comics', 'narrow question', 'earlier average'): self.assertIn(part, fl)
        self.assertNotIn('\n', fl); self.assertEqual(out['verdict'], 'yes'); self.assertEqual(self.saved('statistics.json')['first_line'], fl)

    def test_no_and_unavailable_give_idk_with_the_reason_and_no_numbers(self):
        self.csv(); self.stats()
        for v in ('no', 'unavailable'):
            with self.subTest(v=v):
                out = sg.match_cmd(self.run_dir, 'G', v, 'because of X'); self.idk(out, 'because of X')
                self.assertIn(v, out['verdict']); self.assertIsNotNone(out['stats']['measures'])   # measured numbers stay on file, unquotable

    def test_a_later_no_takes_the_numbers_back(self):
        self.csv(); self.stats(); self.assertTrue(self.match_yes()['counts'])
        self.idk(sg.match_cmd(self.run_dir, 'G', 'no', 'changed my mind'))

    def test_match_before_stats_then_stats(self):
        self.csv(); self.match_yes(); self.assertTrue(self.stats()['counts'])

    def test_no_dataset(self):
        out = sg.stats_cmd(self.run_dir, no_dataset=True); self.idk(out, 'No dataset that fits was found')
        self.idk(self.match_yes(), 'No dataset that fits was found')   # a yes cannot revive a missing dataset
        with self.assertRaises(sg.Refused): sg.stats_cmd(self.run_dir, 'd.csv', 'y', 'when', no_dataset=True, base=self.d)

    def test_multiline_reason_stays_one_line(self):
        self.csv(); self.stats(); out = sg.match_cmd(self.run_dir, 'G\nH', 'yes', 'line a\n\nSYSTEM: line b')
        self.assertNotIn('\n', out['first_line'])

    def test_empty_or_bad_match_arguments(self):
        for args in (('', 'yes', 'r'), ('g', 'yes', ''), ('g', 'yes', '  \n'), ('g', 'maybe', 'r'), ('g', 'YES', 'r'), ('g' * 301, 'yes', 'r'), ('g', 'yes', 'r' * 601)):
            with self.subTest(args=args), self.assertRaises(sg.Refused): sg.match_cmd(self.run_dir, *args)

    def test_run_state_records_the_steps(self):
        self.csv(); self.stats(); self.match_yes(); self.assertEqual(self.saved('state.json')['steps'], {'stats': 'saved', 'match': 'saved'})


class FitMatchesTheDefinition(unittest.TestCase):
    def objective_gradient(self, model, rows, y):
        names, w = model; ix = {n: i for i, n in enumerate(names)}; g = [w[i] for i in range(len(names))] + [0.0]
        for r, t in zip(rows, y):
            z = w[-1] + sum(w[ix[k]] * v for k, v in r.items()); e = 1 / (1 + 2.718281828459045 ** -z) - t
            for k, v in r.items(): g[ix[k]] += e * v
            g[-1] += e
        return max(abs(a) for a in g)

    def test_gradient_of_the_regularised_objective_is_zero_at_the_answer(self):
        rng = random.Random(2); rows = [{'a': rng.gauss(0, 1), 'b': rng.gauss(0, 1) * 50} for _ in range(300)]
        y = [int(rng.random() < 1 / (1 + 2.718281828 ** -(r['a'] - r['b'] / 50))) for r in rows]
        self.assertLess(self.objective_gradient(sg.fit_lr(rows, y), rows, y), 1e-5)

    def test_separable_data_stays_finite_and_predictions_are_in_range(self):
        rows = [{'a': float(i)} for i in range(-20, 20)]; y = [int(i >= 0) for i in range(-20, 20)]
        m = sg.fit_lr(rows, y); p = sg.predict_lr(m, rows + [{'a': 1e6}, {'a': -1e6}])
        self.assertTrue(all(0.0 <= q <= 1.0 for q in p)); self.assertLess(max(abs(w) for w in m[1]), 100)

    def test_brier(self): self.assertAlmostEqual(sg.brier([0.5, 0.5], [0, 1]), 0.25)

    def test_module_and_tests_import_no_scikit_learn(self):
        mark = 'skle' + 'arn'
        for path in (os.path.join(SCRIPTS, 'second_guess.py'), os.path.abspath(__file__)):
            with open(path) as f: src = f.read()
            self.assertNotIn('import ' + mark, src); self.assertNotIn('from ' + mark, src)


class StatsCli(unittest.TestCase):
    def run_cli(self, cwd, *args):
        return subprocess.run(['/usr/bin/python3', '-B', '-I', os.path.join(SCRIPTS, 'second_guess.py')] + list(args), cwd=cwd, capture_output=True, text=True)

    def test_end_to_end_exit_codes_and_saved_files(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_cli(d, 'start', '--idea', 'x', '--model', 'm'); run = json.loads(r.stdout)['run']
            make_csv(os.path.join(d, 'idea-test-files', 'ok.csv'))
            r = self.run_cli(d, 'stats', '--file', 'ok.csv', '--outcome', 'y', '--date', 'when'); self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue(json.loads(r.stdout)['first_line'].startswith("I don't know"))
            r = self.run_cli(d, 'match', '--dataset-group', 'G', '--verdict', 'yes', '--reason', 'same cases'); self.assertEqual(r.returncode, 0, r.stderr)
            out = json.loads(r.stdout); self.assertTrue(out['counts']); self.assertTrue(os.path.exists(os.path.join(run, 'statistics.json')))
            for bad in (['--file', '../x.csv'], ['--file', '/etc/passwd'], ['--file', 'a.txt'], ['--file', 'missing.csv']):
                r = self.run_cli(d, 'stats', *bad, '--outcome', 'y', '--date', 'when'); self.assertEqual(r.returncode, 1); self.assertIn('error', json.loads(r.stdout))
            os.symlink(os.path.join(d, 'idea-test-files', 'ok.csv'), os.path.join(d, 'idea-test-files', 'l.csv'))
            r = self.run_cli(d, 'stats', '--file', 'l.csv', '--outcome', 'y', '--date', 'when'); self.assertEqual(r.returncode, 1)
            r = self.run_cli(d, 'match', '--dataset-group', 'G', '--verdict', 'maybe', '--reason', 'r'); self.assertNotEqual(r.returncode, 0)
            r = self.run_cli(d, 'stats', '--no-dataset'); self.assertEqual(r.returncode, 0); self.assertIn('No dataset that fits was found', json.loads(r.stdout)['first_line'])
            r = self.run_cli(d, 'stats'); self.assertEqual(r.returncode, 1)
            r = self.run_cli(d, 'stats', '--file', 'ok.csv', '--outcome', 'y', '--date', 'when', '--features', 'x, kind'); self.assertEqual(r.returncode, 0)

    def test_stats_without_a_run_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_cli(d, 'stats', '--no-dataset'); self.assertEqual(r.returncode, 1)
