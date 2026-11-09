"""Tests for fix round 6: drop-card, and the card price rule (work/fix-round6-notes.md)."""
import json, os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_report as tr  # noqa: E402
sg = tr.sg

REASON = 'the page has several dates and the year is wrong'
FYTA_Q = 'FYTA Beam G2 (selectable probe length) Sale price From €39,99'
FYTA = dict(tr.GOOD, url='https://example.com/fyta-beam', quote=FYTA_Q, number='€39,99', sample='one shop page', population='A rival sensor', year='2026')


class DropCard(tr.Base):
    go = tr.Cli.go

    def drop(self, card=None, reason=REASON):
        card = card or tr.GOOD
        return sg.drop_card_cmd(self.run_dir, card['url'], card['quote'], reason)

    def test_dropped_cards_number_is_refused_in_a_paragraph(self):
        self.earlier(); self.report()  # the report passes before the drop
        out = self.drop(); self.assertEqual(out['result'], 'dropped')
        with self.assertRaises(sg.Refused) as c: self.report()  # the next report applies the drop
        self.assertIn('25', str(c.exception))

    def test_card_is_in_the_failed_list_with_the_reason(self):
        self.earlier(); self.drop(); self.report(['No figures here.'])
        page = self.page(); self.assertIn('dropped after the source reading: ' + REASON, page)

    def test_no_match_is_refused_in_plain_words(self):
        self.earlier()
        for url, quote in ((tr.GOOD['url'], tr.QUOTE[:-1]), ('https://example.com/other', tr.QUOTE)):
            with self.assertRaises(sg.Refused) as c: sg.drop_card_cmd(self.run_dir, url, quote, REASON)
            self.assertIn('no card', str(c.exception))

    def test_reason_follows_the_lean_rule(self):
        self.earlier()
        for bad in ('', 'x' * 501, 'only 40 percent agree'):
            with self.assertRaises(sg.Refused): self.drop(reason=bad)

    def test_rerun_of_check_cards_keeps_the_drop_even_with_the_page_file(self):
        self.earlier(); self.drop()
        res = self.cards([tr.GOOD], {0: b'<p>' + tr.QUOTE.encode() + b'</p>'})
        self.assertEqual(res['results'][0]['result'], 'fail'); self.assertIn('dropped after the source reading', res['results'][0]['detail'])
        self.assertRefusedClean(['About 25% of new grocery products were gone.'], holds=['25'])

    def test_a_corrected_card_with_the_same_url_and_quote_ends_the_drop(self):
        self.earlier(); self.drop()
        fixed = dict(tr.GOOD, year='2022'); self.cards([fixed], {0: b'<p>' + tr.QUOTE.encode() + b'</p>'})
        self.report()  # the number is authorised again

    def test_cli_exit_codes_and_json(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            name = json.loads(self.go(d, 'start', '--idea', 'x', '--model', 'm').stdout)['name']
            with open(os.path.join(d, 'c.json'), 'w') as f: json.dump(dict(cards=[tr.GOOD]), f)
            with open(os.path.join(d, 'p.txt'), 'w') as f: f.write(tr.QUOTE)
            self.assertEqual(self.go(d, 'check-cards', 'c.json', '--run', name, '--page-file', '0', 'p.txt').returncode, 0)
            args = ('drop-card', '--url', tr.GOOD['url'], '--reason', 'r', '--run', name)
            r = self.go(d, *args, '--quote', 'not a card'); self.assertEqual(r.returncode, 1); self.assertIn('error', json.loads(r.stdout))
            r = self.go(d, *args, '--quote', tr.QUOTE); self.assertEqual(r.returncode, 0, r.stdout); self.assertEqual(json.loads(r.stdout)['result'], 'dropped')

    def test_a_report_can_be_rerun_after_a_drop_and_the_next_report_applies_it(self):
        self.earlier(); self.report(); out = self.drop()
        self.assertIn('next `report`', out['note'])


class CardPrice(tr.Base):
    def judged(self, quote, number):
        return sg.judge(dict(tr.GOOD, quote=quote, number=number), quote)

    def test_euro_and_pound_signs_lead_a_number(self):
        for n in ('€39,99', '£12.50'): self.assertTrue(sg.NUM_OK.fullmatch(n.lower()), n)

    def test_a_sale_price_with_money_passes_as_a_card(self):
        self.assertEqual(self.judged(FYTA_Q, '€39,99')[0], 'pass')
        self.assertEqual(self.judged('The Pro model is on sale at £120.00 in the shop.', '£120.00')[0], 'pass')

    def test_sales_figures_and_purchase_counts_still_fail(self):
        for q, n in (('Sales of $4 million in 2023 were reported by the firm.', '$4 million'),
                     ('We sold 40,000 units for $3 each last quarter at the fair.', '$3'),
                     ('Revenue reached $2 million in the second year of trading.', '$2 million'),
                     ('Price: $39.99 Discontinued - not available for purchase', '$39.99')):
            self.assertEqual(self.judged(q, n)[0], 'fail', q)

    def test_other_callers_of_purchase_figure_are_unchanged(self):
        self.assertTrue(sg.purchase_figure('Sale price From €39,99')); self.assertTrue(sg.field_problem('Sale price From €39,99'))

    def test_end_to_end_with_page_file_and_a_report_paragraph(self):
        self.earlier([FYTA], {0: b'<p>' + FYTA_Q.encode() + b'</p>'})
        self.assertRefusedClean(['The FYTA Beam G2 costs €3,999.'], holds=['3,999'])
        self.report(['The FYTA Beam G2 costs €39,99.'])

    def test_the_european_comma_is_not_read_as_thousands(self):
        self.assertEqual(sg.numbers_in('€39,99'), {sg.decimal.Decimal(39), sg.decimal.Decimal(99)})


if __name__ == '__main__':
    unittest.main()
