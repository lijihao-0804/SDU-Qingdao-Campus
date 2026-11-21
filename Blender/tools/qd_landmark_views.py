"""Named public-facing views of the four campus entrances and Yinghai Lake."""
import math


def set_views(catalog):
    places = {p['key']: p for p in catalog}

    def author(key, aliases, shots):
        place = places[key]
        yaw = place.get('yaw', 0)
        cos, sin = math.cos(yaw), math.sin(yaw)

        def world(local):
            x, y, z = local
            return [round(place['x'] + x*cos + z*sin, 4),
                    round(place['y'] + y, 4),
                    round(place['z'] - x*sin + z*cos, 4)]

        place['aliases'] = list(dict.fromkeys([*place.get('aliases', []), *aliases]))
        place['views'] = {}
        for mode, label, eye, target, fov in shots:
            pose = dict(eye=world(eye), target=world(target), fov=fov, label=label)
            if mode != 'facade':
                pose['hideMapLabels'] = True
            if mode == 'facade' and key in ('west_gate', 'north_gate', 'east_gate', 'south_gate'):
                pose['minAspect'] = 1.18  # Keep both sides of the entrance in a portrait viewport.
            place['views'][mode] = pose

    # The signed tower stands right of the ceremonial approach, 30.23 m from its axis.
    author('west_gate', ['西门', '西校门', '礼仪正门'], [
        ('facade', '西门外观', (-5, 11, 88.5), (0, 7.8, .2), 43),
        ('inscription', '校名题字', (32, 11.2, 18.6), (30.228, 12.12, 4.13), 38),
    ])
    author('north_gate', ['北门', '北校门'], [
        ('facade', '北门外观', (4.0, 7.3, 51), (3.5, 6.9, .5), 39),
        ('detail', '石塔近景', (19.2, 6.5, 20.2), (16.86, 8.4, 3.17), 40),
    ])
    author('east_gate', ['东门', '东校门'], [
        ('facade', '东门外观', (-58, 31.6063, -22), (0, 9.6063, 6), 53),
        ('detail', '南侧门亭与弧廊', (-21, 11.6063, 36), (-2, 3.8063, 32.193), 64.3),
    ])
    # The sign faces the approach along the 17-degree rotation of the southern gate tower.
    author('south_gate', ['南门', '南校门'], [
        ('facade', '南门外观', (-18, 9.8, 49), (-2, 5.7, 1), 36),
        ('inscription', '校名题字', (-17.65, 7.95, 8.15), (-14.90, 8.35, -.55), 40),
    ])
    # Both cameras face across the shoreline from the east towards the setting sun.
    author('lake', ['樱海湖', '湖畔', '湖面'], [
        ('facade', '湖面全景', (121.27, 43.43, -76.35), (2.27, 1.43, -.35), 47),
        ('shore', '湖畔近景', (74.27, 13.93, -25.35), (-36.73, .03, 7.65), 38),
    ])
    places['lake']['note'] = '从东岸向西望，夕阳的倒影沿水纹铺开。湖湾近岸水浅，浅色水边勾出岸线。'

    for key,halfx,halfz in [('zhensheng',61,69),('huagang',62.5,62)]:
        views=[('facade','四翼和内院鸟瞰',(106,105,145),(0,1,0),49)]
        for mode,label,eye,target in [
            ('north','由北入院',(0,1.87,-halfz-8),(0,1.73,-halfz+18)),
            ('east','由东入院',(halfx+6,1.87,0),(halfx-20,1.73,0)),
            ('south','由南入院',(0,1.87,halfz+8),(0,1.73,halfz-18)),
            ('west','由西入院',(-halfx-5,1.87,0),(-halfx+20,1.73,0))]:
            views.append((mode,label,eye,target,54))
        from qd_wing_junctions import GAP
        from qd_teaching_courts import dimensions
        ex,ez,ix,iz=dimensions(key,halfx*2,halfz*2)
        cross=iz-GAP/2
        views.extend([
            ('seams','两端翼楼与连廊',(ex+85,31,9),(ex-6,8,0),52),
            ('end_porch','端楼方洞与凹窗',(ex+11.3,4.3,(ez+iz)/2+3.3),(ex-.8,6.6,(ez+iz)/2),69),
            ('inside_passage','从内院回望翼端',(ix-4,1.74,cross-.45),(ex+5.8,1.78,cross+.38),60),
            ('through','翼端穿廊入院',(ex+5.8,1.78,cross+.38),(ix-4,1.74,cross-.45),57)])
        author(key,['振生苑'] if key=='zhensheng' else [],views)

    def absolute(key, aliases, shots):
        place=places[key]
        place['aliases']=list(dict.fromkeys([*place.get('aliases',[]),*aliases]))
        place.setdefault('views',{}).update({
            mode:dict(eye=eye,target=target,fov=fov,label=label,hideMapLabels=(mode!="facade"))
            for mode,label,eye,target,fov in shots})
    def height(key,xyz):
        return [xyz[0],round(places[key]['y']+xyz[1],3),xyz[2]]
    dorm='way-970257676'
    dshots=[('facade','凤凰居一号楼全貌',(323,36,650),(230,10,699),54),
            ('bow','弧形挑板侧面',(296,12.428,650),(279,8.628,668),47),
            ('porch','方形门廊侧面',(300,11.628,752),(279,6.228,732),44)]
    absolute(dorm,['宿舍阳台','弧形挑板','方形门廊'],[(m,l,height(dorm,e),height(dorm,t),f) for m,l,e,t,f in dshots])
    absolute('library', ['从图书馆望东门','图书馆望海'],[
        ('facade','图书馆西立面',[-8,38,-41],[169,26,-65],45),
        ('sea','从图书馆望东门与海',[218,52,-72],[574,4,80],49)])
    tower='way-868015914'
    absolute(tower,['双创','双创钟楼'],[
        ('facade','从凤凰居望双创',height(tower,[310,24,1035]),height(tower,[359,12,1083]),54),
        ('clock','钟塔与拱窗',[310,40.8,1057.1],[340.4,37.7,1089.4],50)])
    absolute('way-1020621360',['凤凰居六角亭','凤凰居凉亭'],[
        ('facade','六角亭和中轴', [296,21,845],[308,15,828],49),
        ('garden','凤凰居中轴全景',[303,38,909],[309,15,812],54)])
