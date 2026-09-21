"""Small counterfactual and out-of-candidate diagnostics, separate from pilot."""
import json
from pathlib import Path
from build_fixture import ROOT, png

cases=[]
for i in range(4):
    opts=['red','blue','green','insufficient evidence']
    opts=opts[i:]+opts[:i]
    cases.append(dict(id=f'perm-{i}',question='What color is the circle in the image?',
        options=opts,gold=chr(65+opts.index('red')),images=['data/assets/red.png'],
        state='An unreliable caption says that the circle is blue.',group='permutation',media_id='red'))
png(ROOT/'data/assets/yellow.png',[('circle',128,128,68,(235,200,20))])
cases.append(dict(id='out-of-candidate',question='What color is the circle?',
    options=['red','blue','none of the listed colors','insufficient evidence'],gold='C',
    images=['data/assets/yellow.png'],group='out_of_candidate',media_id='yellow'))
png(ROOT/'data/assets/blank.png',[])
cases.append(dict(id='blank',question='What color is the circle?',
    options=['red','blue','green','insufficient evidence'],gold='D',
    images=['data/assets/blank.png'],group='blank_evidence',media_id='blank'))
for reverse in [False,True]:
    images=['data/assets/red.png','data/assets/blue.png']
    if reverse:images.reverse()
    cases.append(dict(id=f'frames-{int(reverse)}',question='The two images are frames in chronological order. What color change happens from the first frame to the second?',
        options=['red to blue','blue to red','no change','insufficient evidence'],gold='B' if reverse else 'A',
        images=images,group='ordered_frames',media_id='red-blue-pair'))
cases.append(dict(id='hidden-audio',question='Is the object in this image making a sound?',
    options=['yes','no','insufficient evidence'],gold='C',images=['data/assets/red.png'],
    group='unobservable_property',media_id='red'))
(ROOT/'data/stress.json').write_text(json.dumps(cases,indent=2)+'\n')
print(f'Wrote {len(cases)} stress cases')
