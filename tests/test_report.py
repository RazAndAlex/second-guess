import datetime, html.parser, json, os, re, subprocess, sys, tempfile, unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, 'skills', 'second-guess', 'scripts')
sys.path.insert(0, SCRIPTS)
import second_guess as sg  # noqa: E402
from short_lines import draft, short_for  # noqa: E402

TODAY = datetime.date(2026, 11, 5)
QUOTE = 'About 25% of new products are gone after 1 year, and 40% after two.'
GOOD = dict(url='https://example.com/grocery-study', quote=QUOTE, number='1 year', sample='7,000 new products', population='New grocery products in the US', year='2021')
MISSING = dict(GOOD, url='https://example.org/report-one', quote='This whole sentence with 99 inside is nowhere on the page at all.', number='99')
BADLINK = dict(GOOD, url='javascript:alert(1)')
OPENQ = dict(GOOD, url='https://example.com/paywalled', quote='A sentence with 77 inside that nobody could read on the page here.', number='77')
PARAS = ['About 25% of new grocery products were gone after 1 year, 40% after 2. That is grocery only.']
ATTACK = [dict(person='A garden centre buyer', kills='A new tool gets no shelf space.', ask='Would you stock it?'), dict(person='A keen gardener', kills='I already have a timer.', ask='Why replace it?')]


LAYOUT_A_RULES = [
    'h1{display:flex;flex-direction:column;align-items:center;font-weight:300;letter-spacing:-.035em}',
    'h1 br{display:none}',
    '.pill{display:block;font-size:clamp(72px,min(28.5vw,24.7vh),190px);background:var(--pill);border-radius:999px;padding:.03em .36em .05em;font-weight:500;line-height:1;color:var(--ink);font-variant-numeric:tabular-nums;white-space:nowrap}',
    '.say{display:block;margin-top:clamp(14px,2.4vh,20px);max-width:24em;font-size:clamp(28px,min(3.4vw,6.76vh),52px);line-height:1.2;text-wrap:balance}',
    '.who{display:block;margin-top:clamp(10px,1.7vh,14px);font-size:clamp(17px,1.5vw,23px);font-weight:400;letter-spacing:-.015em;line-height:1.3;color:var(--body)}',
    '.who b{color:var(--ink)}',
    '.m.hf{width:12px;height:42px;margin-right:-4px}',
    '.m.hf~.t{font-size:clamp(24px,2.3vw,34px);letter-spacing:-.03em;line-height:1.25;padding-block:.45em}',
    '.m.hf~.sev,.m.hs~.sev{border-radius:999px;line-height:1.2;white-space:nowrap}',
    '.m.hf~.sev{background:var(--pill);padding:.34em .9em .38em;font-size:22px;font-weight:500}',
    '.m.hs~.t{font-size:20px}',
    '.m.hs~.sev{box-shadow:inset 0 0 0 1.5px var(--pill);padding:.26em .8em .3em}',
    '.m.hn~.t,.m.hn~.sev{color:var(--body)}',
    '.m.hn~.sev{font-size:16px}',
    '@media (max-width:760px),(max-height:380px){h1,h2,footer b{font-weight:400}.pill{font-weight:500}}',
    ' .sev{justify-self:start}',
    ' .m.hf~.t{padding-block:.1em}',
    ' .m.hf~.sev{font-size:20px;margin-top:6px}',
    ' .m.hs~.sev{margin-top:4px}',
]


def no_network(*a): raise AssertionError('a test tried the network')


