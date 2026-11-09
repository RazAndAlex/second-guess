"""The picked report page: the short lines, the font and every state of the design."""
import json, os, re, unittest
from unittest import mock

import test_ticket13 as t13
import test_report as tr
from short_lines import short_for
sg = tr.sg
GOOD = tr.GOOD; PAGE = {0: b'<p>' + tr.QUOTE.encode() + b'</p>'}
LIST = t13.LIST


class Short(t13.Base13):
    def setUp(self):
        super().setUp(); self.full([dict(GOOD, assumption=1)], PAGE)

    def go(self, **change):
        sh = short_for(self.run_dir); sh.update(change)
        self.write('t.json', dict(name='x', paragraphs=['Plain.'], short=sh))
        return sg.report_cmd(self.run_dir, 't.json', need_list=True)

    def refused(self, *holds, **change):
        with self.assertRaises(sg.Refused) as e: self.go(**change)
        for h in holds: self.assertIn(h, str(e.exception))
        self.assertFalse(os.path.exists(self.page_path))

    def test_one_newline_is_a_break_and_a_second_refuses(self):
        self.refused('2 newlines', target='a\nb\nc')
        self.go(target='A chain\nlists it'); p = self.page()
        self.assertIn('chance that a chain<br> lists it<br> by 30 Jun 2027', p); self.assertNotIn('class="bal"', p)

    def test_no_newline_gets_balance(self):
        self.go(target='A chain lists it'); self.assertIn('chance that <span class="bal">a chain lists it</span> by 30 Jun 2027', self.page())

    def test_lowercase_only_listed_leading_words(self):
        low = sg._lower_lead
        self.assertEqual(low('At least one chain lists it'), 'at least one chain lists it'); self.assertEqual(low('A shop chain'), 'a shop chain')
        self.assertEqual(low('Esselunga, Coop or Conad'), 'Esselunga, Coop or Conad'); self.assertEqual(low('Atlas lists it'), 'Atlas lists it')
        self.assertEqual(low('The Coop'), 'the Coop'); self.assertEqual(low('A'), 'a'); self.assertEqual(low(''), '')
        self.go(target='At least one chain\nlists it'); self.assertIn('chance that at least one chain<br> lists it<br> by 30 Jun 2027', self.page())
        self.go(target='Esselunga lists it'); self.assertIn('chance that <span class="bal">Esselunga lists it</span>', self.page())
        self.assertEqual(low('AT least one'), 'AT least one')
        self.go(target='Esselunga lists it\nAt the Coop'); self.assertIn('chance that Esselunga lists it<br> At the Coop<br>', self.page())

    def test_lowercase_changes_only_the_printed_short_target(self):
        out = self.go(target='At least one chain lists it'); self.assertIn('30% chance that at least one shop chain lists it by 30 June 2027.', out['first_lines'][2]); self.assertNotIn('At least one chain', out['first_lines'][2])  # the long saved target is untouched by the short line

    def test_short_date_has_no_leading_zero_and_a_three_letter_month(self):
        self.assertEqual(sg._short_date('2027-11-05'), 'by 5 Nov 2027'); self.assertEqual(sg._short_date('2027-01-31'), 'by 31 Jan 2027')
        self.go(); p = self.page(); self.assertIn('by 30 Jun 2027', p); self.assertIn('by 30 June 2027.', p)

    def test_wrong_counts_name_both(self):
        self.refused('2 lines', '3 assumptions', assumptions=['one', 'two'])
        self.refused('1 ', '2 ', people=['a'])

    def test_every_word_limit_refuses_one_over_and_takes_the_limit(self):
        words = lambda n: ' '.join(['word'] * n)
        for key, n in (('target', 12), ('reason', 14), ('check_at', 8)):
            self.refused('%d words' % (n + 1), 'limit is %d' % n, **{key: words(n + 1)})
            self.go(**{key: words(n)}); os.unlink(self.page_path)
        self.refused('9 words', 'limit is 8', assumptions=[words(9), 'b', 'c'])
        self.go(assumptions=[words(8), 'b', 'c']); os.unlink(self.page_path)
        self.refused('6 words', 'limit is 5', people=[words(6), 'a'])
        self.go(people=[words(5), 'a'])

    def test_target_and_reason_have_a_character_limit_and_the_newline_counts_one(self):
        for key, n in (('target', 90), ('reason', 100)):
            ok = ('abcdefgh ' * 12)[:n]; self.assertEqual(len(ok), n)   # at most 12 words, so only the character limit can refuse
            self.refused('%d characters' % (n + 1), 'limit is %d' % n, **{key: ok + 'x'})
            self.go(**{key: ok}); os.unlink(self.page_path)
        two = 'abcdefgh ' * 4 + 'abcdefgh\n' + 'abcdefgh ' * 4 + 'abcdefghi'   # 90 characters with the newline counted once
        self.assertEqual(len(two), 90); self.go(target=two); os.unlink(self.page_path)
        self.refused('91 characters', 'limit is 90', target=two + 'x')

    def test_a_long_host_list_prints_three_and_a_count(self):
        h = lambda n: [dict(host='h%d.example.com' % i, url='https://h%d.example.com/p' % i) for i in range(n)]
        for n, want in ((3, 'h0.example.com, h1.example.com, h2.example.com'), (4, 'h0.example.com, h1.example.com, h2.example.com and 1 more'), (14, 'h0.example.com, h1.example.com, h2.example.com and 11 more')):
            self.assertEqual(sg._sites(h(n)), want)
        self.assertEqual(sg._sites(h(2) + h(2)), 'h0.example.com, h1.example.com')   # a repeated host counts once

    def test_a_number_in_each_field_refuses(self):
        for change in (dict(target='Lists it in 7777 shops'), dict(reason='Only 7777 shops'), dict(check_at='Page 7777 of the site'), dict(assumptions=['In 7777 shops', 'b', 'c']),
                       dict(people=['Buyer 7777', 'a'])):
            self.refused('7777', **change)

    def test_a_number_in_the_saved_target_text_is_allowed_only_for_target_and_check_at(self):
        sg.save_json(os.path.join(self.run_dir, 'target.json'), dict(json.load(open(os.path.join(self.run_dir, 'target.json'))), text='a chain lists it in 8888 shops'))
        self.refused('8888', assumptions=['In 8888 shops', 'b', 'c'])
        self.go(target='In 8888 shops', check_at='The 8888 shops'); self.assertIn('In 8888 shops', self.page())

    def test_reason_holds_to_the_lean_reason_rule(self):
        self.refused('reason', reason='Two chains said no')  # any number word, the same rule as lean --reason

    def test_each_field_is_escaped(self):
        evil = '<script>alert</script>&"'
        self.go(target=evil, reason=evil, check_at=evil, assumptions=[evil, 'b', 'c'], people=[evil, 'a']); p = self.page()
        self.assertNotIn('<script', p); self.assertEqual(tr.parse(p).tags.count('script'), 0)
        self.assertEqual(''.join(tr.parse(p).text).count('<script>alert</script>&"'), 5)  # target, reason, check_at, assumption, person

    def test_missing_short_and_wrong_shapes_refuse(self):
        self.write('t.json', dict(name='x', paragraphs=['Plain.']))
        with self.assertRaises(sg.Refused) as e: sg.report_cmd(self.run_dir, 't.json', need_list=True)
        self.assertIn('short', str(e.exception))
        for bad in (dict(target=1), dict(assumptions='a'), dict(people=[dict(person='a', line='b'), 'a']), dict(people=['a', 3])): self.refused(**bad)
        sh = short_for(self.run_dir); del sh['reason']; self.write('t.json', dict(name='x', paragraphs=['Plain.'], short=sh))
        with self.assertRaises(sg.Refused): sg.report_cmd(self.run_dir, 't.json', need_list=True)

    def test_the_program_never_prints_a_short_line_in_place_of_a_long_one(self):
        self.go(assumptions=['First short', 'Second short', 'Third short']); p = self.page()
        for a in LIST: self.assertIn('<p class="long">%s</p>' % a, p)
        self.assertIn('<p class="tgt">at least one shop chain lists it by 30 June 2027.</p>', p); self.assertIn('Check it at: the chain&#x27;s own website', p)
        for f in tr.ATTACK: self.assertIn(f['kills'], p); self.assertIn(f['ask'], p)

    def test_the_font_travels_in_the_page_and_a_missing_file_still_builds(self):
        self.go(); p = self.page(); self.assertIn('src:url(data:font/woff2;base64,', p); self.assertIn('font-display:block', p); os.unlink(self.page_path)
        with mock.patch.object(sg, 'FONT_PATH', os.path.join(self.d, 'gone.woff2')): self.go()
        p = self.page(); self.assertNotIn('@font-face', p); self.assertIn('system-ui', p); self.assertIn('<h1>', p)

    def test_the_font_and_its_license_ship(self):
        self.assertTrue(os.path.isfile(sg.FONT_PATH)); self.assertTrue(os.path.isfile(os.path.join(os.path.dirname(sg.FONT_PATH), 'OFL.txt')))


