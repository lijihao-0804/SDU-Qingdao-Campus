"""Huiwen Square central lawns and library forecourt from photo 3 and overhead imagery.

Campus metre coordinates, X east. The OSM plaza outline starts halfway across
the western oval, so its missing western forecourt is supplied separately.
The blue-grey oval is represented as a flush surface; its use is unverified.
"""
from shapely.affinity import scale
from shapely.geometry import Point,Polygon,LineString,box
from shapely.ops import unary_union


def oval(x,z,rx,rz):
    return scale(Point(x,z).buffer(1,quad_segs=48),rx,rz,origin=(x,z))


WEST_FORECOURT=Polygon([(239.6,-101.4),(324.33,-98.38),(326.,-98.38),
                        (326.,-28.23),(324.27,-28.25),(239.6,-26.5)])
OVAL_CENTER=(319.1,-62.5)
BLUE_OVAL=oval(*OVAL_CENTER,30.7,11.65)
OVAL_WALK=oval(*OVAL_CENTER,35.8,14.65)
WEST_CROSS=box(267.4,-104,271.6,-22)
WEST_PATHS=unary_union([
    WEST_CROSS,
    LineString([(269.5,-89.6),(277.8,-87.9),(283.3,-85.5),(290.3,-81.8),
                (293.2,-78.1),(291.2,-75.0),(287.0,-70.8)]).buffer(.86),
    LineString([(269.5,-35.4),(277.7,-36.9),(283.9,-39.0),(289.6,-42.8),
                (293.4,-46.9),(293.2,-50.8),(291.2,-53.1)]).buffer(.86),
    box(308.4,-104,322.5,-22),
    box(239.6,-69.8,310.,-54.7),
])
# The two winding paths and their crossings are already mapped within the
# main garden. The central turf stops at these paths and at the crossing stones.
def axial_lawns(mapped_paths):
    ribbons=unary_union([box(lo,-66.55,hi,-57.55)
                         for lo,hi in ((249.8,282.7),(368.0,435.0),(474.1,528.4))])
    crossings=unary_union([mapped_paths.buffer(.23),OVAL_WALK,WEST_CROSS,box(372.7,-106,377.2,-16)])
    return ribbons.difference(crossings)


def draw_oval(ground,terrain,footprint):
    blue=BLUE_OVAL.intersection(footprint)
    rim=blue.buffer(.38).difference(blue).intersection(footprint)
    terrain.skin(ground,rim,'#c4c4b7',.17)
    terrain.skin(ground,blue,'#759aa9',.17)
