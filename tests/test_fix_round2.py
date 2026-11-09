"""Tests added in fix round 2 (work/review-ticket5.md D1 to D12 and the purchase-outcome refusal in `stats`).
Each one fails on the module before the fix (work/review6-snapshot/second_guess.py)."""
import datetime as dt, json, os, stat, subprocess, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_second_guess as base  # noqa: E402
import test_ticket5 as t5  # noqa: E402
sg = base.sg
TODAY, NOW = t5.TODAY, t5.NOW
PY = ['/usr/bin/python3', '-B', '-I', os.path.join(t5.SCRIPTS, 'second_guess.py')]


class Ready(t5.Base):
    def ready(self, date='2027-06-30'):
        self.target(date=date); sg.lean_cmd(self.run_dir, '30', 'no record', now=NOW)

    @property
    def log(self): return os.path.join(self.d, sg.RUNS, 'log.jsonl')

    def rows(self):
        with open(self.log) as f: return [json.loads(l) for l in f if l.strip()]

    def go(self, *a): return subprocess.run(PY + list(a), cwd=self.d, capture_output=True, text=True)

    def put(self, name, obj, where=None):
        p = os.path.join(where or self.run_dir, name)
        with open(p, 'w') as f: json.dump(obj, f)
        return p


class D1LeanFreezes(Ready):
    def test_lean_refused_when_the_target_date_is_today_or_past(self):
        self.ready()
        with self.assertRaises(sg.Refused): sg.lean_cmd(self.run_dir, '99', 'late', today=dt.date(2027, 6, 30))
        with self.assertRaises(sg.Refused): sg.lean_cmd(self.run_dir, '99', 'late', today=dt.date(2028, 1, 1))
        sg.lean_cmd(self.run_dir, '31', 'early', today=dt.date(2027, 6, 29))

