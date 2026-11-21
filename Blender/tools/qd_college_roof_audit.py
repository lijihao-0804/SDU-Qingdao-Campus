"""Rebuild the academic roof evidence from editable geometry and source support footprints."""
import math
import sys,json,time
from pathlib import Path
from shapely.geometry import Polygon
from shapely.affinity import translate
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'tools'))
import qd_colleges
from qd_geometry import record_components
record_components.set(True)
idx=qd_colleges.academic_index()
data=json.loads((root/'data/map/campus.json').read_text('utf8'))
rows=[(r,*idx[r['id']]) for r in data['buildings'] if r['id'] in idx]
def get(row,mod):
 cx,cz=row['center'];p=translate(Polygon(row['poly'],row.get('holes',[])),-cx,-cz)
 sh,h=mod.build(row,p);return p,sh,h

import numpy as np, shapely
from shapely.geometry import LineString,box,Point
from shapely.ops import unary_union
from collections import Counter,defaultdict
import importlib.util
v3=root.parent/'春日校园与海岸-v3'
def baseline(module):
 name=module.__name__+'_roof_baseline';sp=importlib.util.spec_from_file_location(name,v3/'tools'/(module.__name__+'.py'));m=importlib.util.module_from_spec(sp);sys.modules[name]=m;sp.loader.exec_module(m);return m
oldmods={md.__name__:baseline(md) for md in {m for m,_ in idx.values()}} if v3.is_dir() else {}
weather={'主瓦坡外表面','连接翼防水顶面','平台周缘金属泛水','有支撑的设备平台防水面'}
def groups(s):
 out=defaultdict(list)
 for mat,(vs,_,ids) in s.parts.items():
  tri=np.asarray(vs,dtype=float)[np.asarray(ids,dtype=np.int64).reshape(-1,3)]
  for label,a,b in s.components.get(mat,()):out[label].append(tri[a:b])
 return {k:np.concatenate(v) for k,v in out.items()}
def sel(g,labels):return np.concatenate([g[k] for k in labels if k in g])
def orientation(t):return np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0])[:,1]
def projection(tri):
 if not len(tri):return Polygon()
 f=abs(orientation(tri))>1.e-9
 xy=tri[f][:,:,[0,2]]
 return shapely.union_all(shapely.polygons(xy),grid_size=.00000001)
def heights(tri):
 return np.round([tri[:,:,1].min(),tri[:,:,1].max()],3).tolist()
def elevation(x,z,t):
 a,b,c=t[:,0,:],t[:,1,:],t[:,2,:]
 den=(b[:,2]-c[:,2])*(a[:,0]-c[:,0])+(c[:,0]-b[:,0])*(a[:,2]-c[:,2])
 m=np.abs(den)>1.e-8;den=np.where(m,den,1.)
 l1=((b[:,2]-c[:,2])*(x-c[:,0])+(c[:,0]-b[:,0])*(z-c[:,2]))/den
 l2=((c[:,2]-a[:,2])*(x-c[:,0])+(a[:,0]-c[:,0])*(z-c[:,2]))/den
 hit=m&(l1>=-1.e-7)&(l2>=-1.e-7)&(l1+l2<=1.+1.e-7)
 if not hit.any():return None
 yh=l1*a[:,1]+l2*b[:,1]+(1-l1-l2)*c[:,1]
 return round(float(max(yh[hit])),3)
EMPTY=np.empty((0,3,3),dtype=float)


def connected_caps(tri):
 """Count actual, connected roof hoods; several named faces may form one hood."""
 parents={}
 def find(k):
  while parents[k]!=k:
   parents[k]=parents[parents[k]];k=parents[k]
  return k
 for face in tri:
  keys=[tuple(q) for q in np.round(face,7)]
  for k in keys:parents.setdefault(k,k)
  root_id=find(keys[0])
  for k in keys[1:]:parents[find(k)]=root_id
 return len({find(k) for k in parents})


class TriangleHeights:
 """Independent vertical hits on upward or downward triangles, including their shared edges."""
 def __init__(self,tri):
  tri=tri[abs(orientation(tri))>1.e-9]
  self.index=shapely.STRtree(shapely.polygons(tri[:,:,[0,2]]))
  norms=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
  self.sx=-norms[:,0]/norms[:,1];self.sz=-norms[:,2]/norms[:,1]
  self.offset=tri[:,0,1]-self.sx*tri[:,0,0]-self.sz*tri[:,0,2]
 def at(self,q):
  ans=np.full(len(q),-np.inf)
  i,j=self.index.query(shapely.points(q[:,0],q[:,2]),predicate='dwithin',distance=1.e-7)
  np.maximum.at(ans,i,self.sx[j]*q[i,0]+self.sz[j]*q[i,2]+self.offset[j])
  if not np.isfinite(ans).all():raise ValueError('垂直射线没有击中对应的实体三角网格')
  return ans


