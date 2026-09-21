"""Package runnable sources, bundled web UI, licenses and measured results.

Excludes virtual environments, model weights and third-party benchmark media.
The archive is a source distribution, not an offline Python installer.
"""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SKIP = {'.git', '.venv', '.venv-eval', '.venv-embodied', 'node_modules',
        '__pycache__', 'dist', '.pytest_cache', 'playwright-results',
        'test-results', 'playwright-report', '.agents', '.codex'}
TOP = {'README.md', 'LICENSE', 'CONTRIBUTING.md', 'SECURITY.md', 'CITATION.cff',
       'THIRD_PARTY_NOTICES.md', 'pyproject.toml', '.gitignore',
       'run_local.sh', 'run_embodied.sh', 'setup_embodied.sh', 'omnijev',
       'embodied', 'scripts', 'tests', 'docs', 'examples', 'data', 'results'}


def included(path):
    rel = path.relative_to(ROOT)
    if rel.parts[0] not in TOP or any(p in SKIP or p.endswith('.egg-info') for p in rel.parts):return False
    if path.is_symlink() or path.suffix in {'.pyc','.log','.tmp','.tsv','.mp4','.gguf'}:return False
    if path.name in {'.DS_Store','.env','MUJOCO_LOG.TXT'}:return False
    if rel.parts[0]=='data' and path.name in {'mmad.json','streamingbench-real.csv'}:return False
    if rel.parts[0]=='results' and any(p in {'videos','images','frames'} for p in rel.parts):return False
    return path.is_file()


def main():
    dest=ROOT/'dist';dest.mkdir(exist_ok=True)
    files=sorted(p for p in ROOT.rglob('*') if included(p))
    archive=dest/'OmniJev-v0.3.0.zip'
    manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:z.write(p,'OmniJev/'+str(p.relative_to(ROOT)))
        z.writestr('OmniJev/RELEASE_MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(digest+'  '+archive.name+'\n')
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        names=set(z.namelist())
        for p in ['run_embodied.sh','setup_embodied.sh','embodied/LICENSE','embodied/src/embodied_jev/web/index.html']:
            assert 'OmniJev/'+p in names,p
    print(f'{archive}: {len(files)} files, {archive.stat().st_size/1024**2:.1f} MiB\nSHA256 {digest}')


if __name__=='__main__':main()
