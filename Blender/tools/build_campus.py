"""Build the Qingdao campus using offline inputs and deterministic metre-scale geometry."""
import argparse, hashlib, json, math, re, sys, time
from pathlib import Path
import numpy as np
from shapely.geometry import Point,LineString,Polygon,box
from shapely.affinity import translate,rotate
from shapely.ops import unary_union
from qd_geometry import CampusFile, Shape
from qd_terrain import Terrain,sourcepolygon,face,polygons
from qd_architecture import building
from qd_planting import plant
from qd_sports import court
from qd_extras import assembly, detail_plaza
ROOT=Path(__file__).resolve().parents[1]
def union(items):return unary_union([v for v in items if not v.is_empty])
def read(p):return json.loads(p.read_text('utf-8-sig'))
def save(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,separators=(',',':')),'utf-8')
def safe(poly):return poly.buffer(0)
def main():
    data=read(ROOT/'data/map/campus.json')
    architecture=read(ROOT/'data/architecture_spring_sources.json')
    residential_keys={key for family in architecture['groups'] for key in family['keys']}
    from qd_geometry import record_components
    import qd_landmarks,qd_civic,qd_colleges
    academies=qd_colleges.academic_index(); inscriptions=[]; door_corridors=[]
    catalog=[];buildings=data['buildings'];metadata=data['metadata'];origin=metadata['origin']
    originlon,originlat=120.68204,36.36559
    m=metadata['metres_per_degree']
    shapes={r['id']:sourcepolygon(r) for k in ['buildings','pitches','plazas','parking','greens','water'] for r in data[k]}
    rows={r['id']:r for k in ['buildings','pitches','plazas','gates'] for r in data[k]}
    def ids(s):
        vals=[s.get('osm','')]+list(s.get('replaces',[]))
        out=set()
        for v in vals:
            if isinstance(v,(list,dict)):continue
            val=str(v)
            if val in rows:out.add(val)
            elif val.isdigit():out.update(x for x in rows if x.split('/')[-1]==val)
            elif val:out.update(x for x,r in rows.items() if r.get('name')==val)
        return out
    specs=[];replace=set()
    for mod in [qd_landmarks,qd_civic]:
        for sp in mod.SPECS:
            s=dict(sp);ids0=ids(s);snames=set([s['name']]+list(s.get('aliases',[])))
            for k,r in rows.items():
                if r.get('name') and r['name'] in snames:ids0.add(k)
            sources=[rows[k] for k in sorted(ids0) if k in rows]
            if s.get('site_x') is not None:x,z=s['site_x'],s['site_z']
            elif s.get('lon') is not None and s.get('lat') is not None:x,z=(s['lon']-originlon)*m['longitude'],-(s['lat']-originlat)*m['latitude']
            elif sources:
                loc=sources[0];x,z=loc.get('center',loc.get('point'))
            else:raise ValueError('Missing placement '+s['name'])
            if 'gate' in s['key']:
                for r in buildings:
                    if shapes[r['id']].area<300 and Point(r['center']).distance(Point(x,z))<65:ids0.add(r['id'])
            replace.update(ids0)
            if any(k in shapes and shapes[k].area>350 for k in ids0):
                base=union([shapes[k] for k in ids0 if k in shapes])
            else:
                base=rotate(box(x-s['w']/2,z-s['d']/2,x+s['w']/2,z+s['d']/2),-math.degrees(s.get('yaw',0)),origin=(x,z))
            specs.append((mod,s,x,z,base))
    boundary=Polygon(data['boundary']).buffer(0)
    scene=CampusFile()
    scene.doc['asset']['extras']={'campus':'山东大学（青岛）','revision':'夕照校园-v6','units':'metres'}
    # Shoreline and its seaward half-plane extend well beyond the filmed campus.
    from qd_waterfront import Waterfront
    waterfront=Waterfront(data)
    outer,ocean=waterfront.outer,waterfront.ocean
    terrain=Terrain(outer.bounds,datum_bounds=(-1100,-1500,1800,1500))
    print('DEM downloaded/read',terrain.terrainRange,flush=True)
    from qd_grading import apply_grading,site_lift
    apply_grading(terrain,data,specs)
    waterfront.grade(terrain)
    from qd_campus_park import land_regions
    domain,core_land=land_regions(waterfront)
    water=union([shapes[r['id']] for r in data['water']]).intersection(domain)
    roads=[];asphalt=[];paths=[];bridges=[]
    for r in data['roads']:
        if r.get('tunnel') or len(r['line'])<2:continue
        line=LineString(r['line']); width=r['width']
        lay=line.buffer(width/2,cap_style=1,join_style=1,quad_segs=4)
        if r.get('bridge'):bridges.append(lay)
        if r.get('kind') in ('footway','pedestrian','cycleway','path','steps','track') and width<7:paths.append(lay)
        else:asphalt.append(lay)
        roads.append(r)
    # The OSM centre lines split around the western median. The paved space
    # between those lines is visible in V2 00:02.5 and must remain drivable.
    west=next(item for item in specs if item[1]['key']=='west_gate')
    wx,wz=west[2:4]
    from shapely.affinity import translate
    gate_drive=translate(Polygon([(-49,-10),(-39,-20),(-15,-21),(12,-21),(18,-16),
                                  (18,16),(12,21),(-15,21),(-39,20),(-49,10)]),wx,wz)
    asphalt.append(gate_drive)
    from qd_gate_details import south_approach
    south=next(item for item in specs if item[1]['key']=='south_gate')
    south_drive,south_aprons,south_crossing=south_approach(*south[2:4])
    asphalt.append(south_drive)
    road=union(asphalt).intersection(domain);walk=union(paths).intersection(domain).difference(road)
    road=road.union(terrain.arena_slope.drive)
    walk=walk.union(terrain.arena_slope.upper_path).difference(road)
    door_corridors.append(terrain.arena_slope.reserve)
    from qd_ganchang_cherries import Layout as CherryLayout, build as build_cherry_walk
    cherry_walk=CherryLayout(data)
    door_corridors.append(cherry_walk.reserve)
    from qd_teaching_courts import CourtGround,PAVING,ROAD_LIFT
    teaching=CourtGround(specs,road)
    import qd_academic_ground
    qd_academic_ground.refine(terrain,[shapes[k] for k in academies])
    qd_academic_ground.refine(terrain,teaching.sites,transition=46)
    def cover(name,geom,col,height):
        if geom.is_empty:return
        def part(label,area,extras):
            if area.is_empty or area.area<.01:return
            sh=Shape(label)
            terrain.skin(sh,area,col,height)
            scene.node(label,shape=sh,kind='ground',**extras)
        if core_land.covers(geom):
            part(name,geom,{})
        else:
            part(name,geom.intersection(core_land),{})
            part('外围地表 · '+name,geom.difference(core_land),dict(sceneRegion='surroundings'))
    import qd_orchard_floor
    soil_domain=domain.difference(water).difference(waterfront.substrate).difference(union([teaching.paving,*teaching.sites]))
    cover('两苑庭院与入口下方土基',union([teaching.paving,*teaching.sites]),'#92866c',-.48)
    plots=qd_orchard_floor.regions(soil_domain)
    cover('校园及滨海地形',soil_domain.difference(union(plots.values())),'grass',0)
    cover('沙岸',union([sourcepolygon(r) for r in data['beaches']]).intersection(domain).difference(waterfront.substrate),'#d1c5a1',.045)
    from qd_coast import add as add_coast
    add_coast(scene,terrain,domain,ocean,outer,waterfront=waterfront)
    for r in data['water']:
        p=shapes[r['id']].intersection(domain)
        if p.is_empty:continue
        cx,cz=r['center'];h=terrain.y(cx,cz)-.04
        sh=Shape(r['name'] or '滨水');face(sh,p,'water',h)
        region={} if core_land.intersects(p) else dict(sceneRegion='surroundings')
        scene.node(sh.name,shape=sh,kind='water',**region)
        if '湖' in r['name']:catalog.append(dict(key='lake',name=r['name'],x=cx,z=cz,y=h,h=3,r=90,group='景观',note='北区水岸与林间步道。'))
    plazas=union(shapes[r['id']] for r in data['plazas'])
    parking=union(shapes[r['id']] for r in data['parking'])
    greenIslands=union(shapes[r['id']] for r in data['greens'] if r['kind']=='grass')
    from qd_huiwen_square import HuiwenSquare, OSM_ID as HUIWEN_SQUARE
    huiwen_square=HuiwenSquare(shapes[HUIWEN_SQUARE],walk,road)
    import qd_v6_alumni,qd_v6_yuxian
    yuxian_gardens=qd_v6_yuxian.Gardens(data,road,walk)
    alumni_site=shapes[qd_v6_alumni.OSM_ID]
    greenIslands=union([greenIslands,huiwen_square.islands,yuxian_gardens.lawns])
    common_square_paving=plazas.difference(greenIslands).difference(road).difference(huiwen_square.site).difference(alumni_site)
    common_square_paving=common_square_paving.difference(teaching.paving)
    cover('石材广场与步行带',common_square_paving,'#c9c3b5',.08)
    cover('停车铺面',parking.difference(road).difference(teaching.paving),'#999993',.09)
    from qd_innovation_plaza import InnovationPlaza
    from qd_library_blooms import AREA as library_garden, build as plant_library_garden
    innovation=InnovationPlaza(data,road,walk)
    door_corridors.extend((innovation.plant_reserve,library_garden.buffer(1.6)))
    from qd_museum_walk import MuseumWalk
    museum_walk=MuseumWalk(data,road,walk)
    door_corridors.append(museum_walk.plant_reserve)
    cover('步行道',walk.difference(museum_walk.pavement).difference(waterfront.path_geom.buffer(.03)).difference(huiwen_square.site).difference(teaching.paving),'#c9c0ac',.17)
    import qd_phoenix_arcades
    galleries=union(qd_phoenix_arcades.cover_plan(key) for key in qd_phoenix_arcades.HOSTS)
    gallery_paving=galleries.buffer(.20,join_style='mitre').difference(road.union(walk))
    cover(qd_phoenix_arcades.GROUND,gallery_paving,'#bdaf99',.135)
    door_corridors.append(galleries.buffer(.75))
    qd_phoenix_arcades.add_view(catalog,terrain)
    cover('车道路缘',road.buffer(.33,quad_segs=3).difference(road).difference(teaching.paving),'#b5b6ac',.21)
    cover('连续沥青路面',road.difference(cherry_walk.pavement),'asphalt',ROAD_LIFT)
    for name,apron in teaching.entries.items():
        cover(name,apron,PAVING,ROAD_LIFT)
    door_corridors.append(teaching.plant_reserve)
    # The approach is part of the same sloped road mesh. The two aprons end
    # at its actual curb so that the underlying terrain and road never coincide.
    south_aprons=south_aprons.intersection(domain).difference(road.buffer(.329,quad_segs=3))
    cover('南校门·石塔及岗亭前石材铺地',south_aprons,'#cbc4b6',.236)
    cover('南校门·人行横道',south_crossing.intersection(road), '#e7e5d9',.225)
    if bridges:cover('跨水通行桥面',union(bridges).intersection(outer),'#aaa99e',.31)
    # Render landmark facades and exact compound footprints separately.
    # Museum forecourt joins the north terrace and the east/west campus road.
    # The paving extent is estimated; the north-door approach is clear in V2 01:14.5.
    museum=next(item for item in specs if item[1]['key']=='museum')
    mx,mz=museum[2:4]
    from shapely.affinity import translate as offset_shape
    forecourt=offset_shape(Polygon([(-32,-49),(32,-49),(32,-59),(22,-70),(9,-77),
                                    (4.2,-77),(4.2,-111),(-4.2,-111),(-4.2,-77),
                                    (-9,-77),(-22,-70),(-32,-59)]),mx,mz)
    cover('博物馆北阶前庭及中轴步道',forecourt.difference(road.buffer(.3)).difference(walk), '#c9c8c0',.19)
    blocks=[forecourt,gate_drive,south_aprons];courtpolys=[];bcount=0
    for mod,s,x,z,p in specs:
        group=Shape(s['name']);ok=mod.build(group,s['key'],s['w'],s['d'],s['h'])
        if ok is False or not group.parts:raise ValueError('empty landmark '+s['key'])
        y=terrain.y(x,z)+site_lift(s['key'])
        scene.node(s['name'],shape=group,at=(x,y,z),yaw=s.get('yaw',0),kind='landmark',key=s['key'])
        if s['key']=='song_arena':
            from qd_video_sport import podium
            p=p.union(translate(podium().convex_hull.buffer(5.5),x,z))
        blocks.append(p);r=max(s['w'],s['d'])/2
        catalog.append(dict(key=s['key'],name=s['name'],x=x,y=y,z=z,h=s['h'],r=r,w=s['w'],d=s['d'],yaw=s.get('yaw',0),
                            group='地标',note=s.get('caption',s.get('description','')) or '依据实景照片复原主要外部形态。'))
    for row in buildings:
        id=row['id']
        if id in replace:continue
        p=shapes[id]
        if p.is_empty:continue
        if id in academies:
            mod,sp=academies[id]
            near=union(shapes[r['id']] for r in buildings if r['id']!=id and shapes[r['id']].distance(p)<80)
            qd_colleges.add(scene,mod,sp,row,p,near,terrain,catalog,inscriptions,door_corridors)
            blocks.append(p);bcount+=1
            continue
        if '会堂' in row['name']:
            g,h=assembly(row,p);special=True
        else:
            x,z=row['center'];flag=record_components.set(id.replace('/','-') in residential_keys)
            try:g,h=building(row,translate(p,-x,-z))
            finally:record_components.reset(flag)
            special=False
        x,z=row['center'];y=terrain.y(x,z)+.22;key='assembly' if special else id.replace('/','-')
        scene.node(row['name'] or '校园建筑 '+id,shape=g,at=(x,y,z),kind='building',key=key,refinedResidence=key in residential_keys)
        from qd_signage import emit
        emit(scene,g,(x,y,z),inscriptions)
        blocks.append(p);bcount+=1
        if id=='way/1020621360':
            catalog.append(dict(key=key,name='凤凰居中轴六角亭',group='校园场地',x=x,y=y,z=z,h=h,r=6,
                                note='六角石台、敞开花架与两层瓦顶。亭顶的小楼开有拱窗。'))
        if row['name']:catalog.append(dict(key=key,name=row['name'],x=x,z=z,y=y,h=h,r=max(p.bounds[2]-p.bounds[0],p.bounds[3]-p.bounds[1])/2,
                                group='院楼与生活区',note='平面来自校园底图，立面依楼群实景推定。' if not special else '北区环抱式体量，屋面轮廓据卫星影像概化。'))
    for row in data['pitches']:
        p=shapes[row['id']];courtpolys.append(p)
        if row['id'] in replace or row['kind']=='track':continue
        if row['kind']=='court_base':
            cover('球场组团铺面',p,'#b5aea1',.26);continue
        if any(p.intersection(xx).area>p.area*.65 for mod,sp,x,z,xx in specs if 'track' in sp['key']):continue
        x,z=row['center'];group,angle=court(row,p)
        scene.node(row['name'] or row['kind']+'球场',shape=group,at=(x,terrain.y(x,z)+.39,z),yaw=angle,kind='sport')
    for r in data['plazas']:
        if r['id'] in replace or r['id']==qd_v6_alumni.OSM_ID:continue
        if r['id']==HUIWEN_SQUARE:
            huiwen_square.build(scene,terrain,door_corridors)
        detail_plaza(scene,terrain,r,shapes[r['id']])
    built=union(blocks+courtpolys)
    # Footways follow both curbs in the academic district aerial. Their widths
    # are estimated; every entrance and road remains connected to the source plan.
    college_zone=union(shapes[k] for k in academies).convex_hull.buffer(10)
    verge_walk=road.buffer(2.65,quad_segs=4).difference(road.buffer(.34,quad_segs=4))
    verge_walk=verge_walk.intersection(college_zone).difference(union([built.buffer(.3),walk,plazas,parking,water]))
    verge_walk=verge_walk.difference(cherry_walk.reserve)
    cover('学院区道路两侧人行道',verge_walk,'#b9b5aa',.165)
    door_corridors.append(verge_walk.buffer(1.1))
    paving=union([plazas.difference(huiwen_square.islands),parking,road,walk,verge_walk])
    aprons=qd_academic_ground.aprons(catalog,built,paving,built)
    if aprons is not None:
        cover('学院门前石材步道',aprons,'#c2bcb1',.145)
        door_corridors.append(aprons.buffer(2.5))
    layers=[(common_square_paving,.08),(huiwen_square.paved,.17),(parking.difference(road),.09),
            (road,.205),(road.buffer(.33,quad_segs=3).difference(road),.21),(walk,.17),(verge_walk,.165)]
    if bridges:layers.append((union(bridges),.31))
    if aprons is not None:layers.append((aprons,.145))
    pedestrian=union([common_square_paving,huiwen_square.paved,walk,verge_walk,aprons if aprons is not None else Polygon()]).difference(road)
    for loc in catalog:
        if loc.get('group')!='学院楼':continue
        pose=loc['views']['entrance'];eye=pose['eye'];target=pose['target'];nx,nz=loc['normal']
        pos=Point(eye[0],eye[2])
        if not pedestrian.covers(pos):
            distance=pos.distance(Point(target[0],target[2]))
            for d in sorted(np.arange(5.5,28.1,.25), key=lambda v:abs(v-distance)):
                q=Point(target[0]+nx*d,target[2]+nz*d)
                if pedestrian.covers(q):
                    pos=q;eye[0],eye[2]=q.x,q.y
                    pose['fov']=float(min(69,48+max(0,13-d)*2.5))
                    break
        lift=max((height for shape,height in layers if shape.covers(pos)),default=0)
        eye[1]=terrain.y(pos.x,pos.y)+lift+1.70
        # Provide a clear sight cone to the left and right plaques, not only the door.
        pts=[(eye[0],eye[2]),(target[0],target[2])]
        for inscription in inscriptions:
            if inscription['owner']==loc['key']:
                rx,_,rz=inscription['world'];half=inscription['width']*.5
                pts.extend([(rx-half*nz,rz+half*nx),(rx+half*nz,rz-half*nx)])
        from shapely.geometry import MultiPoint
        door_corridors.append(MultiPoint(pts).convex_hull.buffer(6.4))
    import qd_spring
    obstacle_footprints=union(shapes[r['id']] for r in buildings)
    from shapely.geometry import MultiPoint
    for view in architecture['viewpoints']:
        if view['key'] not in ('s2-b6','s2-b1','yuehai-north-inscription'):continue
        ex,_,ez=view['eye'];tx,_,tz=view['target']
        dx,dz=tx-ex,tz-ez;length=math.hypot(dx,dz);sx,sz=-dz/length,dx/length
        # Keep the whole pediment and its sides in sight, including branches
        # that project beyond their planting pits into the near camera frustum.
        view_area=MultiPoint([(ex,ez),(tx+sx*10,tz+sz*10),(tx-sx*10,tz-sz*10)]).convex_hull
        door_corridors.append(view_area.buffer(6.1))
    morning_row=next(r for r in buildings if r['id']=='s2/b6')
    front=shapes[morning_row['id']].bounds[2];cz=morning_row['center'][1]
    route=road.boundary
    from shapely.ops import nearest_points
    join=nearest_points(Point(front+.9,cz),route)[1]
    approach=Polygon([(front-.05,cz-11.1),(front+5.0,cz-11.1),(join.x+.04,join.y-4.7),
                      (join.x+.04,join.y+4.7),(front+5.0,cz+11.1),(front-.05,cz+11.1)])
    approach=approach.difference(road.buffer(.33)).difference(obstacle_footprints)
    cover('晨园东门 · 入口铺地',approach,'#bdb7a8',.17)
    door_corridors.append(approach.buffer(2.3))
    hard=union([built.buffer(3.8),obstacle_footprints.buffer(.85), *door_corridors])
    plantarea=boundary.union(union(shapes[r['id']] for r in data['greens'])).intersection(domain)
    exclude=union([hard,water.buffer(2.4),plazas.buffer(1),parking,road.buffer(2.0),walk.buffer(.7),
                   union(sourcepolygon(v) for v in data.get('construction',[])),ocean])
    exclude=exclude.union(waterfront.plant_exclusion).union(huiwen_square.site)
    import qd_v6_parcels,qd_v6_planting,qd_v6_parking
    parcel_reserve=qd_v6_parcels.reserve(data)
    exclude=exclude.union(parcel_reserve)
    available=plantarea.difference(exclude)
    parking_records=qd_v6_parking.build(scene,terrain,data,union([road.buffer(.52),walk.buffer(.23),obstacle_footprints,water,parcel_reserve,teaching.paving]))
    save(ROOT/'data/v6_parking.json',parking_records)
    spring=qd_spring.build(scene,terrain,data,available,exclude,roads,catalog)
    import qd_phoenix_garden
    phoenix=qd_phoenix_garden.build(scene,terrain,data,available,catalog)
    garden_reserve=qd_phoenix_garden.reserve(data)
    reserve=qd_spring.planted_extent(data).union(garden_reserve)
    axis_conflicts=union([road.buffer(.8),walk.buffer(.55),parking.buffer(.5),water,built.difference(next(base for mod,sp,x,z,base in specs if sp['key']=='yuxian')),obstacle_footprints,*door_corridors])
    plants=plant(scene,terrain,plantarea,roads,exclude.union(reserve).union(qd_v6_planting.nursery_rows(data)),union(shapes[r['id']] for r in data['greens']),axis_conflicts=axis_conflicts,axis=next((sp,x,z) for mod,sp,x,z,base in specs if sp['key']=='yuxian'))
    plants[0]+=huiwen_square.tree_count
    from qd_groundcover import add as add_groundcover
    grass=add_groundcover(scene,terrain,data,available.difference(garden_reserve),[(x,z) for mod,sp,x,z,base in specs],garden=huiwen_square.sward)
    waterfront.build(scene,terrain,catalog)
    from qd_public_roofs import build_coastal_structures
    build_coastal_structures(scene,terrain)
    from qd_public_roofs import SHELLS,TOWER
    for place,title,(px,pz),hgt,offset in [
        ('coastal-pavilion-1','滨海公园 · 球壳观景建筑',SHELLS[0][:2],14,(-27,15,19)),
        ('coastal-red-tower','滨海公园 · 红顶观景塔',TOWER,33,(-39,25,56))]:
        base_y=terrain.y(px,pz)
        eye=[px+offset[0],base_y+offset[1],pz+offset[2]]
        catalog.append(dict(key=place,name=title,group='滨海公园',x=px,y=base_y,z=pz,h=hgt,r=23,
                            viewpoint=dict(eye=eye,target=[px,base_y+hgt*.45,pz],fov=45),
                            note='公园实景可辨的拱口、观景层和屋顶。尺度按正射与地面照片估算。'))
    surf_metadata=read(ROOT/'data/surf_sources.json')
    viewpoint=surf_metadata['viewpoint']
    x,y,z=viewpoint['target']
    catalog.append(dict(key='spring_surf',name='鳌山湾 · 湿沙与浅浪',group='滨海公园',x=x,y=y,z=z,h=2,r=35,
                        viewpoint={k:viewpoint[k] for k in ('eye','target','fov')},note='从湿沙向海看，沿沙泥质浅滩观察碎浪、退水和干湿沙色。'))
    for view in architecture['viewpoints']:
        loc=next((item for item in catalog if item['key']==view['key']),None)
        if loc is None:
            x,y,z=view['target']
            loc=dict(key=view['key'],name=view['name'],group='院楼与生活区',x=x,y=y,z=z,h=14,r=40)
            catalog.append(loc)
        loc['viewpoint']={k:view[k] for k in ('eye','target','fov')}
        loc['note']=view['note']
    from qd_video_horizon import build as build_horizon
    build_horizon(scene,terrain,data,catalog)
    from qd_video_views import add as add_film_views
    add_film_views(catalog)
    from qd_video_courts import bind as bind_courts
    bind_courts(scene)
    from qd_spring_surfaces import bind
    surfaces=bind(scene)
    from qd_facade_materials import bind as bind_panels
    surfaces.update(bind_panels(scene))
    surfaces['orchardFloorPixels']=qd_orchard_floor.bind(scene,terrain,plots)
    parcels=qd_v6_parcels.build(scene,terrain,data,catalog)
    save(ROOT/'data/v6_parcels.json',parcels)
    from qd_v6_views import add_views
    add_views(catalog)
    alumni_stats=qd_v6_alumni.build(scene,terrain,data,catalog)
    save(ROOT/'data/v6_alumni.json',alumni_stats)
    from qd_landmark_views import set_views
    set_views(catalog)
    garden_stats=yuxian_gardens.build(scene,terrain,catalog)
    save(ROOT/'data/v6_yuxian.json',garden_stats)
    hall=next(r for r in data['buildings'] if r['id']=='s2/hall-c1')
    inner_court=union(Polygon(ring).buffer(-5) for ring in hall['holes']).difference(union([road.buffer(2),walk.buffer(1),parking,water,parcel_reserve,obstacle_footprints,reserve]))
    plantable=available.difference(reserve).union(inner_court)
    save(ROOT/'data/体育馆下沉花坡.json',terrain.arena_slope.build(scene,terrain,catalog))
    save(ROOT/'data/淦昌苑四行樱花.json',build_cherry_walk(scene,terrain,catalog,cherry_walk))
    save(ROOT/'data/图书馆方格花园.json',plant_library_garden(scene,terrain,catalog))
    from qd_sport_facilities import build as detail_sports
    save(ROOT/"data/运动场细节依据.json",detail_sports(scene,data,catalog))
    planting=qd_v6_planting.build(scene,terrain,data,catalog,plantable)
    save(ROOT/'data/v6_planting.json',planting)
    import qd_grass_relief
    relief_grass = qd_grass_relief.build(scene, terrain, data, catalog, plantable, yuxian_gardens.lawns)
    save(ROOT/'data/立体草坪.json', relief_grass)
    save(ROOT/"data/博物馆北侧步道.json",museum_walk.build(scene,terrain,catalog))
    save(ROOT/'data/双创前庭.json',innovation.build(scene,terrain,catalog,inscriptions))
    from qd_arch_colours import bind as finish_architecture
    surfaces.update(finish_architecture(scene))
    from scipy.spatial.transform import Rotation
    light_setup=read(ROOT/'data/夕照光照.json')
    az,alt=np.radians([light_setup['azimuthDeg'], light_setup['elevationDeg']])
    sunlight=-np.array([np.sin(az)*np.cos(alt),np.sin(alt),-np.cos(az)*np.cos(alt)])
    rotation,_=Rotation.align_vectors([sunlight],[[0,0,-1]])
    lamp={'name':'SDU_Sunset_Key','type':'directional','color':light_setup['sunLinearRGB'],'intensity':light_setup['threeSunIntensity']}
    scene.doc.setdefault('extensions',{})['KHR_lights_punctual']={'lights':[lamp]}
    scene.doc['extensionsUsed'].append('KHR_lights_punctual')
    scene.doc['scenes'][0]['nodes'].append(len(scene.doc['nodes']))
    scene.doc['nodes'].append(dict(name=lamp['name'],rotation=rotation.as_quat().tolist(),extras={'kind':'sunsetRig'},
                                  extensions={'KHR_lights_punctual':{'light':0}}))
    from qd_yinghai_lake import refine as finish_lake
    finish_lake(scene)
    from qd_botanic_detail import bind as finish_botanic_detail
    finish_botanic_detail(scene)
    from qd_natural_finishes import bind as finish_natural_surfaces
    finish_natural_surfaces(scene)
    from qd_coast_cleanup import finish as finish_coast
    finish_coast(scene, waterfront)
    from qd_ground_contacts import ground_scene
    ground_scene(scene)
    for node in scene.doc['nodes']:
        tags=node.get('extras',{})
        if tags.get('kind') in ('hinterland','terrainContext'):
            tags['sceneRegion']='surroundings'
        elif tags.get('kind')=='groundSupport':
            owner=scene.doc['nodes'][tags['groundContactOwner']].get('extras',{})
            if owner.get('sceneRegion')=='surroundings':tags['sceneRegion']='surroundings'
        elif tags.get('kind') in ('flora','groundcover'):
            x,_,z=node['translation']
            if not core_land.covers(Point(x,z)):
                tags['sceneRegion']='surroundings'
    for place in catalog:
        if place.get('group')=='校园周边' or place['key'] in ('film-village','film-ridge'):
            place['sceneRegion']='surroundings'
    from qd_model_area import add_views as add_inspection_views,add_cut_edge
    add_inspection_views(catalog)
    add_cut_edge(scene,terrain,domain,core_land,waterfront)
    out=ROOT/'山东大学青岛校区.glb';scene.save(out)
    save(ROOT/'data'/'locations.json',catalog)
    save(ROOT/'data'/'实体题字.json',inscriptions)
    save(ROOT/'data'/'scene-summary.json',dict(sourceBuildings=len(buildings),mappedRoads=len(roads),mappedSports=len(courtpolys),
        revision='夕照校园-v6',refinedColleges=[p['name'] for p in catalog if p['group']=='学院楼'],
        spring=spring,phoenixGarden=phoenix,surfaces=surfaces,physicalCollegeInscriptionLines=sum(r['owner'] in {p['key'] for p in catalog if p['group']=='学院楼'} for r in inscriptions),physicalInscriptionLines=len(inscriptions),waterfrontExtent=list(waterfront.substrate.bounds),
        modeledLandmarks=[s[1]['name'] for s in specs],
        treeCount=sum(n.get('extras',{}).get('kind')=='flora' and not n['extras'].get('shrub') for n in scene.doc['nodes']),
        shrubCount=sum(n.get('extras',{}).get('kind')=='flora' and bool(n['extras'].get('shrub')) for n in scene.doc['nodes']),
        extent=data['metadata']['bounds_xz'],extentDescription='校园底图边界；滨海精修范围见 waterfrontExtent',
        groundcover=grass,grassRelief=relief_grass,meshCount=len(scene.doc['meshes']),sceneNodes=len(scene.doc['nodes']),terrainDatum=terrain.datum,terrainSource='Mapzen Terrain Tiles / Terrarium',terrainRange=terrain.terrainRange))
    print('GLB',out.stat().st_size,'bytes;',len(catalog),'places;',plants,'plants',flush=True)
if __name__=='__main__':main()

