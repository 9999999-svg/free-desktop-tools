# 批量提取视频音频

支持 MP3/M4A/WAV/FLAC/OGG、采样率、声道和比特率。默认跳过已有输出，--overwrite 可覆盖。

所有功能免费，源码采用 MIT 许可。

## Windows EXE

[下载 Windows EXE](https://github.com/9999999-svg/free-desktop-tools/releases/download/v1.0.0/ExtractAudio.exe) · [查看 Python 源码](extract_audio.py) · [下载全部源码](https://github.com/9999999-svg/free-desktop-tools/releases/download/v1.1.0/free-desktop-tools-source-v1.1.0.zip)。不带参数启动图形界面；命令行用法与 Python 版一致，将 `python extract_audio.py` 换成 `ExtractAudio.exe`。
EXE 版不捆绑 FFmpeg。请从 [FFmpeg 官方下载入口](https://ffmpeg.org/download.html)取得可信 Windows 构建，将 ffmpeg.exe 放在工具 EXE 同目录，或加入 PATH。Python 版也可由 imageio-ffmpeg 提供 FFmpeg（约 31 MB 下载）。

## Python 源码

安装本目录依赖后启动：

```powershell
python -m pip install -r requirements.txt
python extract_audio.py
python extract_audio.py -i "视频目录" -o "音频目录" -f mp3
python extract_audio.py --help
```

## 构建

在仓库根目录安装 `requirements-build.txt`，运行 `python build.py extract-audio`。EXE 输出在 `dist/`。

源码和 EXE 始终免费；赞助完全自愿，见仓库首页。
