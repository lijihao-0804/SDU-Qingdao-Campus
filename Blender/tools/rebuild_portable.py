"""Build an editable campus and its offline viewer in a fresh directory."""
import argparse
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
MODEL = "山东大学青岛校区"
PAGE = "打开青岛校区.html"
INPUT_DIRS = ("tools", "viewer", "data", "assets", "实景参照")
SCRIPTS = ("v6_sunset.py", "build_campus.py", "bake_window_probes.py", "pack_viewer.py", "make_blend.py")


def find_chrome(source, requested):
    if requested:
        candidates = [requested]
    elif os.environ.get("SDU_CHROME"):
        candidates = [Path(os.environ["SDU_CHROME"])]
    else:
        candidates = [base / "运行环境/Chrome/chrome.exe" for base in (source, ROOT, ROOT.parent)]
        for key in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            if os.environ.get(key):
                candidates.append(Path(os.environ[key]) / "Google/Chrome/Application/chrome.exe")
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise ValueError("请用 --chrome 指定 Chrome 的 chrome.exe，或设置 SDU_CHROME。")


def preflight(source, chrome):
    if sys.version_info[:2] != (3, 11):
        raise ValueError("项目依赖使用 Windows x64 的 Python 3.11，请设置 SDU_PYTHON。")
    import bpy, matplotlib, mapbox_earcut, numpy, PIL, scipy, shapely, skimage
    from playwright.sync_api import sync_playwright
    for item in INPUT_DIRS:
        if not (source / item).is_dir():
            raise FileNotFoundError(source / item)
    for script in SCRIPTS:
        if not (source / "tools" / script).is_file():
            raise FileNotFoundError(source / "tools" / script)
    settings = json.loads((source / "data/建筑饰面选色.json").read_text("utf8"))
    for name, _ in settings["samples"]:
        if not any((source / "实景参照").rglob(name)):
            raise FileNotFoundError(name)
    for font in ("simhei.ttf", "msyh.ttc", "arial.ttf", "arialbd.ttf"):
        path = Path(os.environ["WINDIR"]) / "Fonts" / font
        if not path.is_file():
            raise FileNotFoundError(path)
    print(f"Python {sys.version.split()[0]} · bpy {bpy.app.version_string} · Chrome {chrome}", flush=True)


def copy_source(source, target):
    # An existing folder can hold manually edited .blend files. Never enter it.
    if target.is_relative_to(source) or source.is_relative_to(target):
        raise ValueError("输出目录须位于源工程之外，并使用全新的目录名。")
    target.mkdir(parents=True, exist_ok=False)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    for name in INPUT_DIRS + ("preview", "参照模型"):
        if (source / name).is_dir():
            shutil.copytree(source / name, target / name, ignore=ignore)
    if (source / "重建模型.cmd").is_file():
        shutil.copy2(source / "重建模型.cmd", target / "重建模型.cmd")
    # A rebuilt working copy can be moved and used to record on its own.
    runtime = source / "运行环境"
    if runtime.is_dir():
        shutil.copytree(runtime, target / "运行环境", ignore=ignore)
    for launcher in source.glob("*.cmd"):
        shutil.copy2(launcher, target / launcher.name)
    for item in source.iterdir():
        if item.is_file() and item.suffix.lower() in (".md", ".html", ".txt") and item.name != PAGE:
            shutil.copy2(item, target / item.name)


