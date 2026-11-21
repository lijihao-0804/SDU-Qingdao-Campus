"""Build the campus film timeline from the approved edit and its camera curve."""

import json
from pathlib import Path
from runpy import run_path


def _camera_frame(route, seconds):
    pose = route.sample(seconds)
    return {
        'eye': [round(value, 6) for value in pose['eye']],
        'target': [round(value, 6) for value in pose['target']],
        'fov': round(pose['fov'], 6),
    }


def build_plan(root: Path, fps: int) -> dict:
    """Return a 30 or 60 fps plan. All editorial intervals are half-open."""
    if fps not in (30, 60):
        raise ValueError('The manual film supports 30 or 60 fps.')
    root = Path(root)
    data = root / 'data'
    plan = json.loads((data / '海岸航线.json').read_bytes())
    source = plan['frames']
    count = len(source)
    hold = plan['holdStartFrame']
    if plan['fps'] != 30 or count != plan['duration'] * 30:
        raise ValueError('The approved edit must contain one camera sample per 30 Hz tick.')
    if not 0 <= hold < count or any(pose != source[hold] for pose in source[hold:]):
        raise ValueError('The approved panoramic hold contains camera motion or is missing.')

    scale = fps // 30
    for group, first, last in (('labels', 'start', 'end'),
                               ('lowerThirds', 'start', 'end'),
                               ('chapters', 'startFrame', 'endFrame')):
        for cue in plan[group]:
            start, end = cue[first], cue[last]
            if not 0 <= start < end <= count:
                raise ValueError(f'Invalid {group} interval for {cue["key"]}.')
            if group == 'chapters':
                poster = cue['posterFrame']
                if not start <= poster < end:
                    raise ValueError(f'Poster lies outside chapter {cue["key"]}.')
                cue['posterFrame'] = poster * scale
            cue[first], cue[last] = start * scale, end * scale

    if fps == 30:
        return plan

    # Use the curve associated with this project even when invoked from elsewhere.
    build_route = run_path(str(root / 'tools' / 'flight_route.py'))['build_route']
    route = build_route(data / 'locations.json')
    if route.duration != plan['duration'] or route.hold_start != hold / 30:
        raise ValueError('Camera curve timing differs from the approved edit.')

    frames = []
    for i, original in enumerate(source):
        if _camera_frame(route, i / 30) != original:
            raise ValueError(f'Camera curve differs from approved 30 fps frame {i}.')
        frames.append(original)
        midpoint = _camera_frame(route, (2 * i + 1) / fps)
        if i >= hold and midpoint != source[hold]:
            raise ValueError(f'Camera curve moves during the hold at 60 fps frame {2*i+1}.')
        frames.append(midpoint)
    plan.update(fps=fps, frames=frames, holdStartFrame=hold * scale)
    return plan
