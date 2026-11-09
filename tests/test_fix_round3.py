"""Tests for fix round 3 (work/fix-round3-brief.md). Each one was written to fail on the module at sha c1e1d72dc37c."""
import datetime as dt, json, os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_report as tr  # noqa: E402
import test_ticket5 as t5  # noqa: E402
sg = tr.sg
GOOD, QUOTE, TODAY = tr.GOOD, tr.QUOTE, tr.TODAY
MONEYQ = 'The kit retails at $25 in most garden stores across the region this year.'
SALEQ = 'In the survey 62% of 400 respondents said they would pay $20 for it.'


class Item1Fields(tr.Base):
    def result_of(self, **kw):
        card = dict(GOOD, **kw); return self.cards([card], {0: b'<p>' + QUOTE.encode() + b'</p>'})['results'][0]

    def test_sample_with_purchase_figure_fails(self):
        for s in ('4,000 buyers; 62% would pay $20 each', 'About $20 per unit', '62% of buyers returned'):
            r = self.result_of(sample=s); self.assertEqual(r['result'], 'fail', s)

    def test_population_and_year_checked(self):
        self.assertEqual(self.result_of(population='Shoppers, 62% bought it for $20')['result'], 'fail')
        self.assertEqual(self.result_of(year='$20 price')['result'], 'fail')
        self.assertEqual(self.result_of(year='a very long text that is not a year at all, written by an AI')['result'], 'fail')

    def test_ordinary_values_pass(self):
        for kw in (dict(sample='7,000 new products'), dict(year='2021'), dict(year='March 2021'), dict(year='2019-2021')):
            self.assertEqual(self.result_of(**kw)['result'], 'pass', kw)

    def test_model_name(self):
        with self.assertRaises(sg.Refused): sg.start('idea', 'Model: 62% would pay $20', base=self.d)
        with self.assertRaises(sg.Refused): sg.start('idea', 'x costs $20 a month', base=self.d)
        sg.start('idea', 'Opus 5.5', base=self.d)


class Item2QuoteWithPurchaseFigure(tr.Base):
    def test_r5_fails_with_a_plain_reason_and_r6_stays_refused(self):
        card = dict(GOOD, quote=SALEQ, number='62%')
        r = self.cards([card], {0: SALEQ.encode()})['results'][0]
        self.assertEqual((r['result'], r['detail']), ('fail', 'holds a purchase number; this version prints none'))
        sg.stats_cmd(self.run_dir, no_dataset=True, base=self.d)
        sg.target_cmd(self.run_dir, 'at least one shop chain lists it', '2027-06-30', 'site', today=TODAY)
        sg.lean_cmd(self.run_dir, 30, 'chains want a sales record first', today=TODAY)
        self.write('a.json', dict(findings=tr.ATTACK)); sg.attack_cmd(self.run_dir, 'a.json')
        self.assertRefusedClean(['The review found 62 of them.'], holds=['62'])


class Item3Money(tr.Base):
    def test_bare_number_does_not_allow_money(self):
        self.earlier()
        for p in ('The price is $25.', 'It is priced at 25 dollars.'): self.assertRefusedClean([p], holds=['25'])

    def test_money_in_a_passed_quote_allows_the_same_amount(self):
        self.earlier([dict(GOOD, quote=MONEYQ, number='$25')], {0: MONEYQ.encode()})
        self.report(['A kit costs $25 in the stores.', 'Also 25 dollars here.'])

    def test_other_money_amount_refused_even_beside_a_card_with_money(self):
        self.earlier([dict(GOOD, quote=MONEYQ, number='$25')], {0: MONEYQ.encode()})
        self.assertRefusedClean(['A kit costs $30.'], holds=['30'])


class Item4SpelledNumbers(tr.Base):
    def test_words_above_twelve_and_vague_amounts(self):
        self.earlier()
        for p in ('Thirty shops list it.', 'Forty-two shops list it.', 'Thirteen shops list it.', 'Ninety percent of shops list it.', 'Two hundred shops list it.',
                  'Twenty one shops list it.'): self.assertRefusedClean([p])
        for p in ('Half of the shops list it.', 'A third of shops list it.', 'A quarter of shops list it.', 'Dozens of shops list it.', 'Hundreds of shops list it.', 'Thousands of shops list it.'):
            self.assertRefusedClean([p], holds=['number from a source'])


class Item5One(tr.Base):
    def test_one_is_not_a_number(self):
        self.earlier([])
        for p in ('One of the biggest hurdles is shelf space.', 'No one in the trade has tried it.', 'She is the one in charge.', 'The one in the corner shop.'): self.report([p])
        os.remove(self.page_path)
        self.assertRefusedClean(['One thousand shops list it.'])