def audit_windows(g,ro,weather_triangles):
 roof=TriangleHeights(weather_triangles)
 dual=[g[k] for k in ('老虎窗双坡盖瓦','红瓦小坡顶') if k in g]
 dual_count=connected_caps(np.concatenate(dual) if dual else EMPTY)
 arc=g.get('圆拱老虎窗红瓦筒壳',EMPTY)
 arc_count=connected_caps(arc)
 if dual_count!=len(ro.dormer_strip_counts):raise ValueError('双坡窗独立顶盖数与实际封板施工组数不符')
 skirt={'双坡':{side:'老虎窗'+side+'墙贴坡封板' for side in ('前','后','侧')},
        '圆拱':{'前':'圆拱老虎窗石质前脸','后':'圆拱老虎窗后墙贴坡封板','侧':'圆拱老虎窗瓦面接边'}}
 under=g.get('圆拱老虎窗筒瓦檐底',EMPTY)
 if arc_count and not len(under):raise ValueError('圆拱窗没有实体檐底')
 soffit=TriangleHeights(under) if arc_count else None
 quant={};depths=[];edges=[];upper_error=0.
 for kind,count in (('双坡',dual_count),('圆拱',arc_count)):
  info={}
  for side,label in skirt[kind].items():
   mesh=g.get(label,EMPTY)
   if not count:
    if len(mesh):raise ValueError(f'没有{kind}顶盖，却有{side}封板')
    info[side]={'strips':0,'rays':0,'minUnderlapM':None};continue
   if not len(mesh) or len(mesh)%2:raise ValueError(f'{kind}窗的{side}封板缺失或三角片不成对')
   q=mesh.reshape(-1,2,3,3)
   if kind=='双坡' and len(q)!=sum(a[side] for a in ro.dormer_strip_counts):
    raise ValueError('双坡窗有一段已登记的贴坡封板缺失')
   a,b=q[:,0,0],q[:,0,1];fs=np.array([.02,.5,.98])[None,:,None]
   sample=(a[:,None,:]+fs*(b-a)[:,None,:]).reshape(-1,3)
   diff=roof.at(sample)-sample[:,1];depths.extend(diff)
   info[side]={'strips':len(q),'rays':len(diff),'minUnderlapM':round(float(diff.min()),5)}
   if kind=='圆拱':
    a,b=q[:,1,2],q[:,0,2]
    sample=(a[:,None,:]+fs*(b-a)[:,None,:]).reshape(-1,3)
    upper_error=max(upper_error,float(np.max(abs(soffit.at(sample)-sample[:,1]))))
    edges.extend(tuple((p[0],p[2]) for p in pair) for pair in zip(a,b))
  quant[kind]=info
 arc_qa={}
 if arc_count:
  rim=projection(arc).boundary
  rimlines=shapely.union_all(shapely.linestrings(np.asarray(edges)))
  missing=rim.difference(rimlines.buffer(.0015)).length
  # Each outer-shell vertex has a real lower-skin vertex at the same X/Z.
  def ymap(tt):return {tuple(np.round(v[[0,2]],7)):v[1] for v in tt.reshape(-1,3)}
  topmap,undermap=ymap(arc),ymap(under)
  if topmap.keys()!=undermap.keys():raise ValueError('圆拱筒瓦上下面拓扑不对应')
  thick=np.array([v-undermap[k] for k,v in topmap.items()])
  fascia=g.get('圆拱老虎窗筒瓦封檐',EMPTY)
  if not len(fascia):raise ValueError('圆拱筒瓦外缘缺少封檐')
  cap_lines=[]
  for t in fascia:
   uv=np.unique(t[:,[0,2]],axis=0)
   if len(uv)==2 and np.ptp(t[:,1])>=float(thick.min())-1.e-5:cap_lines.append(uv)
  cap_union=shapely.union_all(shapely.linestrings(np.asarray(cap_lines)))
  open_cap=rim.difference(cap_union.buffer(.0015)).length
  inverted=int((orientation(arc)<-1.e-7).sum()+(orientation(under)>1.e-7).sum())
  if missing>.008 or open_cap>.008 or upper_error>.001 or thick.min()<.06 or inverted:
   raise ValueError(f'圆拱窗封边不连续：墙没抵檐{missing:.4f}米，筒口缺边{open_cap:.4f}米，上口错高{upper_error:.4f}米')
  arc_qa=dict(roofSoffitThicknessM=np.round([thick.min(),thick.max()],4).tolist(),roofRimLengthM=round(rim.length,3),
              uncoveredWallToSoffitLengthM=round(missing,5),unsealedTileFasciaLengthM=round(open_cap,5),
              maxWallToSoffitHeightGapM=round(upper_error,5),reversedCapOrSoffitTriangles=inverted)
 # The earlier reports expose the front/back/side roll-up. Keep it and retain the split by roof type.
 combined={}
 for side in ('前','后','侧'):
  pieces=[q[side] for q in quant.values()]
  combined[side]=dict(strips=sum(a['strips'] for a in pieces),rays=sum(a['rays'] for a in pieces),
                      minUnderlapM=min((a['minUnderlapM'] for a in pieces if a['minUnderlapM'] is not None),default=None))
 minimum=float(np.min(depths)) if depths else None
 return dict(windows=dual_count+arc_count,dualPitchWindows=dual_count,archedWindows=arc_count,
             quantities=combined,byShape=quant,archedPerimeter=arc_qa,
             minUnderlapM=round(minimum,5) if minimum is not None else None,
             verified=minimum is None or minimum>=.080,
             method='按独立相连顶盖计窗；逐一解包前墙、后墙和两侧封板的下边，在每小段2%、50%、98%处对主瓦面三角网格发射垂直射线。圆拱另核对弧形下檐与墙顶吻合、全部圆筒口封边、檐底厚度与法线。真正无盖无封板的类型计为零。')

