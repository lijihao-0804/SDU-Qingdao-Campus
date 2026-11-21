"""Bake the editable Qingdao sunset rig to one scene-linear Radiance panorama.

The browser and Cycles use this same texture for lighting and background.
Yaw follows Blender equirectangular projection. The original pixels are
stored in old-style flat RGBE, with a documented Radiance header.
"""
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = json.loads((ROOT / "data/夕照光照.json").read_text("utf8"))
HDR = ROOT / SETTINGS["panorama"]


def sun_enu():
    azimuth, altitude = np.radians([SETTINGS["azimuthDeg"], SETTINGS["elevationDeg"]])
    return np.array([np.sin(azimuth) * np.cos(altitude),
                     np.cos(azimuth) * np.cos(altitude), np.sin(altitude)])


def smooth(lo, hi, x):
    u = np.clip((x - lo) / (hi - lo), 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


def blend(a, b, weight):
    return a + (np.asarray(b) - a) * weight[..., None]


def noise(x, y):
    ix, iy = np.floor(x), np.floor(y)
    ux, uy = smooth(0, 1, x - ix), smooth(0, 1, y - iy)

    def at(dx, dy):
        return np.mod(np.sin((ix + dx) * 12.9898 + (iy + dy) * 78.233) * 43758.5453, 1.0)

    first = (1 - ux) * at(0, 0) + ux * at(1, 0)
    second = (1 - ux) * at(0, 1) + ux * at(1, 1)
    return first * (1 - uy) + second * uy


def scene_radiance(east, north, height):
    sun = sun_enu()
    az_dot = (east * sun[0] + north * sun[1]) / max(0.001, math.hypot(*sun[:2]))
    west = smooth(-0.40, 0.96, az_dot)
    horizon = blend(np.array([0.67, 0.62, 0.66]), [1.62, 0.80, 0.38], west)
    low = blend(np.array([0.41, 0.49, 0.66]), [1.09, 0.59, 0.34], west)
    middle = blend(np.array([0.205, 0.365, 0.585]), [0.45, 0.44, 0.54], west)
    sky = blend(horizon, low, smooth(-0.025, 0.14, height))
    sky = blend(sky, middle, smooth(0.06, 0.41, height))
    sky = blend(sky, [0.075, 0.15, 0.29], smooth(0.38, 1.00, height))

    # Thin cirrus is mapped onto a plane above the viewer, softening at the horizon.
    denom = np.maximum(0.115, height + 0.09)
    x, y = east / denom, north / denom
    long, short = x * 0.64 + y * 0.77, x * -0.77 + y * 0.64
    curl = noise(long * 0.70, short * 0.72) - 0.5
    base = (0.57 * noise(long * 0.70, short * 2.65 + curl)
            + 0.29 * noise(long * 1.28, short * 5.12 + curl * 2.0)
            + 0.14 * noise(long * 2.68, short * 9.61))
    veil = smooth(0.52, 0.79, base) * smooth(0.012, 0.12, height)
    veil *= (1.0 - smooth(0.66, 0.98, height)) * (0.18 + 0.28 * west)
    sky = blend(sky, blend(np.array([0.76, 0.67, 0.73]), [1.40, 0.86, 0.53], west), veil)

    # A broad aureole and sub-degree disc share the directional lamp's unit vector.
    angle = np.degrees(np.arccos(np.clip(east * sun[0] + north * sun[1] + height * sun[2], -1, 1)))
    aureole = 0.46 * np.exp(-angle / 12.0) + 1.38 * np.exp(-angle / 3.0)
    disc = 1.0 - smooth(SETTINGS["sunDiameterDeg"] / 2 - 0.055, SETTINGS["sunDiameterDeg"] / 2 + 0.055, angle)
    sky += aureole[..., None] * np.array([1.0, 0.49, 0.17])
    sky += disc[..., None] * np.array([19.0, 12.2, 5.8])
    return blend(sky, [0.105, 0.114, 0.134], smooth(0.0, 0.23, -height))


def write_panorama(path=HDR, width=2048, height=1024):
    longitude = math.tau * (0.5 - (np.arange(width) + 0.5) / width)
    with path.open("wb") as out:
        out.write(f"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y {height} +X {width}\n".encode("ascii"))
        # Row zero is the north pole of the texture, elevation +90 degrees.
        for first in range(0, height, 64):
            rows = np.arange(first, min(first + 64, height))
            lat = (math.pi * (0.5 - (rows + 0.5) / height))[:, None]
            east = np.cos(lat) * np.cos(longitude)
            north = np.cos(lat) * np.sin(longitude)
            up = np.broadcast_to(np.sin(lat), east.shape)
            pixels = scene_radiance(east, north, up)
            peak = pixels.max(axis=2)
            mantissa, exponent = np.frexp(peak)
            scale = (mantissa * 256 / peak)[..., None]
            rgbe = np.concatenate((pixels * scale, (exponent + 128)[..., None]), axis=2)
            out.write(rgbe.astype(np.uint8).tobytes())
    return path


if __name__ == "__main__":
    print(write_panorama())
