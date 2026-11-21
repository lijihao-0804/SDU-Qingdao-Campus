"""Source-registered roof and open park structures, in local campus metres."""
import math

from shapely.geometry import LineString, Point
from shapely.ops import unary_union

from qd_geometry import Shape


SHELLS = ((536.6,-1447.5,8.2),(532.7,-1431.8,6.8),(535.1,-1415.8,6.5),
          (524.1,-1400.9,6.7),(525.3,-1382.9,6.3))
TOWER = (522.5,-1487.8)


def ring_volume(b,name,mat,x,y,z,w,h,d,innerw,innerd):
    """Four closed, joined strips with a real rectangular aperture."""
    side=(w-innerw)/2
    end=(d-innerd)/2
    for sign in (-1,1):
        b.cube(name,mat,x,y,z+sign*(d-end)/2,w,h,end)
        b.cube(name,mat,x+sign*(w-side)/2,y,z,side,h,innerd)


def library_lantern(b):
    # The aerial shows a low barrel vault, crossed glazing bars and a service
    # deck behind the taller, open-framed terracotta crown.
    width,depth=30.8,31.2
    for sign in (-1,1):
        b.cube('采光顶石质基座','#b9bcaf',0,57.55,sign*(depth/2+.17),width+.96,.69,.40)
        b.cube('采光顶石质基座','#b9bcaf',sign*(width/2+.18),57.55,0,.40,.69,depth+.95)
    def height(x):return 58.02+2.0*(1-(2*x/width)**2)
    def band(x0,z0,x1,z1,wide,mat):
        length=math.hypot(x1-x0,z1-z0)
        px=(z1-z0)*wide/(2*length);pz=(x0-x1)*wide/(2*length)
        corners=[(x0+px,z0+pz),(x1+px,z1+pz),(x1-px,z1-pz),(x0-px,z0-pz)]
        b.poly('天窗斜交钢骨',mat,[(x,height(x)+.065,z) for x,z in corners][::-1])
    n=10;m=10
    for i in range(n):
        x0=(i/n-.5)*width;x1=((i+1)/n-.5)*width
        for j in range(m):
            z0=(j/m-.5)*depth;z1=((j+1)/m-.5)*depth
            b.poly('弧券采光玻璃','#879f9f',[(x0,height(x0),z0),(x0,height(x0),z1),(x1,height(x1),z1),(x1,height(x1),z0)])
            if (i+j)%2:band(x0,z0,x1,z1,.125,'#c8d1c9')
            else:band(x0,z1,x1,z0,.125,'#c8d1c9')
        band(x0,-depth/2,x0,depth/2,.12,'#c8d1c9')
    for side in (-1,1):
        z=side*depth/2
        for i in range(n):
            x0=(i/n-.5)*width;x1=((i+1)/n-.5)*width
            b.poly('端面采光玻璃','#708a8b',[(x0,57.85,z),(x0,height(x0),z),(x1,height(x1),z),(x1,57.85,z)])
        b.cube('天窗侧框','#c8d1c9',side*width/2,57.96,0,.13,.19,depth+.2)


def museum_roofs(b):
    # Each bronze-screened corner terminates in its own ribbed roof, clearly
    # distinct from the square dark rooflight at the centre of the cross.
    b.cube('中央展厅屋面承台','#c4c4b9',0,36.48,0,42.0,4.81,29.0)
    ring_volume(b,'中庭采光带泛水','#b4b8ae',0,38.95,0,42,.42,29,20.0,19.3)
    b.cube('博物馆中庭采光顶','#627d80',0,39.17,0,20.0,.18,19.3)
    for i in range(8):
        x=-10+i*20/7
        b.cube('采光顶纵向压条','#abb7b1',x,39.30,0,.14,.11,19.3)
    for i in range(8):
        z=-9.65+i*19.3/7
        b.cube('采光顶横向压条','#abb7b1',0,39.32,z,20.05,.09,.14)
    for sx in (-1,1):
        for sz in (-1,1):
            x=sx*21.2;z=sz*18.95
            b.cube('四角方盒下凹银灰盖板','#a9aaa2',x,41.344,z,19.9,.042,19.9)
            ring_volume(b,'白石周边压顶','#e2e0d3',x,41.51,z,20.82,.38,20.82,19.32,19.32)
            for k in range(1,7):
                delta=-9.6+k*19.2/7
                b.cube('方盒屋面正交构架','#cccbbf',x+delta,41.51,z,.21,.24,19.1)
                b.cube('方盒屋面正交构架','#d8d6c8',x,41.585,z+delta,19.1,.19,.19)
        for j in (-1,0,1):
            x=sx*45.85;z=j*20.6
            ring_volume(b,'低翼外廊边缘压顶','#d8d7c9',x,13.56,z,22.65,.27,18.43,21.65,17.43)


