# 文本差异查看器

比较两份配置、日志或普通文本，查看新增、删除和修改的行，导出 unified diff。原文件保留，适合检查文本副本具体改了什么。

## 下载

[Windows x64 EXE](https://github.com/9999999-svg/text-diff-viewer/releases/download/v1.0.0/TextDiffViewer.exe) · [Python 源码 ZIP](https://github.com/9999999-svg/text-diff-viewer/releases/download/v1.0.0/text-diff-viewer-source-v1.0.0.zip) · [SHA-256 清单](https://github.com/9999999-svg/text-diff-viewer/releases/download/v1.0.0/SHA256SUMS.txt)

EXE 约 12.5 MiB，内含 Python/Tcl/Tk，无需安装 Python，未签名。全部功能免费；自有代码 MIT，第三方许可随包提供。

## 使用

双击 EXE，选择左、右文本文件及各自编码，点击「比较 / 预览」或「导出新差异文件」。窗口默认显示 3 行上下文，预览最多 50000 字符；导出时重新读取并比较。

```powershell
python text_diff_viewer.py "原文.txt" "新文.txt"
TextDiffViewer.exe "原文.txt" "新文.txt" --output "结果.diff" --context 5
python text_diff_viewer.py "GBK.txt" "UTF16.txt" --left-encoding gbk --right-encoding utf-16
```

命令行输出 JSON 状态：退出码 0 表示内容相同、1 表示内容不同、2 表示失败、130 表示键盘中断。内容相同时导出空 diff 文件；已有输出文件拒绝覆盖。不带参数打开窗口。

## 必要限制

- 支持 UTF-8/BOM、GBK、GB18030、带 BOM 的 UTF-16，需明确选择，不自动猜编码；拒绝文本中的 NUL。
- 每份输入最多 1 MiB、10000 行，每行最多 10000 字符；输出最多 10 MiB。大文件应先选取所需片段。
- 比较行内容及末行有没有换行，忽略 CRLF/LF/CR 样式差异；不比较原编码、BOM、权限或时间戳，不解析 Office/PDF/多行 CSV 字段。
- diff 用 `left`、`right` 标示两侧，UTF-8 输出；只有查看和导出功能，不自动应用补丁。
- 拒绝输入及输出父路径中的链接、目录联接。正常失败或取消清理临时文件；强制结束可能留下 `.text-diff-*.tmp`。取消在读取和产生差异条目时检查，比较计算期间可能延后。

## 源码和构建

Python 3.11+，仅使用标准库与 Tkinter。使用已有虚拟环境可直接运行；构建需要 PyInstaller 6.21.0：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install pyinstaller==6.21.0
.venv\Scripts\python.exe build.py
```

生成 `dist/TextDiffViewer.exe`。依赖版本、体积和卸载见 [DEPENDENCIES.md](DEPENDENCIES.md)，第三方许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。便携版删除 EXE 即可卸载；自己建立的虚拟环境可在关闭程序后删除。

## 自愿赞助

下载、源码和全部功能免费，赞助完全自愿。

<img src="assets/donate-wechat.png" alt="自愿微信赞助二维码" width="280">
