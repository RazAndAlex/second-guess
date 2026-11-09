"""Tests for fix round 5 (work/review-fix4.md defects 1, 3, 4). Each was shown to fail on a mutant of the module (work/fix-round5-notes.md)."""
import json, os, sys, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_report as tr  # noqa: E402
sg = tr.sg


class RunNameGuard(unittest.TestCase):
    go = tr.Cli.go

    def test_separators_in_a_run_name_are_refused_on_lean_and_report(self):
        with tr.tempfile.TemporaryDirectory() as d:
            for name in ('../name', '/etc/x', 'a/b', 'a\\b'):
                for args in (('lean', '--percent', '10', '--reason', 'x'), ('report', '--file', 't.json')):
                    r = self.go(d, *args, '--run', name)
                    self.assertEqual(r.returncode, 1, (name, args, r.stdout, r.stderr))
                    self.assertIn('is a run name, not a path', json.loads(r.stdout)['error'])


class DamagedShapes(tr.Base):
    def test_empty_object_in_lean_or_target_is_damaged_at_report(self):
        for fname in ('lean.json', 'target.json'):
            with self.subTest(fname):
                self.earlier(); self.write(fname, {})
                with self.assertRaises(sg.Refused) as c: self.report()
                self.assertIn('is damaged', str(c.exception)); self.assertIn(fname, str(c.exception))
                self.tearDown(); self.setUp()


class FailedReplace(tr.Base):
    def test_failed_os_replace_leaves_no_temp_and_no_page_and_lean_works(self):
        self.earlier()
        with mock.patch('os.replace', side_effect=OSError(28, 'No space left')):
            with self.assertRaises(sg.Refused) as c: self.report()
        self.assertIn('cannot write report.html', str(c.exception))
        self.assertEqual([n for n in os.listdir(self.run_dir) if n.startswith('.tmp-')], [])
        self.assertFalse(os.path.lexists(self.page_path))
        sg.lean_cmd(self.run_dir, 41, 'still open', today=tr.TODAY)


class LeanFreezeNeedsARealPage(tr.Base):
    def test_a_folder_named_report_html_does_not_freeze_the_lean(self):
        self.earlier(); os.mkdir(self.page_path)
        sg.lean_cmd(self.run_dir, 41, 'still open', today=tr.TODAY)
        with self.assertRaises(sg.Refused) as c: self.report()  # report keeps its own refusal
        self.assertIn('a folder with that name is in the way', str(c.exception))

    def test_a_symlink_named_report_html_does_not_freeze_the_lean(self):
        self.earlier(); os.symlink(os.path.join(self.d, 'nowhere'), self.page_path)
        sg.lean_cmd(self.run_dir, 41, 'still open', today=tr.TODAY)

    def test_a_regular_report_html_still_freezes_the_lean(self):
        self.earlier(); self.report()
        with self.assertRaises(sg.Refused): sg.lean_cmd(self.run_dir, 90, 'late', today=tr.TODAY)


if __name__ == '__main__':
    unittest.main()