class Item6SciAndEuropean(tr.Base):
    def test_1e6_and_40_000(self):
        self.earlier()
        self.assertRefusedClean(['About 1e6 shops list it.'])
        self.assertRefusedClean(['About 40.000 shops list it.'])

    def test_card_text_allows_its_own_form(self):
        q = 'The register lists 40.000 shops across the whole country this year.'
        self.earlier([dict(GOOD, quote=q, number='40.000')], {0: q.encode()}); self.report(['It lists 40.000 shops.'])


class Item7PurchasePhrases(tr.Base):
    def test_wider_list(self):
        self.earlier()
        for p in ('Shoppers will pay more.', 'Shops are keen to buy it.', 'They plan to buy it.', 'Shops are ready to pay.', 'They would definitely and gladly buy it.', 'They would not buy it.'):
            self.assertRefusedClean([p], holds=['purchase phrase'])


class Item8ErrorScore(tr.Base):
    def test_wording(self):
        self.earlier()
        sg.save_json(os.path.join(self.run_dir, 'statistics.json'), dict(counts=True, first_line='Dataset group: garden tools.', quotable=dict(brier_formula=0.1, brier_average=0.2)))
        self.report(); p = self.page()
        self.assertIn('The formula beat the plain average', p); self.assertNotIn('Brier', p)

    def test_first_line(self):
        r = sg.combine
        d = os.path.join(self.run_dir)
        sg.save_json(os.path.join(d, 'stats.json'), dict(status='ok', measures=dict(cases=10, earlier_cases=8, later_cases=2, counts=dict(earlier=dict(a=4, b=4), later=dict(a=1, b=1)),
                     brier_model=0.1, brier_average=0.2, earlier_average=0.5, gain_lower_bound=0.05, earlier_to='2020-01-01 00:00:00', later_from='2020-02-01 00:00:00',
                     shown=dict(outcome='o', positive='b', features=['x']))))
        sg.save_json(os.path.join(d, 'match.json'), dict(group='garden tools', verdict='yes', reason='same kind.'))
        fl = r(d)['first_line']
        self.assertIn('Error score 0.1000 against 0.2000; lower is better. It says nothing about buying.', fl); self.assertNotIn('Brier', fl)


class Item9FailedPage(tr.Base):
    def test_failed_page_write_leaves_no_page(self):
        self.earlier(); os.mkdir(self.page_path)
        with self.assertRaises(sg.Refused): self.report()
        self.assertTrue(os.path.isdir(self.page_path)); self.assertEqual([f for f in os.listdir(self.run_dir) if f.startswith('.tmp-')], [])


class Item10Merge(tr.Base):
    def test_second_file_merges_and_duplicates_count_once(self):
        c2 = dict(GOOD, url='https://example.com/other', quote='A second sentence that is long enough to count as a real quote, 12 shops.', number='12')
        self.cards([GOOD, GOOD], {0: QUOTE.encode()})
        self.cards([c2], {0: c2['quote'].encode()})
        with open(os.path.join(self.run_dir, 'cards.json')) as f: saved = json.load(f)['cards']
        self.assertEqual([c['card']['url'] for c in saved], [GOOD['url'], c2['url']])

    def test_empty_list_gives_a_report_with_zero_sources(self):
        self.cards([], {})
        self.assertTrue(os.path.exists(os.path.join(self.run_dir, 'card-results.json')))
        sg.stats_cmd(self.run_dir, no_dataset=True, base=self.d)
        sg.target_cmd(self.run_dir, 'at least one shop chain lists it', '2027-06-30', 'site', today=TODAY)
        sg.lean_cmd(self.run_dir, 30, 'chains want a sales record first', today=TODAY)
        self.write('a.json', dict(findings=tr.ATTACK)); sg.attack_cmd(self.run_dir, 'a.json')
        self.report(['Nothing was found.']); self.assertIn('0 passed', self.page())


class Item11Caps(tr.Base):
    def test_caps_and_plain_schema_reason(self):
        with self.assertRaises(sg.Refused): sg.start('idea', 'm' * 201, base=self.d)
        with self.assertRaises(sg.Refused): sg.start('i' * 2001, 'm', base=self.d)
        sg.start('i' * 2000, 'm' * 200, base=self.d)
        bad = {k: v for k, v in GOOD.items() if k != 'sample'}
        r = self.cards([bad], {})['results'][0]
        self.assertEqual(r['result'], 'fail'); self.assertNotIn('card[', r['detail']); self.assertNotIn('schema', r['detail'])


class Item12LeanReason(t5.Base):
    def test_reason_rules(self):
        self.target()
        sg.lean_cmd(self.run_dir, 30, 'chains want a sales record first', today=TODAY)
        sg.lean_cmd(self.run_dir, 30, 'most chains buy only from known suppliers', today=TODAY)
        for bad in ('20 shops buy', 'twenty shops buy', 'about $5 each', 'thirty percent buy', 'half of them buy', 'forty-two chains'):
            with self.assertRaises(sg.Refused, msg=bad): sg.lean_cmd(self.run_dir, 30, bad, today=TODAY)


