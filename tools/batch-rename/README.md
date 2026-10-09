# 图片和视频批量重命名

标准库实现，按文件修改日期、序号、自定义模板、查找替换或前后缀重命名；支持递归与扩展名过滤。先用 --preview 预览；目标已存在时跳过。

所有功能免费，源码采用 MIT 许可。

## Windows EXE

[下载 Windows EXE](https://github.com/9999999-svg/batch-rename/releases/download/v1.0.0/BatchRename.exe) · [查看 Python 源码](batch_rename.py) · [下载全部源码](https://github.com/9999999-svg/free-desktop-tools/releases/download/v1.1.0/free-desktop-tools-source-v1.1.0.zip)。不带参数启动图形界面；命令行用法与 Python 版一致，将 `python batch_rename.py` 换成 `BatchRename.exe`。
## Python 源码

安装本目录依赖后启动：

```powershell
python -m pip install -r requirements.txt
python batch_rename.py
python batch_rename.py -i "图片目录" -m custom -p "{y}-{m}-{day}_{n:04d}" --preview
python batch_rename.py --help
```

## 构建

在仓库根目录安装 `requirements-build.txt`，运行 `python build.py batch-rename`。EXE 输出在 `dist/`。

源码和 EXE 始终免费；赞助完全自愿，见仓库首页。

[独立仓库及单独源码包](https://github.com/9999999-svg/batch-rename) · [返回工具合集](../../README.md)
