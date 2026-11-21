"""Render an offline WebGL campus tour at native resolution on its authored timeline."""
import argparse
import base64
from collections import Counter
from dataclasses import dataclass
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import threading
import time

from playwright.sync_api import sync_playwright

SOURCE = Path(__file__).with_name("capture.js")
MODEL = Path(__file__).resolve().parents[2] / '打开青岛校区.html'
CHROME = MODEL.parent / "运行环境/Chrome/chrome.exe"
FLAGS = ["--use-angle=d3d11", "--enable-webgl", "--enable-gpu", "--ignore-gpu-blocklist",
         "--disable-software-rasterizer", "--force-high-performance-gpu",
         "--disable-background-timer-throttling", "--disable-renderer-backgrounding"]


@dataclass(frozen=True)
class CaptureFormat:
    width: int = 1920
    height: int = 1080
    fps: int = 30

    def __post_init__(self):
        if (self.width, self.height) not in ((1920, 1080), (3840, 2160)):
            raise ValueError("Choose 1920x1080 or 3840x2160 for the 16:9 film.")
        if self.fps not in (30, 60):
            raise ValueError("Choose 30 or 60 fps.")

    @property
    def timescale(self):
        return self.fps * 1000

    @property
    def h264_level(self):
        if self.height == 2160:
            return "5.1" if self.fps == 30 else "5.2"
        return "4.1" if self.fps == 30 else "4.2"

    @property
    def bitrate_mbps(self):
        if self.height == 2160:
            return 72 if self.fps == 30 else 108
        return 36 if self.fps == 30 else 48


def digest(path):
    with Path(path).open("rb") as fh:
        return hashlib.file_digest(fh, "sha256").hexdigest()


def dump(path, obj):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def xyz(value):
    if not isinstance(value, (tuple, list)) or len(value) != 3 or not all(math.isfinite(x) for x in value):
        raise ValueError("Invalid world coordinate: " + repr(value))
    return list(value)


def prepare(plan, model, fps=30):
    if plan.get("fps", 30) != fps:
        raise ValueError(f"Expected an authored {fps} fps timeline, got {plan.get('fps', 30)} fps.")
    frames = []
    for item in plan["frames"]:
        eye, target = xyz(item.get("eye", item.get("position"))), xyz(item["target"])
        fov = item.get("fov", item.get("fov_deg"))
        if not (1 <= fov <= 165) or math.dist(eye,target) < 0.01:
            raise ValueError("Invalid camera pose at frame " + str(len(frames)))
        frames.append(dict(eye=eye, target=target, fov=fov))
    if not frames:
        raise ValueError("Empty timeline")
    raw_labels = list(plan.get("labels", []))
    if "labels" not in plan:
        lookup = {}
        for p in read(model.parent / "data" / "locations.json"):
            for key in [p["key"], p["name"], *p.get("aliases", [])]:
                if all(v in p for v in ("x", "y", "z")):
                    lookup[key] = [p["x"], p["y"] + p.get("h", 0), p["z"]]
        active = {}
        for i, frame in enumerate(plan["frames"] + [{}]):
            entries = frame.get("label")
            entries = entries if isinstance(entries, list) else [entries] if entries else []
            live = set()
            for spec in entries:
                spec = {"title":spec} if isinstance(spec,str) else spec
                title = spec.get("title", spec.get("text", spec.get("name")))
                anchor = spec.get("anchor", spec.get("world", lookup.get(title)))
                if not title or anchor is None:
                    raise ValueError(f"Per-frame label at {i} lacks a resolvable name/anchor: {spec}")
                signature = (title, tuple(xyz(anchor)))
                live.add(signature)
                if signature not in active:
                    active[signature] = dict(spec,title=title,anchor=anchor,start=i)
            for signature in set(active)-live:
                raw_labels.append(dict(active.pop(signature),end=i))
    for tag in raw_labels:
        tag["anchor"] = xyz(tag["anchor"])
        if not (isinstance(tag["start"],int) and isinstance(tag["end"],int) and
                0 <= tag["start"] < tag["end"] <= len(frames) and tag["title"]):
            raise ValueError("Invalid projected label: "+repr(tag))
    return frames, raw_labels


