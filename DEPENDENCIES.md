# 依赖和构建环境

实际验证：Windows x64 / Python 3.14.6 / PyInstaller 6.21.0。路径包含中文的输入与输出已通过测试。

下表为当前依赖安装占用的近似体积，不包括 Python 本体；不同平台、版本会不同。

| 组件 | 本次版本 | 近似安装占用 | 本次状态 |
| --- | --- | --- | --- |
| Pillow | 12.3.0 | 约 15.6 MiB | 已安装，复用 |
| numpy | 2.5.1 | 约 51.6 MiB | 已安装，复用 |
| yt-dlp | 2026.7.4 | 约 21.2 MiB | 已安装，复用 |
| imageio-ffmpeg | 0.6.0 | 约 83.7 MiB | 已安装，复用 |
| PyInstaller | 6.21.0 | 约 4.9 MiB | 已安装，复用 |
| altgraph | 0.17.5 | 约 0.1 MiB | 已安装，复用 |
| packaging | 26.2 | 约 0.8 MiB | 已安装，复用 |
| pefile | 2024.8.26 | 约 0.7 MiB | 已安装，复用 |
| pyinstaller-hooks-contrib | 2026.6 | 约 1.1 MiB | 已安装，复用 |
| pywin32-ctypes | 0.2.3 | 约 0.2 MiB | 已安装，复用 |
| setuptools | 83.0.0 | 约 7.1 MiB | 已安装，复用 |

imageio-ffmpeg 为本次新增，下载 31.2 MB，已下载，仅安装在本任务虚拟环境，未重复下载其他依赖。它向 Python 版提供 FFmpeg；EXE 构建明确排除该包，不捆绑 FFmpeg。

EXE 媒体工具使用同目录或 PATH 中的 ffmpeg.exe。请从 https://ffmpeg.org/download.html 获取可信构建；该二进制的体积随构建而变，不确定。视频信息面板可选 ffprobe；实际转换不依赖 ffprobe。

## 安装与卸载

源码版优先在虚拟环境安装各工具自己的 requirements.txt。无全局系统设置、注册表或启动项。卸载时删除自行创建的虚拟环境和工具文件夹即可；EXE 为便携文件，删除即可。自行单独安装的 FFmpeg 可删除其目录，若曾手动加入 PATH，再移除对应 PATH 条目。
# 新增标准库工具

重复文件扫描器、SHA-256 批量校验器、文件夹对比器和文本编码转换器只使用 Python 标准库及 Tkinter，无 pip 运行依赖；复用已有 Python 3.14.6、PyInstaller 6.21.0 与构建依赖，没有再次下载。每款 EXE 约 12.5 MiB，可直接删除下载文件卸载，不添加服务、启动项或系统 PATH。

新增工具的详细构建与卸载说明在各自目录的 DEPENDENCIES.md。

## 本批标准库工具

ZIP 查看与安全解压器、文本行去重器仅使用标准库/Tkinter，复用 Python 3.14.6、PyInstaller 6.21.0 和已安装构建依赖；没有新增下载或全局安装。每款 EXE 约 12.5 MiB，删除文件即可卸载。

## JSON 与空间分析工具

JSON 格式化与检查器、文件夹空间分析器仅使用标准库/Tkinter，复用 Python 3.14.6、PyInstaller 6.21.0 和已安装构建依赖；没有新增下载或全局安装。每款 EXE 约 12.5 MiB，删除文件即可卸载。

## 文本差异及时间戳工具

文本差异查看器、Unix 时间戳转换器仅使用标准库/Tkinter，复用 Python 3.14.6、PyInstaller 6.21.0 和已安装构建依赖；没有新增下载或全局安装。每款 EXE 约 12.5 MiB，删除文件即可卸载。
