"""Plan dimensions shared by the two teaching courts and their campus road connections."""
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

KEYS = {'huagang', 'zhensheng'}
HALF_PASSAGE = 4.30
FLOOR = .11
ROAD_LIFT = .205
PAVING = '#b9b4a8'


def dimensions(key, width, depth):
    if key == 'zhensheng':
        return width/2-3.3, depth/2-2.1, 35.8, 42.4
    return width/2-.7, depth/2-.7, 36.7, 40.0


class CourtGround:
    """Pave each threshold up to the first mapped street on its outward axis."""
    def __init__(self, specs, road):
        self.sites = []
        self.entries = {}
        for _, spec, x, z, _ in specs:
            if spec['key'] not in KEYS:
                continue
            from qd_wing_junctions import GAP
            rx, rz, _, iz = dimensions(spec['key'], spec['w'], spec['d'])
            self.sites.append(box(x-rx, z-rz, x+rx, z+rz))
            entries=[('东',1,0,0),('西',-1,0,0),('南',0,1,0),('北',0,-1,0)]
            for face, dx in [('东',1),('西',-1)]:
                for end, sign in [('北',-1),('南',1)]:
                    entries.append((face+'翼'+end+'端',dx,0,sign*(iz-GAP/2)))
                    entries.append((face+end+'端楼方门',dx,0,sign*(iz+rz)/2))
            for side, dx, dz, offset in entries:
                radius = rx if dx else rz

                def point(along, across):
                    return x+dx*(radius+along)-dz*across, z+offset+dz*(radius+along)+dx*across

                threshold = Point(point(0,0))
                street = LineString([threshold, point(65,0)]).intersection(road)
                if street.is_empty:
                    raise ValueError(f"{spec['name']}{side}侧入口轴线上缺少校园道路")
                curb = threshold.distance(street)
                neck = min(curb*.5, .8 if dx else 3.0)
                far = curb + 2
                half = (GAP/2-.14) if offset else HALF_PASSAGE
                mouth = half + min((curb-neck)*.32, 1.5 if dx else 4.4)
                apron = Polygon([point(0,-half),point(neck,-half),point(far,-mouth),
                                 point(far,mouth),point(neck,half),point(0,half)])
                self.entries[f"{spec['name']}·{side}侧入院道路"] = apron.difference(road)
        self.paving = unary_union(list(self.entries.values()))
        # Courtyard lawns are planted in the landmark itself. Keep independent
        # campus trees, parking objects and groundcover off its paths and doors.
        self.plant_reserve = unary_union([*self.sites, self.paving.buffer(5.5)])
