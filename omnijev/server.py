"""Loopback-only demo/API. One in-flight inference; overload is rejected, not queued."""
import argparse
import base64
import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from .client import OmniJev, Policy

MAX_BODY = 12 * 1024 * 1024


def validate_http_request(data):
    if not isinstance(data, dict):raise ValueError('JSON object required')
    allowed={'question','options','images','state','request_id','policy','mode'}
    if set(data)-allowed:raise ValueError('Unknown fields: '+', '.join(sorted(set(data)-allowed)))
    if len(data.get('question','')) > 8000 or len(data.get('state','')) > 32000:
        raise ValueError('Question/state too large')
    images=data.get('images',[])
    if not isinstance(images,list) or len(images)>8:raise ValueError('At most 8 images')
    for image in images:
        if not isinstance(image,str) or not image.startswith(('data:image/png;base64,','data:image/jpeg;base64,','data:image/webp;base64,')):
            raise ValueError('HTTP accepts image data URLs only, not local paths or remote URLs')
        body=base64.b64decode(image.split(',',1)[1],validate=True)
        if not body:raise ValueError('Empty image')
    policy=data.get('policy',{})
    if not isinstance(policy,dict):raise ValueError('policy must be an object')
    data=dict(data)
    data['policy']=Policy(**policy)
    return data


def make_server(client, port=8765):
    gate=threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):pass

        def send_json(self, status, data):
            encoded=json.dumps(data,ensure_ascii=False,allow_nan=False).encode()
            self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(encoded)));self.send_header('Cache-Control','no-store')
            self.end_headers()
            try:self.wfile.write(encoded)
            except (BrokenPipeError,ConnectionResetError):pass

        def local_request(self):
            # Browser requests must be same-origin; no permissive CORS.
            host=self.headers.get('Host','')
            expected={f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
            return host in expected and self.headers.get('Origin',f'http://{host}') == f'http://{host}'

        def do_GET(self):
            if not self.local_request():return self.send_json(403,{'error':'Same-origin localhost only'})
            if self.path=='/':
                data=Path(__file__).with_name('web').joinpath('index.html').read_bytes()
                self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8')
                self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            elif self.path=='/health':
                ready=False
                try:
                    with urllib.request.urlopen(client.base_url+'/v1/models',timeout=3) as r:
                        models=json.load(r).get('data',[])
                    ready=any(m.get('id')==client.model for m in models)
                except Exception:pass
                self.send_json(200,dict(status='ok',backend_ready=ready,model=client.model,busy=gate.locked(),
                                        audio_supported=False,note='Model listed; readiness is not an inference guarantee'))
            else:self.send_json(404,{'error':'Not found'})

        def do_POST(self):
            if not self.local_request():return self.send_json(403,{'error':'Same-origin localhost only'})
            if self.path!='/decide':return self.send_json(404,{'error':'Not found'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0 < length <= MAX_BODY:return self.send_json(413,{'error':'Body must be 1 byte–12 MiB'})
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':
                    return self.send_json(415,{'error':'application/json required'})
                data=validate_http_request(json.loads(self.rfile.read(length)))
            except (ValueError,TypeError,KeyError) as e:return self.send_json(400,{'error':str(e)})
            if not gate.acquire(blocking=False):return self.send_json(429,{'error':'Inference busy; skip this frame and retry with fresh evidence'})
            try:
                self.send_json(200,client.decide(**data))
            except (ValueError,TypeError) as e:self.send_json(400,{'error':str(e)})
            except Exception as e:self.send_json(502,{'error':str(e)})
            finally:gate.release()

    return ThreadingHTTPServer(('127.0.0.1',port),Handler)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--model',default='omnijev-nemotron')
    p.add_argument('--base-url',default='http://127.0.0.1:1234')
    p.add_argument('--port',type=int,default=8765)
    args=p.parse_args()
    server=make_server(OmniJev(args.model,args.base_url),args.port)
    print(f'OmniJev local console: http://127.0.0.1:{server.server_port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()