def tiled_ring(s,w,d,y,rise,ridge_w,ridge_d,inner_w,inner_d,red):
    """Mitered four-side perimeter roof, inner slopes return to exposed deck."""
    def ring(a,b,level):
        return [(-a/2,level,-b/2),(a/2,level,-b/2),(a/2,level,b/2),(-a/2,level,b/2)]
    outer=ring(w,d,y);ridge=ring(ridge_w,ridge_d,y+rise);inner=ring(inner_w,inner_d,y+.12)
    for n in range(4):
        j=(n+1)%4
        s.mesh('外侧连续瓦坡',[outer[n],ridge[n],ridge[j],outer[j]],[(0,1,2,3)],red)
        s.mesh('内侧连续瓦坡',[ridge[n],inner[n],inner[j],ridge[j]],[(0,1,2,3)],red)
    from qd_civic import beam
    for n in range(4):
        j=(n+1)%4
        beam(s,'环形坡顶正脊',ridge[n],ridge[j],.14,red,8)


def arena_soffit(s,roof_rows,roof_point):
    # Public photographs show the long white canopy wrapping the blue track.
    from qd_civic import beam
    for a,b in zip(roof_rows,roof_rows[1:]):
        for strip in range(12):
            u=strip/12;v=(strip+1)/12
            corners=[roof_point(a[1]+u*(a[2]-a[1]),a[0]),roof_point(a[1]+v*(a[2]-a[1]),a[0]),
                     roof_point(b[1]+v*(b[2]-b[1]),b[0]),roof_point(b[1]+u*(b[2]-b[1]),b[0])]
            under=[(x,y-.76,z) for x,y,z in corners]
            s.mesh('帆形屋面及看台遮棚连续檐底',under,[(0,1,2,3)],'#c9cec9')
    # The fixed east-side seating faces west. Keep service and cross aisles clear.
    for segment,(start,stop) in enumerate(((104,131),(135,163),(167,194),(198,216))):
        for row in range(5):
            p=[]
            for k in range(9):
                rz=start+(stop-start)*k/8
                i=next(i for i in range(len(roof_rows)-1) if roof_rows[i][0]<=rz<=roof_rows[i+1][0])
                a,b=roof_rows[i:i+2];t=(rz-a[0])/(b[0]-a[0])
                outer=a[1]*(1-t)+b[1]*t
                x,_,z=roof_point(outer+1.0+row*.82,rz)
                h=.48+row*.33
                p.extend([(x,h,z),(x+.81,h,z),(x+.81,h-.33,z)])
            s.mesh('蓝色田径场东侧分段看台',p,[(3*k,3*k+3,3*k+4,3*k+1) for k in range(8)]+[(3*k+1,3*k+4,3*k+5,3*k+2) for k in range(8)],'#bbc2bb')


def coastal_reserve():
    elements=[Point(x,z).buffer(r+2.2) for x,z,r in SHELLS]
    x,z=TOWER
    elements.append(LineString([(x-27,z+2),(x+4,z)]).buffer(5.7))
    return unary_union(elements)


