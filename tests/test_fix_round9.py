"""Tests for fix round 9 (work/fix-round9-notes.md). Written before the code; the failing run is work/fix-round9-red.txt."""
import json, os, re, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_report as tr  # noqa: E402
import test_ticket13 as t13  # noqa: E402
sg = tr.sg
GOOD, QUOTE, LIST = tr.GOOD, tr.QUOTE, t13.LIST
PAGE = {0: b'<p>' + QUOTE.encode() + b'</p>'}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*p):
    with open(os.path.join(ROOT, *p), encoding='utf-8') as f: return f.read()


class A_Filing(t13.Base13):
    def test_card_file_names_the_assumption_text(self):
        self.full([dict(GOOD, assumption=2)], PAGE); sg.source_context_cmd(self.run_dir)
        t = open(os.path.join(self.run_dir, 'source-context', 'CARD_0.txt'), encoding='utf-8').read()
        self.assertIn('FILED UNDER THIS ASSUMPTION: ' + LIST[1], t)

    def test_card_without_the_field_has_no_such_line(self):
        self.full([GOOD], PAGE); sg.source_context_cmd(self.run_dir)
        self.assertNotIn('FILED UNDER', open(os.path.join(self.run_dir, 'source-context', 'CARD_0.txt'), encoding='utf-8').read())

    def test_no_list_means_no_line_and_no_crash(self):
        self.full([dict(GOOD, assumption=2)], PAGE, items=False); sg.source_context_cmd(self.run_dir)
        self.assertNotIn('FILED UNDER', open(os.path.join(self.run_dir, 'source-context', 'CARD_0.txt'), encoding='utf-8').read())

    def test_resending_the_card_without_the_field_changes_the_count(self):
        self.full([dict(GOOD, assumption=1)], PAGE); self.report()
        self.assertIn('<b>1 of 3</b> have a checked source', self.page()); os.unlink(self.page_path)
        sg.check_cards(self.write('c2.json', dict(cards=[GOOD]), self.d), self.run_dir, raw=tr.no_network); self.report()
        self.assertIn('<b>0 of 3</b> have a checked source', self.page())

    def test_skill_md_asks_the_fifth_question_word_for_word(self):
        s = read('skills', 'second-guess', 'SKILL.md')
        self.assertIn('5. Does this card speak to the assumption it is filed under? It may speak for or against the assumption. Answer no if the card is on a different question, even if the two share a topic.', s)
        self.assertIn('FILED UNDER THIS ASSUMPTION', s); self.assertIn('`assumption` field removed', s)


class B_AiChose(tr.Base):
    def build(self, drafted):
        self.cards(); sg.stats_cmd(self.run_dir, no_dataset=True, base=self.d)
        sg.target_cmd(self.run_dir, 'at least one shop chain lists it', '2027-06-30', "the chain's own website", ai_drafted=drafted, today=tr.TODAY)
        sg.lean_cmd(self.run_dir, 30, 'chains want a track record first', today=tr.TODAY)
        self.write('a.json', dict(findings=tr.ATTACK)); sg.attack_cmd(self.run_dir, 'a.json')
        sg.assumptions_cmd(self.run_dir, none=True, reason='a plain data question'); self.report(); return self.page()

    def test_marker_shows_when_drafted(self): self.assertIn('The AI chose this target.', self.build(True))

    def test_marker_absent_when_the_user_gave_the_target(self): self.assertNotIn('The AI chose', self.build(False))


