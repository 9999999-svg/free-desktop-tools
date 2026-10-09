#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
万能视频下载器 v1.0
功能：粘贴链接，下载 B站/抖音/Youtube 等平台视频或音频，可选清晰度。
依赖：yt-dlp；媒体合并和 MP3 转码需要 FFmpeg
"""

import os
import sys

# Keep Chinese and emoji CLI output readable in redirected Windows consoles.
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
import re
import argparse
import subprocess
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

# ── 画质映射：中文显示 → yt-dlp 内部值 ──
QUALITY_MAP = {
    "最高": "best",
    "1080p": "1080",
    "720p":  "720",
    "480p":  "480",
    "360p":  "360",
}
QUALITY_REVERSE_MAP = {v: k for k, v in QUALITY_MAP.items()}

# ── 全局 ffmpeg 路径（启动时获取） ──
FFMPEG_PATH = None


def auto_install_ytdlp():
    """Check the bundled Python module without installing at runtime."""
    try:
        import yt_dlp
        print(f'[OK] yt-dlp v{yt_dlp.version.__version__} 已就绪')
        return True
    except ImportError:
        print('[FAIL] 缺少 yt-dlp；源码版请安装 requirements.txt，EXE 版请重新下载完整发布包')
        return False


def get_ffmpeg():
    """Prefer an EXE beside this tool, then PATH, then optional Python package."""
    import shutil
    folder = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
    adjacent = folder / ('ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
    if adjacent.is_file():
        return str(adjacent)
    found = shutil.which('ffmpeg')
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError):
        return None


def auto_install_imageio_ffmpeg():
    global FFMPEG_PATH
    FFMPEG_PATH = get_ffmpeg()
    if not FFMPEG_PATH:
        print('[WARN] FFmpeg 未找到；请将 ffmpeg.exe 放在工具旁或加入 PATH')
    return bool(FFMPEG_PATH)


def ensure_dependencies():
    """启动时确保所有依赖已安装"""
    yt_ok = auto_install_ytdlp()
    ff_ok = auto_install_imageio_ffmpeg()
    return yt_ok, ff_ok


def get_video_info(url):
    try:
        import yt_dlp
        with yt_dlp.YoutubeDL({'quiet': True, 'noplaylist': True, 'socket_timeout': 20}) as downloader:
            info = downloader.extract_info(url, download=False)
        return {key: info.get(key, '') for key in ('title', 'duration', 'uploader', 'webpage_url', 'extractor')}
    except Exception:
        return None


def download_media(url, output_dir, format_type='video', quality='best',
                    output_template=None, playlist=False, batch_file=None,
                    callback=None):
    """
    下载媒体文件

    Args:
        url: 视频链接或批处理文件路径
        output_dir: 输出目录
        format_type: video(视频) 或 audio(仅音频)
        quality: 画质 (best/1080/720/480/360)
        output_template: 输出文件名模板
        playlist: 下载整个播放列表
        batch_file: 从文件读取链接列表
        callback: 进度回调 callback(msg, progress)
    """
    global FFMPEG_PATH

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 确保依赖
    if not auto_install_ytdlp():
        if callback:
            callback("[FAIL] yt-dlp 安装失败，无法继续", 0)
        return
    ffmpeg_available = bool(FFMPEG_PATH)
    if FFMPEG_PATH is None:
        auto_install_imageio_ffmpeg()
    ffmpeg_available = bool(FFMPEG_PATH)

    # 构建命令
    cmd = ['yt-dlp', '--no-mtime', '--no-overwrites']
    if FFMPEG_PATH:
        cmd.extend(['--ffmpeg-location', FFMPEG_PATH])

    # 输出模板
    if output_template:
        template = output_template
    else:
        template = '%(title)s.%(ext)s'

    cmd.extend(['-o', str(output_path / template)])

    # 用户代理
    cmd.extend(['--user-agent',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'])

    # 格式选择
    quality_map = {
        'best': 'bestvideo+bestaudio/best',
        '1080': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
        '720': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
        '480': 'bestvideo[height<=480]+bestaudio/best[height<=480]',
        '360': 'bestvideo[height<=360]+bestaudio/best[height<=360]',
        'audio': 'bestaudio/best',
    }

    if format_type == 'audio':
        fmt = quality_map.get('audio', 'bestaudio/best')
        cmd.extend(['-f', fmt, '-x'])
        cmd.extend(['--audio-format', 'mp3', '--audio-quality', '0'])
        if callback:
            callback("[AUD] 音频下载模式", 0)
        else:
            print("[AUD] 音频下载模式")
    else:
        fmt = quality_map.get(quality, quality_map['best'])
        cmd.extend(['-f', fmt])
        if callback:
            callback(f"[VID] 视频下载模式 (画质: {quality})", 0)
        else:
            print(f"[VID] 视频下载模式 (画质: {quality})")

    # 合并格式
    if ffmpeg_available:
        cmd.append('--merge-output-format')
        cmd.append('mp4')
    else:
        msg = "[WARN] FFmpeg 未安装，下载的视频可能没有音频或无法合并"
        if callback:
            callback(msg, 0)
        else:
            print(msg)

    # 字幕
    cmd.extend(['--write-subs', '--write-auto-subs', '--sub-langs', 'all',
                '--convert-subs', 'srt'])

    # 缩略图
    cmd.append('--embed-thumbnail')

    # 播放列表
    if not playlist:
        cmd.append('--no-playlist')

    # 重试
    cmd.extend(['--retries', '5', '--fragment-retries', '5'])

    # 获取视频信息打印
    if callback:
        info = get_video_info(url if url else '')
        if info:
            duration = info.get('duration', 0)
            dur_str = ""
            if duration:
                mins, secs = divmod(int(duration), 60)
                dur_str = f"{mins}:{secs:02d}"
            callback(f"📺 标题: {info['title']}", 0)
            if dur_str:
                callback(f"⏱ 时长: {dur_str}", 0)
            callback(f"👤 作者: {info['uploader']}", 0)
            callback(f"🔗 平台: {info['extractor']}", 0)

    # 添加URL
    if url:
        cmd.append(url)

    # 批处理文件
    if batch_file and os.path.isfile(batch_file):
        cmd.extend(['--batch-file', batch_file])

    if not url and not batch_file:
        if callback:
            callback("[FAIL] 请提供下载链接或批处理文件", 0)
        return

    if callback:
        callback("[OUT] 开始下载...", 10)
    else:
        print(f"\n[OUT] 开始下载...")

    try:
        import yt_dlp
        parsed = yt_dlp.parse_options(cmd[1:])
        parsed.ydl_opts['socket_timeout'] = 30
        if callback:
            def on_progress(event):
                total = event.get('total_bytes') or event.get('total_bytes_estimate') or 0
                pct = int(event.get('downloaded_bytes', 0) / total * 90) if total else 0
                callback('[OUT] 正在下载...', min(90, pct))
            parsed.ydl_opts['progress_hooks'] = [on_progress]
        with yt_dlp.YoutubeDL(parsed.ydl_opts) as downloader:
            result = downloader.download(parsed.urls)
        if result == 0:
            if callback:
                callback(f"[OK] 下载完成！文件保存到: {output_path}", 100)
            else:
                print(f"\n[OK] 下载完成！")
                print(f"📁 文件保存到: {output_path}")
        else:
            if callback:
                callback(f"[FAIL] 下载失败 (返回码: {result})", 0)
            else:
                print(f"\n[FAIL] 下载失败 (返回码: {result})")
    except subprocess.TimeoutExpired:
        if callback:
            callback("[FAIL] 下载超时 (>1小时)", 0)
        else:
            print("\n[FAIL] 下载超时 (>1小时)")
    except KeyboardInterrupt:
        if callback:
            callback("⏹ 已取消下载", 0)
        else:
            print("\n⏹ 已取消下载")
    except Exception as e:
        if callback:
            callback(f"[FAIL] 错误: {e}", 0)
        else:
            print(f"\n[FAIL] 错误: {e}")


def interactive_mode():
    """交互式下载模式"""
    print(f"{'=' * 50}")
    print("  万能视频下载器 - 交互模式")
    print(f"{'=' * 50}")

    # 检查依赖
    yt_ok, ff_ok = ensure_dependencies()
    if not yt_ok:
        print("[FAIL] 核心依赖 yt-dlp 安装失败，无法继续")
        return
    print()

    while True:
        url = input("📎 粘贴链接 (输入 q 退出): ").strip()
        if url.lower() in ('q', 'quit', 'exit'):
            print("👋 再见！")
            break

        if not url:
            continue

        print("[FIND] 正在解析链接...")
        info = get_video_info(url)
        if info:
            print(f"\n📺 标题: {info['title']}")
            print(f"👤 作者: {info['uploader']}")
            print(f"🔗 平台: {info['extractor']}")
        else:
            print("[WARN] 无法获取视频信息，将继续尝试下载")

        print(f"\n选择下载类型:")
        print("  1. 视频（最高画质）")
        print("  2. 视频（1080p）")
        print("  3. 视频（720p）")
        print("  4. 视频（480p）")
        print("  5. 仅音频（MP3）")

        choice = input("请选择 (1-5, 默认1): ").strip() or '1'

        quality_map = {
            '1': 'best', '2': '1080', '3': '720', '4': '480', '5': 'audio'
        }
        quality = quality_map.get(choice, 'best')
        format_type = 'audio' if choice == '5' else 'video'

        output_dir = input(f"📁 输出目录 (默认: ./下载): ").strip() or './下载'

        print(f"{'-' * 50}")
        download_media(url, output_dir, format_type=format_type, quality=quality)
        print(f"{'-' * 50}\n")


class UniversalDownloaderGUI:
    """万能视频下载器 - 图形界面"""

    def __init__(self, master):
        self.master = master
        master.title("万能视频下载器 v1.0")
        master.geometry("750x650")
        master.configure(bg="white")

        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TLabel', background='white', font=('Microsoft YaHei', 10))
        style.configure('TButton', font=('Microsoft YaHei', 10))
        style.configure('TCheckbutton', background='white', font=('Microsoft YaHei', 10))
        style.configure('TRadiobutton', background='white', font=('Microsoft YaHei', 10))
        style.configure('TFrame', background='white')
        style.configure('TLabelframe', background='white')
        style.configure('TLabelframe.Label', background='white', font=('Microsoft YaHei', 10))
        style.configure('TCombobox', font=('Microsoft YaHei', 10))
        style.configure('Horizontal.TProgressbar', background='#667eea', troughcolor='#e0e0e0')

        self.main_color = '#667eea'

        # --- 标题 ---
        title_frame = tk.Frame(master, bg='white')
        title_frame.pack(pady=(15, 10))
        tk.Label(title_frame, text="🌐 万能视频下载器", font=('Microsoft YaHei', 18, 'bold'),
                fg=self.main_color, bg='white').pack()
        tk.Label(title_frame, text="下载 B站/抖音/YouTube 等平台的视频或音频",
                font=('Microsoft YaHei', 9), fg='#888', bg='white').pack()

        # --- 依赖检测状态 ---
        status_frame = tk.Frame(master, bg='white')
        status_frame.pack()

        self.ytdlp_status = tk.Label(status_frame, text="", font=('Microsoft YaHei', 9), bg='white')
        self.ytdlp_status.pack(side='left', padx=10)

        self.ffmpeg_status = tk.Label(status_frame, text="", font=('Microsoft YaHei', 9), bg='white')
        self.ffmpeg_status.pack(side='left', padx=10)

        # 启动时自动检查并安装依赖
        self.master.after(100, self.check_dependencies)

        # --- 主内容区域 ---
        main_frame = tk.Frame(master, bg='white')
        main_frame.pack(fill='both', expand=True, padx=20, pady=5)

        # URL 输入
        tk.Label(main_frame, text="视频链接：", anchor='w', bg='white',
                font=('Microsoft YaHei', 10)).grid(row=0, column=0, sticky='w', pady=8)
        self.url_var = tk.StringVar()
        tk.Entry(main_frame, textvariable=self.url_var, font=('Microsoft YaHei', 10),
                width=55, relief='solid', bd=1).grid(row=0, column=1, padx=5, pady=8)

        # 输出目录
        tk.Label(main_frame, text="输出目录：", anchor='w', bg='white',
                font=('Microsoft YaHei', 10)).grid(row=1, column=0, sticky='w', pady=8)
        self.output_dir_var = tk.StringVar(value=os.path.join(os.getcwd(), '下载'))
        tk.Entry(main_frame, textvariable=self.output_dir_var, font=('Microsoft YaHei', 10),
                width=55, relief='solid', bd=1).grid(row=1, column=1, padx=5, pady=8)
        tk.Button(main_frame, text="浏览", command=self.browse_output,
                 bg=self.main_color, fg='white', font=('Microsoft YaHei', 10),
                 relief='flat', cursor='hand2', padx=12).grid(row=1, column=2, padx=5, pady=8)

        # --- 下载设置 ---
        settings_frame = tk.LabelFrame(main_frame, text=" 下载设置 ", font=('Microsoft YaHei', 10, 'bold'),
                                      bg='white', fg=self.main_color, relief='groove', bd=1)
        settings_frame.grid(row=2, column=0, columnspan=3, sticky='ew', pady=10)

        # 下载类型 (RadioButton)
        tk.Label(settings_frame, text="下载类型：", bg='white', font=('Microsoft YaHei', 10)).grid(
            row=0, column=0, sticky='w', padx=10, pady=5)
        self.dl_type_var = tk.StringVar(value='video')
        tk.Radiobutton(settings_frame, text="视频", variable=self.dl_type_var,
                      value='video', bg='white', font=('Microsoft YaHei', 10),
                      command=self.on_type_change).grid(row=0, column=1, sticky='w', padx=5, pady=5)
        tk.Radiobutton(settings_frame, text="仅音频", variable=self.dl_type_var,
                      value='audio', bg='white', font=('Microsoft YaHei', 10),
                      command=self.on_type_change).grid(row=0, column=2, sticky='w', padx=5, pady=5)

        # 画质（中文显示，仅视频模式有效）
        tk.Label(settings_frame, text="画质：", bg='white', font=('Microsoft YaHei', 10)).grid(
            row=1, column=0, sticky='w', padx=10, pady=5)
        self.quality_var = tk.StringVar(value='最高')
        self.quality_menu = ttk.Combobox(settings_frame, textvariable=self.quality_var,
                                         values=list(QUALITY_MAP.keys()),
                                         state='readonly', width=12, font=('Microsoft YaHei', 10))
        self.quality_menu.grid(row=1, column=1, sticky='w', padx=5, pady=5)
        self.quality_label = tk.Label(settings_frame, text="(仅视频模式)", bg='white',
                                      font=('Microsoft YaHei', 8), fg='#888')
        self.quality_label.grid(row=1, column=2, sticky='w', padx=5, pady=5)

        # --- 视频信息显示 ---
        self.info_text = tk.Text(settings_frame, height=3, width=60,
                                font=('Microsoft YaHei', 9), bg='#f0f4ff',
                                fg='#333', relief='solid', bd=1,
                                wrap='word', state='disabled')
        self.info_text.grid(row=2, column=0, columnspan=3, sticky='ew', padx=10, pady=5)

        # --- 操作按钮 ---
        btn_frame = tk.Frame(main_frame, bg='white')
        btn_frame.grid(row=3, column=0, columnspan=3, pady=10)

        self.info_btn = tk.Button(btn_frame, text="📋 获取信息", command=self.get_info,
                                 bg='#ff9800', fg='white',
                                 font=('Microsoft YaHei', 11, 'bold'),
                                 relief='flat', cursor='hand2', padx=15, pady=4)
        self.info_btn.pack(side='left', padx=5)

        self.download_btn = tk.Button(btn_frame, text="⬇ 开始下载", command=self.start_download,
                                      bg=self.main_color, fg='white',
                                      font=('Microsoft YaHei', 11, 'bold'),
                                      relief='flat', cursor='hand2', padx=20, pady=4)
        self.download_btn.pack(side='left', padx=5)

        # --- 进度条 ---
        self.progress = ttk.Progressbar(main_frame, mode='determinate',
                                        style='Horizontal.TProgressbar')
        self.progress.grid(row=4, column=0, columnspan=3, sticky='ew', pady=5)

        # --- 日志 ---
        log_frame = tk.LabelFrame(main_frame, text=" 日志输出 ", font=('Microsoft YaHei', 10, 'bold'),
                                 bg='white', fg=self.main_color, relief='groove', bd=1)
        log_frame.grid(row=5, column=0, columnspan=3, sticky='nsew', pady=5)
        main_frame.grid_rowconfigure(5, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)

        self.log_text = tk.Text(log_frame, height=12, width=80, font=('Consolas', 9),
                               bg='#f8f8f8', fg='#333', relief='solid', bd=1,
                               wrap='word', state='disabled')
        scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.config(yscrollcommand=scrollbar.set)
        self.log_text.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        scrollbar.pack(side='right', fill='y', pady=5)

        # 初始状态
        self.on_type_change()

    def check_dependencies(self):
        yt_ok, ff_ok = ensure_dependencies()
        self.ytdlp_status.config(text='✓ yt-dlp 已就绪' if yt_ok else '✗ 缺少 yt-dlp', fg='green' if yt_ok else 'red')
        self.ffmpeg_status.config(text='✓ FFmpeg 已就绪' if ff_ok else '✗ 缺少 FFmpeg', fg='green' if ff_ok else 'red')
        self.log('依赖检查完成；没有自动安装或修改系统环境。')

    def on_type_change(self):
        """切换下载类型时更新画质控件状态"""
        if self.dl_type_var.get() == 'audio':
            self.quality_menu.config(state='disabled')
            self.quality_label.config(text="(音频模式不适用)")
        else:
            self.quality_menu.config(state='readonly')
            self.quality_label.config(text="(仅视频模式)")

    def browse_output(self):
        dir_path = filedialog.askdirectory(title="选择输出目录")
        if dir_path:
            self.output_dir_var.set(dir_path)

    def log(self, msg):
        self.log_text.config(state='normal')
        self.log_text.insert('end', msg + '\n')
        self.log_text.see('end')
        self.log_text.config(state='disabled')
        self.master.update_idletasks()

    def set_info(self, msg):
        self.info_text.config(state='normal')
        self.info_text.delete('1.0', 'end')
        self.info_text.insert('1.0', msg)
        self.info_text.config(state='disabled')

    def update_progress(self, msg, progress):
        self.log(msg)
        self.progress['value'] = progress
        self.master.update_idletasks()

    def get_info(self):
        """获取视频信息"""
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("提示", "请先粘贴视频链接")
            return

        self.info_btn.config(state='disabled', text='⏳ 解析中...')
        self.set_info("正在解析链接，请稍候...")

        def task():
            try:
                info = get_video_info(url)
                if info:
                    duration = info.get('duration', 0)
                    dur_str = ""
                    if duration:
                        mins, secs = divmod(int(duration), 60)
                        dur_str = f"{mins}:{secs:02d}"

                    lines = []
                    lines.append(f"📺 标题: {info['title']}")
                    lines.append(f"👤 作者: {info['uploader']}  |  🔗 平台: {info['extractor']}")
                    if dur_str:
                        lines.append(f"⏱ 时长: {dur_str}")

                    info_text = '\n'.join(lines)
                    self.master.after(0, lambda: self.set_info(info_text))
                    self.master.after(0, lambda: self.log("✓ 视频信息获取成功"))
                else:
                    self.master.after(0, lambda: self.set_info("⚠ 无法获取视频信息，请检查链接是否有效"))
                    self.master.after(0, lambda: self.log("✗ 视频信息获取失败"))
            finally:
                self.master.after(0, lambda: self.info_btn.config(
                    state='normal', text='📋 获取信息'))

        t = threading.Thread(target=task, daemon=True)
        t.start()

    def start_download(self):
        """开始下载"""
        url = self.url_var.get().strip()
        output_dir = self.output_dir_var.get().strip()

        if not url:
            messagebox.showwarning("提示", "请先粘贴视频链接")
            return

        if not output_dir:
            messagebox.showwarning("提示", "请选择输出目录")
            return

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # 禁用按钮
        self.info_btn.config(state='disabled')
        self.download_btn.config(state='disabled', text='⏳ 下载中...')
        self.progress['value'] = 0
        self.log_text.config(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.config(state='disabled')

        format_type = self.dl_type_var.get()
        # 中文画质名 → 内部值
        quality_cn = self.quality_var.get()
        quality = QUALITY_MAP.get(quality_cn, 'best')

        def task():
            try:
                download_media(
                    url, output_dir,
                    format_type=format_type,
                    quality=quality,
                    callback=lambda msg, pct: self.master.after(0, lambda: self.update_progress(msg, pct))
                )
            finally:
                self.master.after(0, self.on_download_done)

        t = threading.Thread(target=task, daemon=True)
        t.start()

    def on_download_done(self):
        self.info_btn.config(state='normal')
        self.download_btn.config(state='normal', text='⬇ 开始下载')
        self.log("=" * 40)
        self.log("下载任务已结束")


def main():
    parser = argparse.ArgumentParser(
        description='🌐 万能视频下载器 - 下载B站/抖音/YouTube等平台视频或音频',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  %(prog)s -u "https://www.youtube.com/watch?v=xxx"
  %(prog)s -u "https://www.bilibili.com/video/BV1xx" --quality 1080
  %(prog)s -u "https://www.douyin.com/video/xxx" -a
  %(prog)s -u "https://www.youtube.com/playlist?list=xxx" --playlist
  %(prog)s -b urls.txt -o ./下载目录
  %(prog)s --interactive  (交互模式)
        """
    )

    parser.add_argument('-u', '--url', help='视频链接')
    parser.add_argument('-o', '--output', default='./下载',
                        help='输出目录 (默认: ./下载)')
    parser.add_argument('-a', '--audio', action='store_true',
                        help='仅下载音频 (MP3)')
    parser.add_argument('--quality', default='best',
                        choices=['best', '1080', '720', '480', '360'],
                        help='画质 (默认: best)')
    parser.add_argument('--playlist', action='store_true',
                        help='下载整个播放列表')
    parser.add_argument('-b', '--batch', help='从文件读取链接列表')
    parser.add_argument('--template', default=None,
                        help='输出文件名模板 (默认: %%(title)s.%%(ext)s)')
    parser.add_argument('--interactive', action='store_true',
                        help='交互式模式')

    args = parser.parse_args()

    if args.interactive:
        interactive_mode()
        return

    if not args.url and not args.batch:
        interactive_mode()
        return

    format_type = 'audio' if args.audio else 'video'

    download_media(
        args.url, args.output,
        format_type=format_type, quality=args.quality,
        output_template=args.template,
        playlist=args.playlist,
        batch_file=args.batch
    )


if __name__ == '__main__':
    # CLI 模式或 GUI 模式
    if len(sys.argv) > 1:
        main()
    else:
        root = tk.Tk()
        app = UniversalDownloaderGUI(root)
        root.mainloop()
