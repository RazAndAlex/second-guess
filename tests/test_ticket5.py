import datetime, json, os, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, 'skills', 'second-guess', 'scripts')
sys.path.insert(0, SCRIPTS)
import second_guess as sg  # noqa: E402

MUST_REFUSE = [
    'sell 1,000 units', '$10k in revenue', '500 paying customers', '30% of visitors would buy', '1,000 pre-orders',
    'reach $5k MRR', '1k subscribers', '100 sales', 'one thousand buyers',
    'Sell one thousand units by launch', 'ten thousand dollars in sales', 'a million in revenue', 'half a million dollars',
    'make ten grand', 'at least 75 percent of shoppers would purchase it', 'one in ten visitors buys it', '9 out of 10 people would pay for it',
    'half of all visitors would buy', 'most people would order it', 'conversion rate above 3%', 'revenue exceeds 10k', 'sales of 2000',
    'sold 2k copies', 'sell at least 500', 'reach five hundred customers', 'three hundred orders in the first month', '800 backers on Kickstarter',
    '1 000 units', '1,000,000 units shipped', '€2m ARR', 'a dozen sales', '12 monthly paying subscribers', 'a 5% market share would buy',
    '1000 PRE ORDERS', 'twenty-five hundred buyers', '５００ units', 'over 100 unit sales', '100 were sold', 'GMV of 50k',
    'sell up to 500', '20 percent of people who see it pay for it', 'gain 50 new paying customers',
]
MUST_PASS = [
    'at least one shop chain lists it', 'funded on Kickstarter', 'a named journal publishes a review', 'the app reaches the App Store',
    'a patent is granted', 'the founder is interviewed by a national newspaper', 'a university lab pilots it by 2027',
    'a regulator clears the device', 'a distributor signs a contract', 'it appears in two regional stores', 'Google Play lists the app',
    'three shop chains order it', 'a retailer places a first order', 'a sales team is hired', 'it is stocked in stores in 3 countries',
    'the product gets ten reviews on Trustpilot', 'sales channel opens in 2027', 'a named podcast features it', 'the company announces a partnership',
    'the company is acquired', 'the campaign launches on Indiegogo',
]
# today's behaviour for wording the word list cannot catch; if one of these starts being refused, move it to MUST_REFUSE
KNOWN_MISSES = [
    '10,000 downloads', 'reach 2k users', 'sell out the first production run', 'become profitable', 'break even in year one',
    'ѕell 1,000 uniтs', 'get 3 million views', 'make the first sale',
]
TODAY = datetime.date(2026, 11, 5); NOW = lambda: datetime.datetime(2026, 11, 5, 16, 0, 0)


class Rule(unittest.TestCase):
    def test_list_sizes(self):
        self.assertGreaterEqual(len(MUST_REFUSE), 25); self.assertGreaterEqual(len(MUST_PASS), 10)

    def test_every_must_refuse_text_is_refused(self):
        for t in MUST_REFUSE: self.assertIsNotNone(sg.target_problem(t), t)

    def test_every_must_pass_text_passes(self):
        for t in MUST_PASS: self.assertIsNone(sg.target_problem(t), t)

    def test_known_misses_record_todays_behaviour(self):
        for t in KNOWN_MISSES: self.assertIsNone(sg.target_problem(t), t)


