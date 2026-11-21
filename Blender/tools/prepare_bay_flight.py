"""Sample the curated route at display time and place world-anchored captions."""
from pathlib import Path
import json, math
import numpy as np
from flight_route import build_route

ROOT=Path(__file__).resolve().parents[1]
FPS=30

def project(frames, anchor):
    eye=np.array([f['eye'] for f in frames]);forward=np.array([f['target'] for f in frames])-eye
    forward/=np.linalg.norm(forward,axis=1)[:,None]
    right=np.cross(forward,[0,1,0]);right/=np.linalg.norm(right,axis=1)[:,None]
    up=np.cross(right,forward);v=np.array(anchor)-eye
    depth=(forward*v).sum(axis=1)
    k=540/np.maximum(.01,depth)/np.tan(np.radians([f['fov']/2 for f in frames]))
    return np.c_[960+k*(v*right).sum(axis=1),540-k*(v*up).sum(axis=1),depth]

def runs(mask):
    borders=np.flatnonzero(np.diff(np.r_[False,mask,False].astype(int))).reshape(-1,2)
    return [(a,b) for a,b in borders if b-a>=12]

def introduction_cues(chapters, frame_count):
    """Give each introduction enough reading time while its building remains in view."""
    copy=json.loads((ROOT/'data/海岸航线解说.json').read_text('utf8'))
    selected=[(i,chapter) for i,chapter in enumerate(chapters) if chapter['key'] in copy]
    cues=[]
    for k,(i,chapter) in enumerate(selected):
        text=copy[chapter['key']]
        first=chapter['startFrame']
        last=chapter['endFrame']
        if text.get('through'):
            tail=next(item for item in chapters[i:] if item['key']==text['through'])
            last=tail['endFrame']
        previous_end=cues[-1]['end']+4 if cues else 0
        next_start=selected[k+1][1]['startFrame'] if k+1<len(selected) else frame_count+4
        start=max(previous_end,0,first-8)
        end=min(frame_count,next_start-4,max(last+7,start+round(FPS*(2.05+len(text['caption'])/10))))
        if end<=start: raise ValueError('Overlapping introductions for '+chapter['key'])
        cues.append(dict(key=chapter['key'],title=text['title'],caption=text['caption'],start=start,end=end))
    return cues

def main():
    places={p['key']:p for p in json.loads((ROOT/'data/locations.json').read_text('utf8'))}
    route=build_route(places)
    assert 0<route.duration<=135
    n=int(round(FPS*route.duration))
    frames=[]
    for i in range(n):
        s=route.sample(i/FPS)
        frames.append(dict(eye=[round(float(v),6) for v in s['position']],target=[round(float(v),6) for v in s['target']],fov=round(float(s['fov_deg']),6)))
    labels=[];chapters=[];busy=np.zeros(n,dtype=bool)
    for s in route.shots:
        a,b=round(s['label_start']*FPS),min(n,round(s['label_end']*FPS))
        title=s['title'];sub=s.get('subtitle','');anchor=s['anchor']
        coords=project(frames[a:b],anchor)
        margin=25+max(23*len(title),17*len(sub))/2
        mask=(coords[:,2]>2)&(coords[:,0]>margin)&(coords[:,0]<1920-margin)&(coords[:,1]>(94 if sub else 76))&(coords[:,1]<995)
        visible=runs(mask)
        if visible:
            left,right=max(visible,key=lambda v:v[1]-v[0])
            if s['key']!='overview':
                labels.append(dict(title=title,subtitle=sub,anchor=anchor,start=int(a+left),end=int(a+right),kind='public',key=s['key']))
            poster=a+(left+right)//2
        else:
            poster=(a+b)//2
            if s['key'] not in ('waterfront-beach','overview'):
                raise ValueError('No visible label interval: '+title)
        chapters.append(dict(key=s['key'],title=title,posterFrame=int(poster),startFrame=a,endFrame=b))
        busy[max(0,a-5):min(n,b+6)]=True
    # A passing college may carry a small second name during a gap in the main
    # captions. Only foreground roofs near the middle of the picture qualify.
    for key in ('way-970257672','way-970257673','way-868015915','way-970257670','way-868015918','huagang','way-1020621360'):
        p=places[key];position=[p['x'],p['y']+p['h']+1.2,p['z']]
        v=project(frames,position)
        mask=~busy & (v[:,2]>45)&(v[:,2]<220)&(v[:,0]>160)&(v[:,0]<1760)&(v[:,1]>135)&(v[:,1]<860)
        visible=[(a,b) for a,b in runs(mask) if b-a>=40]
        if not visible:continue
        a,b=max(visible,key=lambda q:q[1]-q[0]);b=min(b,a+83)
        labels.append(dict(title=p['name'],anchor=position,start=int(a),end=int(b),kind='passing',key=key))
        busy[max(0,a-14):min(n,b+15)]=True
    assert any(l.get('subtitle')=='信息科学与工程学院' and l['end']-l['start']>=40 for l in labels)
    plan=dict(fps=FPS,scope='core',duration=n/FPS,holdStartFrame=round(route.hold_start*FPS),frames=frames,labels=labels,chapters=chapters,lowerThirds=introduction_cues(chapters,n))
    dest=ROOT/'data/海岸航线.json'
    dest.write_text(json.dumps(plan,ensure_ascii=False,separators=(',',':')),'utf8')
    print(n,'frames;',len(labels),'captions;',n/FPS,'seconds')
if __name__=='__main__':main()
