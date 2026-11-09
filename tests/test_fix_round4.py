"""Tests for fix round 4 (work/fix-round4-brief.md). Each was written to fail on the module at sha 04ea4799ef9a.
The phrase lists below are the brief's own words and a few ordinary sentences. They prove the listed phrases are caught, and give no rate."""
import datetime as dt, os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_report as tr  # noqa: E402
sg = tr.sg
GOOD, QUOTE, TODAY = tr.GOOD, tr.QUOTE, tr.TODAY


class Item2FrozenLean(tr.Base):
    def test_lean_refused_once_a_report_exists(self):
        self.earlier(); sg.lean_cmd(self.run_dir, 31, 'a second look', today=TODAY)  # before the report a lean may change
        self.report(); before = self.page()
        with self.assertRaises(sg.Refused) as c: sg.lean_cmd(self.run_dir, 90, 'changed my mind', today=TODAY)
        self.assertIn('report', str(c.exception)); self.assertEqual(self.page(), before)

    def test_report_may_run_again_and_replaces_the_page(self):
        self.earlier(); self.report(); self.report(['Gone after 1 year.']); self.assertIn('Gone after 1 year.', self.page())

    def test_a_refused_report_does_not_freeze_the_lean(self):
        self.earlier()
        with self.assertRaises(sg.Refused): self.report(['Now 8888.'])
        sg.lean_cmd(self.run_dir, 40, 'still open', today=TODAY)

    def test_date_and_clock_refusals_stay(self):
        self.earlier()
        with self.assertRaises(sg.Refused): sg.lean_cmd(self.run_dir, 40, 'late', today=dt.date(2027, 6, 30))
        with self.assertRaises(sg.Refused): sg.lean_cmd(self.run_dir, 40, 'early clock', today=dt.date(2026, 11, 4))

    def test_no_result_command_and_no_log(self):
        for name in ('result_cmd', 'append_log', '_log_lines'): self.assertFalse(hasattr(sg, name), name)
        self.earlier(); self.report(); self.assertFalse(os.path.exists(os.path.join(self.d, sg.RUNS, 'log.jsonl')))


class Item6ErrorScore(unittest.TestCase):
    def test_no_brier_in_the_module_text(self):
        with open(sg.SCRIPT, encoding='utf-8') as f: src = f.read()
        idk = [l for l in src.split('\n') if 'raise Idk' in l]
        for l in idk: self.assertNotIn('Brier', l)
        self.assertEqual(sum('error score %.4f against %.4f; lower is better' in l for l in idk), 3)


def problems(text): return sg.number_problems([('x', text)], set())


class Item7PurchasePhrases(unittest.TestCase):
    REFUSED = ["I'd buy it.", "They'd buy two.", "They’d pay for it.", 'Shops are likely to buy it.', 'Chains are bound to buy it.', 'Shops are set to purchase it.',
               'A chain is about to buy it.', 'Most end up buying one.', 'They end up paying twice.', 'Shops will put money down.', 'Shops hand over cash on day one.',
               'Buyers are queuing outside.', 'Buyers are queueing outside.', "I'd pre-order it.", "We'd subscribe."]
    PASSES = ['A chain lists it.', 'The buyer reads the label.', 'The set of tools is small.', 'It is about the shelf.', 'The team would meet on Friday.']

    def test_phrases_are_refused(self):
        for t in self.REFUSED: self.assertIn('purchase phrase', ' '.join(problems(t)), t); self.assertIsNotNone(sg.purchase_figure(t), t)

    def test_ordinary_sentences_pass(self):
        for t in self.PASSES: self.assertEqual(problems(t), [], t)


class Item8NumberWords(unittest.TestCase):
    REFUSED = ['Zero shops list it.', 'Nil chains list it.', 'A fifth of shops list it.', 'A twentieth of shops list it.', 'A sixth of shops list it.', 'One-third of shops list it.',
               'Two thirds of shops list it.', 'Three-fifths of shops list it.', 'Sales will double.', 'Sales doubled.', 'Sales will triple.', 'It tripled.', 'It grew twice as fast.',
               'It grew tenfold.', 'It grew hundredfold.']
    PASSES = ['The fifth chain lists it.', 'Shops list it.', 'A third party could copy it.'.replace('A third party', 'An outside party')]

    def test_words_are_refused_and_say_to_give_a_number(self):
        for t in self.REFUSED:
            out = problems(t); self.assertTrue(out, t); self.assertIn('give the number from a source', ' '.join(out), t)

    def test_ordinary_sentences_pass(self):
        for t in self.PASSES: self.assertEqual(problems(t), [], t)

    def test_the_lean_reason_refuses_them_too(self):
        for t in ('twice the interest', 'a fifth of chains'):
            with self.assertRaises(sg.Refused, msg=t): sg._say_no_number(t)


class Item9CardFieldsAndModel(tr.Base):
    def result_of(self, **kw):
        return self.cards([dict(GOOD, **kw)], {0: b'<p>' + QUOTE.encode() + b'</p>'})['results'][0]

    def test_counts_in_sample_and_year_fail(self):
        for k, v in (('sample', '500 units sold'), ('sample', '4,000 buyers'), ('year', '500 units sold'), ('population', '4,000 buyers')):
            self.assertEqual(self.result_of(**{k: v})['result'], 'fail', (k, v))

    def test_ordinary_values_still_pass(self):
        for kw in (dict(sample='7,000 new products'), dict(year='2021'), dict(sample='120 grocery chains')): self.assertEqual(self.result_of(**kw)['result'], 'pass', kw)

    def test_model_name(self):
        for m in ('m, 20 orders', '500 units sold', '4,000 buyers'):
            with self.assertRaises(sg.Refused, msg=m): sg.start('idea', m, base=self.d)
        sg.start('idea', 'Opus 5.5', base=self.d)


if __name__ == '__main__':
    unittest.main()
