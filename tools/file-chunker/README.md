# 大文件分割与合并器

把大文件分成指定大小的分块，附带 SHA-256 清单；合并时检查每块内容及最终文件。适合按容量限制传输文件，或把大文件分次搬运。

## 使用

双击 EXE。在“分割”页选择原文件、填写新的分块文件夹和每块 MiB，点击“开始分割”。分割完成后，把整个文件夹中的 `manifest.json` 和全部 `part-*.bin` 一起传送。

接收方在“合并”页选择清单和新的输出文件，点击“校验并合并”。输出文件名与扩展名由你指定。

```powershell
FileChunker.exe split "D:\大文件.zip" "D:\大文件分块" --chunk-mib 100
FileChunker.exe join "D:\大文件分块\manifest.json" "D:\恢复的大文件.zip"
```

不带参数打开图形界面；`--help` 查看参数。退出码：0 完成，2 输入、内容或输出错误，130 手动中断。

## 必要限制

原文件不修改，分块文件夹和合并文件必须是新路径，拒绝覆盖已有输出。每块支持 1–4096 MiB，最多 100000 块；1 MiB = 1048576 字节。空文件也支持。清单与分块必须在同一普通文件夹，拒绝链接、目录联接和清单路径跳转。合并输出应位于分块文件夹之外。

分割取消或失败会保留已写入的部分分块，未完成时没有最终 `manifest.json`；可自行删除该新文件夹后重试。合并在全部校验通过后才发布输出，普通错误或取消会清理临时输出；进程强制终止或断电可能留下 `.file-chunker-*.tmp`，可自行删除。合并需要足够空间保存完整新文件。

分块只是拆分字节，不压缩、不加密。SHA-256 用于内容一致性检查，不能证明发送者身份。保留原文件直至对方成功合并，勿在分割过程中修改它。

## 下载

[下载 Windows x64 EXE](https://github.com/9999999-svg/file-chunker/releases/download/v1.0.0/FileChunker.exe) · [下载 Python 源码](https://github.com/9999999-svg/file-chunker/releases/download/v1.0.0/file-chunker-source-v1.0.0.zip) · [校验文件](https://github.com/9999999-svg/file-chunker/releases/download/v1.0.0/SHA256SUMS.txt)

EXE 无需安装 Python，未签名。全部功能和源码免费，自有代码 MIT，第三方组件保留各自许可。

## 源码运行与构建

源码仅使用标准库和 Tkinter。使用带 Tkinter 的 Python 3.11 或以上运行 `file_chunker.py`；构建方法：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.venv\Scripts\python.exe build.py
```

生成 `dist/FileChunker.exe`。依赖版本、体积及卸载见 [DEPENDENCIES.md](DEPENDENCIES.md)，许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。更多工具见[免费工具总仓库](https://github.com/9999999-svg/free-desktop-tools)。

## 自愿赞助

工具全部免费，赞助完全自愿。

<img src="assets/donate-wechat.png" alt="自愿微信赞助二维码" width="280">
