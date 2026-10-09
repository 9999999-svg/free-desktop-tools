# 批量正方形缩图

按指定边长缩放并居中裁剪为正方形；默认跳过已有输出。原 README 中的宽高、百分比与 fit 模式并非当前实现。

所有功能免费，源码采用 MIT 许可。

## Windows EXE

从仓库 Releases 下载 `BatchResize.exe`。不带参数启动图形界面；命令行用法与 Python 版一致，将 `python batch_resize.py` 换成 `BatchResize.exe`。
## Python 源码

本次验证环境：Windows x64 / Python 3.14.6。安装本目录依赖后启动：

```powershell
python -m pip install -r requirements.txt
python batch_resize.py
python batch_resize.py -i "输入目录" -o "输出目录" --size 512
python batch_resize.py --help
```

## 构建

在仓库根目录安装 `requirements-build.txt`，运行 `python build.py batch-resize`。EXE 输出在 `dist/`。

源码和 EXE 始终免费；赞助完全自愿，见仓库首页。
