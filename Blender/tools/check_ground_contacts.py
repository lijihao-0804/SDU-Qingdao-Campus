"""Compare measured support to exported ground, paving, planted terraces and beach triangles."""
import argparse
import hashlib
import json
from pathlib import Path

from check_sport_facilities import read_model
from qd_ground_contacts import Geometry, LIMITS, SAMPLE_STEP, evaluate, ground_scene

ROOT=Path(__file__).resolve().parents[1]
MODEL=ROOT/'山东大学青岛校区.glb'
REPORT=ROOT/'data'/'地面接触核验.json'

def inspect(path):
    scene=read_model(path)
    result,_,_=evaluate(Geometry(scene.doc,scene.raw))
    with path.open('rb') as stream:
        result['glbSha256']=hashlib.file_digest(stream,'sha256').hexdigest()
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--glb',type=Path,default=MODEL)
    ap.add_argument('--before',type=Path,help='The unmodified, baseline GLB')
    ap.add_argument('--output',type=Path,default=REPORT)
    ap.add_argument('--preview-repair',type=Path,help='Apply the contact pass alone to --before and serialize this separate GLB before measuring it')
    opts=ap.parse_args()
    if opts.preview_repair:
        if not opts.before or opts.preview_repair.resolve()==opts.before.resolve():
            ap.error('preview-repair requires a distinct --before')
        scene=read_model(opts.before)
        preview=ground_scene(scene);scene.save(opts.preview_repair)
        print('Incremental repair',preview,flush=True)
        del scene
        opts.glb=opts.preview_repair
    else:preview=None
    old=json.loads(opts.output.read_text('utf-8')) if opts.output.exists() else {}
    before=inspect(opts.before) if opts.before else old.get('before')
    after=inspect(opts.glb)
    report=dict(method='实际 GLB 世界坐标三角面与铅垂射线求交。单位米。结构沿外沿分段，测两端与中点，检查实导出侧墙的顶边相接与底边埋入；植株逐实例以最低根部的中心近点与 X/Z 两轴极值顶点测离地，五点均高于容差才校正。',tolerancesM=LIMITS,
        edgeSamplingM={'default':1.5,**SAMPLE_STEP},horizontalTileToleranceM=.001,tidalApronReachM=1.25,before=before,after=after,
        designedClearances=['观海桥的桥面中跨和栏杆、拱廊与门洞、建筑屋檐和挑板允许离地，仅测支承构件。','地被在坡上的个别叶片、树冠和花枝、汽车底盘均允许悬起。停车车辆单列测轮底，以五点中首个触地点判定。','涂漆标线、网球网、灯具上部与海面波浪分别以路面、立柱、杆身和水域为载体。'],
        coverageLimits=['观海廊桥下部分水域未建海床。waterOnlyStations 单独记录桥墩底低于实际导出水面（初始动态帧）的站数及浸没深度，水深与承载地层未知。伸入潮水而距离既有潮下沙底不超过1.25m的末级台阶，侧趾斜落到沙面。','这是沿实模边缘有限间距的采样，最窄裂缝可位于采点之间。基础以最低结构层为准；分层楼身上方由本体支撑，不逐片检查窗台、挑檐与装饰。','树丛内部无独立节点的花朵、混合园林造景与球网柱等专用设施未逐件追踪。运动标线、网柱等保留原专项检查。','仅纳入模型可辨识的地形、铺装与有高度筛选的种植池；卫星背景仅用于项目地形缺失处。底部完全埋藏与地面短程相交不作为悬空。'])
    if before:report['comparison']={k:{m:[before['categories'][k][m],v[m]] for m in ('overLimit','worstGapM')} for k,v in after['categories'].items()}
    if preview:report['incrementalTrial']=preview
    opts.output.parent.mkdir(parents=True,exist_ok=True)
    opts.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),'utf-8')
    print('Audit:',[(k,v['overLimit'],v['worstGapM'],v['uncovered']) for k,v in after['categories'].items()],flush=True)
    if any(v['overLimit'] or v['noSampleNodes'] or v['uncovered']>v['waterOnlyStations'] for v in after['categories'].values()):raise SystemExit(1)

if __name__=='__main__':main()

