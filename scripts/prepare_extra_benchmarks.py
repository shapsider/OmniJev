"""Fixed, resource-bounded public pilot subsets; not official leaderboard runs."""
import ast
import base64
import collections
import csv
import hashlib
import json
import random
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from remote_zip import open_zip

ROOT=Path(__file__).resolve().parents[1]
SEED=20260920


def digest(blob):return hashlib.sha256(blob).hexdigest()


def save_manifest(out,dataset,source,cases,notes,source_file):
    out.mkdir(parents=True,exist_ok=True)
    manifest=dict(dataset=dataset,source=source,source_sha256=digest(source_file.read_bytes()),seed=SEED,cases=cases,
        protocol=dict(methods=['omnijev','direct','json','reasoning'],temperature=0,thinking_max_tokens=20480,thinking_temperature=0.6,thinking_top_p=0.95,
            direct_max_tokens=4,json_max_tokens=32,sampling=notes,cache='natural cache; globally shuffled sequential requests',
            timing='client encoding + HTTP + answer parsing; excludes offline media preparation and model loading'))
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print(dataset,len(cases),'cases ready',flush=True)


def mmbench(out=None):
    source=ROOT/'data/MMBench_DEV_EN.tsv'
    assert hashlib.md5(source.read_bytes()).hexdigest()=='b6caf1133a01c6bb705cf753bb527ed8'
    csv.field_size_limit(100000000)
    rows=list(csv.DictReader(source.open(),delimiter='\t'))
    indexed={r['index']:r for r in rows}
    groups=collections.defaultdict(list)
    for r in rows:
        if int(r['index'])<1000000:groups[r['category']].append(r)
    out=out or ROOT/'results/mmbench-public'
    (out/'images').mkdir(parents=True,exist_ok=True)
    rng=random.Random(SEED)
    cases=[]
    for category in sorted(groups):
        for r in rng.sample(groups[category],min(3,len(groups[category]))):
            image=r['image'];seen=set()
            while image.isdigit():
                if image in seen:raise ValueError('Cyclic image reference')
                seen.add(image);image=indexed[image]['image']
            blob=base64.b64decode(image,validate=True)
            path=out/'images'/(r['index']+('.png' if blob.startswith(b'\x89PNG') else '.jpg'))
            path.write_bytes(blob)
            options=[r[x] for x in 'ABCD' if r[x]]
            cases.append(dict(id='mmbench-'+r['index'],question=r['question'],state=r['hint'],options=options,
                gold=r['answer'],images=[str(path)],category=category,image_sha256=digest(blob)))
    save_manifest(out,'MMBench DEV EN pilot','https://github.com/open-compass/MMBench',cases,
        '3 canonical (index < 1000000) questions per category, seed fixed; one option order only. NOT official circular evaluation.',source)


def mmad(out=None):
    source=ROOT/'data/mmad.json'
    rows=json.loads(source.read_text());groups=collections.defaultdict(list)
    for key,r in rows.items():
        if key.startswith('DS-MVTec/'):
            for i,q in enumerate(r['conversation']):groups[q['type']].append((key,i,q))
    rng=random.Random(SEED);selected=[];used=set()
    for category in sorted(groups):
        candidates=groups[category][:];rng.shuffle(candidates);count=0
        for key,i,q in candidates:
            if key in used:continue
            selected.append((key,i,q));used.add(key);count+=1
            if count==5:break
    out=out or ROOT/'results/mmad-public';(out/'images').mkdir(parents=True,exist_ok=True)
    (out/'selection.json').write_text(json.dumps(selected,ensure_ascii=False,indent=2))
    z=open_zip('https://huggingface.co/datasets/jiang-cc/MMAD/resolve/main/DS-MVTec.zip',1663225174)
    cases=[]
    for key,i,q in selected:
        path=out/'images'/(digest(key.encode())[:16]+'.png')
        if not path.exists():path.write_bytes(z.read(key))
        blob=path.read_bytes()
        labels=sorted(q['Options'])
        assert labels==[chr(65+j) for j in range(len(labels))]
        cases.append(dict(id='mmad-'+digest((key+str(i)).encode())[:16],question=q['Question'],
            options=[q['Options'][x] for x in labels],gold=q['Answer'],images=[str(path)],
            category=q['type'],image_sha256=digest(blob),original_path=key))
        print('MMAD image',len(cases),'/',len(selected),flush=True)
    save_manifest(out,'MMAD DS-MVTec zero-shot pilot','https://huggingface.co/datasets/jiang-cc/MMAD',cases,
        '5 questions per annotation type, distinct images, DS-MVTec partition only; no reference images or domain knowledge; no previous QA answers.',source)


