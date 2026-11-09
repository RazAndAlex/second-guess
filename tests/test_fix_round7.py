"""Tests for fix round 7: source-context, drop-card --index, the money figure with a decimal comma (work/fix-round7-notes.md)."""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_report as tr  # noqa: E402
import test_fix_round6 as r6  # noqa: E402
sg = tr.sg
FYTA, FYTA_Q = r6.FYTA, r6.FYTA_Q
PAGE = ('<html><head><title>The soil sensor review</title><meta property="article:published_time" content="2026-03-02">'
        '</head><body><p>' + 'before words ' * 20 + tr.QUOTE + ' after words ' * 20 + '</p><script>var secret=1</script></body></html>')


class Money(tr.Base):
    def setUp(self):
        super().setUp(); self.earlier([FYTA], {0: b'<p>' + FYTA_Q.encode() + b'</p>'})

    def test_the_whole_figure_passes_in_both_written_forms(self):
        for p in ('The FYTA Beam G2 costs €39,99.', 'The FYTA Beam G2 costs 39,99 euros.', 'The FYTA Beam G2 costs €39.99.'): self.report([p])

    def test_parts_and_look_alikes_are_refused(self):
        for p, h in (('The FYTA Beam G2 costs €39.', '39'), ('Reviewers tested 99 sensors.', '99'), ('Reviewers tested 39 sensors.', '39'), ('It costs 39 euros.', '39')):
            self.assertRefusedClean([p], holds=[h])

    def test_a_european_thousands_figure_still_works_as_written(self):
        q = 'The Pro kit is on sale for a list price of €1.299,00 in the shop.'
        c = dict(FYTA, quote=q, number='€1.299,00', url='https://example.com/pro')
        self.cards([c], {0: b'<p>' + q.encode() + b'</p>'}); sg.attack_cmd(self.run_dir, 'a.json')
        self.report(['The Pro kit costs €1.299,00.'])

    def test_number_words_and_plain_numbers_still_hold(self):
        self.assertRefusedClean(['It costs €3,99.'], holds=['3,99'])


class PurchaseFigure(unittest.TestCase):
    def test_the_sale_words_stay_refused_outside_the_card_check(self):
        self.assertTrue(sg.purchase_figure('The kit is on sale for $39.99'))
        self.assertIsNone(sg.card_purchase_figure('The kit is on sale for $39.99'))


class SourceContext(tr.Base):
    go = tr.Cli.go

    def setUp(self):
        super().setUp(); self.pf = os.path.join(self.d, 'p.html')
        with open(self.pf, 'w') as f: f.write(PAGE)

    def card_in(self):
        self.earlier([tr.GOOD, tr.MISSING], {0: PAGE.encode(), 1: b'<p>nothing here</p>'})

    def test_writes_one_file_per_passing_card_with_the_parts(self):
        self.card_in(); out = sg.source_context_cmd(self.run_dir)
        self.assertEqual([c['index'] for c in out['cards']], [0]); self.assertEqual(out['cards'][0]['url'], tr.GOOD['url'])
        path = os.path.join(self.run_dir, 'source-context', 'CARD_0.txt'); self.assertTrue(os.path.isfile(path))
        t = open(path, encoding='utf-8').read()
        for h in ('"quote"', 'PAGE TITLE: The soil sensor review', 'PAGE DATE LINES:', '2026-03-02', 'PAGE TEXT AROUND THE QUOTE', 'DATA FROM A WEB PAGE', tr.QUOTE.lower()):
            self.assertIn(h, t)
        self.assertNotIn('secret', t)

    def test_page_file_flag_gives_text_for_a_card_that_has_none(self):
        self.card_in(); cache = os.path.join(self.run_dir, 'cache')
        for f in os.listdir(cache) if os.path.isdir(cache) else []: os.unlink(os.path.join(cache, f))
        out = sg.source_context_cmd(self.run_dir, {0: self.pf})
        self.assertEqual(out['cards'][0]['file'], os.path.join(self.run_dir, 'source-context', 'CARD_0.txt'))

    def test_a_card_passed_with_a_page_file_keeps_its_text(self):
        self.card_in(); out = sg.source_context_cmd(self.run_dir); self.assertNotIn('missing', out['cards'][0])

    def test_missing_text_is_said_for_that_card_and_the_rest_go_on(self):
        q2 = 'Another long enough sentence with 77 inside it for the second card here.'
        c2 = dict(tr.GOOD, url='https://example.com/two', quote=q2, number='77')
        self.earlier([tr.GOOD, c2], {0: PAGE.encode(), 1: q2.encode()})
        import hashlib
        h = hashlib.sha256(sg.encode_url(c2['url']).encode()).hexdigest()
        for e in ('.body', '.json'):
            p = os.path.join(self.run_dir, 'cache', h + e)
            if os.path.exists(p): os.unlink(p)
        out = sg.source_context_cmd(self.run_dir)
        self.assertEqual(len(out['cards']), 2); bad = [c for c in out['cards'] if c['index'] == 1][0]
        self.assertIn('no page text', bad['missing']); self.assertNotIn('file', bad)
        self.assertTrue(os.path.isfile([c for c in out['cards'] if c['index'] == 0][0]['file']))

    def test_cli_source_context_and_drop_by_index(self):
        with tempfile.TemporaryDirectory() as d:
            name = json.loads(self.go(d, 'start', '--idea', 'x', '--model', 'm').stdout)['name']
            with open(os.path.join(d, 'c.json'), 'w') as f: json.dump(dict(cards=[tr.GOOD]), f)
            self.go(d, 'check-cards', 'c.json', '--run', name, '--page-file', '0', self.pf)
            r = self.go(d, 'source-context', '--run', name); self.assertEqual(r.returncode, 0, r.stdout); out = json.loads(r.stdout)
            self.assertTrue(os.path.isfile(out['cards'][0]['file']))
            a = ('drop-card', '--run', name, '--reason', 'r')
            self.assertEqual(self.go(d, *a, '--index', '0', '--url', tr.GOOD['url'], '--quote', tr.QUOTE).returncode, 1)
            self.assertEqual(self.go(d, *a, '--index', '5').returncode, 1)
            self.assertEqual(self.go(d, *a).returncode, 1)
            r = self.go(d, *a, '--index', '0'); self.assertEqual(r.returncode, 0, r.stdout); self.assertEqual(json.loads(r.stdout)['result'], 'dropped')


if __name__ == '__main__':
    unittest.main()