def shell_pavilion(s,cx,cy,cz,r):
    from qd_civic import beam
    # Cut four complete arches through the spherical shell. A glazed inner
    # storey and balcony sit back from the openings, above the shaded arcade.
    def pt(lat,ang):
        return (cx+r*math.cos(lat)*math.cos(ang),cy+r*(.92+math.sin(lat)),cz+r*math.cos(lat)*math.sin(ang))
    latitudes=[-.98+i*(math.pi/2+.98)/32 for i in range(33)]
    def opening(lat):
        y=(.92+math.sin(lat))
        rel=(y-.80)/.74
        return 0 if abs(rel)>=1 else math.asin(min(.72,.62*math.sqrt(1-rel*rel)/max(.22,math.cos(lat))))
    for sector in range(4):
        theta=sector*math.pi/2
        for a,b in zip(latitudes,latitudes[1:]):
            ra,rb=opening(a),opening(b)
            for k in range(12):
                t=k/12;u=(k+1)/12
                def ang(alpha,weight):return theta+alpha+(math.pi/2-2*alpha)*weight
                quad=[pt(a,ang(ra,t)),pt(b,ang(rb,t)),pt(b,ang(rb,u)),pt(a,ang(ra,u))]
                faces=[(0,1,3)] if abs(math.cos(b))<1.e-8 else [(0,1,2,3)]
                s.mesh('球壳开敞拱门与拱顶',quad,faces,'#c4c8c1')
            if ra>0 or rb>0:
                for sign in (-1,1):
                    edgea=pt(a,theta+sign*ra);edgeb=pt(b,theta+sign*rb)
                    beam(s,'球壳门洞收边',edgea,edgeb,.09,'#e0e0d6',7)
    s.cyl('球亭下部基座',cx,cy+.43,cz,r*.70,.86,'#c0beb0',32)
    s.cyl('架空层上方观景平台',cx,cy+r*.81,cz,r*1.0,.39,'#d5d4c9',48)
    s.cyl('楼层玻璃围护',cx,cy+r*1.106,cz,r*.67,r*.56,'#607981',40)
    for k in range(20):
        a=k*math.tau/20
        s.cyl('内退玻璃竖梃',cx+math.cos(a)*r*.669,cy+r*1.1,cz+math.sin(a)*r*.669,.063,r*.56,'#42545a',6)
        p1=(cx+math.cos(a)*r*.94,cy+r*.81+.98,cz+math.sin(a)*r*.94)
        q=(k+1)*math.tau/20;p2=(cx+math.cos(q)*r*.94,p1[1],cz+math.sin(q)*r*.94)
        beam(s,'外廊通透栏杆',p1,p2,.045,'#c0c5bf',6)
        s.cyl('外廊栏杆立柱',p1[0],p1[1]-.46,p1[2],.045,.92,'#bfc3bc',6)


def build_coastal_structures(scene,terrain):
    from qd_civic import beam
    for i,(x,z,r) in enumerate(SHELLS):
        shell=Shape('滨海公园 · 球壳观景建筑 '+str(i+1))
        shell_pavilion(shell,0,0,0,r)
        scene.node(shell.name,shape=shell,at=(x,terrain.y(x,z),z),kind='waterfront',surface='parkBuilding',key='coastal-pavilion-'+str(i+1))
    t=Shape('滨海公园 · 红顶观景塔与曲廊');x,z=TOWER;h=32.5
    for cx in (-2.6,2.6):
        for cz in (-2.6,2.6):
            t.box('白色观景塔主钢柱',cx,h/2,cz,.38,h,.38,'#d8dcd5')
    for j in range(8):
        y0=j*h/8;y1=(j+1)*h/8
        for sign in (-1,1):
            for a,b in [((-2.6,y0,sign*2.6),(2.6,y1,sign*2.6)),((sign*2.6,y0,2.6),(sign*2.6,y1,-2.6))]:
                beam(t,'通透钢桁架斜撑',a,b,.085,'#ccd2cb',8)
            t.box('钢塔水平横梁',0,y1,sign*2.6,5.6,.15,.15,'#d8dcd5')
            t.box('钢塔水平横梁',sign*2.6,y1,0,.15,.15,5.6,'#d8dcd5')
    t.cyl('观景悬台',1.55,h*.85,0,4.75,.55,'#c3c9c3',36)
    for k in range(36):
        a=k*math.tau/36;b=(k+1)*math.tau/36
        ax=1.55+4.65*math.cos(a);az=4.65*math.sin(a)
        beam(t,'悬台护栏',(ax,h*.85+1.3,az),(1.55+4.65*math.cos(b),h*.85+1.3,4.65*math.sin(b)),.055,'#d6d8cb',6)
        t.cyl('悬台栏柱',ax,h*.85+.77,az,.044,1.05,'#d6d8cb',6)
    line=[(-26,4.3),(-18,4.35),(-12.4,4.52),(-9,5.0),(-7.5,5.9),(-6.2,7.45),(-5.2,10.6),(-4.65,14.6),
          (-4.2,20),(-3.8,25.6),(-3.5,29.55),(-3.0,31.1),(-2.0,32.0),(-.4,32.4),(2.,32.52),(8.7,32.52)]
    for (a,y),(b,yy) in zip(line,line[1:]):
        t.mesh('红色连续弯折顶盖',[(a,y,-2.53),(a,y,2.53),(b,yy,2.53),(b,yy,-2.53)],[(0,1,2,3)],'#a84b43')
    for xx in (-24,-17,-10):
        for zz in (-2.2,2.2):t.cyl('低廊支柱',xx,2.19,zz,.14,4.38,'#d6d9d2',8)
    scene.node(t.name,shape=t,at=(x,terrain.y(x,z),z),kind='waterfront',surface='parkBuilding',key='coastal-red-tower')
    return {'spheres':len(SHELLS),'tower':1}



