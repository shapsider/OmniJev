"""Download public annotation/image tables and verify known source hashes."""
import hashlib
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FILES=[
    ('MMStar.tsv','https://huggingface.co/datasets/Lin-Chen/MMStar/resolve/main/MMStar.tsv','sha256','38a99f4a33743665e6990961a9a0072b07f7ac6a74d1555b43c4f82145377cb4'),
    ('mmad.json','https://huggingface.co/datasets/jiang-cc/MMAD/resolve/main/mmad.json','sha256','639343b491bc67b2abb3c5d719f221ce27f83b2ed97948f4e88055aaa31f1c1e'),
    ('MMBench_DEV_EN.tsv','http://opencompass.openxlab.space/utils/VLMEval/MMBench_DEV_EN.tsv','md5','b6caf1133a01c6bb705cf753bb527ed8'),
    ('streamingbench-real.csv','https://huggingface.co/datasets/mjuicem/StreamingBench/resolve/main/StreamingBench/Real_Time_Visual_Understanding.csv','git-sha1','4f5de97f62999210055c841ce66ef4efc30adf86'),
]


def check(blob,algorithm,expected):
    if algorithm=='git-sha1':
        result=hashlib.sha1(b'blob '+str(len(blob)).encode()+b'\0'+blob).hexdigest()
    else:result=hashlib.new(algorithm,blob).hexdigest()
    if result!=expected:raise ValueError('Public source checksum mismatch: '+result)


def main():
    (ROOT/'data').mkdir(exist_ok=True)
    for name,url,algorithm,expected in FILES:
        path=ROOT/'data'/name
        if path.exists():
            check(path.read_bytes(),algorithm,expected)
            print('Verified existing',name,flush=True)
            continue
        with urllib.request.urlopen(url,timeout=180) as response:blob=response.read()
        check(blob,algorithm,expected)
        temporary=path.with_suffix(path.suffix+'.part')
        temporary.write_bytes(blob)
        temporary.replace(path)
        print('Downloaded and verified',name,len(blob),'bytes',flush=True)


if __name__=='__main__':main()
