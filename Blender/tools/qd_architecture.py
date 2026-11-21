"""Footprint-faithful residential and academic buildings, facade trim and lettering."""
import math
from functools import lru_cache
from shapely.geometry import Polygon,MultiPolygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
from qd_geometry import Shape
from qd_terrain import face,polygons

@lru_cache(maxsize=256)
def letters(text):
    from matplotlib.textpath import TextPath
    from matplotlib.font_manager import FontProperties
    import os
    font=FontProperties(fname=os.path.join(os.environ.get('WINDIR','C:/Windows'),'Fonts','simhei.ttf'))
    path=TextPath((0,0),text,prop=font,size=1)
    geom=Polygon()
    for ring in path.to_polygons():
        if len(ring)>=4:geom=geom.symmetric_difference(Polygon(ring).buffer(0))
    return geom
def sign(self,name,text,x,y,z,width,height,material,yaw=0):
    from qd_terrain import ear,np
    geom=letters(text)
    if geom.is_empty:return
    l,b,r,t=geom.bounds; sc=min(width/max(.01,r-l),height/max(.01,t-b));sn=math.sin(yaw);cs=math.cos(yaw)
    for p in polygons(geom):
        p=orient(p,1);rings=[list(k.coords)[:-1] for k in (p.exterior,*p.interiors)]
        vs=[((a-(l+r)/2)*sc,(b1-(t+b)/2)*sc) for ring in rings for a,b1 in ring]
        ts=ear.triangulate_float64(np.array(vs,np.float64),np.cumsum([len(k) for k in rings],dtype=np.uint32)).reshape(-1,3)
        self.mesh(name,[(x+a*cs,y+b1,z-a*sn) for a,b1 in vs],ts,material)
Shape.sign=sign
def strip(s,poly,bottom,top,color):
    for piece in polygons(poly):
        p=orient(piece,1)
        for ring in [p.exterior,*p.interiors]:
            c=list(ring.coords)
            for (x,z),(xx,zz) in zip(c,c[1:]):
                s.mesh('墙体',[(x,bottom,z),(xx,bottom,zz),(xx,top,zz),(x,top,z)],[(0,3,2,1)],color)
def building(row,poly):
    if row.get('id')=='way/1020621360':
        from qd_phoenix_garden import axis_pavilion
        return axis_pavilion(poly)
    if row.get("id")=="way/868015914":
        from qd_innovation import build
        return build(poly)
    from qd_arch_spring import build_if_known
    spring = build_if_known(row,poly)
    if spring is not None:
        return spring
    s=Shape(row['name'] or '校园建筑');name=row['name'];area=poly.area
    dorm=any(word in name for word in ['凤凰','公寓','居舍'])
    ann='会文' in name; small=area<230; lab=any(word in name for word in ['院','实验','中心','研究'])
    h=row.get('height') or (20.4 if dorm else 18.8 if ann else 21.5 if lab else 5.2 if small else 15.2 if area>500 else 8.5)
    levels=row.get('levels') or (6 if dorm else 4 if ann else max(1,round(h/4.1)))
    levels=max(1,min(15,int(levels)));era=h/levels
    wall='#a66555' if dorm else '#a05f4e' if ann else '#ac7160' if lab else '#b78470'
    trim='#ddcfb9';eave='#708383';roof='#687e7d';stone='#c4b49f'
    strip(s,poly,-2,h,wall);strip(s,poly.buffer(.085,join_style=2),-.18,min(3.65,h*.43),stone)
    import qd_residence_roofs as roof_geometry
    if dorm or ann or (area>550 and lab):
        decks=roof_geometry.pitched_deck(s,poly,h,2.85,1.40,roof,'#a7a8a1',eave,0.)
        if '专家公寓' in name:
            for deck,level,_ in decks:
                roof_geometry.expert_equipment(s,deck,level,row['id'])
    else:
        roofpoly=poly.buffer(.42,join_style=2)
        roof_geometry.eave(s,poly,roofpoly,h,h+.15,trim)
        roof_geometry.terrace(s,roofpoly,h+.15,'#a7a8a1')
    best=None
    for p in polygons(poly):
        p=orient(p,1)
        for ring in (p.exterior,*p.interiors):
            cc=list(ring.coords)
            for (a,b),(c,d) in zip(cc,cc[1:]):
                dx,dz=c-a,d-b; length=math.hypot(dx,dz)
                if length<4:continue
                ux,uz=dx/length,dz/length;nx,nz=uz,-ux; angle=-math.atan2(uz,ux)
                if best is None or length*(1.1+.25*nz)>best[0]:best=(length*(1.1+.25*nz),(a+c)/2,(b+d)/2,nx,nz,angle,length)
                bays=max(1,int((length-.9)/(4.4 if dorm else 5.1)));pitch=(length-.8)/bays
                for level in range(levels):
                    cy=(level+.54)*era;wh=era*(.56 if dorm else .63)
                    for j in range(bays):
                        loc=.4+(j+.5)*pitch;px,pz=a+ux*loc,b+uz*loc
                        ww=min(pitch*(.56 if dorm else .69),3.9)
                        s.box('窗框',px+nx*.105,cy,pz+nz*.105,ww+.22,wh+.23,.22,trim,angle)
                        s.box('窗扇',px+nx*.235,cy,pz+nz*.235,ww,wh,.065,'glass',angle)
                        s.box('中梃',px+nx*.28,cy,pz+nz*.28,.075,wh,.06,'#667574',angle)
                        if (dorm and j%3==1 and level>0):
                            s.box('阳台栏板',px+nx*.7,cy-wh*.33,pz+nz*.7,ww+.55,.63,.18,stone,angle)
                            s.box('阳台底板',px+nx*.40,cy-wh*.56,pz+nz*.40,ww+.72,.16,1.0,trim,angle)
                    if level==0 or (ann and level==levels-2):
                        s.box('水平腰线',(a+c)/2+nx*.13,(level+1)*era,(b+d)/2+nz*.13,length,.2,.27,trim,angle)
    if best and not small and name:
        _,x,z,nx,nz,yaw,width=best;ww=min(12,width*.5)
        s.box('入口玻璃',x+nx*.36,1.55,z+nz*.36,ww*.67,3.1,.24,'glass',yaw)
        s.box('门廊挑檐',x+nx*1.6,3.53,z+nz*1.6,ww, .4,3.5,stone,yaw)
        for i in range(3):
            s.box('门阶',x+nx*(1.5+i*.4),.22-i*.09,z+nz*(1.5+i*.4),ww+.9,.26,2.8+i*.4,trim,yaw)
    return s,roof_geometry.exact_top(s)