class Server(ThreadingHTTPServer):
    daemon_threads = True


class CaptureHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def reply(self, code, body=b""):
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self):
        if self.path.partition("?")[0] != self.server.base + "/model":
            self.reply(404)
            return
        source = self.server.model
        self.send_response(200)
        self.send_header("Content-Type","text/html; charset=utf-8")
        self.send_header("Content-Length",str(source.stat().st_size))
        self.end_headers()
        with source.open("rb") as handle:
            shutil.copyfileobj(handle,self.wfile,length=1024*1024)

    def do_POST(self):
        srv = self.server
        n = int(self.headers.get("Content-Length","0"))
        expected = srv.index
        if self.path != f"{srv.base}/frames/{expected}" or srv.sink is None or n != srv.frame_bytes:
            self.close_connection=True
            self.reply(409,b"Unexpected frame, byte count or uninitialized encoder")
            return
        try:
            data = self.rfile.read(n)
            if len(data) != n:
                raise EOFError("Incomplete frame")
            srv.sink.write(data)
            srv.index += 1
            self.reply(204)
        except (OSError,EOFError) as error:
            self.close_connection=True
            srv.failure = str(error)
            self.reply(500,b"Raw frame could not be written to the encoder")


def encode_args(target, fmt):
    # Preserve the existing unconstrained 1080p30 CRF encode. At UHD, VBV
    # limits bursts while CRF continues to set quality below the ceiling.
    vbv = []
    if fmt.height == 2160:
        ceiling = 96 if fmt.fps == 30 else 144
        vbv = ["-maxrate", f"{ceiling}M", "-bufsize", f"{ceiling * 2}M"]
    return ["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
            "-f","rawvideo","-pix_fmt","rgba","-video_size",f"{fmt.width}x{fmt.height}","-framerate",str(fmt.fps),"-i","pipe:0",
            "-an","-c:v","libx264","-preset","veryfast","-crf","16","-threads","6",*vbv,
            "-vf","scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p",
            "-pix_fmt","yuv420p","-profile:v","high","-level:v",fmt.h264_level,"-g",str(2*fmt.fps),"-keyint_min",str(fmt.fps),
            "-colorspace","bt709","-color_primaries","bt709","-color_trc","iec61966-2-1",
            "-video_track_timescale",str(fmt.timescale),"-movflags","+faststart",str(target)]


def verify(file, expected, fmt, timestamps=False):
    # Packet PTS are cheap to check at every checkpoint. Decode the final film
    # in presentation order as a second, independent check across segment joins.
    entries = "stream=codec_type,codec_name,level,width,height,pix_fmt,r_frame_rate,avg_frame_rate,nb_frames,time_base,duration_ts"
    entries += ":frame=pts,best_effort_timestamp" if timestamps else ":packet=pts"
    cmd = ["ffprobe","-v","error","-show_frames" if timestamps else "-show_packets","-show_entries",entries]
    info = json.loads(subprocess.check_output(cmd+["-of","json",str(file)]))
    streams=info["streams"]
    if len(streams) != 1:
        raise ValueError(f"Video is expected to consist of one visual stream: {streams}")
    v=streams[0]
    expected_keys = {"codec_type":"video","codec_name":"h264","width":fmt.width,"height":fmt.height,"pix_fmt":"yuv420p",
                     "r_frame_rate":f"{fmt.fps}/1","avg_frame_rate":f"{fmt.fps}/1","nb_frames":str(expected),
                     "time_base":f"1/{fmt.timescale}","duration_ts":expected*1000}
    if any(v.get(k)!=val for k,val in expected_keys.items()):
        raise ValueError(f"Stream metadata for {file.name}: {v}")
    if fmt.height == 2160 and v.get("level", 0) < int(fmt.h264_level.replace(".", "")):
        raise ValueError(f"H.264 level in {file.name} is too low for the requested UHD frame rate: {v.get('level')}")
    clock = list(range(0, expected * 1000, 1000))
    if timestamps:
        frames = info["frames"]
        valid = all([frame.get(key) for frame in frames] == clock for key in ("pts", "best_effort_timestamp"))
    else:
        packet_pts = [packet.get("pts") for packet in info["packets"]]
        valid = all(isinstance(pts, int) for pts in packet_pts) and sorted(packet_pts) == clock
    if not valid:
        raise ValueError(f"PTS sequence in {file.name} is not an exact {fmt.fps} Hz clock.")
    return v


