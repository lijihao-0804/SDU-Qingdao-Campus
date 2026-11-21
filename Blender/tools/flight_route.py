"""Continuous QD v6 flight. Positions use metres [east, up, south], vertical FOV."""
from bisect import bisect_right
from math import atan2, cos, degrees, hypot, radians, sin
from pathlib import Path
import json

DATA = Path(__file__).resolve().parents[1] / 'data/locations.json'
DURATION = 131.5
# All camera and title times below are elapsed seconds in the film.

# Seconds, eye position, sightline target, vertical angle. Each pose is traversed
# continuously. The panning curves are independent of distance to the subject.
POSES = [
    # West gate, the rising axis across Yuxian Square, then the library.
    (0, (-272.2094, 9.0453, -72.4672), (-183.9094, 5.8453, -67.4672), 43),
    (1.4698, (-263, 11, -72.18), (-184, 6.5, -67.5), 43),
    (3.5826, (-215, 22, -70.7), (161, 24, -64), 46),
    (5.3279, (-163, 33, -69.1), (164, 25, -64), 47),
    (7.1651, (-95, 40, -67.01), (165, 26, -64.3), 47),
    (8.7267, (-50, 43.5, -65.62), (140, 25, -64.2), 43),
    (10.7477, (-6, 46, -64.27), (167, 29, -65), 38),
    (12.493, (26, 47, -63.28), (167, 31, -65), 38),
    (14.0547, (46, 48, -62.67), (164, 31, -64), 40),
    (15.157, (66, 54, -62.05), (163, 32, -45), 44),
    (16.3512, (94, 68, -56), (154, 29, -15), 48),
    (17.4535, (113, 86, -36), (168, 10, 43), 51),
    (18.464, (118, 94, -4), (158, 6, 91), 52),
    (19.8419, (118, 96, 52), (151, 6, 151), 53),
    (21.3116, (118, 96, 116), (135, 9, 199), 53),
    (22.5977, (118, 96, 175), (107, 12, 256), 52),
    # Hold the incoming altitude; let all four courtyard wings sit within the frame.
    (23.4, (114, 96, 193), (35, 13, 289), 53),
    (24.3, (110, 96, 206), (-17, 13, 314), 53),
    (25.05, (108, 96, 211), (-29.65, 12, 322.7), 52),
    (26.8, (105.5, 96, 213), (-29.65, 12, 322.7), 50.5),
    (28.65, (102.5, 96, 216), (-29.65, 12, 322.7), 50),
    (29.4, (96, 96, 226), (-24, 13, 332), 51),
    (30.4, (75, 96, 252), (-3, 16, 361), 52),
    (31.4, (54, 93, 294), (30, 21, 420), 52),
    (32.45, (48, 81, 347), (59, 24, 484), 50),
    (33.5, (52, 62, 385), (68, 26, 503), 47),
    (34.55, (59, 54, 403), (68, 25, 505), 44),
    (35.5, (64, 52, 418), (68, 25, 505), 44),
    # Travel diagonally southwest from the museum to the arena and its flower slope.
    (36.45, (57, 57, 430), (64, 25, 510), 47),
    (37.25, (39, 64, 447), (36, 24, 522), 50),
    (38.15, (7, 71, 466), (-3, 23, 557), 51),
    (39.25, (-38, 77, 493), (-51, 22, 602), 51),
    (40.5, (-96, 82, 532), (-95, 21, 650), 50),
    (41.7, (-150, 83, 574), (-126, 21, 701), 50),
    (42.8, (-192, 81, 617), (-140, 22, 754), 50),
    (44.1, (-221, 77, 689), (-144, 22, 798), 50),
    (45.25, (-227, 75, 753), (-140, 20, 828), 51),
    (46.4, (-218, 71, 820), (-123, 18, 855), 50),
    (47.45, (-198, 70, 867), (-85, 20, 890), 51),
    # Approach the innovation centre from the west. Compose the clock tower with the forecourt.
    (48.4, (-159, 70, 902), (-16, 23, 940), 51),
    (49.7, (-78, 70, 946), (89, 27, 992), 50),
    (51, (18, 69, 989), (174, 30, 1025), 49),
    (52.2, (109, 66, 1023), (271, 33, 1058), 47),
    (53.15, (175, 63, 1046), (331, 34, 1080), 46),
    (54.25, (228, 59, 1056), (350, 33, 1082), 45),
    (55.35, (257, 55, 1057), (351, 33, 1084), 43),
    (56.55, (265, 53, 1056), (352, 33, 1067), 43),
    (57.5, (269, 53, 1055), (351, 32, 1031.5), 44),
    # Turn across the plaza toward the south wing of Residence 9, then its central garden.
    (58.2, (271, 54, 1054), (335, 32, 1004), 46),
    (59.05, (274, 56, 1052), (310, 31, 974), 48),
    (59.85, (272, 57, 1050), (273.5, 29, 966), 46),
    (60.9, (267, 57, 1048), (237, 30, 973), 44),
    (62.1, (270, 58, 1040), (239, 30, 975), 45),
    (63.1, (278, 61, 1025), (258, 28, 957), 47),
    (64.05, (285, 65, 998), (297, 20, 916), 50),
    (65.15, (297, 69, 948), (311, 14, 869), 51),
    # Follow the garden-to-college line at an even pace; slow down before the west facade.
    (66.45, (316, 71, 878), (328, 16, 797), 51),
    (68.3, (344, 72, 775), (374, 17, 663), 50),
    (70.25, (373, 70, 665), (403, 19, 550), 50),
    (72, (397, 66, 566), (440, 20, 436), 49),
    (73.4, (412, 61, 489), (476, 18, 366), 48),
    (74.5, (420, 55, 434), (492, 17, 338), 47),
    (75.5, (422, 51, 397), (499, 16, 329), 46),
    (76.5, (423, 48, 373), (499, 16, 329), 46),
    (77.6, (424, 46, 359), (499, 16, 329), 45),
    (79.1, (427, 44, 350), (499, 16, 329), 44),
    (80.6, (431, 43, 344), (499, 16, 329), 44),
    # Leave the college for the beach, red tower and shell pavilion.
    (81.4, (437, 46, 330), (508, 17, 311), 47),
    (82.3, (458, 53, 285), (528, 18, 237), 49),
    (83.35, (507, 60, 197), (586, 18, 86), 50),
    (84.6, (590, 64, 32), (663, 13, -108), 51),
    (86, (698, 58, -162), (752, 0, -310), 52),
    (87.32, (745, 49, -319), (726, -4, -485), 53),
    (88.65, (679, 45, -488), (566, -5, -648), 53),
    (90.18, (578, 40, -703), (472, -5, -873), 53),
    (91.54, (522, 37, -890), (438, -5, -1052), 53),
    (92.7, (501, 37, -1055), (432, -4, -1226), 52),
    (93.85, (526, 37, -1210), (488, 2, -1375), 51),
    (94.95, (605, 36, -1336), (526, 8, -1475), 49),
    (95.83, (634, 34, -1415), (527, 10, -1483), 48),
    (96.92, (644, 32, -1467), (526, 10, -1483), 47),
    (98.17, (626, 31, -1500), (528, 9, -1470), 47),
    (99.36, (606, 29, -1515), (534, 6, -1460), 47),
    (100.456, (585, 30, -1522), (532, 5, -1457), 47),
    (101.479, (564, 34, -1520), (511, 5, -1455), 47),
    (102.606, (532, 40, -1480), (441, 13, -1346), 49),
    (103.922, (456, 49, -1393), (350, 13, -1228), 50),
    (105.306, (344, 57, -1309), (223, 16, -1159), 50),
    (106.708, (236, 59, -1239), (112, 16, -1085), 48),
    (107.654, (156, 57, -1200), (27, 13, -1052), 46),
    (108.566, (109, 50, -1148), (12, 12, -1030), 45),
    (109.606, (80, 43, -1114), (8, 12, -1018), 44),
    (110.604, (64, 40, -1094), (7, 12, -1012), 44),
    (111.49, (55, 39, -1082), (6, 12, -1009), 44),
    (112.16, (49, 40, -1073), (7, 12, -1003), 45),
    (112.831, (43, 44, -1054), (12, 12, -976), 46),
    (113.485, (42, 55, -1001), (36, 11, -901), 49),
    (114.2, (42, 65, -903), (58, 11, -768), 50),
    (114.85, (39, 65, -809), (70, 12, -681), 48),
    (115.68, (36, 60, -755), (76, 12, -651), 45),
    (116.6, (32, 60, -725), (77, 13, -650), 46),
    # Pull back from the hall; the middle of the ascent has equal vertical and horizontal increments.
    (117.05, (23.0231, 70.1057, -725.3687), (77.032, 12.9983, -649.9679), 46.0004),
    (117.55, (-8.008, 105.039, -726.6433), (77.6253, 12.9666, -649.3724), 46.0077),
    (118.25, (-88.689, 195.8655, -729.9571), (82.4591, 12.7082, -644.5202), 46.0673),
    (119, (-198.4063, 319.3795, -734.4636), (95.753, 11.9977, -631.1761), 46.2313),
    (120.1, (-359.325, 500.5335, -741.0731), (126.2572, 10.3672, -600.5565), 46.6076),
    (121.35, (-542.1872, 706.3902, -748.5839), (171.2121, 7.9644, -555.4316), 47.1621),
    (122.6, (-725.0494, 912.247, -756.0948), (220.2003, 5.346, -506.258), 47.7663),
    (123.8, (-900.597, 1109.8695, -763.3051), (264.3379, 2.9869, -461.9534), 48.3107),
    (125.85, (-1200.491, 1447.4745, -775.6229), (314.7609, 0.2918, -411.3398), 48.9327),
    (126.55, (-1281.172, 1538.301, -778.9367), (319.5947, 0.0334, -406.4876), 48.9923),
    (127.05, (-1312.2031, 1573.2343, -780.2113), (320.188, 0.0017, -405.8921), 48.9996),
    (127.5, (-1321.18, 1583.34, -780.58), (320.22, 0, -405.86), 49),
    (131.5, (-1321.18, 1583.34, -780.58), (320.22, 0, -405.86), 49),
]
# Titles use v6 catalog spelling. Label anchor altitude is relative to stored
# ground except for a few entries that already describe an elevated surface.
SHOTS = [
    ('west_gate', '西门', 0, 3.76, 11, None),
    ('yuxian', '育贤广场', 5.19, 7.67, 2, None),
    ('library', '青岛校区图书馆', 9.32, 15.02, 31, None),
    ('zhensheng', '振声苑', 24.7, 28.85, 14, None),
    ('museum', '山东大学博物馆', 33.55, 36.75, 21, (69.0, 25.0, 505.0)),
    ('song_arena', '宋君复体育馆', 43.0, 47.4, 24, (-144.0, 24.0, 804.0)),
    ('way-868015914', '创新创业中心', 52.95, 56.9, 0, (351.0, 31.5, 1068.5)),
    ('way-970257678', '凤凰居学生宿舍 · 9号楼', 59.85, 63.05, 15, (255.0, 31.0, 994.63)),
    ('spring_phoenix_garden', '凤凰居中轴花园', 64.3, 66.3, 2.5, None),
    ('way-868015916', '第周苑 D 座', 75.5, 80.85, 13, None),
    ('waterfront-beach', '鳌山湾 · 滨海沙滩', 88.9, 91.52, 0, None),
    ('coastal-red-tower', '红顶观景塔', 95.6, 98.12, 15, None),
    ('coastal-pavilion-1', '球壳观景建筑', 98.32, 101.2, 9, None),
    ('s2-b1', '阅海居', 108.75, 112.95, 13, None),
    ('assembly', '学生会堂', 114.3, 116.7, 16, None),
    ('overview', '山东大学青岛校区', 127.5, 131.5, 0, (205, 0, -125)),
]

