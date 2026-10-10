# 文件清单导出器

递归生成文件夹清单，记录相对路径、字节大小与 UTC 修改时间；可选 SHA-256。适合备份交接、资料盘点和归档留档。

## 使用

双击 EXE，选择文件夹，按需筛选扩展名或勾选 SHA-256，点击“扫描”，再“导出 CSV”。CSV 使用 UTF-8 BOM，可用 Excel 打开。导出保留全部记录，界面预览前 1000 项。

```powershell
FileCatalog.exe "D:\资料" --sha256 --csv "D:\文件清单.csv"
FileCatalog.exe "D:\照片" --extensions .jpg,.png --top-only --csv "D:\图片清单.csv"
```

不带参数打开图形界面；`--help` 查看参数。退出码：0 完整扫描，1 含跳过或错误，2 输入/输出错误，130 手动中断。

## 必要限制

只读取源文件，不重命名或删除。跳过符号链接、目录联接、重解析点和非普通文件；不把空文件夹列为文件。硬链接按路径分别记录，合计大小是文件逻辑字节数，不是实际磁盘占用。修改时间以 UTC 表示。默认不读文件内容，勾选 SHA-256 时会检查读取期间的文件标识、大小和修改时间变化。

CSV 拒绝覆盖已有文件，并对可能被表格程序识别为公式的文本加前导单引号。扫描是某次读取时的清单，不锁定正在变化的文件夹；请在备份或复制完成后扫描。导出中断或磁盘写入失败时可能留下不完整 CSV，可删除后重新导出。

## 下载

[下载 Windows x64 EXE](https://github.com/9999999-svg/file-catalog/releases/download/v1.0.0/FileCatalog.exe) · [下载 Python 源码](https://github.com/9999999-svg/file-catalog/releases/download/v1.0.0/file-catalog-source-v1.0.0.zip) · [校验文件](https://github.com/9999999-svg/file-catalog/releases/download/v1.0.0/SHA256SUMS.txt)

EXE 无需安装 Python，未签名。全部功能和源码免费，自有代码 MIT，第三方组件保留各自许可。

## 源码运行与构建

源码仅使用标准库和 Tkinter。使用带 Tkinter 的 Python 3.11 或以上运行 `file_catalog.py`；构建方法：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.venv\Scripts\python.exe build.py
```

生成 `dist/FileCatalog.exe`。依赖版本、体积及卸载见 [DEPENDENCIES.md](DEPENDENCIES.md)，许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。更多工具见[免费工具总仓库](https://github.com/9999999-svg/free-desktop-tools)。

## 自愿赞助

工具全部免费，赞助完全自愿。

<img src="assets/donate-wechat.png" alt="自愿微信赞助二维码" width="280">
