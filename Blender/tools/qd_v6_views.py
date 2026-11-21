"""Fixed review cameras. All positions are campus metres, X east, Y up, Z south."""
VIEWS=[
 ('sun-yuxian-garden','育贤广场 · 林园与仪式中轴',[-185,96,-176],[15,9,-77],53),
 ('sun-alumni-garden','校友广场 · 博物馆旁的文化林',[399,102,401],[240,10,523],51),
 ('sun-court','华岗苑与西停车场',[-219,83,194],[-76,8,125],49),
 ('sun-orchard','樱海湖与校园绿地',[154,117,-1062],[-38,10,-1151],52),
 ('sun-north','北区运动场',[52,92,-1058],[-92,11,-966],50),
 ('sun-assembly','学生会堂项目用地',[292,129,-530],[84,15,-643],49),
 ('sun-west-blocks','研究院与北区校园',[565,195,-1180],[45,18,-895],53),
 ('sun-library-tile','图书馆屋瓦迎光面',[200.64,62.77,-22.96],[179.02,57.11,-28.37],48),
 ('sun-huagang-tile','华岗苑陶瓦与檐口',[-24.67,24.01,179.71],[-46.30,16.41,181.59],48),
 ('coast-sandline','鳌山湾 · 从滨海步道看潮线',[510,55,-468],[656,-6,-482],49),
 ('sun-sea','从校园向鳌山湾',[-639,192,492],[266,21,16],51)]
def add_views(catalog):
    for key,name,eye,tgt,fov in VIEWS:
        x,y,z=tgt
        catalog.append(dict(key=key,name=name,group='夕照校园',x=x,y=y,z=z,h=16,r=35,viewpoint=dict(eye=eye,target=tgt,fov=fov),note='夕照环境下的实景地块与建筑材质。'))


    import json
    from pathlib import Path
    cfg=json.loads((Path(__file__).resolve().parents[1]/'data/夕照光照.json').read_text('utf8'))
    for loc in cfg['viewpoints']:
        x,y,z=loc['viewpoint']['target'];catalog.append(dict(x=x,y=y,z=z,h=32,r=38,**loc))