locations={p['key']:p for p in json.loads((root/'data/locations.json').read_text('utf8'))}
allrows=[]
for row,mod,sp in rows:
 p,s,h=get(row,mod);g=groups(s);ro=s.college_roof
 t=sel(g,weather);w=projection(t)
 scaffold=projection(g['承重楼板上盖']);soff=projection(g['外挑檐底'])
 courtyard=p.convex_hull.difference(p.buffer(ro.overhang+.07,join_style=2))
 edge=ro.outer.difference(p)
 prev={};old_roof=None
 if mod.__name__ in oldmods:
  oldmod=oldmods[mod.__name__];old,_=oldmod.build(row,p);prev=groups(old)
  from qd_geometry import Shape
  old_roof=Shape('V3屋面原网格')
  if mod.__name__=='qd_dizhou':oldmod.crown(old_roof,p,ro.height,oldmod.KEYS[sp['key']])
  else:oldmod.roof(old_roof,p,oldmod.BY_ID[sp['osm']])
 profile=[]
 # Sample two representative transects per building, one through the major terrace
 # and one through the re-entrant front courtyard. Empty rays mean open to the sky.
 largest=max((d for u in ro.sections for _,d in u.decks),key=lambda d:d.area)
 ctr=largest.centroid
 cort_pts=[q for q in (courtyard.geoms if hasattr(courtyard,'geoms') else [courtyard]) if q.area>8 and q.geom_type=='Polygon']
 court=max(cort_pts,key=lambda z:z.area).representative_point() if cort_pts else Point(*p.representative_point().coords[0])
 for tag,co in [('最大平台横断面',ctr),('开敞凹院横断面',court)]:
  if ro.axis=='x':a=(co.x,p.bounds[1]-1);b=(co.x,p.bounds[3]+1)
  else:a=(p.bounds[0]-1,co.y);b=(p.bounds[2]+1,co.y)
  line=LineString([a,b]);cc=[]
  for d in np.linspace(0,line.length,int(math.ceil(line.length/1.0))+1):
   q=line.interpolate(float(d));cc.append(elevation(q.x,q.y,t))
  profile.append(dict(name=tag,start=[round(a[0],3),round(a[1],3)],end=[round(b[0],3),round(b[1],3)],heights=cc,
                      sampleIntervalM=round(line.length/(len(cc)-1),4)))
 wing_sunk=[]
 for u in ro.sections:
  for _,d in u.decks:
   q=d.representative_point();height=elevation(q.x,q.y,t);wing_sunk.append(round(u.high-height,4) if height is not None else None)
 rc=dict(key=sp['key'],name=sp['name'],roofSupportAreaM2=round(p.area,3),eaveOverhangM=ro.overhang,
         nominalWeatherAreaM2=round(ro.outer.area,3),supportMissingFromStructureM2=round(p.difference(scaffold).area,5),
         missingBodyUnderWeatherM2=round(p.difference(w).area,5),missingOuterWeatherM2=round(ro.outer.difference(w).area,5),
         unsealedEaveSoffitM2=round(edge.difference(soff).area,5),upwardWeatherTriangles=int((orientation(t)>0).sum()),
         downwardWeatherTriangles=int((orientation(t)<-1.e-8).sum()),primaryCourseHeightM=heights(t),
         exemptOpenCourtAndRecessM2=round(courtyard.area,3),weatherInsideProtectedOpeningM2=round(w.intersection(courtyard).area,6),
         roofGroups=len(ro.sections),lowerFlatConnectors=sum(u.connector for u in ro.sections),serviceTerraces=len(wing_sunk),
         measuredCopingToDeckM=wing_sunk,photoBlueBands=len(g.get('屋面带状构件支座',()))//12,
         retainedPlanHoles=len(p.interiors),transects=profile)
 # A pre-revision audit is optional when the prior release is installed next to v4.
 if old_roof is not None:
  old_all=groups(old_roof)
  bt=np.concatenate(list(old_all.values()))
  old_union=projection(bt[orientation(bt)>1.e-7])
  baseline_result={'missingBodyUnderVisibleOrStructuralRoofM2':round(p.difference(old_union).area,5)}
  if mod.__name__=='qd_dizhou':
   old_gable=prev.get('中央横向红瓦屋脊',np.empty((0,3,3)))
   tt=old_all['铺面']
   yspan=np.ptp(tt[:,:,1],axis=1)
   flat_tri=tt[(yspan<1.e-6)&(orientation(tt)>0)]
   flat_levels=sorted({round(float(a),4) for a in flat_tri[:,0,1]})
   crest_heights=sorted({round(float(a),4) for a in tt[yspan>1.,:,1].max(1) if a>ro.height+2.})
   # A few fan triangles happen to be horizontal at the crest. A terrace must cover
   # a substantial part of this old model, separate from the lower full-footprint slab.
   deck_levels=[yy for yy in flat_levels if orientation(flat_tri[np.isclose(flat_tri[:,0,1],yy,atol=.0001)]).sum()/2>p.area*.20]
   terrace=max(deck_levels)
   baseline_result.update(terraceLevel=terrace,measuredValleyToLowerAndUpperHipM=[round(crest_heights[0]-terrace,3),round(crest_heights[-1]-terrace,3)],
                          invertedEntryGableTriangles=int((orientation(old_gable)<0).sum()))
  baseline_result['explicitOverhangSoffitTriangles']=sum(len(a) for k,a in old_all.items() if '檐底' in k)
  rc['v3MeshMeasurements']=baseline_result
 from qd_college_roofs import PLANS
 policy=PLANS[sp['osm']]
 rc['photoPlan']={'roofValleysLocalM':policy[2],'rectanglesLocalXZ':policy[3],'mainAxis':policy[1],
                  'layoutRotationDegrees':round(ro.angle,4),'flatLinkIndicesNorthOrWestFirst':policy[6]}
 base=locations[sp['key']]['y'];x,z=row['center'];nx,nz=mod.VIEWS[sp['key']]['normal'];dist=math.hypot(nx,nz);nx,nz=nx/dist,nz/dist
 size=max(p.bounds[2]-p.bounds[0],p.bounds[3]-p.bounds[1])
 def vals(xx):return [round(v,4) for v in xx]
 rc['views']={'roof_plan':dict(eye=vals([x,base+h+size*1.53,z+.04]),target=vals([x,base+h-.50,z]),fov=42),
              'roof_edge':dict(eye=vals([x+(nx+.36*nz)*size*.70,base+h+size*.19,z+(nz-.36*nx)*size*.70]),
                               target=vals([x,base+h-1.15,z]),fov=53)}
 rc['upwardSlopeAndDeckTriangles']=int((orientation(t)>1.e-8).sum())
 rc['pitchedGableCapDownwardTriangles']=int(sum((orientation(v)<-1.e-7).sum() for k,v in g.items() if k in ('中央横向红瓦屋脊','门厅红瓦双坡','老虎窗双坡盖瓦','红瓦小坡顶')))
 rc['newPhysicalHipsTriangles']=len(g.get('红瓦斜脊压瓦',()))
 rc['dormerWalls']=audit_windows(g,ro,t)
 rc['verified']=bool(rc['missingBodyUnderWeatherM2']<.001 and rc['missingOuterWeatherM2']<.001 and rc['supportMissingFromStructureM2']<.001 and rc['unsealedEaveSoffitM2']<.001 and rc['weatherInsideProtectedOpeningM2']<.001 and rc['downwardWeatherTriangles']==0 and rc['pitchedGableCapDownwardTriangles']==0 and rc['dormerWalls']['verified'])
 print(sp['name'],rc['missingOuterWeatherM2'],rc['unsealedEaveSoffitM2'],rc['verified'],flush=True)
 allrows.append(rc)

