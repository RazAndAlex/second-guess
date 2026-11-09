"""Tests for ticket 13: the assumption count (decision 0012). Written before the code."""
import json, os, re, subprocess, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_report as tr  # noqa: E402
sg = tr.sg
GOOD, QUOTE, SCRIPTS = tr.GOOD, tr.QUOTE, tr.SCRIPTS
LIST = ['Some gardeners have no way to water plants while away.', 'They already spend effort on a fix today.', 'A shop chain would list a new tool.']
SENTENCE = "Which assumption a card speaks to is the AI's reading. The code counts it and does not judge it."


class Base13(tr.Base):
    def assume(self, items=None, name='as.json'):
        self.write(name, dict(assumptions=LIST if items is None else items)); return sg.assumptions_cmd(self.run_dir, name)

    def full(self, cards, pages, items=None):
        self.earlier(cards, pages)
        if items is not False: self.assume(items)


class Command(Base13):
    def test_saves_the_list_and_prints_it(self):
        out = self.assume(); self.assertEqual(out['assumptions'], LIST)
        self.assertEqual(sg.read_state(self.run_dir)['steps']['assumptions'], 'saved')

    def test_one_to_ten_items(self):
        for bad in ([], ['x'] * 11): 
            with self.assertRaises(sg.Refused) as e: self.assume(bad)
            self.assertIn('1 to 10', str(e.exception))
        self.assume(['a'] * 10)

    def test_items_must_be_short_text(self):
        for bad in ([5], ['x' * 300], ['  ']):
            with self.assertRaises(sg.Refused): self.assume(bad)

    def test_purchase_number_rule_as_for_the_attack(self):
        for bad in ('Half of them would buy it.', 'They would pay $20 for it.', '40% of owners would buy it.'):
            with self.assertRaises(sg.Refused) as e: self.assume([bad])
            self.assertIn('this version prints none', str(e.exception))

    def test_the_kinds_the_skill_names_pass(self):
        self.assume(['Someone has the problem.', 'They pay for a fix today.', 'They would switch to a new one.', 'There is a route to reach them.', 'It can be built at this cost.'])

    def test_file_is_read_like_attack(self):
        for name in ('../a.json', '/etc/passwd', 'sub/a.json', 'missing.json'):
            with self.assertRaises(sg.Refused): sg.assumptions_cmd(self.run_dir, name)
        with open(os.path.join(self.run_dir, 'bad.json'), 'w') as f: f.write('{nope')
        with self.assertRaises(sg.Refused) as e: sg.assumptions_cmd(self.run_dir, 'bad.json')
        self.assertIn('not valid JSON', str(e.exception))
        self.write('wrong.json', dict(items=['a']))
        with self.assertRaises(sg.Refused) as e: sg.assumptions_cmd(self.run_dir, 'wrong.json')
        self.assertIn('assumptions', str(e.exception))

    def test_second_call_replaces_until_a_report_exists(self):
        self.assume(); out = self.assume(['Only one now.']); self.assertEqual(out['assumptions'], ['Only one now.'])
        self.earlier(); self.report()
        with self.assertRaises(sg.Refused) as e: self.assume()
        self.assertIn('report', str(e.exception)); self.assertIn('new run', str(e.exception))
        with open(os.path.join(self.run_dir, 'assumptions.json')) as f: self.assertEqual(json.load(f)['assumptions'], ['Only one now.'])

    def test_none_needs_a_reason_without_a_number(self):
        with self.assertRaises(sg.Refused): sg.assumptions_cmd(self.run_dir, none=True, reason='')
        with self.assertRaises(sg.Refused): sg.assumptions_cmd(self.run_dir, none=True, reason='about 5 of them')
        with self.assertRaises(sg.Refused): sg.assumptions_cmd(self.run_dir, file='a.json', none=True, reason='x')
        with self.assertRaises(sg.Refused): sg.assumptions_cmd(self.run_dir)
        out = sg.assumptions_cmd(self.run_dir, none=True, reason='a pure data question'); self.assertEqual(out['assumptions'], [])

    def test_a_list_replaces_none_and_back(self):
        sg.assumptions_cmd(self.run_dir, none=True, reason='nothing to list'); self.assume()
        with open(os.path.join(self.run_dir, 'assumptions.json')) as f: self.assertNotIn('none', json.load(f))