class States(t13.Base13):
    """Each row of the design's state table."""
    def build(self, need=True, **change):
        sh = short_for(self.run_dir); sh.update(change); self.write('t.json', dict(name='x', paragraphs=['Plain.'], short=sh))
        sg.report_cmd(self.run_dir, 't.json', need_list=need); return self.page()

    def test_statistics_found_a_number(self):
        self.full([GOOD], PAGE); s = os.path.join(self.run_dir, 'statistics.json')
        line = 'Dataset group: tools. Error score 0.1 against 0.2; lower is better. It says nothing about buying.'
        sg.save_json(s, dict(counts=True, first_line=line, quotable=dict(brier_formula=0.1, brier_average=0.2)))
        p = self.build(); self.assertIn('<p class="l">Statistics</p><p class="v"><b>The formula beat the plain average.</b></p><p class="w">Computed by code</p>', p); self.assertIn('<p>Statistics: %s</p>' % line, p)

    def test_saved_with_none(self):
        self.earlier([GOOD], PAGE); sg.assumptions_cmd(self.run_dir, none=True, reason='It rests on nothing new.'); p = self.build(assumptions=[])
        sent = 'The AI listed no assumptions on purpose.'
        self.assertIn('<div data-thing="5"><p class="l">Assumptions</p><p class="v"><b>%s</b></p><p class="w">Counted by code</p></div>' % sent, p); self.assertIn('<h2>%s</h2>' % sent, p)
        self.assertIn('<div class="notes"><p>It rests on nothing new.</p></div>', p); self.assertNotIn('class="marks ten', p); self.assertNotIn('row got', p)

    def test_no_list(self):
        self.earlier([GOOD], PAGE); p = self.build(need=False)
        self.assertNotIn('The AI listed no assumptions', p); self.assertNotIn('assumptions have', p); self.assertNotIn('class="marks ten', p)

    def test_zero_of_n_all_marks_empty(self):
        self.full([GOOD], PAGE); p = self.build(); self.assertIn('<b>0 of 3</b>', p); self.assertIn('<h2>0 of 3 <span', p)
        head = p[p.index('<h2>0 of 3'):p.index('assumptions have a checked source</h2>')]; self.assertNotIn('b on', head); self.assertEqual(head.count('<i class="b"><u></u></i>'), 3)

    def test_more_than_twelve_marks_wrap(self):
        self.full([GOOD], PAGE, items=False)
        sg.save_json(os.path.join(self.run_dir, 'assumptions.json'), dict(assumptions=['Assumption word %s.' % c for c in 'abcdefghijklm']))
        p = self.build(); self.assertIn('class="marks ten many"', p); self.assertIn('<b>0 of 13</b>', p); self.assertIn('.marks.many{flex-wrap:wrap', p)

    def test_twelve_marks_do_not_wrap(self):
        self.full([GOOD], PAGE, items=False)
        sg.save_json(os.path.join(self.run_dir, 'assumptions.json'), dict(assumptions=['Assumption word %s.' % c for c in 'abcdefghijkl']))
        self.assertNotIn('class="marks ten many"', self.build())

    def test_no_findings(self):
        self.full([GOOD], PAGE); s = os.path.join(self.run_dir, 'attack.json'); sg.save_json(s, dict(json.load(open(s)), findings=[]))
        p = self.build(); self.assertNotIn('simulated people', p); self.assertIn('Reason it would miss', p)

    def test_loose_row_only_when_cards_belong_to_no_assumption(self):
        self.full([dict(GOOD, assumption=1)], PAGE); self.assertNotIn('row loose', self.build()); os.unlink(self.page_path)
        sg.check_cards(self.write('c2.json', dict(cards=[GOOD]), self.d), self.run_dir, {0: self._page()}, raw=tr.no_network)
        p = self.build(); self.assertIn('row loose', p); self.assertIn('1 passed card belongs to no assumption', p)

    def _page(self):
        f = os.path.join(self.d, 'p0')
        with open(f, 'wb') as o: o.write(PAGE[0])
        return f

    def test_no_failed_or_unchecked_blocks(self):
        self.full([GOOD], PAGE); p = self.build(); self.assertNotIn('failed card</summary>', p); self.assertNotIn('could not be checked</summary>', p)

    def test_failed_and_unchecked_blocks_when_there_are_some(self):
        self.earlier(); self.assume(); p = self.build(); self.assertIn('2 failed cards</summary>', p); self.assertIn('1 card could not be checked</summary>', p)

    def test_ai_drafted_sentence_only_when_drafted(self):
        self.full([GOOD], PAGE); self.assertNotIn('The AI chose this target.', self.build()); os.unlink(self.page_path)
        s = os.path.join(self.run_dir, 'target.json'); sg.save_json(s, dict(json.load(open(s)), ai_drafted=True)); self.assertIn('The AI chose this target.', self.build())

    def test_severity_sets_the_mark_and_any_other_start_is_empty(self):
        attack = [dict(person='Ann', kills='Fatal: no.', ask='a?'), dict(person='Ben', kills='Serious: no.', ask='b?'), dict(person='Cas', kills='Minor: no.', ask='c?'), dict(person='Dee', kills='Nope.', ask='d?')]
        self.earlier([GOOD], PAGE, attack=attack); self.assume(); p = self.build().split('<body>')[1]
        sec = p[p.index("AI's simulated people"):]; self.assertEqual(re.findall(r'<span class="s sev">([^<]*)</span>', sec), ['Fatal', 'Serious', 'Minor', ''])

    def test_people_sort_fatal_serious_minor_then_no_word_and_stay_paired(self):
        attack = [dict(person='Dee', kills='Nope.', ask='d?'), dict(person='Cas', kills='Minor: no.', ask='c?'), dict(person='Ben', kills='Serious: no.', ask='b?'),
                  dict(person='Ann', kills='Fatal: no.', ask='a?'), dict(person='Eve', kills='Serious: also.', ask='e?'), dict(person='Fay', kills='Fatal: too.', ask='f?')]
        self.earlier([GOOD], PAGE, attack=attack); self.assume(); p = self.build(people=['d line', 'c line', 'b line', 'a line', 'e line', 'f line']).split('<body>')[1]
        sec = p[p.index("AI's simulated people"):]
        self.assertEqual(re.findall(r'<span class="t">([^<]*)</span>', sec), ['a line', 'f line', 'b line', 'e line', 'c line', 'd line'])
        self.assertEqual(re.findall(r'<span class="s sev">([^<]*)</span>', sec), ['Fatal', 'Fatal', 'Serious', 'Serious', 'Minor', ''])
        self.assertEqual(re.findall(r'<i class="b ?(\w*)"><u>', sec.split('</h2>')[0]), ['pf', 'pf', 'ps', 'ps', 'pn', ''])
        self.assertIn('<p class="long">Ann</p>', sec.split('<span class="t">f line')[0])  # the long text follows its short line

    def test_labels_stay(self):
        self.full([GOOD], PAGE); p = self.build().replace('&#x27;', "'")
        for label in ("AI's opinion", "AI's simulated people", 'AI wrote this; code checked its numbers', 'Computed by code', 'Quotes checked by code', 'Counted by code', 'example-model-1'): self.assertIn(label, p)

    def test_mark_ranges_follow_the_data(self):
        self.assertEqual(sg._mark_ranges([]), '')
        r = sg._mark_ranges([[1], [], [1]]); self.assertEqual(len(re.findall(r'animation-range', r)), 2); self.assertIn('cover 8%', r); self.assertIn('cover 48%', r)
