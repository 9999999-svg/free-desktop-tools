# 图片隐藏文字标记

提供文件二进制标记和 RGB 像素 LSB 隐写；LSB 仅输出 PNG/BMP 无损文件，不支持抗 JPEG 压缩、裁剪或加密保护。文件尾部标记也可能被重编码移除。

所有功能免费，源码采用 MIT 许可。

## Windows EXE

[下载 Windows EXE](https://github.com/9999999-svg/batch-watermark/releases/download/v1.0.0/Watermark.exe) · [查看 Python 源码](batch_watermark.py) · [下载全部源码](https://github.com/9999999-svg/free-desktop-tools/releases/download/v1.1.0/free-desktop-tools-source-v1.1.0.zip)。不带参数启动图形界面；命令行用法与 Python 版一致，将 `python batch_watermark.py` 换成 `Watermark.exe`。
## Python 源码

安装本目录依赖后启动：

```powershell
python -m pip install -r requirements.txt
python batch_watermark.py
python batch_watermark.py -i "输入目录" -o "输出目录" -m binary -t "版权信息"
python batch_watermark.py --help
```

## 构建

在仓库根目录安装 `requirements-build.txt`，运行 `python build.py batch-watermark`。EXE 输出在 `dist/`。

源码和 EXE 始终免费；赞助完全自愿，见仓库首页。

LSB 输出使用原文件名追加 `.lsb.png`，保证无损恢复。默认跳过已有输出，并拒绝覆盖输入原图。

[独立仓库及单独源码包](https://github.com/9999999-svg/batch-watermark) · [返回工具合集](../../README.md)
