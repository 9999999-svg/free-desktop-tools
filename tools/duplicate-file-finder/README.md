# 重复文件扫描器 / Duplicate File Finder

免费开源的 Windows 文件内容扫描工具。用 SHA-256 找出不同目录、不同文件名的相同内容副本，导出 CSV，帮助整理重复照片、视频、资料和下载文件。只读取扫描目录，不执行删除或移动。

## 下载与使用

[下载 Windows EXE](https://github.com/9999999-svg/duplicate-file-finder/releases/download/v1.0.0/DuplicateFinder.exe) · [下载 Python 源码 ZIP](https://github.com/9999999-svg/duplicate-file-finder/archive/refs/heads/main.zip) · [查看源码](duplicate_finder.py)

双击打开图形界面。选择文件夹，点击“开始扫描”，查看分组和多余副本的逻辑容量，按需“导出 CSV”。报告使用 UTF-8 BOM，方便表格软件显示中文路径；已有报告不会被覆盖。

界面预览最多 1000 个重复文件，CSV 包含全部结果。最小字节数默认 1，设为 0 可包含空文件。硬链接别名不计作额外副本；符号链接、目录联接和其他重解析点会跳过，避免沿链接扫描或读取云端占位文件。

容量为文件逻辑大小估算，不等同于磁盘实际占用。扫描期间修改文件可能使结果不完整；检测到无法读取或变动的候选文件时，报告错误并跳过它。结果按大小及 SHA-256 分组，不声称提供数学上的哈希无碰撞证明。

## 命令行与 Python 版

Python 源码只依赖标准库，无需 pip 安装。

```powershell
python duplicate_finder.py
python duplicate_finder.py "D:\照片" --csv "D:\重复文件.csv"
DuplicateFinder.exe "D:\下载" --min-size 1048576 --csv "D:\大文件报告.csv"
DuplicateFinder.exe --help
```

退出码：0 扫描完成；1 目录、大小范围或报告写入错误；2 命令行参数格式错误，或扫描完成但有文件读取错误；130 用户中断。扫描一个文件夹时递归包含子目录。取消扫描不会导出新报告。

## 构建

构建使用 Windows x64、Python 3.14.6、PyInstaller 6.21.0。使用独立虚拟环境：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.venv\Scripts\python.exe build.py
```

依赖大小、来源及卸载见 [DEPENDENCIES.md](DEPENDENCIES.md)。EXE 未签名，自有源码使用 MIT。Python、Tcl/Tk 及 PyInstaller 组件保留各自许可，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 和 `licenses/`。

## 自愿赞助

下载、使用和源码全部免费，赞助完全自愿。

<img src="assets/donate-wechat.png" alt="自愿微信赞助二维码" width="280">