class Links(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.tags = []; self.attrs_of = []; self.text = []

    def handle_starttag(self, tag, attrs): self.tags.append(tag); self.attrs_of.append((tag, dict(attrs)))
    def handle_data(self, d): self.text.append(d)


def parse(page):
    p = Links(); p.feed(page); p.close(); return p


class Base(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory(); self.d = os.path.realpath(self._d.name)
        self.run_dir = sg.start('Smart Garden', 'example-model-1', base=self.d, today='2026-11-05')
        self.page_path = os.path.join(self.run_dir, 'report.html')

    def tearDown(self): self._d.cleanup()

    def write(self, name, data, folder=None):
        p = os.path.join(folder or self.run_dir, name)
        with open(p, 'w') as f: json.dump(data, f)
        return p

    def cards(self, cards=None, pages=None):
        """Default: one pass, one failed quote, one refused link, one unreadable page. All page files: nothing may reach the network."""
        if cards is None: cards = [GOOD, MISSING, BADLINK, OPENQ]; pages = {0: b'<p>' + QUOTE.encode() + b'</p>', 1: b'<p>' + QUOTE.encode() + b'</p>', 3: b'\x1f\x8bnot gzip'}
        paths = {}
        for i, b in (pages or {}).items():
            paths[i] = os.path.join(self.d, 'page%d' % i)
            with open(paths[i], 'wb') as f: f.write(b)
        return sg.check_cards(self.write('cards-in.json', dict(cards=cards), self.d), self.run_dir, paths, raw=no_network)

    def earlier(self, cards=None, pages=None, attack=None):
        self.cards(cards, pages); sg.stats_cmd(self.run_dir, no_dataset=True, base=self.d)
        sg.target_cmd(self.run_dir, 'at least one shop chain lists it', '2027-06-30', "the chain's own website", today=TODAY)
        sg.lean_cmd(self.run_dir, 30, 'chains want a track record first', today=TODAY)
        self.write('a.json', dict(findings=attack or ATTACK)); sg.attack_cmd(self.run_dir, 'a.json')

    def report(self, paragraphs=None, name='Smart Garden'):
        self.write('text.json', draft(self.run_dir, name=name, paragraphs=PARAS if paragraphs is None else paragraphs))
        return sg.report_cmd(self.run_dir, 'text.json')

    def page(self):
        with open(self.page_path, encoding='utf-8') as f: return f.read()

    def assertRefusedClean(self, paragraphs=None, name='Smart Garden', holds=()):
        with self.assertRaises(sg.Refused) as e: self.report(paragraphs, name)
        for h in holds: self.assertIn(h, str(e.exception))
        self.assertFalse(os.path.exists(self.page_path))
        return str(e.exception)

    def force_pass(self, card):
        """A saved pass for a card the checker would fail: the page must stay safe whatever the saved files hold."""
        key = sg._card_key(card, 0)
        self.write('cards.json', dict(cards=[dict(key=key, card=card)])); self.write('card-results.json', {key: dict(index=0, url=card['url'], result='pass', detail='quote on page', pending=0)})


class NumberCheck(Base):
    def test_invented_number_is_refused_with_its_sentence_and_can_run_again(self):
        self.earlier()
        msg = self.assertRefusedClean(['Good start. About 1234 gardeners agree.'], holds=['1234', 'About 1234 gardeners agree.'])
        self.assertNotIn('Good start', msg)
        out = self.report()
        self.assertTrue(os.path.exists(self.page_path)); self.assertEqual(out['path'], self.page_path)

    def test_every_offending_number_is_listed(self):
        self.earlier(); self.assertRefusedClean(['We saw 111 here. We saw 222 there.'], holds=['111', '222', 'We saw 111 here.', 'We saw 222 there.'])

    def test_comma_form_matches_a_saved_statistic(self):
        self.earlier(); sg.save_json(os.path.join(self.run_dir, 'statistics.json'), dict(counts=True, first_line='Dataset group: x.', quotable=dict(counts=dict(cases=1000), brier_formula=0.162, brier_average=0.1976)))
        self.report(['The data holds 1,000 cases, and the scores are 0.1620 and 0.1976.'])
        self.assertIn('1,000', self.page())

    def test_comma_form_matches_a_passing_cards_number(self):
        q = 'The review counted 1000 new products launched across the region.'
        self.earlier([dict(GOOD, quote=q, number='1000')], {0: q.encode()}); self.report(['It counted 1,000 products.', 'It counted one thousand products.'])

    def test_unverified_card_fields_authorise_nothing(self):
        self.earlier(); self.assertRefusedClean(['The sample was 7,000 products.'], holds=['7,000'])
        self.assertRefusedClean(['The study came out in 2021.'], holds=['2021'])

    def test_failed_card_authorises_nothing(self):
        self.earlier(); self.assertRefusedClean(['It said 99 of them.'], holds=['99']); self.assertRefusedClean(['It said 77 of them.'], holds=['77'])

    def test_lean_percent_and_target_year_authorise_nothing(self):
        self.earlier(); self.assertRefusedClean(['The model says 30%.'], holds=['30']); self.assertRefusedClean(['By June 2027.'], holds=['2027'])

    def test_number_words_two_to_twelve_count(self):
        self.earlier()
        for w in 'three twelve'.split(): self.assertRefusedClean(['There are %s rivals.' % w], holds=[w])
        self.assertEqual(sg.numbers_in('two rivals'), {sg.decimal.Decimal(2)}); self.assertEqual(sg.numbers_in('tenth'), set())

    def test_one_counts_only_before_in_of_out(self):
        # fix round 3, D17: "one" alone is no number; "one thousand" is, and "one in ten" is caught through "ten"
        self.assertEqual(sg.numbers_in('one in ten'), {sg.decimal.Decimal(10)}); self.assertIn(sg.decimal.Decimal(1000), sg.numbers_in('one thousand'))
        for t in ('no one cares', 'this one works', 'someone in here', 'one of them', 'one out of'): self.assertEqual(sg.numbers_in(t), set(), t)

    def test_word_in_quote_authorises_the_digit(self):
        self.earlier(); self.report(['Gone after 2.'])  # the quote says "two"

    def test_scale_changes_the_value(self):
        self.earlier(); self.assertRefusedClean(['Sized at 25 thousand.'], holds=['25 thousand']); self.assertRefusedClean(['Sized at 40k.'], holds=['40k'])
        self.assertEqual(sg.numbers_in('1.2 million') , sg.numbers_in('1,200,000')); self.assertEqual(sg.numbers_in('2 hundred thousand'), {sg.decimal.Decimal(200000)})

    def test_digits_after_a_letter_are_a_name_and_hidden_forms_still_count(self):
        self.assertEqual(sg.numbers_in('Web3 and Q3'), set())
        self.earlier(); self.assertRefusedClean(['We saw ５００ people.'], holds=['500']); self.assertRefusedClean(['We saw 1​234 people.'], holds=['1234'])

    def test_long_numbers_stay_distinct(self):
        a, b = '1' + '0' * 40, '1' + '0' * 39 + '1'; self.assertNotEqual(sg.numbers_in(a), sg.numbers_in(b))

    def test_dollar_amount_tied_to_purchases_is_refused_even_with_a_source(self):
        q = 'The firm reported $5,000 in the first quarter across all regions.'
        self.earlier([dict(GOOD, quote=q, number='$5,000')], {0: q.encode()})
        for t in ('It made $5,000 in sales.', 'Customers pay $5,000.', 'It brought 5,000 dollars of revenue.'): self.assertRefusedClean([t], holds=['tied to purchases', t])
        self.report(['The firm reported $5,000 in that quarter.'])  # the amount has a source and no purchase word

    def test_purchase_phrases_are_refused(self):
        self.earlier()
        for t in ('Most people would buy it.', 'Nobody would ever pay for it.', 'They are willing to pay.'): self.assertRefusedClean([t], holds=['purchase phrase', t])

    def test_attack_text_is_checked_and_fixed_through_attack(self):
        self.earlier(attack=[dict(person='A buyer', kills='I have seen 4242 such tools.', ask='Which one?')])
        self.assertRefusedClean(holds=['4242', 'finding 1 kills'])
        self.write('a.json', dict(findings=ATTACK)); sg.attack_cmd(self.run_dir, 'a.json'); self.report()

    def test_attack_ask_and_person_are_checked(self):
        self.earlier(attack=[dict(person='Buyer 5151', kills='No.', ask='Did 6161 say so?')]); self.assertRefusedClean(holds=['5151', '6161'])

    def test_name_is_checked(self):
        self.earlier(); self.assertRefusedClean(name='Reach 900 shops', holds=['900', 'the name'])
        self.report(name='Web3 garden'); self.assertIn('<title>Web3 garden: no purchase number in this version</title>', self.page()); self.assertIn('<p>Web3 garden: no purchase number in this version</p>', self.page())


class Refusals(Base):
    def test_refused_until_each_earlier_step_is_saved(self):
        self.write('text.json', draft(self.run_dir, name='x', paragraphs=['y']))
        for step, want in [(lambda: self.cards(), 'check-cards'), (lambda: sg.stats_cmd(self.run_dir, no_dataset=True, base=self.d), 'stats'),
                           (lambda: sg.target_cmd(self.run_dir, 'a chain lists it', '2027-06-30', 'site', today=TODAY), 'target'),
                           (lambda: sg.lean_cmd(self.run_dir, 30, 'no record', today=TODAY), 'lean'),
                           (lambda: (self.write('a.json', dict(findings=ATTACK)), sg.attack_cmd(self.run_dir, 'a.json')), 'attack')]:
            with self.assertRaises(sg.Refused) as e: sg.report_cmd(self.run_dir, 'text.json')
            self.assertIn(want, str(e.exception)); self.assertFalse(os.path.exists(self.page_path)); step()
        self.write('text.json', draft(self.run_dir, name='x', paragraphs=['y'])); sg.report_cmd(self.run_dir, 'text.json')

    def test_dataset_without_a_reviewer_answer_is_refused(self):
        self.earlier(); s = os.path.join(self.run_dir, 'statistics.json')
        sg.save_json(s, dict(counts=False, first_line="I don't know. The blind reviewer has not judged.", quotable={}, verdict=None, stats=dict(status='ok')))
        self.assertRefusedClean(holds=['match'])

    def test_unknown_missing_and_wrong_keys(self):
        self.earlier()
        for doc in (dict(name='x'), dict(paragraphs=['y']), dict(name='x', paragraphs=['y'], extra=1), [], dict(name=1, paragraphs=['y']), dict(name='x', paragraphs='y'), dict(name='x', paragraphs=[]), dict(name='x', paragraphs=[1]), dict(name=' ', paragraphs=['y']), dict(name='x', paragraphs=[' '])):
            self.write('t.json', dict(doc, short=short_for(self.run_dir)) if isinstance(doc, dict) else doc)  # a valid short, so each doc refuses for its own fault
            with self.assertRaises(sg.Refused): sg.report_cmd(self.run_dir, 't.json')
        self.assertFalse(os.path.exists(self.page_path))

    def test_file_follows_the_bare_name_rule(self):
        self.earlier(); self.write('text.json', draft(self.run_dir, name='x', paragraphs=['y']))
        for bad in ('../text.json', os.path.join(self.run_dir, 'text.json'), 'missing.json', ''):
            with self.assertRaises(sg.Refused): sg.report_cmd(self.run_dir, bad)
        os.symlink(os.path.join(self.run_dir, 'text.json'), os.path.join(self.run_dir, 'link.json'))
        with self.assertRaises(sg.Refused): sg.report_cmd(self.run_dir, 'link.json')
        self.write('good.json', draft(self.run_dir, name='x', paragraphs=['y']), os.path.join(self.d, sg.FILES)); sg.report_cmd(self.run_dir, 'good.json')

    def test_pending_card_is_refused(self):
        self.earlier(); saved = json.load(open(os.path.join(self.run_dir, 'cards.json')))
        self.write('card-results.json', {saved['cards'][0]['key']: dict(result='pending')}); self.assertRefusedClean(holds=['check-cards'])

    def test_damaged_saved_file_is_named(self):
        self.earlier()
        with open(os.path.join(self.run_dir, 'attack.json'), 'w') as f: f.write('{broken')
        self.assertRefusedClean(holds=['attack.json', 'delete it'])


class Log(Base):

    def test_a_rerun_replaces_the_page(self):
        self.earlier(); self.report(); self.report(['Gone after 1 year.'])
        self.assertIn('Gone after 1 year.', self.page())

    def test_lean_is_frozen_after_the_report(self):
        self.earlier(); self.report()
        with self.assertRaises(sg.Refused): sg.lean_cmd(self.run_dir, 90, 'changed my mind', today=TODAY)

    def test_refused_rerun_changes_nothing(self):
        self.earlier(); self.report(); before = self.page()
        with self.assertRaises(sg.Refused): self.report(['Now 8888.'])
        self.assertEqual(self.page(), before)


class Page(Base):
    def test_title_sections_labels_and_no_test_score(self):
        self.earlier(); self.report(); p = self.page()
        t = 'Smart Garden: no purchase number in this version'
        with open(os.path.join(self.run_dir, 'state.json')) as f: made = datetime.date.fromisoformat(json.load(f)['created'][:10])
        self.assertIn('<title>%s</title>' % t, p); self.assertIn('</svg>\n<p>%s</p>' % t, p); self.assertIn('<footer><svg class="end-g" role="img" aria-label="second-guess" viewBox="0 0 1199 1312" fill="currentColor">', p); self.assertIn('Model: example-model-1. Run on %d %s %d.' % (made.day, made.strftime('%B'), made.year), p)
        self.assertIn('''<h1><span class="pill" data-thing="1">30%</span> <span class="say" data-thing="2">chance that <span class="bal">a shop chain lists it</span> by 30 Jun 2027</span> <span class="who" data-thing="3"><b>AI's opinion</b> example-model-1</span></h1>''', p)
        order = ['<h1>', '>30%<', '<p class="l">Statistics</p>', "AI's simulated people", '>Check at: ', '>What the sources say<', '>Sources: ', '>How this report was made<', '<footer>']
        at = [p.index(x) for x in order]; self.assertEqual(at, sorted(at))
        self.assertIn('The target and date were saved before the percentage.', p); self.assertIn('AI&#x27;s opinion', p.replace("AI's opinion", 'AI&#x27;s opinion'))
        self.assertIn('<p class="tgt">at least one shop chain lists it by 30 June 2027.</p>', p); self.assertNotIn('score', p.split('</style>')[1].lower())

    def test_parses_with_one_h1(self):
        self.earlier(); self.report(); self.assertEqual(parse(self.page()).tags.count('h1'), 1)

    def test_table_uses_the_runs_counts(self):
        self.earlier(); self.report(); p = self.page()
        self.assertIn('<b>1 passed</b>, 2 failed, 1 could not be checked.', p)
        for row in ('<td>AI</td><td>4 cards</td>', '<td>Code</td><td>1 passed, 2 failed, 1 unchecked</td>', '<td>AI</td><td>2 findings</td>', '<td>AI judged, code saved</td><td>30%</td>', '<td>AI wrote, code built</td><td>This page</td>',
                    '<td>Code</td><td>Every number traced to a saved source. Saved on this computer.</td>'): self.assertIn(row, p)
        self.assertIn('<summary>2 failed cards</summary>', p); self.assertIn('<summary>1 card could not be checked</summary>', p)

    def test_no_empty_details_block(self):
        self.earlier([GOOD], {0: QUOTE.encode()}); self.report(); p = self.page()
        self.assertNotIn('failed card', p); self.assertNotIn('could not be checked</summary>', p)
        for body in re.findall(r'</summary>(.*?)</details>', p, re.S): self.assertTrue(re.sub(r'<[^>]+>', '', body).strip())

    def test_i_dont_know_is_bold_and_a_saved_statistic_is_not(self):
        self.earlier(); self.report(); self.assertIn('<p class="l">Statistics</p><p class="v"><b>I don&#x27;t know.</b></p><p class="w">Computed by code</p>', self.page()); self.assertIn('<p>Statistics: I don&#x27;t know. No dataset that fits was found.</p>', self.page())
        sg.save_json(os.path.join(self.run_dir, 'statistics.json'), dict(counts=True, first_line='Dataset group: garden tools.', quotable=dict(brier_formula=0.1, brier_average=0.2)))
        self.report(); p = self.page(); self.assertIn('<p>Statistics: Dataset group: garden tools.</p>', p); self.assertIn('<p class="l">Statistics</p><p class="v"><b>The formula beat the plain average.</b></p><p class="w">Computed by code</p>', p)

    def test_no_outside_request_and_no_src_or_url(self):
        self.earlier(); self.report(['See http://evil.example/x.png and url(x) src=y.']); p = self.page()
        p, fonts = re.subn(r'@font-face\{font-family:"Hanken Grotesk";src:url\(data:font/woff2;base64,[A-Za-z0-9+/=]+\) format\("woff2"\);[^}]*\}', '', p); self.assertEqual(fonts, 1)  # the one allowed url(, the font itself
        for bad in ('src=', 'url('): self.assertNotIn(bad, p)
        links = [a['href'] for t, a in parse(p).attrs_of if t == 'a']; self.assertEqual(links, [GOOD['url']])
        without = p.replace('href="%s"' % GOOD['url'], ''); self.assertEqual(re.findall(r'https?://[^ <]*', without), ['http://evil.example/x.png'])  # as text
        self.assertEqual(parse(p).tags.count('script') + parse(p).tags.count('img') + parse(p).tags.count('link'), 0)

    def test_head_is_exact(self):
        self.earlier(); self.report(); p = self.page()
        self.assertIn('''<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; font-src data:">''', p); self.assertIn('<meta name="referrer" content="no-referrer">', p)

    LOGO_CSS = '.sg-logo{position:absolute;top:20px;left:28px;width:131px;height:24px;color:var(--ink);z-index:2}\n@media (max-width:760px){.sg-logo{top:10px;left:16px}}\n'

    def test_small_logo_sits_straight_after_body_with_its_two_exact_rules(self):
        self.earlier(); self.report(); p = self.page()
        self.assertIn('<style>\n' + self.LOGO_CSS + '</style>\n</head>\n<body>\n<svg class="sg-logo" role="img" aria-label="second-guess" viewBox="2 -80.5 694.75 127.5">', p)
        self.assertEqual(p.count('class="sg-logo"'), 1); self.assertIn('</svg>\n<main>', p)
        self.assertNotIn('xmlns', p)  # inline svg needs none, and the no-outside-address test stays strict

    def test_no_logo_file_means_no_logo_and_the_rest_is_the_same(self):
        self.earlier(); self.report(); with_logo = self.page()
        with mock.patch.object(sg, 'LOGO_PATH', os.path.join(self.d, 'gone.svg')): self.report()
        p = self.page(); self.assertNotIn('sg-logo', p)
        self.assertEqual(with_logo.replace('<style>\n' + self.LOGO_CSS + '</style>\n', '').replace(sg._logo()[1], ''), p)

    def test_logo_asset_holds_no_script_href_or_handler(self):
        with open(sg.LOGO_PATH, encoding='utf-8') as f: svg = f.read()
        for bad in ('<script', 'href', 'javascript:'): self.assertNotIn(bad, svg.lower())
        self.assertEqual(re.findall(r'\son\w+\s*=', svg.lower()), [])

    FACTS_CSS = """.fb{grid-template-columns:1.5fr 1fr 1fr;gap:0 clamp(20px,2.4vw,40px);width:min(1120px,100%);text-align:left;font-size:clamp(17px,1.25vw,20px);line-height:1.35}
.fb>div{border-top:1px solid var(--edge);padding-top:12px}
.fb .l,.fb .w{color:var(--body)}.fb .v{color:var(--ink)}
@media (max-width:760px){.fb{grid-template-columns:1fr;gap:14px;width:min(358px,100%)}.fb>div{padding-top:10px}}
"""
    END_CSS = ".end-g{height:clamp(150px,24vh,190px);width:auto;color:var(--ink);margin-bottom:12px}\nfooter{gap:10px}\n"

    def test_small_print_is_three_cells_with_its_exact_rules(self):
        self.earlier(); self.report(); p = self.page(); css = p.split('</style>')[0]
        self.assertIn(self.FACTS_CSS, css); self.assertIn(self.END_CSS, css)
        self.assertNotIn('.facts .by', css); self.assertNotIn('.facts span{display:block}', css); self.assertNotIn('class="by"', p)
        self.assertIn('<div class="facts fb">\n<div data-thing="4"><p class="l">Reason it would miss</p><p class="v">', p)
        self.assertIn('</p></div>\n<div data-thing="5"><p class="l">Statistics</p><p class="v"><b>', p)
        self.assertIn('</b></p><p class="w">Computed by code</p></div>\n</div>\n</div>', p)  # no list saved: two cells, and the grid keeps its three columns
        self.assertNotIn('Assumptions</p>', p.split('</div>\n</div>')[0])

    def test_footer_g_is_the_flower_g_with_no_fill_and_no_xmlns(self):
        self.earlier(); self.report(); p = self.page(); foot = p[p.index('<footer>'):]
        self.assertEqual(p.count('class="end-g"'), 1); self.assertNotIn('<b>second-guess</b>', foot)
        svg = foot[len('<footer>'):foot.index('</svg>\n') + 7]; self.assertNotIn('fill="#', svg); self.assertNotIn('xmlns', p)
        self.assertEqual(sg._end_g()[1], svg)

    def test_no_end_g_file_keeps_the_word_and_the_rest_is_the_same(self):
        self.earlier(); self.report(); with_logo = self.page()
        with mock.patch.object(sg, 'END_G_PATH', os.path.join(self.d, 'gone.svg')): self.report()
        p = self.page(); self.assertNotIn('end-g', p); self.assertIn('<footer><b>second-guess</b><p>', p)
        self.assertIn('class="sg-logo"', p)  # the two logo files fail separately
        self.assertEqual(with_logo.replace(self.END_CSS, '').replace(sg._end_g()[1], '<b>second-guess</b>'), p)
        with mock.patch.object(sg, 'LOGO_PATH', os.path.join(self.d, 'gone.svg')): self.report()
        self.assertIn('class="end-g"', self.page()); self.assertNotIn('sg-logo', self.page())

    def _bad_end_g_keeps_the_word(self, text):
        self.earlier(); self.report(); good = self.page()
        bad = os.path.join(self.d, 'bad.svg')
        with open(bad, 'w', encoding='utf-8') as f: f.write(text)
        with mock.patch.object(sg, 'END_G_PATH', bad):
            self.assertEqual(sg._end_g(), ('', '')); self.report()
        p = self.page(); self.assertNotIn('end-g', p); self.assertIn('<footer><b>second-guess</b><p>', p)
        self.assertEqual(good.replace(self.END_CSS, '').replace(sg._end_g()[1], '<b>second-guess</b>'), p)

    def test_end_g_file_with_no_svg_keeps_the_word(self):
        self._bad_end_g_keeps_the_word('<?xml version="1.0"?>\n<!-- no drawing here -->\n')

    def test_end_g_file_with_another_header_keeps_the_word(self):
        self._bad_end_g_keeps_the_word('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><path d="M0 0"/></svg>\n')

    def test_end_g_file_cut_off_after_the_header_keeps_the_word(self):
        self._bad_end_g_keeps_the_word('<svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="1199" height="1312" viewBox="0 0 1199 1312">\n')

    def test_end_g_asset_holds_no_script_href_or_handler(self):
        with open(sg.END_G_PATH, encoding='utf-8') as f: svg = f.read()
        for bad in ('<script', 'href', 'javascript:'): self.assertNotIn(bad, svg.lower())
        self.assertEqual(re.findall(r'\son\w+\s*=', svg.lower()), [])

    SPECIMEN = os.path.join(ROOT, 'docs', 'artifacts', 'report-round', 'round5', 'a-headline', 'index.html')

    @unittest.skipUnless(os.path.exists(SPECIMEN), 'specimen is local only')
    def test_style_is_the_approved_specimens_but_for_the_named_changes(self):
        def rules(s):
            s = re.sub(r'/\*.*?\*/', '', s[s.index('<style>') + 7:s.index('</style>')]); s = re.sub(r'url\(data:[^)]*\)', 'url(F)', s)
            return {' '.join(r.split()) for r in s.split('}')}
        with open(self.SPECIMEN, encoding='utf-8') as f: spec = rules(f.read())
        self.earlier(); self.report(); page = rules(self.page())
        hand = re.compile(r'\.marks\.ten \.b:nth-child|animation-range')  # the ranges are generated from the data
        only = lambda a, b: sorted(r for r in a - b if not hand.search(r))
        self.assertEqual(only(spec, page), ['.facts .by{margin-left:.7em', '.facts .by{margin:0', '.facts span{display:block'])  # the old small print rules go
        new = sorted(' '.join(r.split()) for r in re.sub(r'/\*.*?\*/', '', self.FACTS_CSS + self.END_CSS).split('}') if r.strip())
        self.assertEqual(only(page, spec), sorted(r for r in new if not hand.search(r)))  # layout A, whole, but for the small print and the end logo

    def test_layout_a_rules_are_pinned_exactly(self):
        self.earlier(); self.report(); css = self.page().split('</style>')[0]
        for rule in LAYOUT_A_RULES: self.assertIn(rule, css)  # exact rules, since a prefix comparison passed broken ones
        self.assertNotIn('.bal{', css); self.assertNotIn('.bet{', css); self.assertNotIn('.bet ', css)

    def test_script_in_a_saved_quote_shows_as_text(self):
        self.earlier(); card = dict(GOOD, quote='Quote <script>alert(1)</script> holding 1 year in the middle of it.'); self.force_pass(card); self.report(['Gone after 1 year.']); p = self.page()
        self.assertIn('&lt;script&gt;alert&#40;1)&lt;/script&gt;', p); self.assertNotIn('<script', p); self.assertEqual(parse(p).tags.count('script'), 0)
        self.assertIn('<script>alert(1)</script>', ''.join(parse(p).text))

    def test_the_checker_itself_fails_a_quote_with_markup_and_the_page_holds_no_quote(self):
        q = 'Quote <script>alert(1)</script> holding 1 year in the middle of it.'
        self.earlier([dict(GOOD, quote=q)], {0: q.encode()}); self.report(['Nothing to quote.']); p = self.page()
        self.assertNotIn('alert', p.split('</style>')[1]); self.assertIn('quote holds &lt; or &gt;', p); self.assertNotIn('<a ', p)

    def test_script_in_every_outside_field_is_text(self):
        evil = '<script>alert(1)</script>"><img src=x onerror=alert(1)>'
        self.earlier([dict(GOOD, sample=evil, population=evil, year=evil)], {0: QUOTE.encode()}, attack=[dict(person=evil, kills=evil, ask=evil)])
        sg.save_json(os.path.join(self.run_dir, 'statistics.json'), dict(counts=False, first_line="I don't know. " + evil, quotable=dict(x=1)))
        self.report([evil], name=evil); p = self.page(); q = parse(p)
        for t in ('script', 'img'): self.assertEqual(q.tags.count(t), 0)
        self.assertEqual(q.tags.count('h1'), 1); self.assertNotIn('src=', p); self.assertIn(evil, ''.join(q.text))

    def test_javascript_link_becomes_plain_text(self):
        self.earlier(); self.report(); p = self.page()
        self.assertIn('<li>javascript:alert&#40;1)<span class="why">url outside whitelist</span></li>', p)
        self.assertNotIn('href="javascript', p); self.assertEqual([a['href'] for t, a in parse(p).attrs_of if t == 'a'], [GOOD['url']])
        self.force_pass(dict(GOOD, url='JaVaScRiPt:alert(1)')); self.report(['Gone after 1 year.'])
        self.assertEqual([t for t in parse(self.page()).tags if t == 'a'], [])

    def test_failed_link_is_plain_text_and_passed_link_has_rel(self):
        self.earlier(); self.report(); p = self.page()
        self.assertIn('<li>example.org/report-one<span class="why">quote not on page</span></li>', p); self.assertNotIn('href="https://example.org', p)
        self.assertIn('<a href="https://example.com/grocery-study" rel="noreferrer noopener">example.com/grocery-study</a>', p)

    def test_link_attribute_is_escaped(self):
        url = "https://example.com/a'onmouseover=alert(1)&b=2"
        self.earlier([dict(GOOD, url=url)], {0: QUOTE.encode()}); self.report(); q = parse(self.page())
        a = [x for t, x in q.attrs_of if t == 'a'][0]; self.assertEqual(a['href'], url); self.assertEqual(set(a), {'href', 'rel'})

    def test_mark_when_found_and_plain_when_not(self):
        self.earlier(); self.report(); self.assertIn('gone after <mark>1 year</mark>, and', self.page())
        self.force_pass(dict(GOOD, number='1 YEAR')); self.report(['Gone after 1 year.'])
        self.assertNotIn('<mark>', self.page()); self.assertIn('gone after 1 year, and', self.page())

    def test_mark_takes_a_whole_number_only(self):
        self.assertEqual(sg._marked('it was 112 and 12 here', '12'), 'it was 112 and <mark>12</mark> here'); self.assertEqual(sg._marked('it was 112', '12'), 'it was 112')

    def test_surrogates_right_to_left_and_a_long_word_are_safe(self):
        odd = 'a\ud800b ‮abc אב ' + 'W' * 400
        self.earlier([dict(GOOD, sample=odd)], {0: QUOTE.encode()}, attack=[dict(person=odd[:300], kills=odd, ask='q')])
        self.report([odd], name=odd)
        with open(self.page_path, 'rb') as f: raw = f.read()
        text = raw.decode('utf-8'); self.assertNotIn('‮', text); self.assertIn('ab ', text); self.assertIn('אב', text); self.assertIn('W' * 400, text)

    def test_a_local_path_in_a_reason_does_not_travel(self):
        self.assertNotIn('/', sg._why(dict(result='unchecked', detail=sg.PDF_HINT % sg.SCRIPT))); self.assertNotIn('/', sg._why(dict(result='unchecked', detail='cannot read page file: /Users/x/y')))

    def test_file_mode_and_no_temp_left(self):
        self.earlier(); self.report(); self.assertEqual(os.stat(self.page_path).st_mode & 0o777, 0o644)
        self.assertEqual([n for n in os.listdir(self.run_dir) if n.startswith('.tmp')], [])


class Cli(unittest.TestCase):
    def go(self, d, *a):
        return subprocess.run([sys.executable, '-B', '-I', os.path.join(SCRIPTS, 'second_guess.py')] + list(a), cwd=d, capture_output=True, text=True)

    def test_from_start_to_report(self):
        with tempfile.TemporaryDirectory() as d:
            run = json.loads(self.go(d, 'start', '--idea', 'Smart Garden', '--model', 'm1').stdout)['run']
            with open(os.path.join(d, 'c.json'), 'w') as f: json.dump(dict(cards=[GOOD]), f)
            with open(os.path.join(d, 'p.txt'), 'w') as f: f.write(QUOTE)
            self.assertEqual(self.go(d, 'check-cards', 'c.json', '--page-file', '0', 'p.txt').returncode, 0)
            self.assertEqual(self.go(d, 'stats', '--no-dataset').returncode, 0)
            self.assertEqual(self.go(d, 'target', '--text', 'a chain lists it', '--date', '2099-06-30', '--place', 'site').returncode, 0)
            self.assertEqual(self.go(d, 'lean', '--percent', '12.5', '--reason', 'no record yet').returncode, 0)
            with open(os.path.join(run, 'a.json'), 'w') as f: json.dump(dict(findings=ATTACK), f)
            self.assertEqual(self.go(d, 'attack', '--file', 'a.json').returncode, 0)
            self.assertEqual(self.go(d, 'assumptions', '--none', '--reason', 'test of the report route').returncode, 0)
            with open(os.path.join(run, 't.json'), 'w') as f: json.dump(draft(run, name='Smart Garden', paragraphs=['About 3333 of them.']), f)
            r = self.go(d, 'report', '--file', 't.json'); self.assertEqual(r.returncode, 1); self.assertIn('3333', json.loads(r.stdout)['error'])
            self.assertFalse(os.path.exists(os.path.join(run, 'report.html')))
            with open(os.path.join(run, 't.json'), 'w') as f: json.dump(draft(run, name='Smart Garden', paragraphs=PARAS), f)
            r = self.go(d, 'report', '--file', 't.json'); self.assertEqual(r.returncode, 0, r.stdout + r.stderr); out = json.loads(r.stdout)
            self.assertEqual(set(out), {'path', 'first_lines'}); self.assertTrue(os.path.isfile(out['path']))
            self.assertEqual(out['first_lines'][0], 'Smart Garden: no purchase number in this version'); self.assertIn('12.5%', ''.join(out['first_lines']))
            self.assertEqual(self.go(d, 'report').returncode, 2)


if __name__ == '__main__':
    unittest.main()
