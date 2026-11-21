"""Interactive launcher for the approved Qingdao campus tour. --check never records."""
import argparse
from contextlib import contextmanager
import json
import msvcrt
import os
from pathlib import Path
import subprocess
import sys

from manual_plan import build_plan

ROOT = Path(__file__).resolve().parents[2]
ENGINE = Path(__file__).with_name("capture.py")
MODEL_NAME = "打开青岛校区.html"
PROFILES = {"1": ("4K60", 3840, 2160, 60),
            "2": ("4K30", 3840, 2160, 30),
            "3": ("1080p30", 1920, 1080, 30)}


def preflight(root):
    from playwright.sync_api import sync_playwright  # also checks the active Python environment

    if sys.version_info < (3, 11):
        raise RuntimeError("采集需要 Python 3.11 或以上版本。")
    for path in (root / MODEL_NAME, ENGINE, ENGINE.with_suffix(".js")):
        if not path.is_file():
            raise FileNotFoundError(path)
    bundle = root / "运行环境"
    chrome = bundle / "Chrome" / "chrome.exe"
    if not chrome.is_file():
        raise FileNotFoundError(chrome)
    env = os.environ.copy()
    env["PATH"] = str(bundle / "bin") + os.pathsep + env.get("PATH", "")
    env.update(PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    for tool in ("ffmpeg", "ffprobe"):
        exe = bundle / "bin" / (tool + ".exe")
        if not exe.is_file():
            raise RuntimeError(f"找不到 {tool}。")
        subprocess.run([exe, "-version"], check=True, stdout=subprocess.DEVNULL, env=env)
        if tool == "ffmpeg":
            encoders = subprocess.check_output([exe, "-hide_banner", "-encoders"], env=env)
            if b"libx264" not in encoders:
                raise RuntimeError("当前 FFmpeg 缺少备用的 libx264 编码器。")
    return chrome, env


def summary(plan):
    return (f'{len(plan["frames"]):,} 帧，{plan["duration"]:g} 秒，'
            f'{len(plan["labels"])} 个建筑标记、{len(plan["lowerThirds"])} 段左下角介绍。')


@contextmanager
def capture_lock(directory):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "manual.lock").open("a+b") as handle:
        if not handle.seek(0, os.SEEK_END):
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise RuntimeError("另一份手动采集正在运行，请使用已打开的采集窗口。") from exc
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def run_engine(args, backend, env, log):
    cmd = [sys.executable, "-B", "-u", str(ENGINE), *args, "--backend", backend]
    # Keep progress in the console and retain the reason for an interrupted session.
    unavailable = False
    with subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                          errors="replace") as proc:
        try:
            for line in proc.stdout:
                print(line, end="", flush=True)
                log.write(line)
                log.flush()
                if "use --backend rgba" in line.lower():
                    unavailable = True
        except BaseException:
            proc.terminate()
            proc.wait()
            raise
        return proc.wait(), unavailable


def record(profile):
    name, width, height, fps = profile
    chrome, env = preflight(ROOT)
    plan = build_plan(ROOT, fps)
    exports = ROOT / "手动采集"
    work = ROOT / ".jobs" / "手动采集"
    output = exports / f"山东大学青岛校区·西门至海岸（{name}）.mp4"
    with capture_lock(work):
        if output.exists():
            print(f"此规格已有成片，如需重采，请先将它改名。\n{output}")
            return 0
        exports.mkdir(exist_ok=True)
        job = work / name
        job.mkdir(exist_ok=True)
        timeline = job / "航线.json"
        pending_plan = job / "航线.tmp"
        pending_plan.write_text(json.dumps(plan, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        pending_plan.replace(timeline)
        print(f"{name}，{summary(plan)}\n成片将保存到 {output}\n分片与运行日志在 {job}", flush=True)
        args = ["--width", str(width), "--height", str(height), "--fps", str(fps),
                "--model", str(ROOT / MODEL_NAME), "--plan", str(timeline), "--chrome", str(chrome),
                "--work", str(job), "--chunk", "90", "--output", str(output)]
        with (job / "采集.log").open("a", encoding="utf-8") as log:
            code, unavailable = run_engine(args, "webcodecs", env, log)
            if code and unavailable:
                print("本机硬件视频编码器未就绪，将以相同分辨率和帧率使用软件编码。", flush=True)
                code, _ = run_engine(args, "rgba", env, log)
        if code:
            print(f"采集退出码 {code}。排除错误后，重新选同一规格可接着已核验的分片继续。")
        else:
            print(f"\n成片已核验并保存到\n{output}")
        return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="只检查采集环境和航线")
    options = parser.parse_args()
    if options.check:
        chrome, _ = preflight(ROOT)
        print(f"Chrome 路径已确认：{chrome}")
        for fps in (30, 60):
            plan = build_plan(ROOT, fps)
            print(f"{fps} fps：{summary(plan)}")
        print("只读检查通过。")
        return 0

    print("山东大学青岛校区 · 西门至海岸\n")
    print("1   4K 60 帧\n2   4K 30 帧\n3   1080p 30 帧\n0   退出")
    while True:
        key = input("\n输入规格编号并回车开始采集，直接回车退出：").strip()
        if key in ("", "0"):
            return 0
        if key in PROFILES:
            return record(PROFILES[key])
        print("请输入 1、2、3 或 0。")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyboardInterrupt, EOFError):
        print("\n已取消。")
        sys.exit(130)
    except Exception as error:
        print(f"\n{type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)