def survey_export(doc,raw):
    """Inspect vertical sightlines in the actual glTF meshes in node-local metres."""
    import numpy as np
    requested={'library','museum','zhensheng','huagang','xiyuan','assembly','song_arena',
               'blue_track','east_track','west_gate','north_gate','east_gate','south_gate','coastal-red-tower'}
    requested.update('coastal-pavilion-'+str(i) for i in range(1,6))
    def array(idx):
        acc=doc['accessors'][idx];view=doc['bufferViews'][acc['bufferView']]
        count=acc['count'];size={'SCALAR':1,'VEC3':3}[acc['type']]
        dt={5121:'u1',5123:'<u2',5125:'<u4',5126:'<f4'}[acc['componentType']]
        return np.frombuffer(raw,dtype=dt,count=count*size,offset=view.get('byteOffset',0)+acc.get('byteOffset',0)).reshape(count,size)
    items={}
    for node in doc['nodes']:
        key=node.get('extras',{}).get('key')
        if key not in requested or 'mesh' not in node:continue
        primitive=doc['meshes'][node['mesh']]['primitives']
        tri=np.concatenate([array(p['attributes']['POSITION'])[array(p['indices']).reshape(-1,3)] for p in primitive]).astype('float64')
        p,q,r=np.moveaxis(tri,1,0)
        def cross2(a,b):return a[:,0]*b[:,1]-a[:,1]*b[:,0]
        def highest(first,second,axes=(0,2),height=1):
            a=p[:,axes];u=q[:,axes]-a;v=r[:,axes]-a;d=cross2(u,v);hit=np.abs(d)>1.e-8
            delta=np.array([first,second])-a
            aa=np.divide(cross2(delta,v),d,out=np.zeros(len(d)),where=hit);bb=np.divide(cross2(u,delta),d,out=np.zeros(len(d)),where=hit)
            hit&=(aa>=-1.e-6)&(bb>=-1.e-6)&(aa+bb<=1.000001)
            if not hit.any():return None
            y=p[:,height]+aa*(q[:,height]-p[:,height])+bb*(r[:,height]-p[:,height])
            return round(float(np.max(y[hit])),4)
        item={'triangles':len(tri),'max_y_m':round(float(tri[:,:,1].max()),3)}
        if key=='library':
            item.update(lantern_crown_m=highest(0,0),lantern_spring_m=highest(15.1,0),inner_service_deck_m=highest(22,0),mansard_high_m=highest(.27,31.40))
        elif key=='museum':
            item.update(central_rooflight_m=highest(.5,1),upper_corner_infill_m=[highest(a*21.2,b*18.95) for a in (-1,1) for b in (-1,1)],upper_corner_parapets_m=[highest(a*31.15,b*18.95) for a in (-1,1) for b in (-1,1)],low_wing_m=highest(45.85,.5))
        elif key in ('zhensheng','huagang'):
            open_heights=[highest(x,z) for x,z in [(0,0),(-8.,0),(8.,0),(0,-11.),(0,11.)]]
            item['court_sky_rays_near_ground_m']=open_heights
            item['four_wing_roofs_m']=[highest(0.,v) for v in (-51.,51.)]+[highest(v,0) for v in (-47.,47.)]
        elif key=='xiyuan':
            item.update(service_deck_m=highest(.4,.4),tile_ridge_m=highest(0,26.48),inner_tile_eave_m=highest(0,15.42),outside_tile_eave_m=highest(0,36.94))
        elif key=='assembly':
            cross=np.cross(q-p,r-p);ny=cross[:,1]/np.maximum(1.e-8,np.linalg.norm(cross,axis=1))
            top=(tri[:,:,1].min(axis=1)>11.0)&(np.abs(ny)>.12)
            item['roof_orientation']={'up_triangles':int(np.count_nonzero(top&(ny>0))),
                                      'down_triangles':int(np.count_nonzero(top&(ny<0)))}
            item['court_rays_18_positions']=[highest(a*math.cos(k*math.tau/6),a*math.sin(k*math.tau/6)) for k in range(6) for a in (0.,25.,53.)]
            item['open_radial_slots']=[highest(70*math.cos(math.radians(a)),70*math.sin(math.radians(a))) for a in (-140,-16,129)]
            item['three_shell_crests_m']=[highest(70*math.cos(math.radians(a)),70*math.sin(math.radians(a))) for a in (-79,55,172)]
        elif key in ('blue_track','east_track'):
            item.update(open_playing_surface_m=highest(0,.54))
        elif key=='west_gate':
            item.update(open_vehicle_axis=highest(0,0),two_roof_peaks_m=[highest(v,0) for v in (-30.21,30.21)])
        elif key=='north_gate':
            item.update(open_vehicle_axis=highest(0,0),tower_m=highest(16.8625,0),porter_roof_m=highest(-16.15,0))
        elif key=='east_gate':
            north,south=highest(-2.75,-24.48),highest(-3.1,20.70)
            item.update(open_roadway=highest(0,8.4),north_tower_m=north,south_pavilion_m=south,paired_gate_roofs_m=[north,south],
                        axial_green_island_top_m=highest(0.,.05),
                        north_court_surface_m=highest(9,-34),south_gallery_roof_m=highest(.6,40.))
        elif key=='south_gate':
            item.update(open_roadway=highest(0,0),east_side_kiosk_m=highest(12.2,6.3))
        elif key=='song_arena':
            item.update(spectator_canopy_m=highest(-15.5,-122),main_vault_m=highest(-17.5,51.),northern_eave_m=highest(-25.3,-204))
        elif key.startswith('coastal-pavilion-'):
            rad=SHELLS[int(key.rsplit('-',1)[1])-1][2]
            item['crown_centre_m']=highest(0,0)
            item['crown_ring_m']=[highest(.2*math.cos(k*math.tau/6),.2*math.sin(k*math.tau/6)) for k in range(6)]
            item['open_arch_east_glazing_setback_m']=round(rad-highest(1.11*rad,0,axes=(1,2),height=0),3)
        elif key=='coastal-red-tower':
            item.update(red_crown_m=highest(0,0),covered_walk_m=highest(-18.,0),open_east_side=highest(5,6))
        items[key]=item
    return items


def read_export(path):
    import json,struct
    binary=path.read_bytes();n=struct.unpack_from('<I',binary,12)[0]
    return survey_export(json.loads(binary[20:20+n]),memoryview(binary)[28+n:])


if __name__=='__main__':
    from pathlib import Path
    import argparse,json
    parser=argparse.ArgumentParser(description='Sample the campus GLB roof geometry directly.')
    parser.add_argument('glb',type=Path)
    args=parser.parse_args()
    print(json.dumps(read_export(args.glb),ensure_ascii=False,indent=2))
