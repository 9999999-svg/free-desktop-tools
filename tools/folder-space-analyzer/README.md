# 文件夹空间分析器

查看哪个子文件夹和哪些文件较大，帮助整理下载、备份及工作资料。只读扫描文件元数据，按直接子文件夹汇总所有后代文件的逻辑大小，列出大文件，并导出 CSV。

## 下载

[Windows x64 EXE](https://github.com/9999999-svg/folder-space-analyzer/releases/download/v1.0.0/FolderSpaceAnalyzer.exe) · [Python 源码 ZIP](https://github.com/9999999-svg/folder-space-analyzer/releases/download/v1.0.0/folder-space-analyzer-source-v1.0.0.zip) · [SHA-256 清单](https://github.com/9999999-svg/folder-space-analyzer/releases/download/v1.0.0/SHA256SUMS.txt)

EXE 约 12.5 MiB，内含 Python/Tcl/Tk，无需安装 Python，未签名。全部功能免费；自有代码 MIT，第三方许可随包提供。

## 使用

双击 EXE，选择文件夹，设置大文件数量，点击「开始分析」。在「子文件夹汇总」「大文件」「跳过与错误」查看结果；「导出 CSV」保存到新文件。更改路径或数量后需重新分析。

```powershell
python folder_space_analyzer.py "D:\资料" --top 20
FolderSpaceAnalyzer.exe "D:\资料" --top 100 --csv "D:\空间报告.csv"
```

命令行输出 JSON 报告：退出码 0 表示完整完成、1 表示有跳过/错误或达到上限、2 表示操作失败、130 表示键盘中断。不带参数打开窗口。

## 必要限制

- 大小是文件逻辑字节数，不是磁盘实际占用。硬链接按每条路径重复计数；压缩、稀疏文件和云占位文件的逻辑大小可能与占用不同。
- 不读取文件内容，不删除或移动文件。跳过链接、目录联接和重解析点；根路径包含这些内容则拒绝扫描。无权限或变化的目录会在问题页显示。
- 最多扫描 1000000 个条目，大文件数量 1–1000。窗口每表最多显示 1000 行；CSV 包含全部子文件夹汇总、选定数量的大文件及前 1000 条问题记录，并注明问题总数。
- 扫描不是一致快照；扫描期间其他程序修改文件，结果可能变化。目录变化检查只能发现部分变化，`complete` 不表示与某一时刻的磁盘完全一致。
- CSV 为 UTF-8 BOM，文本字段开头的 `= + - @` 会加单引号，便于按文字打开。已有 CSV 拒绝覆盖；正常失败或取消会清理临时文件，强制结束可能留下 `.folder-space-*.tmp`。

## 源码和构建

Python 3.11+，仅使用标准库和 Tkinter。使用已有虚拟环境可直接运行源码；构建需要 PyInstaller 6.21.0：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install pyinstaller==6.21.0
.venv\Scripts\python.exe build.py
```

EXE 在 `dist/FolderSpaceAnalyzer.exe`。依赖版本、体积和卸载见 [DEPENDENCIES.md](DEPENDENCIES.md)，第三方许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。卸载便携版直接删除 EXE；自行建立的虚拟环境可在关闭程序后删除。

## 自愿赞助

下载、源码和全部功能免费，赞助完全自愿。

<img src="assets/donate-wechat.png" alt="自愿微信赞助二维码" width="280">