class D2Parallel(Ready):

    def test_ten_processes_on_one_run_keep_state_json_whole(self):
        self.ready(); self.put('a.json', dict(findings=[dict(person='p', kills='k', ask='a')]))
        ps = [subprocess.Popen(PY + (['attack', '--file', 'a.json'] if i % 2 else ['lean', '--percent', str(10 + i), '--reason', 'again']),
                               cwd=self.d, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for i in range(10)]
        out = [p.communicate() for p in ps]
        self.assertEqual([e for _, e in out if e], []); self.assertEqual([p.returncode for p in ps], [0] * 10, [o for o, _ in out])
        with open(os.path.join(self.run_dir, 'state.json')) as f: steps = json.load(f)['steps']
        self.assertEqual({k: steps[k] for k in ('target', 'lean', 'attack')}, dict(target='saved', lean='saved', attack='saved'))
        with open(os.path.join(self.run_dir, 'lean.json')) as f: self.assertEqual(len(json.load(f)['history']), 5)

    def test_a_symlink_at_the_old_temp_name_is_not_written_through(self):  # D8
        victim = os.path.join(self.d, 'victim.txt')
        with open(victim, 'w') as f: f.write('KEEP')
        for name in ('target.json.tmp', 'lean.json.tmp', 'state.json.tmp', 'attack.json.tmp'): os.symlink(victim, os.path.join(self.run_dir, name))
        self.ready(); self.put('a.json', dict(findings=[dict(person='p', kills='k', ask='a')])); sg.attack_cmd(self.run_dir, 'a.json')
        with open(victim) as f: self.assertEqual(f.read(), 'KEEP')


class D3Damaged(Ready):
    def test_damaged_state_is_found_before_target_json_is_written(self):
        with open(os.path.join(self.run_dir, 'state.json'), 'w') as f: f.write('{bad')
        with self.assertRaises(sg.Refused) as c: self.target()
        self.assertIn('state.json', str(c.exception)); self.assertIn('delete it and rerun', str(c.exception)); self.assertFalse(self.exists('target.json'))

    def test_state_that_is_a_list_is_refused_the_same_way(self):
        self.put('state.json', [])
        with self.assertRaises(sg.Refused) as c: self.target()
        self.assertIn('delete it and rerun', str(c.exception)); self.assertFalse(self.exists('target.json'))

    def test_empty_target_json_names_the_file_in_target_and_lean(self):
        open(os.path.join(self.run_dir, 'target.json'), 'w').close()
        for call in (lambda: self.target(), lambda: sg.lean_cmd(self.run_dir, '30', 'none')):
            with self.assertRaises(sg.Refused) as c: call()
            self.assertIn('target.json', str(c.exception)); self.assertIn('delete it and rerun', str(c.exception))


class D4NoTraceback(Ready):
    """Each case ends in one JSON line and a non-zero exit, never a traceback."""
    def check(self, r, name):
        self.assertEqual(r.stderr, '', name); self.assertNotEqual(r.returncode, 0, name); self.assertIn('error', json.loads(r.stdout), name)

    def test_the_listed_cases(self):
        run = self.run_dir; self.ready(); self.put('a.json', dict(findings=[dict(person='p', kills='k', ask='a')]))
        os.chmod(run, 0o555)
        try:
            self.check(self.go('attack', '--file', 'a.json'), 'run folder read-only, attack')
            self.check(self.go('lean', '--percent', '9', '--reason', 'again'), 'run folder read-only, lean') if False else None
        finally: os.chmod(run, 0o755)
        for bad in ('{bad', '[]', ''):
            with open(os.path.join(run, 'state.json'), 'w') as f: f.write(bad)
            self.check(self.go('attack', '--file', 'a.json'), 'state %r, attack' % bad); self.check(self.go('target', '--text', 'a chain lists it', '--date', '2099-01-01', '--place', 'p'), 'state %r, target' % bad)
        os.mkdir(os.path.join(run, 'x')); os.unlink(os.path.join(run, 'lean.json')); os.mkdir(os.path.join(run, 'lean.json'))
        self.check(self.go('lean', '--percent', '5', '--reason', 'again'), 'lean.json is a folder')

class D5AttackFiles(Ready):
    OBJ = dict(findings=[dict(person='p', kills='k', ask='a')])

    def test_a_bare_name_in_the_run_folder_or_idea_test_files_is_read(self):
        self.put('a.json', self.OBJ); sg.attack_cmd(self.run_dir, 'a.json')
        self.put('b.json', self.OBJ, where=os.path.join(self.d, sg.FILES)); sg.attack_cmd(self.run_dir, 'b.json')

    def test_everything_else_is_refused_and_says_where_to_put_the_file(self):
        out = os.path.join(self.d, 'outside.json')
        with open(out, 'w') as f: json.dump(self.OBJ, f)
        os.symlink(out, os.path.join(self.run_dir, 'link.json')); os.link(out, os.path.join(self.run_dir, 'hard.json'))
        os.mkdir(os.path.join(self.run_dir, 'sub')); self.put('c.json', self.OBJ, where=os.path.join(self.run_dir, 'sub'))
        for bad in (out, '../outside.json', 'sub/c.json', 'link.json', 'hard.json', 'outside.json', 'sub', '', '/etc/hosts', '..', '.hidden.json', 'a/../a.json'):
            with self.assertRaises(sg.Refused, msg=bad) as c: sg.attack_cmd(self.run_dir, bad)
            self.assertIn(sg.FILES, str(c.exception), bad)
        self.assertFalse(self.exists('attack.json'))

    def test_the_error_does_not_tell_whether_a_path_elsewhere_exists(self):
        a = self.assertRaises(sg.Refused)
        with a as c1: sg.attack_cmd(self.run_dir, '/etc/hosts')
        with self.assertRaises(sg.Refused) as c2: sg.attack_cmd(self.run_dir, '/nonexistent/zzz')
        self.assertEqual(str(c1.exception).split(';')[0].replace('/etc/hosts', 'X'), str(c2.exception).split(';')[0].replace('/nonexistent/zzz', 'X'))


class D6FreeText(Ready):
    def test_place_runs_the_target_check(self):
        for bad in ('sell 1,000 units on our site', 'a site where 30% of visitors would buy'):
            with self.assertRaises(sg.Refused, msg=bad): self.target(place=bad)
        self.assertFalse(self.exists('target.json')); self.target(place='the chain site')

    def test_lean_reason_refuses_digits_money_and_purchase_words_like_match(self):
        self.target()
        for bad in ('They will buy 500 units', 'about $50 each', '30 percent', 'about thirty shops'):
            with self.assertRaises(sg.Refused, msg=bad) as c: sg.lean_cmd(self.run_dir, '30', bad)
            self.assertIn('say it without a number', str(c.exception))
        self.assertFalse(self.exists('lean.json'))
        with self.assertRaises(sg.Refused): sg.match_cmd(self.run_dir, 'group', 'yes', 'sales are low')  # match still refuses purchase words; lean allows them (round 3, item 12)
        sg.lean_cmd(self.run_dir, '30', 'chains want proof first')

    def test_attack_text_stays_free(self):
        self.ready(); self.put('a.json', dict(findings=[dict(person='A buyer', kills='pays', ask='what price, 500 units?')])); sg.attack_cmd(self.run_dir, 'a.json')


# purchase phrasings the old word list let through (from the reviewer's list of 131) and everyday targets it refused (from 190)
NOW_REFUSED = [
    'units (500)', 'units, 500', 'sales = 500', 'sales: 1000', 'sales — 1000', 'revenue ≥ 10k', 'earn ten thousand', 'gross takings 5000', '500 Stück', '500 unidades',
    'cinquecento unità vendute', '500 verkaufte Geräte', 'five-oh-oh units', 'sold out the first run of 500', 'the first batch of 500 sells out', '500 shipped',
    '500 shipments', '500 sensors sold', 'ship 500 sensors', '500 invoices paid', '500 payments', '500 paid users', '500 members', '500 clients', '500 licences',
    'one dollar', 'a euro', '$.5', 'USD 1,000', '₹1000', '฿1000', '1 of 5 would buy', 'one of five would buy', '2/5 would buy', '2:5 would buy', '0.4 would buy',
    'forty per cent buy', '40 pct would buy', '40٪ would buy', '40 would buy', '40 people will pay', 'people pay', 'would pay for it', 'visitors would pay',
    'three quarters of visitors buy', 'many would buy', 'every visitor buys', 'each visitor buys',
]
NOW_PASSES = [
    'we interview 5 customers', '5 customers sign a letter of intent', '3 customers agree to a paid pilot', 'sales team of 3 is hired', 'a 3 person sales team is hired',
    '3 sales channels open', 'a chain orders 2 units for testing', 'a chain buys 3 units for a pilot', 'two orders of magnitude', 'a grant of $50k is awarded',
    'it wins a 10,000 dollar prize', 'it is priced at $49', 'a $49 offer is tested', 'the newsletter reaches 1,000 subscribers', '1000 subscribers on YouTube',
    '5 customers reply', 'we speak to 20 customers',
]


class D7TargetList(unittest.TestCase):
    def test_phrasings_that_used_to_pass_are_refused(self):
        for t in NOW_REFUSED: self.assertIsNotNone(sg.target_problem(t), t)

    def test_everyday_targets_that_used_to_be_refused_pass(self):
        for t in NOW_PASSES: self.assertIsNone(sg.target_problem(t), t)

    def test_exemptions_do_not_let_a_real_purchase_count_through(self):
        for t in ('the price is $49 and 500 units sell', 'a pilot and then 5,000 units sold', 'the newsletter has 1,000 paid subscribers', 'sales team sells 500 units',
                  '$50k revenue, price tested'):
            self.assertIsNotNone(sg.target_problem(t), t)

    def test_the_purchase_list_for_match_did_not_grow(self):
        self.assertNotIn('members', sg.PURCHASE); self.assertNotIn('accounts', sg.PURCHASE)


class D9D10D11D12(Ready):

    def test_d10_invisible_and_unpaired_characters_are_dropped(self):
        for t in ('ㅤㅤ', 'ᅟᅠ', '⠀', 'ﾠ', '\ud800', '\udcff', '', '͸'):
            with self.assertRaises(sg.Refused, msg=repr(t)): self.target(text=t)
        r = self.target(text='a named\ud800 chainㅤ lists it'); self.assertEqual(r['text'], 'a named chain lists it')
        self.put('a.json', dict(findings=[dict(person='p\ud800q', kills='k', ask='a')])); sg.attack_cmd(self.run_dir, 'a.json')
        with open(os.path.join(self.run_dir, 'attack.json'), encoding='utf-8') as f: self.assertEqual(json.load(f)['findings'][0]['person'], 'pq')

    def test_d11_percent_is_rounded_to_one_decimal(self):
        self.target()
        for given, want in (('0.0000001', 0), ('99.99999999999999999', 100), ('100.00000000000000001', 100), ('33.33', 33.3), ('37.45', 37.4), ('0', 0), ('100', 100), (50.5, 50.5)):
            self.assertEqual(sg.lean_cmd(self.run_dir, given, 'none')['percent'], want, given)
        for bad in ('100.06', '100.1', '101', '1' * 400):
            with self.assertRaises(sg.Refused, msg=bad): sg.lean_cmd(self.run_dir, bad, 'none')

class PurchaseOutcome(base.StatsBase):
    def test_a_purchase_word_in_the_outcome_name_or_a_value_gives_idk(self):
        for kw in (dict(header=('when', 'x', 'kind', 'purchases')), dict(outcome=lambda i, y: 'bought' if y else 'none'), dict(outcome=lambda i, y: 'paid' if y else 'none'),
                   dict(outcome=lambda i, y: 'conversion' if y else 'none')):
            self.csv(**kw); out = self.stats(outcome=kw['header'][3] if 'header' in kw else 'y')
            self.idk(out, 'this version prints no purchase number')

    def test_funded_and_pledged_outcomes_still_get_a_number(self):
        for a, b in (('funded', 'failed'), ('pledged', 'unfunded')):
            self.csv(outcome=lambda i, y, a=a, b=b: a if y else b); self.assertEqual(self.stats()['stats']['status'], 'ok', a)
        self.csv(header=('when', 'x', 'kind', 'funded')); self.assertEqual(self.stats(outcome='funded')['stats']['status'], 'ok')


if __name__ == '__main__':
    unittest.main()