class CardField(Base13):
    def test_schema_allows_the_seventh_field(self):
        item = sg.load_schema()['properties']['cards']['items']
        self.assertEqual(sg.validate(dict(GOOD), item, ''), [])
        for ok in (1, 10): self.assertEqual(sg.validate(dict(GOOD, assumption=ok), item, ''), [])
        for bad in (0, 11, -1, '1', 1.5, True, None): self.assertTrue(sg.validate(dict(GOOD, assumption=bad), item, ''), bad)
        self.assertTrue(sg.validate(dict(GOOD, extra=1), item, ''))

    def test_card_with_the_field_is_checked_and_kept(self):
        out = self.cards([dict(GOOD, assumption=2)], {0: b'<p>' + QUOTE.encode() + b'</p>'}); self.assertEqual(out['results'][0]['result'], 'pass')
        with open(os.path.join(self.run_dir, 'cards.json')) as f: self.assertEqual(json.load(f)['cards'][0]['card']['assumption'], 2)

    def test_a_bad_field_fails_the_card_with_a_plain_reason(self):
        out = self.cards([dict(GOOD, assumption='one')], {0: b'<p>' + QUOTE.encode() + b'</p>'})
        self.assertEqual(out['results'][0]['result'], 'fail'); self.assertIn('assumption', out['results'][0]['detail'])

    def test_changing_the_field_does_not_force_a_recheck(self):
        page = {0: b'<p>' + QUOTE.encode() + b'</p>'}
        self.cards([dict(GOOD, assumption=1)], page)
        out = sg.check_cards(self.write('c2.json', dict(cards=[dict(GOOD, assumption=3)]), self.d), self.run_dir, raw=tr.no_network)
        self.assertEqual(out['results'][0]['result'], 'pass')
        with open(os.path.join(self.run_dir, 'cards.json')) as f: d = json.load(f)['cards']
        self.assertEqual(len(d), 1); self.assertEqual(d[0]['card']['assumption'], 3)


class Count(Base13):
    PAGE = {0: b'<p>' + QUOTE.encode() + b'</p>'}

    def test_one_of_three_and_the_links(self):
        self.full([dict(GOOD, assumption=1)], self.PAGE); out = self.report()
        pg = self.page(); self.assertIn('<b>1 of 3</b> have a checked source', pg); self.assertIn('<div data-thing="5"><p class="l">Assumptions</p><p class="v"><b>1 of 3</b> have a checked source</p><p class="w">Counted by code</p></div>\n</div>\n</div>', pg)
        self.assertIn('1 of 3 assumptions have a checked source.', out['first_lines'])
        txt = ' '.join(tr.parse(pg).text)
        self.assertEqual(txt.count('no checked source'), 4)  # 2 rows: on the closed row, and again inside it; self.assertIn('checked source', txt)
        self.assertIn('example.com/grocery-study', pg)
        for a in LIST: self.assertIn(a.rstrip('.'), txt)
        self.assertEqual(sorted(out), ['first_lines', 'path'])

    def test_the_fixed_sentence_stands_under_the_list(self):
        self.full([dict(GOOD, assumption=1)], self.PAGE); self.report()
        txt = ' '.join(''.join(tr.parse(self.page()).text).split()); self.assertIn(SENTENCE, txt)
        self.assertLess(txt.index('no checked source'), txt.index(SENTENCE))

    def test_the_count_sits_in_its_own_section_apart_from_the_lean(self):
        self.full([dict(GOOD, assumption=1)], self.PAGE); self.report(); pg = self.page()
        sec = [s for s in pg.split('<section') if '<h2>1 of 3 <span' in s]; self.assertEqual(len(sec), 1)
        self.assertNotIn('lean', sec[0].lower().replace('<style', '')); self.assertNotIn('30%', sec[0])  # the lean; a quote in an open row may hold its own percent
        self.assertIn('coverage', sec[0])

    def test_two_cards_on_one_assumption_list_both_and_count_once(self):
        q2 = 'A second long sentence about gardeners and their watering habits is here.'
        self.full([dict(GOOD, assumption=2), dict(GOOD, quote=q2, number='second', url='https://example.com/two', assumption=2)], {0: self.PAGE[0], 1: b'<p>' + q2.encode() + b'</p>'}); self.report()
        pg = self.page(); self.assertIn('<b>1 of 3</b> have a checked source', pg); self.assertIn('example.com/two', pg); self.assertIn('example.com/grocery-study', pg)

    def test_failed_unchecked_and_dropped_cards_do_not_count(self):
        self.full([dict(tr.MISSING, assumption=1), dict(tr.OPENQ, assumption=2), dict(GOOD, assumption=3)], {0: b'<p>' + QUOTE.encode() + b'</p>', 2: self.PAGE[0], 1: b'\x1f\x8bnot gzip'})
        sg.drop_card_cmd(self.run_dir, index=2, reason='the page says something else'); self.report(['Plain words only.'])
        self.assertIn('<b>0 of 3</b> have a checked source', self.page())

    def test_unlisted_number_is_refused_plainly(self):
        self.full([dict(GOOD, assumption=4)], self.PAGE)
        msg = self.assertRefusedClean(holds=['assumption 4', 'card'])
        self.assertIn('3', msg)

    def test_a_failed_card_naming_nothing_listed_is_refused_too(self):
        self.full([dict(tr.MISSING, assumption=9)], {0: b'<p>' + QUOTE.encode() + b'</p>'}); self.assertRefusedClean(holds=['assumption 9'])

    def test_cards_with_no_field_still_report_and_count_zero(self):
        self.full([GOOD], self.PAGE); self.report(); self.assertIn('<b>0 of 3</b> have a checked source', self.page())

    def test_assumption_text_goes_through_the_number_check(self):
        self.full([GOOD], self.PAGE, items=['About 1234 gardeners have the problem.'])
        self.assertRefusedClean(holds=['1234'])

    def test_assumption_text_is_escaped(self):
        self.full([GOOD], self.PAGE, items=['A <script>x</script> idea.']); self.report(); self.assertNotIn('<script>x', self.page())

    def test_none_on_purpose_shows_the_reason_and_no_count(self):
        self.earlier(); sg.assumptions_cmd(self.run_dir, none=True, reason='a pure data question'); self.report()
        pg = self.page(); self.assertNotIn('assumptions have a checked source', pg); self.assertIn('a pure data question', pg)

    def test_none_with_a_card_that_names_one_is_refused(self):
        self.earlier([dict(GOOD, assumption=1)], self.PAGE); sg.assumptions_cmd(self.run_dir, none=True, reason='nothing'); self.assertRefusedClean(holds=['assumption 1'])

    def test_the_cli_refuses_with_no_list_and_names_the_command(self):
        self.earlier()
        with self.assertRaises(sg.Refused) as e: sg.report_cmd(self.run_dir, self.write('t.json', tr.draft(self.run_dir, name='x', paragraphs=tr.PARAS)) and 't.json', need_list=True)
        self.assertIn('assumptions', str(e.exception)); self.assertIn('--none', str(e.exception))
        self.assertFalse(os.path.exists(self.page_path))


