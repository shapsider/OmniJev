"""Read-only local result dashboard routes for the integrated workbench."""
import json
import os
from pathlib import Path
import urllib.request

ROOT = Path(os.getenv('OMNIJEV_PROJECT_ROOT', Path(__file__).resolve().parents[1])).resolve()


def install_routes(app):
    from fastapi import HTTPException
    from fastapi.responses import FileResponse
    from .embodied_policy import connection

    @app.get('/api/omnijev/status')
    def status():
        cfg = connection()
        try:
            with urllib.request.urlopen(cfg['url'].replace('/chat/completions', '/models'), timeout=3) as f:
                names = [x['id'] for x in json.load(f).get('data', [])]
            return {'ready':cfg['model'] in names,'model':cfg['model'],'models':names,
                    'note':'The model is listed by the service; this does not guarantee successful inference.'}
        except Exception as exc:return {'ready':False,'model':cfg['model'],'error':type(exc).__name__}

    @app.get('/benchmarks')
    def dashboard():return FileResponse(Path(__file__).with_name('web')/'benchmarks.html')

    @app.get('/api/omnijev/benchmarks')
    def benchmarks():
        public = ROOT/'results/public-suite-summary.json'
        runs = []
        for p in sorted((ROOT/'results/embodied').glob('*/summary.json')):
            value = json.loads(p.read_text())
            runs.append({'run':p.parent.name, **value})
        return {'public':json.loads(public.read_text()) if public.exists() else {}, 'embodied':runs}

    @app.get('/api/omnijev/artifact/{name:path}')
    def artifact(name:str):
        base = (ROOT/'results').resolve()
        path = (base/name).resolve()
        if not path.is_relative_to(base) or not path.is_file() or path.suffix not in {'.json','.jsonl','.md','.png','.pdf','.zip'}:
            raise HTTPException(404,'Artifact not found')
        return FileResponse(path, filename=path.name)