def verify(target):
    # Only import project helpers after all writes have moved to the fresh copy.
    sys.path.insert(0, str(target / "tools"))
    from v6_sunset import HDR
    from v6_sunset_review import file_sha, offline_asset_hashes
    import bpy
    glb = target / (MODEL + ".glb")
    with glb.open("rb") as stream:
        magic, version, size, n, kind = struct.unpack("<4sIII4s", stream.read(20))
        if (magic, version, size, kind) != (b"glTF", 2, glb.stat().st_size, b"JSON"):
            raise ValueError("GLB 文件头、版本或长度不符")
        gltf = json.loads(stream.read(n))
    externals = [item["uri"] for group in ("buffers", "images") for item in gltf.get(group, [])
                 if "uri" in item and not item["uri"].startswith("data:")]
    if externals or not gltf["meshes"]:
        raise ValueError(f"GLB 几何或外部资源异常 {externals}")
    model_hash = file_sha(glb)
    sky_hash = file_sha(HDR)
    offline_asset_hashes(target / PAGE, model_hash, sky_hash)
    probes = target / "assets/校园窗景"
    manifest = json.loads((probes / "位置.json").read_text("utf8"))
    if manifest["modelSHA256"] != model_hash or manifest["environmentSHA256"] != sky_hash:
        raise ValueError("窗景绑定的模型或天空摘要有误")
    for probe in manifest["probes"]:
        for filename, digest in (("file", "sha256"), ("coreFile", "coreSHA256")):
            if file_sha(probes / probe[filename]) != probe[digest]:
                raise ValueError(f"窗景验证失败 {probe[filename]}")
    bpy.ops.wm.open_mainfile(filepath=str(target / (MODEL + ".blend")), load_ui=False, use_scripts=False)
    if bpy.context.scene.get("GLB SHA256") != model_hash or not bpy.data.meshes:
        raise ValueError("可编辑工程没有匹配当前 GLB")
    if bpy.data.libraries or bpy.utils.blend_paths(absolute=False, local=False, packed=False):
        raise ValueError("可编辑工程含未打包的外部路径")
    details = {"sourceSHA256": model_hash, "blendSHA256": file_sha(target / (MODEL + ".blend")),
               "htmlSHA256": file_sha(target / PAGE), "skySHA256": sky_hash,
               "objects": len(bpy.data.objects), "meshes": len(bpy.data.meshes),
               "packedImages": sum(bool(im.packed_files) for im in bpy.data.images),
               "windowLocations": len(manifest["probes"])}
    return details


def main():
    cli = argparse.ArgumentParser(description="从当前模型脚本与数据生成独立的新工程。")
    cli.add_argument("--source", type=Path, default=ROOT, help="含 tools、assets、data、viewer 的源目录")
    cli.add_argument("--output", type=Path, help="须为源目录以外、尚不存在的新目录")
    cli.add_argument("--chrome", type=Path, help="指定 chrome.exe")
    cli.add_argument("--check", action="store_true", help="检查输入、Python 依赖和 Chrome 路径")
    opt = cli.parse_args()
    source = opt.source.resolve()
    target = (opt.output or source.with_name(source.name + "-模型重建-" + datetime.now().strftime("%Y%m%d-%H%M%S"))).resolve()
    if not opt.check and (target.exists() or target.is_relative_to(source) or source.is_relative_to(target)):
        raise ValueError("请使用源目录之外、尚不存在的输出目录。")
    chrome = find_chrome(source, opt.chrome)
    preflight(source, chrome)
    if opt.check:
        print("输入与依赖检查通过。")
        return
    copy_source(source, target)
    env = dict(os.environ, SDU_CHROME=str(chrome), PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)
    print(f"新工程 {target}", flush=True)
    for index, script in enumerate(SCRIPTS, 1):
        print(f"[{index}/{len(SCRIPTS)}] {script}", flush=True)
        subprocess.run([sys.executable, "-B", "-X", "utf8", "-u", str(target / "tools" / script)],
                       cwd=target, env=env, check=True)
    details = verify(target)
    report = target / "重建模型核验.json"
    report.write_text(json.dumps(details, ensure_ascii=False, indent=2) + "\n", "utf8")
    print(f"生成并核验完成。成品位于 {target}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, ImportError, subprocess.CalledProcessError) as exc:
        print(f"重建模型未完成。{exc}", file=sys.stderr, flush=True)
        raise SystemExit(1)
