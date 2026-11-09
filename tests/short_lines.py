"""One valid `short` block for any run, so every test that writes a report draft stays about what it tests."""
import json, os


def short_for(run_dir):
    def saved(name, key):
        try:
            with open(os.path.join(run_dir, name), encoding='utf-8') as f: return json.load(f).get(key) or []
        except (OSError, ValueError, AttributeError): return []  # a test may have damaged the file on purpose
    return dict(target='A shop chain lists it', reason='Chains want a track record first', check_at="The chain's own website",
                assumptions=['A short line for this assumption'] * len(saved('assumptions.json', 'assumptions')),
                people=['A short name' for _ in saved('attack.json', 'findings')])


def draft(run_dir, **fields):
    return dict(fields, short=short_for(run_dir))
