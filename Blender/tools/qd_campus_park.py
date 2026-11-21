"""Continuous dry ground from the campus east boundary to the park and adjacent strand."""
from shapely import union_all
from shapely.geometry import Polygon, box

from qd_terrain import sourcepolygon


def connecting_land(waterfront):
    """Bound the added land separately from the campus, park and coastal water.

    The north cap aligns with the campus's northern edge. The south cap runs
    from the east campus flank to the adjoining strand, tapering along the park's
    southern entrance. The irregular tidal outline, including inlets, is retained.
    X/Z values are metres in the map's established model frame.
    """
    envelope = Polygon([
        (245, -1279), (387, -1279), (454, -900), (542, -650),
        (720, -330), (950, -20), (945, -10), (921, -3),
        (858, 0), (766, 1), (697, 4), (661, 11), (40, 11), (40, -1200),
    ])
    # The divided coast road also leaves a narrow median north of campus.
    # Close the short lateral breaks here without extending the observed shore.
    north = waterfront.substrate.intersection(box(260, -1980, 650, -1265))
    closed_road = north.buffer(10, quad_segs=4).buffer(-10, quad_segs=4)
    # Provide a 1 m verge outside the carriageway at the focused-view edge.
    median = closed_road.buffer(1, quad_segs=4).difference(north)
    median = median.intersection(waterfront.park.buffer(27))
    water = union_all([sourcepolygon(row) for row in waterfront.data['water']])
    return envelope.union(median).intersection(waterfront.land).difference(water)


def land_regions(waterfront):
    """Return the detailed-land domain and the land visible in focused mode."""
    data = waterfront.data
    campus = Polygon(data['boundary']).buffer(0)
    park = waterfront.substrate.union(waterfront.path_geom.intersection(waterfront.land))
    corridor = connecting_land(waterfront)
    cover = union_all([
        sourcepolygon(row) for group in ('greens', 'beaches') for row in data[group]
    ])
    local = campus.buffer(70, join_style=1).union(cover).intersection(waterfront.outer)
    domain = local.union(waterfront.substrate).union(corridor).difference(waterfront.ocean)
    core = campus.buffer(22, quad_segs=5).union(park.buffer(2.5)).union(corridor)
    return domain, core
