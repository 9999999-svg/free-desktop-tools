# 免费桌面工具集 / Free Desktop Tools

7 个 Windows 图形界面与命令行工具，提供可编辑 Python 源码及 Windows x64 EXE。全部功能免费，自有源码采用 MIT 许可。

| 工具 | Python 源码 | Windows EXE |
| --- | --- | --- |
| [批量正方形缩图](tools/batch-resize/README.md) | `batch_resize.py` | `BatchResize.exe` |
| [批量图片格式转换](tools/batch-convert/README.md) | `batch_convert.py` | `BatchConvert.exe` |
| [图片隐藏文字标记](tools/batch-watermark/README.md) | `batch_watermark.py` | `Watermark.exe` |
| [视频片段转 GIF](tools/video-to-gif/README.md) | `video_to_gif.py` | `Video2GIF.exe` |
| [批量提取视频音频](tools/extract-audio/README.md) | `extract_audio.py` | `ExtractAudio.exe` |
| [图片和视频批量重命名](tools/batch-rename/README.md) | `batch_rename.py` | `BatchRename.exe` |
| [视频和音频下载器](tools/video-downloader/README.md) | `universal_downloader.py` | `UniversalDL.exe` |

## 下载与使用

在 **Releases** 下载源码 ZIP 或对应 EXE。不带参数启动图形界面，`--help` 查看命令行参数。图片处理默认使用单独的输出目录；重命名先预览，删除原图选项先备份。

视频相关 EXE 需要 FFmpeg：从 [官方入口](https://ffmpeg.org/download.html)获取，将 ffmpeg.exe 放在 EXE 同目录或加入 PATH。本仓库不捆绑 FFmpeg 二进制。下载器的站点支持随 yt-dlp 和平台变化，不保证每个网站可用。

## 从源码运行和构建

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.venv\Scripts\python.exe tools\batch-resize\batch_resize.py
.venv\Scripts\python.exe tests\smoke.py
.venv\Scripts\python.exe build.py
```

验证环境和具体依赖见 [DEPENDENCIES.md](DEPENDENCIES.md)，验证记录见 [VALIDATION.md](VALIDATION.md)。第三方组件保留各自许可，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。EXE 未做代码签名。

## 请我喝杯咖啡

下载、使用和源码均免费，赞助完全自愿，不解锁额外功能。

<img src="assets/donate-wechat.png" alt="自愿微信赞助二维码" width="280">
