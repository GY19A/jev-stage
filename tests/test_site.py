"""Dependency-free checks for the public stage and its Pages payload."""
import json
import hashlib
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text()
MATCH = re.search(r'window\.STAGE_META = (.*?);</script>', HTML)
assert MATCH is not None, 'Missing stage metadata'
META = json.loads(MATCH.group(1))

class StageTests(unittest.TestCase):
    def test_all_motion_references_are_bundled_glb_files(self):
        names = {m['id'] for m in META['motions']}
        self.assertTrue(set(META['idle']).issubset(names))
        self.assertTrue({m['id'] for m in META['byEmotion'].values()}.issubset(names))
        self.assertEqual(names, {p.stem for p in (ROOT / 'static/vrma').glob('*.vrma')})
        for name in names:
            self.assertEqual((ROOT / 'static/vrma' / (name + '.vrma')).read_bytes()[:4], b'glTF')

    def test_no_secrets_or_private_network_targets_in_public_runtime(self):
        patterns = [rb'gh[pousr]_[A-Za-z0-9_]{20,}', rb'github_pat_[A-Za-z0-9_]{20,}',
                    rb'apikey_[A-Za-z0-9_]{10,}', rb'sk-[A-Za-z0-9]{20,}',
                    rb'BEGIN [A-Z ]*PRIVATE KEY', rb'(?<![\d.])192\.168\.\d+\.\d+',
                    rb'(?<![\d.])10\.\d+\.\d+\.\d+', rb'(?<![\d.])172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+',
                    rb'__MAXSAY__']
        for path in [ROOT / 'index.html', *list((ROOT / 'static').rglob('*'))]:
            if not path.is_file():
                continue
            data = path.read_bytes()
            for pattern in patterns:
                self.assertIsNone(re.search(pattern, data), f'Forbidden content in {path.relative_to(ROOT)}')

    def test_pages_build_contains_only_runtime_allowlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / 'site'
            build = subprocess.run([sys.executable, str(ROOT / 'scripts/build_pages.py'), str(dest)], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            expected = {'index.html', 'LICENSE', 'NOTICE', '.nojekyll', 'asset-manifest.json'}
            expected.update('static/vrm/' + a['file'] for a in META['avatars'])
            expected.update('static/vrma/' + m['id'] + '.vrma' for m in META['motions'])
            self.assertEqual({p.relative_to(dest).as_posix() for p in dest.rglob('*') if p.is_file()}, expected)
            manifest = json.loads((dest / 'asset-manifest.json').read_text())
            self.assertEqual(set(manifest['sha256']), expected - {'asset-manifest.json'})
            self.assertEqual(manifest['avatars'], [a['file'] for a in META['avatars']])
            for name, digest in manifest['sha256'].items():
                self.assertEqual(hashlib.sha256((dest / name).read_bytes()).hexdigest(), digest)

    def test_input_limit_is_rendered_in_static_html(self):
        limit = re.search(r'id="inp"[^>]*maxlength="([^"]+)"', HTML)
        self.assertIsNotNone(limit)
        assert limit is not None
        self.assertEqual(limit.group(1), str(META['maxSay']))

    def test_only_requested_avatars_are_selectable_and_bundled(self):
        expected = ['CosmicBot.vrm', 'Cyberpal.vrm', 'anime_girl.vrm']
        self.assertEqual([a['file'] for a in META['avatars']], expected)
        self.assertEqual(sorted(p.name for p in (ROOT / 'static/vrm').iterdir()), sorted(expected))

if __name__ == '__main__':
    unittest.main()