class C_CountInWords(t13.Base13):
    PAGE = PAGE

    def refused(self, sentence):
        self.full([dict(GOOD, assumption=1)], self.PAGE)
        return self.assertRefusedClean([sentence])

    def test_words_that_state_a_count_are_refused_with_the_code_prints_message(self):
        for s in ('All of the assumptions have a checked source.', 'Both assumptions have a checked source.', 'Of the assumptions, the price one has a checked source.', 'Most assumptions are checked.', 'Two assumptions have a source.'):
            with self.subTest(s):
                self.setUp(); msg = self.refused(s); self.assertIn('assumption', msg); self.assertIn('code prints', msg); self.tearDown()

    def test_other_sentences_pass(self):
        for s in ('The plastic worry is only loosely supported.', 'The assumption that gardeners water by hand has no source.', 'Gardeners are the buyers that matter, and the sources are shop pages.', 'Every assumption needs a source before launch.', 'The assumption that many people reorder has a checked source.', 'The plastic assumption is supported by two sources.'):
            with self.subTest(s):
                self.setUp(); self.full([dict(GOOD, assumption=1)], self.PAGE); self.report([s]); self.assertIn('0 of 3'.replace('0', '1'), self.page()); self.tearDown()

    def test_singular_assumption_with_a_count_word_passes_the_count_check(self):
        # at `report` this sentence is refused by the separate number check ("three"), so the count check is tested alone
        self.assertEqual(sg.count_words_problems([('paragraph 1', 'The three sources on the price assumption all agree.')]), [])
        self.assertEqual(len(sg.count_words_problems([('paragraph 1', 'All of the assumptions have a checked source.')])), 1)


class D_Messages(t13.Base13):
    def test_refused_assumption_sentence_points_to_the_assumptions_command(self):
        self.full([dict(GOOD, assumption=1)], PAGE)
        # the list is saved before any purchase check at report time only through attack-style text; force one in
        with open(os.path.join(self.run_dir, 'assumptions.json'), 'w') as f: json.dump(dict(assumptions=['Gardeners would buy it.']), f)
        msg = self.assertRefusedClean()
        self.assertIn('assumption 1', msg); self.assertIn('assumptions --file', msg); self.assertNotIn('attack text is fixed with `attack --file`', msg)

    def test_attack_lines_still_point_to_attack(self):
        self.earlier([GOOD], {0: PAGE[0]}, attack=[dict(person='A buyer', kills='It was found in step 7.', ask='Why?')]); self.assume()
        self.assertIn('attack --file', self.assertRefusedClean())

    def test_none_then_a_card_with_the_field_says_so(self):
        self.earlier([dict(GOOD, assumption=1)], {0: PAGE[0]}); sg.assumptions_cmd(self.run_dir, none=True, reason='a plain data question')
        msg = self.assertRefusedClean(); self.assertIn('--none', msg); self.assertNotIn('no assumption list was given', msg)


class F_Sentence(t13.Base13):
    def test_page_says_a_card_can_speak_against(self):
        self.full([dict(GOOD, assumption=1)], PAGE); self.report()
        txt = ' '.join(''.join(tr.parse(self.page()).text).split())
        self.assertIn('A card can speak against the assumption.', txt); self.assertIn(t13.SENTENCE, txt)


class G_TimeShare(tr.Base):
    def setUp(self): super().setUp(); sg._last[0] = 0.0  # the pacing table keeps the fake clocks of earlier tests

    def test_the_first_slow_card_cannot_take_all_the_time(self):
        t = [0.0]; seen = []
        def raw(url, timeout):
            seen.append((url, t[0]))
            if 'slow' in url: t[0] += timeout; return 0, b'', url, 'TimeoutError: overall time limit'
            if 'cdx/search' in url: return 200, b'20250101000000\n', url, ''
            if url.startswith('https://web.archive.org') or url.startswith('https://github.com'): return 200, b'', url, ''
            return 200, b'<p>' + QUOTE.encode() + b'</p>', url, ''
        def sleep(s): t[0] += s
        c1 = dict(GOOD, url='https://example.com/slow'); c2 = dict(GOOD, url='https://example.com/second')
        out = sg.check_cards(self.write('c.json', dict(cards=[c1, c2]), self.d), self.run_dir, raw=raw, sleep=sleep, clock=lambda: t[0], time_limit=60)
        starts = [s for u, s in seen if u == c2['url']]
        self.assertTrue(starts, 'the second card was never tried: %r %r' % (seen, out['results'])); self.assertLessEqual(min(starts), 50)


if __name__ == '__main__': unittest.main()