class Cli13(unittest.TestCase):
    go = tr.Cli.go

    def test_commands_exist_and_report_refuses_then_counts(self):
        with tempfile.TemporaryDirectory() as d:
            run = json.loads(self.go(d, 'start', '--idea', 'Smart Garden', '--model', 'm1').stdout)['run']
            with open(os.path.join(d, 'c.json'), 'w') as f: json.dump(dict(cards=[dict(GOOD, assumption=1)]), f)
            with open(os.path.join(d, 'p.txt'), 'w') as f: f.write(QUOTE)
            self.assertEqual(self.go(d, 'check-cards', 'c.json', '--page-file', '0', 'p.txt').returncode, 0)
            self.go(d, 'stats', '--no-dataset'); self.go(d, 'target', '--text', 'a chain lists it', '--date', '2099-06-30', '--place', 'site'); self.go(d, 'lean', '--percent', '12.5', '--reason', 'no record yet')
            with open(os.path.join(run, 'a.json'), 'w') as f: json.dump(dict(findings=tr.ATTACK), f)
            self.go(d, 'attack', '--file', 'a.json')
            with open(os.path.join(run, 't.json'), 'w') as f: json.dump(tr.draft(run, name='Smart Garden', paragraphs=tr.PARAS), f)
            r = self.go(d, 'report', '--file', 't.json'); self.assertEqual(r.returncode, 1); self.assertIn('assumptions', json.loads(r.stdout)['error'])
            with open(os.path.join(run, 'as.json'), 'w') as f: json.dump(dict(assumptions=LIST), f)
            r = self.go(d, 'assumptions', '--file', 'as.json'); self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            with open(os.path.join(run, 't.json'), 'w') as f: json.dump(tr.draft(run, name='Smart Garden', paragraphs=tr.PARAS), f)
            r = self.go(d, 'report', '--file', 't.json'); self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            with open(os.path.join(run, 'report.html')) as f: self.assertIn('<b>1 of 3</b> have a checked source', f.read())
            r = self.go(d, 'assumptions', '--file', 'as.json'); self.assertEqual(r.returncode, 1)


class ArchiveDetail(unittest.TestCase):
    """Fix round 8 rerun: a live 429 plus an archive that never answered must not read as a bare 'http 429'."""
    CARD = dict(GOOD, url='https://example.com/page')

    def run_check(self, cdx):
        get = lambda u: cdx if 'web.archive.org' in u else (429, b'', u, '')
        return sg.check(self.CARD, get, probe=lambda: None)

    def test_archive_timeout_is_named(self):
        s, d = self.run_check((0, b'', 'u', 'URLError: <urlopen error timed out>'))
        self.assertEqual(s, 'throttled'); self.assertIn('http 429', d); self.assertIn('archive', d); self.assertIn('timed out', d); self.assertIn('not read', d)

    def test_archive_429_is_named(self):
        s, d = self.run_check((429, b'', 'u', ''))
        self.assertEqual(s, 'throttled'); self.assertIn('archive index http 429', d); self.assertIn('not read', d)