def streaming(out=None):
    import imageio_ffmpeg
    source=ROOT/'data/streamingbench-real.csv'
    rows=list(csv.DictReader(source.open()))
    out=out or ROOT/'results/streaming-public';(out/'videos').mkdir(parents=True,exist_ok=True);(out/'images').mkdir(exist_ok=True)
    url='https://huggingface.co/api/datasets/mjuicem/StreamingBench/tree/main'
    with urllib.request.urlopen(url,timeout=60) as f:entries=json.load(f)
    archives={};videos={}
    for entry in entries:
        if not entry['path'].startswith('Real-Time Visual Understanding_'):continue
        print('Indexing',entry['path'],flush=True)
        z=open_zip('https://huggingface.co/datasets/mjuicem/StreamingBench/resolve/main/'+urllib.parse.quote(entry['path']),entry['size'])
        archives[entry['path']]=z
        for info in z.infolist():
            m=re.fullmatch(r'sample_(\d+)/video\.mp4',info.filename)
            if m and info.compress_size<=100_000_000:
                videos[int(m[1])]=(entry['path'],info.filename,info.compress_size)
    groups=collections.defaultdict(list)
    for r in rows:
        video=int(re.search(r'_sample_(\d+)_',r['question_id'])[1])
        if video in videos:groups[r['task_type']].append((video,r))
    rng=random.Random(SEED);used=set();selected=[]
    for category in sorted(groups):
        options=groups[category][:];rng.shuffle(options);count=0
        for video,r in options:
            if video in used:continue
            selected.append((video,r));used.add(video);count+=1
            if count==2:break
    (out/'selection.json').write_text(json.dumps(selected,ensure_ascii=False,indent=2))
    cases=[]
    for video,r in selected:
        archive,member,size=videos[video]
        path=out/'videos'/f'{video}.mp4'
        if not path.exists():path.write_bytes(archives[archive].read(member))
        h,m,s=map(float,r['time_stamp'].split(':'));timestamp=h*3600+m*60+s
        # Uniform 8-frame window spanning at most 60 seconds. 0.1 s safety
        # offset keeps the selected frame before the annotated query boundary.
        end=max(0,timestamp-.1);start=max(0,end-60)
        times=[start+(end-start)*i/7 for i in range(8)]
        images=[];actual_times=[]
        for i,t in enumerate(times):
            frame=out/'images'/f'{video}-{i}.jpg'
            info=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','info','-copyts','-ss',str(t),'-i',str(path),
                '-frames:v','1','-vf',"showinfo,scale='min(512,iw)':'min(512,ih)':force_original_aspect_ratio=decrease",'-q:v','2',str(frame)],
                check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            pts=re.search(r'n:\s*0\s+pts:\s*\S+\s+pts_time:([0-9.e+-]+)',info.stderr)
            if not pts:raise RuntimeError('Cannot verify frame timestamp')
            actual=float(pts[1])
            if actual>timestamp:raise RuntimeError(f'Future frame at {actual} for query at {timestamp}')
            actual_times.append(actual)
            if not frame.exists():raise RuntimeError('Missing video frame')
            images.append(str(frame))
        options=[re.sub(r'^[A-Z][.：:]\s*','',x) for x in ast.literal_eval(r['options'])]
        cases.append(dict(id=r['question_id'],question=r['question'],
            state='Frames are chronological, sampled before the question time. Question time in seconds: '+str(timestamp)+'. Actual frame times: '+str(actual_times),
            options=options,gold=r['answer'],images=images,category=r['task_type'],
            image_sha256=digest(path.read_bytes()),video_id=video,query_timestamp=timestamp,frame_timestamps=times,actual_frame_timestamps=actual_times,
            frame_sha256=[digest(Path(p).read_bytes()) for p in images]))
        print('Streaming video',len(cases),'/',len(selected),flush=True)
    save_manifest(out,'StreamingBench causal 8-frame pilot','https://github.com/THUNLP-MT/StreamingBench',cases,
        '2 questions per task type; distinct videos; restricted to videos compressed <=100 MB. 8 chronological frames over a <=60 s window ending 0.1 s before query (earliest target up to 60.1 s before query); actual decoded frame timestamps verified <= query. No audio. Offline causal replay, not official full protocol or live stream. Offline decoding excluded from inference latency.',source)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset',choices=['mmbench','mmad','streaming'])
    parser.add_argument('--out',type=Path,help='New output directory for a fresh run')
    args=parser.parse_args()
    if args.out:args.out=args.out.resolve()
    if args.out and (args.out/'records.jsonl').exists():parser.error('Choose a new output directory; existing measurements are immutable.')
    {'mmbench':mmbench,'mmad':mmad,'streaming':streaming}[args.dataset](args.out)
