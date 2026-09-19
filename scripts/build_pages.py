"""Package only the stage runtime; never upload a working tree wholesale."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_AVATARS = ['CosmicBot.vrm', 'Cyberpal.vrm', 'anime_girl.vrm']

def build(destination):
    destination = Path(destination).resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Refusing a non-empty output directory; use a fresh destination')
    html = (ROOT / 'index.html').read_text()
    match = re.search(r'window\.STAGE_META = (.*?);</script>', html)
    if match is None:
        raise ValueError('Stage metadata is missing')
    meta = json.loads(match.group(1))
    if [a['file'] for a in meta['avatars']] != EXPECTED_AVATARS:
        raise ValueError('Public avatar allowlist changed')
    files = ['index.html', 'LICENSE', 'NOTICE']
    files += ['static/vrm/' + name for name in EXPECTED_AVATARS]
    for motion in meta['motions']:
        if not re.fullmatch(r'[A-Za-z0-9_-]+', motion['id']):
            raise ValueError('Invalid motion identifier')
        files.append('static/vrma/' + motion['id'] + '.vrma')
    destination.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name in files:
        source = ROOT / name
        if source.is_symlink() or not source.is_file():
            raise ValueError('Missing or symlinked runtime asset: ' + name)
        data = source.read_bytes()
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        hashes[name] = hashlib.sha256(data).hexdigest()
    (destination / '.nojekyll').write_text('')
    hashes['.nojekyll'] = hashlib.sha256(b'').hexdigest()
    manifest = {'avatars': EXPECTED_AVATARS, 'motions': [m['id'] for m in meta['motions']], 'sha256': hashes}
    (destination / 'asset-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Built {len(hashes)+1} files: {len(EXPECTED_AVATARS)} avatars, {len(meta["motions"])} motions -> {destination}')

if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else ROOT / '.pages-build')