class Base(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory(); self.d = self._d.name
        self.run_dir = sg.start('idea', 'm', base=self.d, today='2026-11-05'); self.name = os.path.basename(self.run_dir)

    def tearDown(self): self._d.cleanup()

    def target(self, text='a named chain lists it', date='2027-06-30', place='the chain site', **kw):
        return sg.target_cmd(self.run_dir, text, date, place, today=TODAY, now=NOW, **kw)

    def exists(self, name): return os.path.exists(os.path.join(self.run_dir, name))

    def saved(self, name):
        with open(os.path.join(self.run_dir, name)) as f: return json.load(f)


class Target(Base):
    def test_saves_with_time_and_ai_flag_and_folds_newlines(self):
        r = self.target(text='a named\nchain  lists it', ai_drafted=True)
        self.assertEqual(r['text'], 'a named chain lists it'); self.assertTrue(r['ai_drafted']); self.assertEqual(r['saved'], '2026-11-05T16:00:00')
        self.assertEqual(self.saved('target.json'), r); self.assertEqual(self.saved('state.json')['steps']['target'], 'saved')

    def test_second_call_refused_even_with_same_text(self):
        first = self.target()
        for kw in (dict(), dict(text='something else entirely')):
            with self.assertRaises(sg.Refused): self.target(**kw)
        self.assertEqual(self.saved('target.json'), first)
        self.assertFalse(self.exists('target.json.tmp'))

    def test_refusals_save_nothing(self):
        for kw in (dict(date='2026-11-05'), dict(date='2026-11-04'), dict(date='2027-02-30'), dict(date='30/06/2027'), dict(date='2027-6-30'),
                   dict(date='２０２７-06-30'), dict(date=''), dict(text=''), dict(text='  \n '), dict(place=' '), dict(text='x' * 301), dict(place='x' * 201),
                   dict(text='sell 1,000 units')):
            with self.assertRaises(sg.Refused, msg=str(kw)): self.target(**kw)
            self.assertFalse(self.exists('target.json'), kw); self.assertFalse(self.exists('target.json.tmp'))
        self.assertNotIn('target', self.saved('state.json')['steps'])

    def test_limits_are_inclusive_and_tomorrow_is_ok(self):
        self.target(text='x' * 300, date='2026-11-06', place='y' * 200)

    def test_the_refusal_names_the_reason(self):
        with self.assertRaises(sg.Refused) as c: self.target(text='$10k in revenue')
        self.assertIn('money', str(c.exception))


class Lean(Base):
    def lean(self, p='30', reason='chains want proof first', **kw): return sg.lean_cmd(self.run_dir, p, reason, now=NOW, **kw)

    def test_refused_before_target(self):
        with self.assertRaises(sg.Refused): self.lean()
        self.assertFalse(self.exists('lean.json'))

    def test_percent_range(self):
        self.target()
        for ok, v in (('0', 0), ('100', 100), ('37.5', 37.5), (' 30 ', 30)): self.assertEqual(self.lean(ok)['percent'], v)
        for bad in ('-1', '-0.1', '100.1', '101', 'nan', 'NaN', 'inf', '-inf', 'infinity', '', 'abc', '1e2', '1_0', '30%', '0x10', '١٠', '1,5', None, True):
            with self.assertRaises(sg.Refused, msg=repr(bad)): self.lean(bad)
        self.assertEqual(self.saved('lean.json')['percent'], 37.5 if False else 30)

    def test_reason_required(self):
        self.target()
        for bad in ('', '   ', None, 'x' * 501):
            with self.assertRaises(sg.Refused): self.lean(reason=bad)
        self.assertFalse(self.exists('lean.json'))

    def test_rerun_keeps_history_with_times(self):
        self.target(); self.lean('30', 'first'); r = self.lean('45', 'second'); r = sg.lean_cmd(self.run_dir, '50', 'third', now=lambda: datetime.datetime(2026, 11, 6, 9, 0, 0))
        self.assertEqual((r['percent'], r['reason'], r['saved']), (50, 'third', '2026-11-06T09:00:00'))
        self.assertEqual([(h['percent'], h['reason']) for h in r['history']], [(30, 'first'), (45, 'second')])
        self.assertTrue(all(h['saved'] for h in r['history'])); self.assertNotIn('score', json.dumps(r))


class Attack(Base):
    def file(self, obj, raw=None):
        with open(os.path.join(self.run_dir, 'a.json'), 'w') as f: f.write(raw if raw is not None else json.dumps(obj))
        return 'a.json'  # a bare name inside the run folder

    F = {'person': 'A buyer', 'kills': 'too dear', 'ask': 'what price?'}

    def test_saves_text_and_rerun_replaces(self):
        sg.attack_cmd(self.run_dir, self.file(dict(findings=[self.F, dict(self.F, person='B\n  two')])))
        self.assertEqual(len(self.saved('attack.json')['findings']), 2); self.assertEqual(self.saved('attack.json')['findings'][1]['person'], 'B two')
        sg.attack_cmd(self.run_dir, self.file(dict(findings=[self.F]))); self.assertEqual(len(self.saved('attack.json')['findings']), 1)

    def test_wrong_shapes_refused_and_nothing_saved(self):
        F = self.F
        for bad in ({}, [], {'findings': []}, {'findings': 'x'}, {'findings': [F], 'extra': 1}, {'findings': [{'person': 'a', 'kills': 'b'}]},
                    {'findings': [dict(F, extra='z')]}, {'findings': [dict(F, ask=5)]}, {'findings': [dict(F, ask='')]}, {'findings': [dict(F, kills=' ')]},
                    {'findings': ['x']}, {'findings': [dict(F, person='x' * 501)]}, {'findings': [F] * 21}, {'findings': [None]}):
            with self.assertRaises(sg.Refused, msg=str(bad)[:60]): sg.attack_cmd(self.run_dir, self.file(bad))
        for raw in ('not json', '', '[' * 100000):
            with self.assertRaises(sg.Refused): sg.attack_cmd(self.run_dir, self.file(None, raw))
        with self.assertRaises(sg.Refused): sg.attack_cmd(self.run_dir, os.path.join(self.d, 'missing.json'))
        with self.assertRaises(sg.Refused): sg.attack_cmd(self.run_dir, self.d)
        self.assertFalse(self.exists('attack.json'))

    def test_failed_rerun_keeps_the_old_file(self):
        sg.attack_cmd(self.run_dir, self.file(dict(findings=[self.F])))
        with self.assertRaises(sg.Refused): sg.attack_cmd(self.run_dir, self.file({'findings': []}))
        self.assertEqual(len(self.saved('attack.json')['findings']), 1)

    def test_markup_is_kept_as_plain_text(self):
        sg.attack_cmd(self.run_dir, self.file(dict(findings=[dict(self.F, kills='<script>x</script>')])))
        self.assertEqual(self.saved('attack.json')['findings'][0]['kills'], '<script>x</script>')


class Cli(unittest.TestCase):
    def go(self, cwd, *a):
        return subprocess.run(['/usr/bin/python3', '-B', '-I', os.path.join(SCRIPTS, 'second_guess.py')] + list(a), cwd=cwd, capture_output=True, text=True)

    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            run = json.loads(self.go(d, 'start', '--idea', 'x', '--model', 'm').stdout)['run']
            r = self.go(d, 'lean', '--percent', '30', '--reason', 'r'); self.assertEqual(r.returncode, 1); self.assertIn('error', json.loads(r.stdout))
            r = self.go(d, 'target', '--text', 'sell 1,000 units', '--date', '2099-01-01', '--place', 'p'); self.assertEqual(r.returncode, 1)
            r = self.go(d, 'target', '--text', 'a named chain lists it', '--date', '2020-01-01', '--place', 'p'); self.assertEqual(r.returncode, 1)
            self.assertFalse(os.path.exists(os.path.join(run, 'target.json')))
            r = self.go(d, 'target', '--text', 'a named chain lists it', '--date', '2099-01-01', '--place', 'p', '--ai-drafted'); self.assertEqual(r.returncode, 0, r.stdout)
            self.assertTrue(json.loads(r.stdout)['ai_drafted'])
            r = self.go(d, 'target', '--text', 'a named chain lists it', '--date', '2099-01-01', '--place', 'p'); self.assertEqual(r.returncode, 1)
            for bad in ('-5', '101', 'nan', 'inf', '-inf'):
                r = self.go(d, 'lean', '--percent', bad, '--reason', 'r'); self.assertNotEqual(r.returncode, 0, bad); self.assertIn('error', json.loads(r.stdout))
            r = self.go(d, 'lean', '--percent', '--5', '--reason', 'r'); self.assertNotEqual(r.returncode, 0)
            r = self.go(d, 'lean', '--percent', '30', '--reason', 'r'); self.assertEqual(r.returncode, 0, r.stdout)
            r = self.go(d, 'lean', '--percent', '40', '--reason', 'again'); self.assertEqual(len(json.loads(r.stdout)['history']), 1)
            with open(os.path.join(run, 'a.json'), 'w') as f: json.dump(dict(findings=[dict(person='p', kills='k', ask='a')]), f)
            self.assertEqual(self.go(d, 'attack', '--file', 'a.json').returncode, 0)
            self.assertEqual(self.go(d, 'attack', '--file', 'missing.json').returncode, 1)
            self.assertEqual(self.go(d, 'result', '--run', os.path.basename(run), '--happened', 'yes').returncode, 2)  # the command is gone (decision 0011)
            self.assertEqual(self.go(d, 'report').returncode, 2)
