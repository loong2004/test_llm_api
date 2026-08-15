# 构建 macOS 应用

本项目可在 macOS 上构建为可直接双击启动的 `LLM API Lab.app`。

## 环境要求

- macOS
- Python 3.9 或更高版本
- Xcode Command Line Tools

如未安装 Xcode Command Line Tools，先执行：

```bash
xcode-select --install
```

确认 Python 可用：

```bash
python3 --version
```

## 构建

在项目根目录执行：

```bash
chmod +x scripts/build_macos.sh
./scripts/build_macos.sh
```

脚本会自动安装构建依赖，并使用 PyInstaller 生成 macOS 应用。

## 产物

构建完成后的应用位于：

```text
dist/LLM API Lab.app
```

在 Finder 中双击该文件即可启动。

也可以通过终端打开：

```bash
open "dist/LLM API Lab.app"
```