report={
 'title':'v5 会文、淦昌苑、第周苑屋面、双坡窗与圆拱窗逐栋核验',
 'units':'X东 Z南，Y高，单位米。屋面矩形在各楼平面中心局部坐标中，部件用各楼主轴微调旋转；剖面采自最终实体三角网格。',
 'references':[
  {'title':'用户本地三段航拍，第2段00:46.50及第3段00:26.50–00:42.50','use':'区分拱形与三角屋窗，核对蓝灰色长棚和设备平台。','index':'data/v5_video_colleges.json'},
  {'title':'Esri World Imagery，正射底图','url':'https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9','use':'独立识别14栋灰色设备平台、横脊、连接翼和带状屋面构件，未离线分发影像瓦片。'},
  {'title':'周青先2019年校园航拍','url':'https://house.qingdaonews.com/wap/2019-09/16/content_20763146.htm','files':['实景参照/会文与淦昌/2019_淦昌六座_原图裁切.png','实景参照/会文与淦昌/2019_会文广场双楼_原图裁切.png']},
  {'title':'观海新闻2021年南向航拍','url':'https://www.dailyqd.com/guanhai/121068_2.html','files':['实景参照/第周苑/区域-2021-六楼南向航拍.jpg','实景参照/会文与淦昌/2021_淦昌前后院楼_原图裁切.png']},
  {'title':'山东大学青岛校区楼位图与工程档案','url':'https://hq.qd.sdu.edu.cn/info/1053/1824.htm','use':'核对第周苑A至F分组与楼位。'}],
 'interpretation':'部件立面和入口铭牌沿用原始实景登记。图中灰色顶面、连接翼和内凹的露天通行院分开制作。蓝灰长条的颜色、排列与体量可辨，采光、集热或设备用途尚无逐项竣工资料。高度、屋顶微小管罩、泛水及屋面构造尺寸属于建模估计。',
 'method':'从十四栋原生成函数启用 componentRanges 后取每一个真实三角片。主瓦坡/防水面/泛水合并为外露围护投影，单独检验混凝土盖板与檐底。对每栋最大平台和凹院分别发射约1米间距的垂直射线，记录最高实际交点高度，null 表示该射线可直达露天。检查平面法线，比较顶面和老虎窗的封檐。投影求并的精度为1e-8米；网格闭合数值容差0.001平方米。凹院保护区扣除真实檐出挑及7厘米数值余量。',
 'findings':['原会文双楼的两端与中段被统一斜屋面连接，灰色平顶连接翼位置与航拍不符。','原第周苑的灰色顶面在周围坡脊下方约2.14至2.64米，形成深槽；第周C、D、E、F的中央双坡三角片法线向下。','现有灰色设备平台均为实体承托的屋面，其与收边顶面高差约0.23米。每栋外挑檐有下表面以及可辨的封板；山墙和老虎窗补齐相应侧壁、檐底和前沿。'],
 'buildings':allrows,'areaUnits':'m²','verifiedBuildings':sum(r['verified'] for r in allrows)}
report['dormerSummary']={key:sum(r['dormerWalls'][key] for r in allrows) for key in ('windows','dualPitchWindows','archedWindows')}
report['dormerSummary']['edgeRays']=sum(q['rays'] for r in allrows for q in r['dormerWalls']['quantities'].values())
if report['verifiedBuildings']!=14:raise RuntimeError([r['name'] for r in allrows if not r['verified']])
dest=root/'data/v5_academic_roofs.json'
dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf8')
print('Verified',report['verifiedBuildings'],'individual roof envelopes',report['dormerSummary'],dest)
