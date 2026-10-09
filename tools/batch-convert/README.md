# 批量图片格式转换

支持 PNG/JPEG/WebP/AVIF/BMP/TIFF；转换为 RGB 时将透明背景合成白色。默认跳过已有输出，--delete 会在转换成功后删除原图，使用前先备份。

所有功能免费，源码采用 MIT 许可。

## Windows EXE

[下载 Windows EXE](https://github.com/9999999-svg/free-desktop-tools/releases/download/v1.0.0/BatchConvert.exe) · [查看 Python 源码](batch_convert.py) · [下载全部源码](https://github.com/9999999-svg/free-desktop-tools/releases/download/v1.1.0/free-desktop-tools-source-v1.1.0.zip)。不带参数启动图形界面；命令行用法与 Python 版一致，将 `python batch_convert.py` 换成 `BatchConvert.exe`。
## Python 源码

安装本目录依赖后启动：

```powershell
python -m pip install -r requirements.txt
python batch_convert.py
python batch_convert.py -i "输入目录" -o "输出目录" -f webp --quality 90
python batch_convert.py --help
```

## 构建

在仓库根目录安装 `requirements-build.txt`，运行 `python build.py batch-convert`。EXE 输出在 `dist/`。

源码和 EXE 始终免费；赞助完全自愿，见仓库首页。