def confirm_unique(file, expected):
    out = subprocess.check_output(["ffmpeg","-nostdin","-v","error","-threads","4","-i",str(file),
                                   "-map","0:v:0","-fps_mode","passthrough","-f","framemd5","-"],text=True)
    hashes = [ln.rsplit(",",1)[-1].strip() for ln in out.splitlines() if ln and not ln.startswith("#")]
    repeats=[i for i in range(1,len(hashes)) if hashes[i-1]==hashes[i]]
    if len(hashes)!=expected:
        raise ValueError(f"Decoded {len(hashes)} frames for {expected} poses")
    return dict(frames=len(hashes),uniqueFrames=len(set(hashes)),adjacentDuplicates=repeats)


def boot(page, server, frames, labels, introductions, args, fmt):
    base = f"http://127.0.0.1:{server.server_port}{server.base}"
    page.on("pageerror",lambda err:server.errors.append(str(err)))
    page.goto(base+"/model?film=1&scope=core", wait_until="domcontentloaded", timeout=240000)
    page.wait_for_function("window.qd?.ready || window.qd?.error",timeout=240000)
    if not page.evaluate("window.qd.ready"):
        raise RuntimeError(page.evaluate("window.qd.error"))
    hw=page.evaluate(SOURCE.read_text(encoding="utf-8-sig"),
                     dict(width=fmt.width,height=fmt.height,fps=fmt.fps,frames=frames,labels=labels,
                          lowerThirds=introductions,endpoint=base+"/frames",allowFullSea=args.allow_full_sea,
                          backend=args.backend,h264Level=fmt.h264_level,bitrate=fmt.bitrate_mbps*1_000_000))
    print("Renderer",json.dumps(hw,ensure_ascii=False),flush=True)
    return hw


def native_part(page,begin,end,file,fmt):
    encoded=page.evaluate("([a,b])=>film.encode(a,b)",[begin,end])
    annexb=base64.b64decode(encoded["data"],validate=True)
    if not annexb.startswith((b"\0\0\0\1",b"\0\0\1")):
        raise ValueError("Encoder did not return Annex B")
    tmp=file.with_suffix(".partial.mp4")
    # Annex B has no packet timestamps. Assign one exact interval per IP-only frame.
    subprocess.run(["ffmpeg","-nostdin","-v","error","-y","-f","h264","-framerate",str(fmt.fps),"-i","pipe:0",
                    "-an","-c:v","copy","-bsf:v",f"setts=time_base=1/{fmt.timescale}:pts=N*1000:dts=N*1000:duration=1000",
                    "-video_track_timescale",str(fmt.timescale),"-movflags","+faststart",str(tmp)],
                   input=annexb,check=True)
    verify(tmp,end-begin,fmt)
    tmp.replace(file)
    return encoded["hits"]


def render_part(page,server,begin,end,file,fmt):
    tmp=file.with_suffix(".partial.mp4")
    with subprocess.Popen(encode_args(tmp,fmt), stdin=subprocess.PIPE) as proc:
        server.index,server.sink,server.failure = begin,proc.stdin,None
        try:
            counts=page.evaluate("([a,b])=>film.render(a,b)",[begin,end])
            if server.index!=end or server.failure:
                raise RuntimeError(f"Raw frame delivery stopped at {server.index}: {server.failure}")
        except BaseException:
            proc.kill()
            raise
        finally:
            server.sink = None
            proc.stdin.close()
        if proc.wait():
            raise RuntimeError(f"Encoder failed on [{begin},{end})")
    verify(tmp,end-begin,fmt)
    tmp.replace(file)
    return counts


