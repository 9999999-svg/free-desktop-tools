# 文件夹对比器

免费开源的备份检查工具。选择两份文件夹，按相对路径和 SHA-256 比较文件内容，列出相同、内容不同、仅左侧、仅右侧，以及未能读取或跳过的项目。比较过程只读；没有自动同步、删除或覆盖功能。

## Windows EXE

[下载 Windows EXE](https://github.com/9999999-svg/folder-compare/releases/download/v1.0.0/FolderCompare.exe) · [下载 Python 源码 ZIP](https://github.com/9999999-svg/folder-compare/archive/refs/heads/main.zip) · [查看源码](folder_compare.py)

双击打开界面。选择左右文件夹，点击“开始比较”，需要时导出 CSV。支持取消，已有报告不会被覆盖。

GUI 最多预览 1000 项，CSV 包含全部结果。跳过文件或读取错误会明确列出，此时不能认为两份文件夹已完整比较。

## Python 和命令行

仅使用 Python 标准库，不需要 pip 运行依赖。

```powershell
python folder_compare.py
python folder_compare.py "D:\资料" "E:\备份" --csv "D:\对比报告.csv"
FolderCompare.exe "D:\资料" "E:\备份"
FolderCompare.exe --help
```

相对路径在 Windows 中按大小写归一化匹配；内容相同的文件允许时间戳不同。比较普通文件，跳过符号链接、目录联接和其他重解析点，避免误遍历其他目录；检测读取期间的文件变化。空目录、权限、时间戳和文件属性不参与差异判断，因此“相同”指纳入比较的文件内容一致，并不代表两份目录的全部系统属性一致。SHA-256 比较不是数学意义的无碰撞证明。

CSV 使用 UTF-8 BOM，中文可直接在表格软件中打开；可能被解释为公式的字段按文本输出。目录内容在扫描后变化时，报告也可能过时。

退出码：0 纳入比较的文件全部相同；1 有内容差异或单侧文件；2 有跳过、读取错误、输入错误或报告保存错误；130 用户中断。

## 构建

构建环境：Windows x64、Python 3.14.6、PyInstaller 6.21.0。EXE 未签名。依赖体积、卸载见 [DEPENDENCIES.md](DEPENDENCIES.md)。

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.venv\Scripts\python.exe build.py
```

自有源码和文档采用 MIT，第三方许可保留在 `licenses/` 和 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 自愿赞助

下载、源码和功能全部免费；赞助完全自愿。

<img src="assets/donate-wechat.png" alt="自愿微信赞助二维码" width="280">
