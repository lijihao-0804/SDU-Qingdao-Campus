# SDU-Qingdao-Campus

山东大学青岛校区 Blender 3D 建模工程（春日夕照版），包含可编辑 `.blend` 工程、`.glb` 三维模型、离线交互浏览网页、程序化重建脚本与 4K60 漫游视频采集工具。

---

## 一、克隆 / 拉取仓库

本仓库的大文件（`*.blend`、`*.glb` 及 `Blender/打开青岛校区.html`）通过 **Git LFS** 管理，请按以下步骤获取完整工程：

### 1. 安装并启用 Git LFS

- **Windows**：安装 [Git for Windows](https://git-scm.com/download/win)（默认已内置 Git LFS）。
- **macOS**：`brew install git-lfs`
- **Linux (Ubuntu/Debian)**：`sudo apt install git-lfs`

在本机执行一次启用命令：

```bash
git lfs install
```

### 2. 克隆仓库

```bash
git clone https://github.com/lijihao-0804/SDU-Qingdao-Campus.git
```

### 3. 若克隆后大文件无法打开（仅几百字节）

说明克隆时未启用 Git LFS，进入仓库目录补拉大文件即可：

```bash
cd SDU-Qingdao-Campus
git lfs install
git lfs pull
```

> **注意**：请勿直接使用 GitHub 网页端的 **Download ZIP** 下载整包，否则 Git LFS 管理的大文件只会是指针文本，而非实际文件。

---

## 二、快速使用（无需配置 Python 环境）

- **离线浏览校园**：直接用浏览器打开 `Blender/打开青岛校区.html` 即可 3D 漫游、点选地标。
- **编辑三维模型**：安装 [Blender 4.3](https://www.blender.org/download/)（或兼容版本），直接打开 `Blender/山东大学青岛校区.blend`（47 张贴图已打包在文件内）。

---

## 三、环境配置与依赖安装（重建模型 / 视频采集）

原本地便携目录 `Blender/运行环境/`（约 1.96 GB）未上传至仓库，如需运行程序化重建或视频采集脚本，请按以下说明在 **Windows x64** 上配置环境。

### 1. 基础环境要求

- **操作系统**：Windows 10 / 11 (x64)（需包含系统自带中文字体：黑体、微软雅黑、Arial、Arial Bold）
- **Python 版本**：**Python 3.11 (64-bit)**（[官方下载](https://www.python.org/downloads/release/python-3119/)，`bpy==4.3.0` 依赖 Python 3.11）
- **显卡驱动**：视频采集需支持 WebGL / Direct3D 11 的可用显卡驱动

### 2. 安装 Python 依赖（用于重建模型 `重建模型.cmd`）

在仓库的 `Blender` 目录下打开 PowerShell，创建 Python 3.11 虚拟环境 `.venv` 并安装 [Blender/requirements.txt](Blender/requirements.txt)：

```powershell
cd Blender
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`requirements.txt` 包含的核心依赖如下：

| 依赖包 | 版本 | 用途 |
| --- | --- | --- |
| `bpy` | `4.3.0` | Blender 4.3 Python 引擎（程序化建模与导出） |
| `numpy` | `1.26.2` | 数值与网格计算 |
| `scipy` | `1.11.4` | 科学计算与插值 |
| `shapely` | `2.0.3` | 校园地块/道路二维几何处理 |
| `mapbox-earcut` | `2.1.0` | 多边形三角剖分 |
| `Pillow` | `10.1.0` | 贴图与图像处理 |
| `matplotlib` | `3.8.2` | 图表与色彩处理 |
| `scikit-image` | `0.25.2` | 图像分析与核验 |
| `opencv-python` | `4.6.0.66` | 图像处理与视觉核验 |
| `playwright` | `1.63.0` | 浏览器自动化（用于视频采集） |

安装完成后，运行检查命令验证重建环境：

```powershell
.\重建模型.cmd --check
```

> `重建模型.cmd` 会自动识别 `Blender\.venv\Scripts\python.exe`（也可通过环境变量 `SDU_PYTHON` 指定其他 Python 3.11 路径）。
> 检查通过后，可执行 `.\重建模型.cmd --output "D:\山青\建筑修订01"` 重建模型。

### 3. 配置视频采集环境（用于校园漫游视频采集）

视频采集工具默认从 `Blender\运行环境\` 读取 Chrome、FFmpeg 与 FFprobe，请按以下步骤补齐：

1. **配置 Chrome（`Blender\运行环境\Chrome\chrome.exe`）**：
   - 将本机已安装的 Google Chrome 目录（通常位于 `C:\Program Files\Google\Chrome\Application\`）完整复制到 `Blender\运行环境\Chrome\`，确保 `Blender\运行环境\Chrome\chrome.exe` 存在。
   - （也可先运行 `.\.venv\Scripts\python.exe -m playwright install chromium`，再将其目录复制到 `Blender\运行环境\Chrome\` 并确保主程序为 `chrome.exe`。）

2. **配置 FFmpeg 与 FFprobe（`Blender\运行环境\bin\`）**：
   - 下载带 `libx264` 编码器的 Windows x64 版 FFmpeg（如 [gyan.dev FFmpeg builds](https://www.gyan.dev/ffmpeg/builds/) 或执行 `winget install Gyan.FFmpeg`）。
   - 将 `ffmpeg.exe` 和 `ffprobe.exe` 复制到 `Blender\运行环境\bin\`。

3. **检查环境并开始采集**：
   - 使用第 2 步创建的 `.venv` 直接运行（无需额外配置 `运行环境\Python`）：
     ```powershell
     cd Blender
     # 检查环境与航线
     .\.venv\Scripts\python.exe -B -X utf8 -u .\tools\bay_film\manual_capture.py --check
     # 启动交互式采集（按提示选 1: 4K60 / 2: 4K30 / 3: 1080p30）
     .\.venv\Scripts\python.exe -B -X utf8 -u .\tools\bay_film\manual_capture.py
     ```
   - 如需直接双击 `Blender\开始采集校园漫游.cmd`，则需将 Python 3.11 安装到 `Blender\运行环境\Python\`（使 `Blender\运行环境\Python\python.exe` 存在）并执行 `.\运行环境\Python\python.exe -m pip install -r requirements.txt`。

---

## 四、目录结构说明

更详细的建模依据、航线修改与采集说明请查看 [Blender/README.md](Blender/README.md) 和 [Blender/建模说明.md](Blender/建模说明.md)。