def run():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan",type=Path,required=True)
    p.add_argument("--model",type=Path,default=MODEL)
    p.add_argument("--chrome",type=Path,default=CHROME)
    p.add_argument("--work",type=Path,required=True)
    p.add_argument("--output",type=Path)
    p.add_argument("--allow-full-sea",action="store_true",help="Allow old reference page for rehearsal only")
    p.add_argument("--backend",choices=("rgba","webcodecs"),default="rgba")
    p.add_argument("--width",type=int,default=1920,help="Native film width, paired with --height")
    p.add_argument("--height",type=int,default=1080,help="Native film height (1920x1080 or 3840x2160)")
    p.add_argument("--fps",type=int,choices=(30,60),default=30,help="Must match the authored plan frame rate")
    p.add_argument("--chunk",type=int,default=90,help="Frames per independent H.264 segment, multiple of 3")
    p.add_argument("--stills",help="Comma-separated exact frame indices to export as JPEG files")
    p.add_argument("--still-dir",type=Path)
    args=p.parse_args()
    try:
        fmt = CaptureFormat(args.width, args.height, args.fps)
    except ValueError as error:
        p.error(str(error))
    if args.chunk<3 or args.chunk%3:
        p.error("--chunk must be a positive multiple of 3")
    if not args.stills and not args.output:
        p.error("--output is required to render a movie")
    args.work.mkdir(parents=True,exist_ok=True)
    start_time = time.monotonic()
    plan=read(args.plan)
    frames,labels=prepare(plan,args.model,fmt.fps)
    introductions=plan.get("lowerThirds",[])
    previous_end=0
    for cue in introductions:
        if not previous_end<=cue['start']<cue['end']<=len(frames) or not cue['title'] or not cue['caption']:
            raise ValueError("Invalid lower-third cue: "+repr(cue))
        previous_end=cue['end']
    hold=plan.get("holdStartFrame",len(frames))
    if not isinstance(hold,int) or not 0<=hold<=len(frames):
        raise ValueError("holdStartFrame must be an integer index on the authored timeline")
    if hold<len(frames) and any(f!=frames[hold] for f in frames[hold+1:]):
        raise ValueError("The declared panoramic hold includes moving cameras")
    signature=hashlib.sha256("|".join([digest(args.model),digest(args.plan),digest(__file__),digest(SOURCE),
                                      str(args.chunk),str(args.allow_full_sea),args.backend,
                                      str(fmt.width),str(fmt.height),str(fmt.fps)]).encode()).hexdigest()[:20]
    folder=args.work/signature
    folder.mkdir(exist_ok=True)
    server=Server(("127.0.0.1",0),CaptureHandler)
    server.base="/"+secrets.token_urlsafe(18)
    server.model=args.model.resolve()
    server.frame_bytes=fmt.width*fmt.height*4
    server.index,server.sink,server.errors = -1,None,[]
    threading.Thread(target=server.serve_forever,daemon=True).start()
    parts=[]
    hits=Counter()
    try:
        with sync_playwright() as api:
            browser=api.chromium.launch(executable_path=str(args.chrome),headless=True,args=FLAGS)
            try:
                page=browser.new_page(viewport={"width":fmt.width,"height":fmt.height},device_scale_factor=1)
                hw=boot(page,server,frames,labels,introductions,args,fmt)
                if args.stills:
                    directory=args.still_dir or folder/"stills"
                    directory.mkdir(parents=True,exist_ok=True)
                    for i in sorted(set(map(int,args.stills.split(",")))):
                        if not 0 <= i < len(frames):
                            raise ValueError(f"Still frame outside supported range: {i}")
                        item=page.evaluate("i=>film.still(i)",i)
                        (directory/f"frame-{i:06}.jpg").write_bytes(base64.b64decode(item["data"],validate=True))
                        names=[labels[int(k)]["title"] if k.isdigit() else introductions[int(k.split("/")[1])]["title"] for k in item["hits"]]
                        print("Still",i,names,flush=True)
                    if server.errors:raise RuntimeError(server.errors)
                    return
                for begin in range(0,len(frames),args.chunk):
                    end=min(begin+args.chunk,len(frames))
                    file=folder/f"part-{begin:06}.mp4"
                    note=file.with_suffix(".json")
                    counts = None
                    if file.exists() and note.exists():
                        try:
                            verify(file,end-begin,fmt)
                            record=read(note)
                            if record.get("hash") != digest(file):
                                raise ValueError("Checkpoint checksum mismatch")
                            values=record["labels"]
                            if not isinstance(values,dict) or any(type(v) is not int or v < 0 for v in values.values()):
                                raise ValueError("Invalid label counts in checkpoint")
                            counts=values
                        except (ValueError, KeyError, subprocess.CalledProcessError) as error:
                            print(f"Rebuilding invalid checkpoint {file.name}: {error}",flush=True)
                    if counts is None:
                        then=time.monotonic()
                        if args.backend=="webcodecs":
                            counts=native_part(page,begin,end,file,fmt)
                        else:
                            counts=render_part(page,server,begin,end,file,fmt)
                        dump(note,{"hash":digest(file),"labels":counts})
                        print(f"Encoded {begin}-{end-1}/{len(frames)} at {(end-begin)/(time.monotonic()-then):.2f} frames/s",flush=True)
                    hits.update(counts)
                    parts.append(file)
                if server.errors:raise RuntimeError(server.errors)
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
    listing=folder/"concat.ffconcat"
    listing.write_text("ffconcat version 1.0\n"+"".join(f"file '{path.name}'\n" for path in parts),encoding="ascii")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    staged=args.output.with_name(args.output.stem+".pending.mp4")
    subprocess.run(["ffmpeg","-nostdin","-v","error","-y","-f","concat","-safe","1","-i",str(listing),
                    "-map","0:v:0","-c","copy","-video_track_timescale",str(fmt.timescale),"-movflags","+faststart",str(staged)],check=True)
    info=verify(staged,len(frames),fmt,timestamps=True)
    decoded=confirm_unique(staged,len(frames))
    unexpected=[i for i in decoded["adjacentDuplicates"] if i<=hold]
    decoded["holdStartFrame"]=hold
    decoded["unexpectedAdjacentDuplicates"]=unexpected
    if unexpected:
        raise ValueError("Adjacent decoded frames repeat during camera motion: "+str(unexpected[:30]))
    if fmt.height == 2160:
        missing_labels = [tag["title"] for i, tag in enumerate(labels) if hits[str(i)] <= 0]
        missing_intros = [cue["title"] for i, cue in enumerate(introductions) if hits[f"intro/{i}"] <= 0]
        if missing_labels or missing_intros:
            raise ValueError(f"UHD overlays never exceeded quarter opacity: labels={missing_labels}, lowerThirds={missing_intros}")
    report={"sha256":digest(staged),"sceneSHA256":digest(args.model),"planSHA256":digest(args.plan),
            "stream":info,"decoded":decoded,"renderer":hw,"durationSeconds":len(frames)/fmt.fps,
            "elapsedSeconds":round(time.monotonic()-start_time,3),
            "labels":[dict(title=tag["title"],start=tag["start"],end=tag["end"],
                           visibleFramesAboveQuarterOpacity=hits[str(i)]) for i,tag in enumerate(labels)]}
    report["lowerThirds"]=[dict(cue,visibleFramesAboveQuarterOpacity=hits[f"intro/{i}"]) for i,cue in enumerate(introductions)]
    dump(args.output.with_suffix(".capture.json"),report)
    staged.replace(args.output)
    print("Verified",str(args.output),len(frames),"frames",flush=True)


if __name__ == "__main__":
    run()

