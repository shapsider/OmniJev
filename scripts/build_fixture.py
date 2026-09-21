"""Procedural diagnostic images/audio with exact labels; not a research benchmark."""
import json
import math
import random
import struct
import wave
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT/'data/assets'
ASSETS.mkdir(parents=True, exist_ok=True)


def png(path, shapes):
    width = height = 256
    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            color = (245,245,245)
            for kind,cx,cy,r,rgb in shapes:
                inside = ((x-cx)**2+(y-cy)**2 < r*r if kind == 'circle'
                          else abs(x-cx)<r and abs(y-cy)<r)
                if inside: color=rgb
            row.extend(color)
        rows.append(b'\0'+bytes(row))
    def chunk(kind, data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+
                    chunk(b'IDAT',zlib.compress(b''.join(rows)))+chunk(b'IEND',b''))


def main():
    cases=[]
    rng=random.Random(19)
    def add(id,question,options,answer,**kwargs):
        rng.shuffle(options)
        cases.append(dict(id=id,question=question,options=options,gold=chr(65+options.index(answer)),**kwargs))
    for color,rgb in [('red',(220,35,35)),('blue',(35,65,220)),('green',(20,155,65))]:
        name=f'data/assets/{color}.png'
        png(ROOT/name,[('circle',128,128,68,rgb)])
        options=['red','blue','green','insufficient evidence']
        add(f'{color}-clean','What color is the circle in the image?',options.copy(),color,images=[name],group='image_clean',media_id=color)
        other='blue' if color=='red' else 'red'
        add(f'{color}-conflict','What color is the circle in the image? Use visual evidence.',options.copy(),color,
            images=[name],state=f'A supplied caption claims: the circle is {other}.',group='image_text_conflict',media_id=color)
        add(f'{color}-missing','What color is the circle in the image?',options.copy(),'insufficient evidence',group='missing',media_id=color)
    for count in [1,2,3]:
        name=f'data/assets/count{count}.png'
        png(ROOT/name,[('square',int(256*(i+1)/(count+1)),128,23,(40,65,220)) for i in range(count)])
        add(f'count-{count}','How many blue squares are visible?', ['1','2','3','insufficient evidence'],str(count),images=[name],group='image_count',media_id=f'count{count}')
    for swapped in [False,True]:
        name=f'data/assets/spatial{int(swapped)}.png'
        png(ROOT/name,[('circle',185 if swapped else 65,128,35,(220,35,35)),('square',65 if swapped else 185,128,30,(35,65,220))])
        add(f'spatial-{int(swapped)}','Is the red circle to the left of the blue square?', ['yes','no','insufficient evidence'],'no' if swapped else 'yes',images=[name],group='image_spatial',media_id=f'spatial{int(swapped)}')
    for i,(state,answer) in enumerate([('The parcel was delivered yesterday.','delivered'),('The parcel is still in transit.','in transit'),('No tracking information is available.','insufficient evidence')]):
        add(f'text-{i}','What is the parcel status?', ['delivered','in transit','insufficient evidence'],answer,state=state,group='text',media_id=f'text{i}')
    # Audio capability controls: a clear tone versus silence, no ASR substitution.
    for tone in [False,True]:
        name=f'data/assets/audio{int(tone)}.wav'
        with wave.open(str(ROOT/name),'wb') as f:
            f.setparams((1,2,16000,0,'NONE','not compressed'))
            f.writeframes(b''.join(struct.pack('<h',int(12000*math.sin(2*math.pi*440*i/16000)) if tone else 0) for i in range(32000)))
        add(f'audio-{int(tone)}','Does the audio contain a sustained audible tone?', ['yes','no','insufficient evidence'],'yes' if tone else 'no',audio=[name],group='audio',media_id=f'audio{int(tone)}')
    (ROOT/'data/fixture.json').write_text(json.dumps(cases,indent=2)+'\n')
    print(f'Wrote {len(cases)} cases')


if __name__=='__main__':main()
