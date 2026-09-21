"""HTTP integration tests with a deterministic stub; not model-quality evidence."""
import json
import threading
import unittest
import urllib.request
import urllib.error
from omnijev.server import make_server


class Stub:
    model='test';base_url='http://127.0.0.1:1'
    def __init__(self):self.started=threading.Event();self.release=threading.Event()
    def decide(self,**request):
        self.started.set();self.release.wait(3)
        return {'status':'decided','action':'test'}


class HTTPContracts(unittest.TestCase):
    def setUp(self):
        self.client=Stub();self.server=make_server(self.client,0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base=f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.client.release.set();self.server.shutdown();self.server.server_close();self.thread.join()

    def post(self,payload,origin=None):
        headers={'Content-Type':'application/json'}
        if origin:headers['Origin']=origin
        req=urllib.request.Request(self.base+'/decide',json.dumps(payload).encode(),headers)
        try:
            with urllib.request.urlopen(req,timeout=5) as r:return r.status,json.load(r)
        except urllib.error.HTTPError as e:return e.code,json.load(e)

    def test_busy_request_is_rejected_instead_of_queued(self):
        first=[]
        t=threading.Thread(target=lambda:first.append(self.post({})));t.start()
        self.assertTrue(self.client.started.wait(2))
        self.assertEqual(self.post({})[0],429)
        self.client.release.set();t.join();self.assertEqual(first[0][0],200)

    def test_local_files_and_cross_origin_rejected(self):
        self.assertEqual(self.post({'images':['/etc/passwd']})[0],400)
        self.assertEqual(self.post({},origin='https://example.com')[0],403)

    def test_unknown_fields_and_bad_policy_return_400(self):
        self.assertEqual(self.post({'surprise':True})[0],400)
        self.assertEqual(self.post({'policy':{'min_margin':-1}})[0],400)


if __name__=='__main__':unittest.main()
