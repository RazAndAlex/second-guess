"""Tests for fix round 8: a throttled live page still reaches the archive, source-context fixes, euro forms, two mutant tests (work/fix-round8-notes.md)."""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_report as tr  # noqa: E402
import test_fix_round6 as r6  # noqa: E402
import test_fix_round7 as r7  # noqa: E402
sg = tr.sg
LIVE = tr.GOOD['url']
CDX = b'20240101000000\n20250101000000\n'


class Net:
    """A fake network with a fake clock. The live page answers `live`; the archive answers with `capture` bytes."""
    def __init__(self, live=429, capture=b'<p>' + tr.QUOTE.encode() + b'</p>'):
        self.t = 0.0; self.live = live; self.capture = capture; self.urls = []; self.slept = []

    def clock(self): return self.t

    def sleep(self, s): self.slept.append(s); self.t += s

    def raw(self, url, timeout):
        self.urls.append(url)
        assert timeout <= 90 - self.t + 1e-9, 'a request started with more time than is left'
        if 'cdx/search' in url: return 200, CDX, url, ''
        if url.startswith('https://web.archive.org/web/'): return 200, self.capture, url, ''
        if url.startswith('https://web.archive.org') or url.startswith('https://github.com'): return 200, b'', url, ''
        return (self.live, b'local_rate_limited', url, '') if self.live else (200, b'<p>x</p>', url, '')


class ThrottledLivePage(tr.Base):
    def run_cards(self, net, limit=90):
        p = self.write('c.json', dict(cards=[tr.GOOD]), self.d)
        return sg.check_cards(p, self.run_dir, raw=net.raw, sleep=net.sleep, clock=net.clock, time_limit=limit)

    def test_archive_capture_with_the_quote_passes_in_the_same_run(self):
        n = Net(); r = self.run_cards(n)['results'][0]
        self.assertEqual(r['result'], 'pass', r); self.assertIn('archive capture', r['detail'])
        self.assertLessEqual(n.t, 90)

    def test_archive_capture_without_the_quote_is_throttled_and_says_why(self):
        n = Net(capture=b'<p>some other page text</p>'); r = self.run_cards(n)['results'][0]
        self.assertEqual(r['result'], 'throttled', r)
        self.assertIn('live page refused', r['detail']); self.assertIn('archive', r['detail']); self.assertIn('does not hold the quote', r['detail'])

    def test_the_wait_is_short_and_nothing_passes_the_deadline(self):
        n = Net(); self.run_cards(n); self.assertLessEqual(max(n.slept), 15); self.assertLessEqual(n.t, 90)

    def test_a_live_503_keeps_its_full_backoff(self):
        slept = []
        r = sg.fetch('https://example.com/b', raw=lambda u, t: (503, b'', u, ''), sleep=slept.append, clock=lambda: 0.0, max_wait=sg.LIVE_WAIT)
        self.assertEqual(r[0], 503); self.assertEqual([s for s in slept if s in sg.BACKOFF], list(sg.BACKOFF))

    def test_two_throttled_cards_both_get_checked_in_one_run(self):
        n = Net(); c2 = dict(tr.GOOD, url='https://example.com/second')
        p = self.write('c.json', dict(cards=[tr.GOOD, c2]), self.d)
        out = sg.check_cards(p, self.run_dir, raw=n.raw, sleep=n.sleep, clock=n.clock, time_limit=90)
        self.assertEqual([r['result'] for r in out['results']], ['pass', 'pass'], out)

    def test_a_page_that_fails_on_a_live_200_still_fails(self):
        n = Net(live=0, capture=b'<p>other</p>'); r = self.run_cards(n)['results'][0]
        self.assertEqual(r['result'], 'fail', r)

    def test_fetch_default_still_waits_the_full_backoff(self):
        slept = []
        r = sg.fetch('https://example.com/a', raw=lambda u, t: (429, b'', u, ''), sleep=slept.append, clock=lambda: 0.0)
        self.assertEqual(r[0], 429); self.assertEqual([s for s in slept if s in sg.BACKOFF], list(sg.BACKOFF))