def _slopes(xs, ys):
    """Shape-preserving Hermite derivatives, with a zero start and finish."""
    h = [b-a for a,b in zip(xs,xs[1:])]
    d = [(b-a)/dt for a,b,dt in zip(ys,ys[1:],h)]
    slopes = [0.0]
    for i in range(1,len(xs)-1):
        if d[i-1] * d[i] <= 0.0:
            slopes.append(0.0)
        else:
            a, b = 2*h[i]+h[i-1], h[i]+2*h[i-1]
            slopes.append((a+b)/(a/d[i-1]+b/d[i]))
    return slopes+[0.0]

class Route:
    def __init__(self, locations):
        self.duration=DURATION
        self.times=[p[0] for p in POSES]
        self.hold_start=self.times[-2]
        poses=list(POSES)
        gate=locations['west_gate']['views']['facade']
        poses[0]=(0,gate['eye'],gate['target'],gate['fov'])
        data=[]
        for t,eye,target,fov in poses:
            dx,dy,dz=(target[k]-eye[k] for k in range(3))
            horizontal=hypot(dx,dz)
            yaw=degrees(atan2(dx,dz))
            if data:
                yaw=data[-1][3]+((yaw-data[-1][3]+180)%360)-180
            data.append((*eye,yaw,degrees(atan2(dy,horizontal)),hypot(horizontal,dy),fov))
        self.values=list(zip(*data))
        self.slopes=[_slopes(self.times,vals) for vals in self.values]
        self.shots=[]
        for key,title,start,end,height,anchor in SHOTS:
            if anchor is None:
                place=locations[key]
                anchor=(place['x'],place['y']+height,place['z'])
            self.shots.append(dict(key=key,title=title,start=start,end=end,label_start=start,label_end=end,anchor=list(anchor),
                                   subtitle='信息科学与工程学院' if key=='way-868015916' else ''))
    def sample(self, seconds):
        t=min(max(float(seconds),0.0),self.duration)
        i=min(bisect_right(self.times,t)-1,len(self.times)-2)
        span=self.times[i+1]-self.times[i]
        u=(t-self.times[i])/span
        a=(1+2*u)*(1-u)**2
        b=u*(1-u)**2*span
        c=u*u*(3-2*u)
        d=u*u*(u-1)*span
        x,y,z,yaw,pitch,depth,fov=[a*k[i]+b*v[i]+c*k[i+1]+d*v[i+1] for k,v in zip(self.values,self.slopes)]
        yaw,pitch=radians(yaw),radians(pitch)
        h=cos(pitch)*depth
        target=[x+sin(yaw)*h,y+sin(pitch)*depth,z+cos(yaw)*h]
        shot=next((s for s in self.shots if s['start']<=t<=s['end']),None)
        return {'position':[x,y,z],'eye':[x,y,z],'target':target,'fov_deg':fov,'fov':fov,
                'label':shot['title'] if shot else '', 'key':shot['key'] if shot else ''}

def build_route(locations=None):
    if locations is None or isinstance(locations,(str,Path)):
        locations=json.loads(Path(locations or DATA).read_bytes())
    if not isinstance(locations,dict):
        locations={p['key']:p for p in locations}
    return Route(locations)
