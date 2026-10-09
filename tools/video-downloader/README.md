# 视频和音频下载器

使用 yt-dlp 的内置 Python 接口下载视频或 MP3，支持画质与批量链接。站点支持随 yt-dlp、登录状态和平台变化，只下载你有权下载的内容。

所有功能免费，源码采用 MIT 许可。

## Windows EXE

[下载 Windows EXE](https://github.com/9999999-svg/video-downloader/releases/download/v1.0.0/UniversalDL.exe) · [查看 Python 源码](universal_downloader.py) · [下载全部源码](https://github.com/9999999-svg/free-desktop-tools/releases/download/v1.1.0/free-desktop-tools-source-v1.1.0.zip)。不带参数启动图形界面；命令行用法与 Python 版一致，将 `python universal_downloader.py` 换成 `UniversalDL.exe`。
EXE 版不捆绑 FFmpeg。请从 [FFmpeg 官方下载入口](https://ffmpeg.org/download.html)取得可信 Windows 构建，将 ffmpeg.exe 放在工具 EXE 同目录，或加入 PATH。Python 版也可由 imageio-ffmpeg 提供 FFmpeg（约 31 MB 下载）。

## Python 源码

安装本目录依赖后启动：

```powershell
python -m pip install -r requirements.txt
python universal_downloader.py
python universal_downloader.py -u "视频链接" -o "下载目录" --quality 720
python universal_downloader.py --help
```

## 构建

在仓库根目录安装 `requirements-build.txt`，运行 `python build.py video-downloader`。EXE 输出在 `dist/`。

源码和 EXE 始终免费；赞助完全自愿，见仓库首页。

[独立仓库及单独源码包](https://github.com/9999999-svg/video-downloader) · [返回工具合集](../../README.md)
