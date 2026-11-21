# SDU-Qingdao-Campus

山东大学青岛校区 Blender 3D 建模工程。

## 克隆 / 拉取说明

本仓库中的大文件（`*.blend`、`*.glb` 以及 `Blender/打开青岛校区.html`）使用 **Git LFS** 管理，请按以下步骤拉取完整工程：

### 1. 安装并启用 Git LFS

- **Windows**：安装 [Git for Windows](https://git-scm.com/download/win)（默认已内置 Git LFS）。
- **macOS**：`brew install git-lfs`
- **Linux (Ubuntu/Debian)**：`sudo apt install git-lfs`

在当前电脑上执行一次启用命令：

```bash
git lfs install
```

### 2. 克隆仓库

```bash
git clone https://github.com/lijihao-0804/SDU-Qingdao-Campus.git
```

### 3. 如果已克隆但大文件打不开（仅几百字节）

说明克隆时未启用 Git LFS，进入仓库目录补拉大文件即可：

```bash
cd SDU-Qingdao-Campus
git lfs install
git lfs pull
```

> **注意**：请勿直接使用 GitHub 网页端的 **Download ZIP** 下载整包，否则 Git LFS 管理的大文件只会包含指针文本而非实际文件。