class Item14LeanShape(unittest.TestCase):
    def test_finite_zero_to_100(self):
        for v in (150, -1, float('nan'), float('inf')): assert not sg._ok_lean(dict(percent=v, reason='x')), v
        for v in (0, 50, 100, 12.5): assert sg._ok_lean(dict(percent=v, reason='x')), v


class Item15Attack(tr.Base):
    def attack(self, **kw):
        f = dict(person='A buyer', kills='Few use it.', ask='Why?'); f.update(kw)
        self.write('b.json', dict(findings=[f])); return sg.attack_cmd(self.run_dir, 'b.json')

    def test_money_and_percent_tied_to_purchases_refused(self):
        for kw in (dict(kills='Buyers pay $80.'), dict(kills='62% would pay for it.'), dict(ask='Would 40% of buyers return?'), dict(kills='Customers spend $20 a month.')):
            with self.assertRaises(sg.Refused, msg=str(kw)): self.attack(**kw)
        self.attack(kills='A gardener already owns a timer.')

class Item19Small(t5.Base):
    def test_match_refuses_spelled_numbers(self):
        for kw in (dict(reason='ninety three percent of these cases look alike'), dict(group='Twelve thousand projects')):
            a = dict(group='garden tools', verdict='yes', reason='same kind of items'); a.update(kw)
            with self.assertRaises(sg.Refused, msg=str(kw)): sg.match_cmd(self.run_dir, a['group'], a['verdict'], a['reason'])

    def test_lone_surrogate_dropped(self):
        sg.stats_cmd(self.run_dir, no_dataset=True, base=self.d)
        sg.match_cmd(self.run_dir, 'G\udcff tools', 'unavailable', 'no reviewer')
        self.assertNotIn('\udcff', json.dumps(self.saved('match.json'))); self.assertNotIn('\udcff', sg.combine(self.run_dir)['first_line'])

    def test_first_lean_date_is_stored_and_a_clock_before_it_is_refused(self):
        self.target()
        sg.lean_cmd(self.run_dir, 30, 'chains want a record first', today=TODAY)
        self.assertEqual(self.saved('lean.json')['first_date'], '2026-11-05')
        with self.assertRaises(sg.Refused): sg.lean_cmd(self.run_dir, 31, 'chains want a record first', today=dt.date(2026, 11, 1))
        sg.lean_cmd(self.run_dir, 31, 'chains want a record first', today=dt.date(2026, 11, 6))
        self.assertEqual(self.saved('lean.json')['first_date'], '2026-11-05')


class Item17Charset(tr.Base):
    PL = 'Zażółć gęślą jaźń: to jest dość długie polskie zdanie testowe.'

    def get(self, charset):
        body = ('<p>%s</p>' % self.PL).encode('cp1250')
        return lambda u, timeout=30: (200, body, u, '', '', charset) if charset else (200, body, u, '', '')

    def test_header_charset_passes(self):
        card = dict(GOOD, quote=self.PL, number='1', sample='x', population='y', year='2020')
        card['quote'] = self.PL + ' 1'
        body = ('<p>%s</p>' % card['quote']).encode('cp1250')
        raw = lambda u, timeout=30: (200, body, u, '', '', 'windows-1250')
        r = sg.check_cards(self.write('c.json', dict(cards=[card]), self.d), self.run_dir, raw=raw, sleep=lambda s: None)['results'][0]
        self.assertEqual(r['result'], 'pass', r)

    def test_no_charset_and_high_bytes_is_unchecked(self):
        card = dict(GOOD, quote=self.PL + ' 1', number='1'); body = ('<p>%s</p>' % card['quote']).encode('cp1250')
        raw = lambda u, timeout=30: (200, body, u, '', '')
        r = sg.check_cards(self.write('c.json', dict(cards=[card]), self.d), self.run_dir, raw=raw, sleep=lambda s: None)['results'][0]
        self.assertEqual(r['result'], 'unchecked', r)


class Item13StatsPurchaseNames(unittest.TestCase):
    def test_names(self):
        for n in ('unitsSold', 'units_sold', 'Purchased', 'bought_it', 'orderPlaced', 'PAID', 'checkout_done', 'revenue_usd', 'isCustomer', 'converted'):
            self.assertTrue(sg._purchasey(n), n)
        for n in ('funded', 'successful', 'pledged', 'launched', 'category', 'success'):
            self.assertFalse(sg._purchasey(n), n)


class Item18Noise(unittest.TestCase):
    def test_min_gain(self):
        self.assertEqual(sg.MIN_GAIN, 0.01)


if __name__ == '__main__':
    unittest.main()