class SourceContextFixes(tr.Base):
    def setUp(self):
        super().setUp(); self.pf = os.path.join(self.d, 'p.html')

    card_in = r7.SourceContext.card_in

    def test_a_wrong_page_file_keeps_the_old_page_and_says_so_for_that_card(self):
        self.card_in(); bad = os.path.join(self.d, 'bad.html')
        with open(bad, 'w') as f: f.write('<p>local_rate_limited</p>')
        out = sg.source_context_cmd(self.run_dir, {0: bad})
        self.assertIn('page file', out['cards'][0]['missing']); self.assertIn('quote', out['cards'][0]['missing'])
        self.assertNotIn('file', out['cards'][0])
        self.assertTrue(os.path.isfile(os.path.join(self.run_dir, 'cache', __import__('hashlib').sha256(sg.encode_url(tr.GOOD['url']).encode()).hexdigest() + '.body')))
        with open(os.path.join(self.run_dir, 'cache', __import__('hashlib').sha256(sg.encode_url(tr.GOOD['url']).encode()).hexdigest() + '.body'), 'rb') as f: self.assertEqual(f.read(), r7.PAGE.encode())
        self.assertNotIn('missing', sg.source_context_cmd(self.run_dir)['cards'][0])  # the old page still serves

    def test_old_card_files_for_cards_no_longer_listed_are_removed(self):
        self.card_in(); sg.source_context_cmd(self.run_dir); folder = os.path.join(self.run_dir, 'source-context')
        stale = os.path.join(folder, 'CARD_7.txt')
        with open(stale, 'w') as f: f.write('old')
        other = os.path.join(folder, 'notes.txt')
        with open(other, 'w') as f: f.write('mine')
        sg.source_context_cmd(self.run_dir)
        self.assertFalse(os.path.lexists(stale)); self.assertTrue(os.path.isfile(os.path.join(folder, 'CARD_0.txt'))); self.assertTrue(os.path.isfile(other))

    def test_a_symlink_named_like_a_card_file_is_neither_followed_nor_deleted(self):
        self.card_in(); sg.source_context_cmd(self.run_dir); folder = os.path.join(self.run_dir, 'source-context')
        target = os.path.join(self.d, 'outside.txt')
        with open(target, 'w') as f: f.write('keep')
        link = os.path.join(folder, 'CARD_9.txt'); os.symlink(target, link)
        sg.source_context_cmd(self.run_dir)
        self.assertTrue(os.path.islink(link)); self.assertEqual(open(target).read(), 'keep')

    def test_the_window_is_3000_characters_each_side(self):
        page = '<p>' + 'a ' * 2500 + tr.QUOTE + ' b' * 2500 + '</p>'
        self.earlier([tr.GOOD], {0: page.encode()}); t = open(sg.source_context_cmd(self.run_dir)['cards'][0]['file'], encoding='utf-8').read()
        body = t.split('<<<PAGE\n')[1].split('\nPAGE>>>')[0]; k = body.lower().index(tr.QUOTE.lower())
        self.assertEqual(k, 3000); self.assertEqual(len(body) - k - len(tr.QUOTE), 3000)

    def test_drop_card_refuses_a_negative_index(self):
        self.card_in()
        with self.assertRaises(sg.Refused): sg.drop_card_cmd(self.run_dir, index=-1, reason='r')


class EuroForms(unittest.TestCase):
    def test_trailing_sign_and_leading_code_are_one_figure(self):
        for a, b in (('39,99€', '39.99€'), ('EUR 39,99', 'EUR 39.99'), ('€39,99', '€39.99'), ('39,99 euros', '39.99 euros')):
            self.assertEqual(sg._dec_comma('It costs %s.' % a), 'It costs %s.' % b)

    def test_the_figures_pass_the_report_rule(self):
        for s in ('The FYTA Beam G2 costs 39,99€.', 'The FYTA Beam G2 costs EUR 39,99.'):
            m = r7.Money('test_the_whole_figure_passes_in_both_written_forms'); m.setUp()
            try: m.report([s])
            finally: m.tearDown()


if __name__ == '__main__':
    unittest.main()
