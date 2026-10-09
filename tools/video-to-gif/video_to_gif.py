#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频转GIF v2.0
功能：截取视频片段，输出为GIF动图
- 自动通过 imageio-ffmpeg 管理 FFmpeg，无需手动安装
- 支持视频首帧预览
- 可调帧率、宽度、时长等参数
依赖：pip install imageio-ffmpeg Pillow
"""

import os
import sys

# Keep Chinese and emoji CLI output readable in redirected Windows consoles.
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
import argparse
import subprocess
import threading
import json
from pathlib import Path

# imageio-ffmpeg 会在安装后自动提供 ffmpeg 路径
try:
    import imageio_ffmpeg
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    FFMPEG_PATH = None


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


def get_video_info(video_path):
    """获取视频基本信息"""
    ffmpeg = get_ffmpeg()
    if not ffmpeg:
        return None
    try:
        ffprobe = str(Path(ffmpeg).parent / 'ffprobe.exe') if os.name == 'nt' else str(Path(ffmpeg).parent / 'ffprobe')
        if not os.path.isfile(ffprobe):
            ffprobe = 'ffprobe'
        cmd = [
            ffprobe, '-v', 'quiet',
            '-print_format', 'json',
            '-show_format', '-show_streams',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        info = json.loads(result.stdout)

        video_stream = None
        for stream in info.get('streams', []):
            if stream.get('codec_type') == 'video':
                video_stream = stream
                break

        if video_stream:
            fps_str = video_stream.get('r_frame_rate', '0/1')
            if '/' in fps_str:
                num, den = fps_str.split('/')
                fps = float(num) / float(den) if float(den) != 0 else 0
            else:
                fps = float(fps_str)
            return {
                'width': int(video_stream.get('width', 0)),
                'height': int(video_stream.get('height', 0)),
                'fps': fps,
                'duration': float(info.get('format', {}).get('duration', 0)),
                'codec': video_stream.get('codec_name', 'unknown'),
            }
    except Exception:
        pass
    return None


def extract_first_frame(video_path, output_img_path):
    """提取视频第一帧保存为图片"""
    ffmpeg = get_ffmpeg()
    if not ffmpeg:
        return False
    try:
        cmd = [
            ffmpeg, '-y',
            '-ss', '0',
            '-i', video_path,
            '-vframes', '1',
            '-q:v', '2',
            output_img_path
        ]
        subprocess.run(cmd, capture_output=True, timeout=30, check=True)
        return os.path.isfile(output_img_path)
    except Exception:
        return False


def video_to_gif(video_path, output_path, start_time='00:00:00',
                  duration=5, fps=10, width=480, loop=0, progress_callback=None):
    ffmpeg = get_ffmpeg()
    if not ffmpeg:
        raise RuntimeError('FFmpeg 未找到；请将 ffmpeg.exe 放在工具旁或加入 PATH')
    if duration <= 0 or fps <= 0 or width <= 0 or loop < 0:
        raise ValueError('时长、帧率和宽度必须大于零，循环次数不得为负数')
    if not Path(video_path).is_file():
        raise FileNotFoundError(video_path)
    output_path = Path(output_path)
    if output_path.suffix.lower() != '.gif':
        raise ValueError('输出文件扩展名必须为 .gif')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if progress_callback:
        progress_callback(10, 100, '正在生成 GIF...')
    filters = (f'fps={fps},scale={width}:-1:flags=lanczos,split[a][b];'
               '[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5')
    result = subprocess.run([ffmpeg, '-y', '-ss', str(start_time), '-t', str(duration),
                             '-i', str(video_path), '-filter_complex', filters,
                             '-loop', str(loop), str(output_path)],
                            capture_output=True, text=True, timeout=300)
    if result.returncode:
        raise RuntimeError(f'FFmpeg 错误: {result.stderr}')
    if progress_callback:
        progress_callback(100, 100, f'GIF 已生成: {output_path.name} ({output_path.stat().st_size} bytes)')


def main():
    parser = argparse.ArgumentParser(
        description='[VID] 视频转GIF v2.0 - 截取视频片段输出GIF动图（自动管理FFmpeg）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  %(prog)s -i 视频.mp4 -o 输出.gif
  %(prog)s -i 视频.mp4 -o 输出.gif -ss 00:01:30 -t 3
  %(prog)s -i 视频.mp4 -o 输出.gif --fps 15 --width 360
        """
    )

    parser.add_argument('-i', '--input', required=True, help='输入视频文件路径')
    parser.add_argument('-o', '--output', default=None,
                        help='输出 GIF 路径 (默认: 视频名.gif)')
    parser.add_argument('-ss', '--start', default='00:00:00',
                        help='起始时间 HH:MM:SS (默认: 00:00:00)')
    parser.add_argument('-t', '--duration', type=float, default=5,
                        help='截取时长 秒 (默认: 5)')
    parser.add_argument('--fps', type=int, default=10,
                        help='输出帧率 帧/秒 (默认: 10)')
    parser.add_argument('--width', type=int, default=480,
                        help='GIF 宽度 像素 (默认: 480)')

    args = parser.parse_args()

    if get_ffmpeg() is None:
        print('[FAIL] FFmpeg 未找到；请将 ffmpeg.exe 放在工具旁或加入 PATH')
        sys.exit(1)

    # 自动生成输出路径
    if args.output is None:
        video_name = Path(args.input).stem
        args.output = f"{video_name}.gif"

    try:
        video_to_gif(
            args.input, args.output,
            start_time=args.start, duration=args.duration,
            fps=args.fps, width=args.width
        )
    except Exception as e:
        print(f"[FAIL] 错误: {e}")
        sys.exit(1)


# ============================================================
# GUI (Tkinter)
# ============================================================

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False


class VideoToGifGUI:
    """视频转GIF - 图形界面 (含预览)"""

    def __init__(self, root):
        self.root = root
        self.root.title("🎬 视频转GIF v2.0")
        self.root.geometry("700x780")
        self.root.configure(bg="#f0f2f5")
        self.root.resizable(False, False)

        self.main_color = "#667eea"
        self.main_color_light = "#8b9cf7"
        self.running = False
        self.ffmpeg_checked = False

        self._build_ui()

    def _build_ui(self):
        # 标题栏
        title_frame = tk.Frame(self.root, bg=self.main_color, height=50)
        title_frame.pack(fill="x")
        title_frame.pack_propagate(False)
        tk.Label(title_frame, text="🎬 视频转GIF v2.0", font=("Microsoft YaHei", 16, "bold"),
                 bg=self.main_color, fg="white").pack(expand=True)

        main_frame = tk.Frame(self.root, bg="#f0f2f5", padx=20, pady=12)
        main_frame.pack(fill="both", expand=True)

        # ====== 预览区域 ======
        preview_frame = tk.LabelFrame(main_frame, text=" 视频预览 ", bg="#f0f2f5",
                                      font=("Microsoft YaHei", 10, "bold"),
                                      relief="groove", padx=8, pady=8)
        preview_frame.pack(fill="x", pady=(0, 8))

        self.preview_label = tk.Label(preview_frame, text="← 请选择视频文件",
                                      bg="#e0e0e0", font=("Microsoft YaHei", 9),
                                      width=60, height=8, relief="sunken")
        self.preview_label.pack(fill="x")

        self.video_info_label = tk.Label(preview_frame, text="", bg="#f0f2f5",
                                         font=("Microsoft YaHei", 9), fg="gray")
        self.video_info_label.pack(anchor="w", pady=(3, 0))

        # ====== 输入视频 ======
        row1 = tk.Frame(main_frame, bg="#f0f2f5")
        row1.pack(fill="x", pady=4)
        tk.Label(row1, text="视频文件：", width=9, anchor="w",
                 bg="#f0f2f5", font=("Microsoft YaHei", 10)).pack(side="left")
        self.input_var = tk.StringVar()
        self.input_var.trace('w', self._on_input_changed)
        tk.Entry(row1, textvariable=self.input_var, font=("Microsoft YaHei", 9)).pack(
            side="left", fill="x", expand=True, padx=5)
        tk.Button(row1, text="浏览", command=self._browse_input,
                  bg=self.main_color, fg="white", font=("Microsoft YaHei", 9),
                  relief="flat", cursor="hand2").pack(side="right")

        # ====== 输出路径 ======
        row2 = tk.Frame(main_frame, bg="#f0f2f5")
        row2.pack(fill="x", pady=4)
        tk.Label(row2, text="输出路径：", width=9, anchor="w",
                 bg="#f0f2f5", font=("Microsoft YaHei", 10)).pack(side="left")
        self.output_var = tk.StringVar()
        tk.Entry(row2, textvariable=self.output_var, font=("Microsoft YaHei", 9)).pack(
            side="left", fill="x", expand=True, padx=5)
        tk.Button(row2, text="保存到", command=self._browse_output,
                  bg=self.main_color, fg="white", font=("Microsoft YaHei", 9),
                  relief="flat", cursor="hand2").pack(side="right")

        # ====== 参数区域 ======
        cfg_frame = tk.LabelFrame(main_frame, text="转换参数", bg="#f0f2f5",
                                  font=("Microsoft YaHei", 10, "bold"),
                                  relief="groove", padx=10, pady=10)
        cfg_frame.pack(fill="x", pady=6)

        # 起始时间 (秒)
        time_frame = tk.Frame(cfg_frame, bg="#f0f2f5")
        time_frame.pack(fill="x", pady=3)
        tk.Label(time_frame, text="起始时间(秒)：", width=12, anchor="w",
                 bg="#f0f2f5", font=("Microsoft YaHei", 9)).pack(side="left")
        self.start_var = tk.IntVar(value=0)
        tk.Spinbox(time_frame, from_=0, to=99999, textvariable=self.start_var,
                   width=8, font=("Microsoft YaHei", 9)).pack(side="left")

        # 截取时长
        tk.Label(time_frame, text="    截取时长(秒)：", bg="#f0f2f5",
                 font=("Microsoft YaHei", 9)).pack(side="left", padx=(10, 0))
        self.duration_var = tk.IntVar(value=5)
        tk.Spinbox(time_frame, from_=1, to=30, textvariable=self.duration_var,
                   width=6, font=("Microsoft YaHei", 9)).pack(side="left")

        # 帧率
        fps_frame = tk.Frame(cfg_frame, bg="#f0f2f5")
        fps_frame.pack(fill="x", pady=3)
        tk.Label(fps_frame, text="帧率(fps)：", width=12, anchor="w",
                 bg="#f0f2f5", font=("Microsoft YaHei", 9)).pack(side="left")
        self.fps_var = tk.IntVar(value=10)
        tk.Spinbox(fps_frame, from_=1, to=30, textvariable=self.fps_var,
                   width=6, font=("Microsoft YaHei", 9)).pack(side="left")

        # 宽度
        tk.Label(fps_frame, text="    宽度(px)：", bg="#f0f2f5",
                 font=("Microsoft YaHei", 9)).pack(side="left", padx=(10, 0))
        self.width_var = tk.IntVar(value=480)
        tk.Spinbox(fps_frame, from_=50, to=1920, textvariable=self.width_var,
                   width=6, font=("Microsoft YaHei", 9)).pack(side="left")

        # ====== 进度条 ======
        progress_frame = tk.Frame(main_frame, bg="#f0f2f5")
        progress_frame.pack(fill="x", pady=6)
        self.progress_var = tk.IntVar(value=0)
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var,
                                            length=660, mode="determinate")
        self.progress_bar.pack(fill="x")

        # ====== 日志区域 ======
        log_frame = tk.LabelFrame(main_frame, text="运行日志", bg="#f0f2f5",
                                  font=("Microsoft YaHei", 9, "bold"),
                                  relief="groove", padx=5, pady=5)
        log_frame.pack(fill="both", expand=True, pady=4)

        self.log_text = tk.Text(log_frame, height=8, font=("Consolas", 9),
                                bg="white", fg="#333", relief="sunken",
                                wrap="word", state="disabled")
        self.log_text.pack(fill="both", expand=True)

        # ====== 开始按钮 ======
        btn_frame = tk.Frame(main_frame, bg="#f0f2f5")
        btn_frame.pack(fill="x", pady=6)
        self.start_btn = tk.Button(btn_frame, text="▶ 开始转换", command=self._start_convert,
                                   bg=self.main_color, fg="white",
                                   font=("Microsoft YaHei", 12, "bold"),
                                   relief="flat", cursor="hand2", height=1,
                                   activebackground=self.main_color_light)
        self.start_btn.pack(fill="x")

    def _log(self, msg):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        self.root.update_idletasks()

    def _browse_input(self):
        path = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=[
                ("视频文件", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm"),
                ("所有文件", "*.*")
            ]
        )
        if path:
            self.input_var.set(path)

    def _on_input_changed(self, *args):
        path = self.input_var.get().strip()
        if path and os.path.isfile(path):
            # 自动设置输出
            if not self.output_var.get():
                p = Path(path)
                self.output_var.set(str(p.parent / f"{p.stem}.gif"))
            self._update_preview(path)

    def _update_preview(self, path):
        """更新预览：显示视频首帧缩略图和信息"""
        try:
            # 显示视频信息
            info = get_video_info(path)
            if info:
                w, h = info['width'], info['height']
                dur = info['duration']
                fps = info['fps']
                mins, secs = divmod(int(dur), 60)
                hrs, mins = divmod(mins, 60)
                info_text = f"📐 {w}x{h}  |  ⏱ {hrs:02d}:{mins:02d}:{secs:02d}  |  🎞 {fps:.2f}fps"
                self.video_info_label.configure(text=info_text)

                # 提取首帧
                import tempfile
                tmp_img = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
                tmp_path = tmp_img.name
                tmp_img.close()

                if extract_first_frame(path, tmp_path) and os.path.isfile(tmp_path):
                    from PIL import Image, ImageTk
                    try:
                        # 限制预览图尺寸
                        preview = Image.open(tmp_path)
                        max_w, max_h = 500, 200
                        preview.thumbnail((max_w, max_h), Image.LANCZOS)
                        photo = ImageTk.PhotoImage(preview)
                        self.preview_label.configure(image=photo, text="", width=0, height=0)
                        self.preview_label.image = photo  # keep reference
                    except Exception:
                        pass
                    finally:
                        try:
                            os.unlink(tmp_path)
                        except Exception:
                            pass
                else:
                    # 无法提取帧，至少显示文件名和大小
                    size = os.path.getsize(path)
                    if size > 1024 * 1024:
                        size_str = f"{size / 1024 / 1024:.1f} MB"
                    else:
                        size_str = f"{size / 1024:.1f} KB"
                    fname = os.path.basename(path)
                    self.preview_label.configure(text=f"📁 {fname}  ({size_str})\n(无法提取预览帧，请安装 imageio)",
                                                 bg="#e0e0e0", font=("Microsoft YaHei", 9))
                    if hasattr(self.preview_label, 'image'):
                        del self.preview_label.image
            else:
                self.video_info_label.configure(text="未能读取视频信息")
                self.preview_label.configure(text="⚠️ 未能解析视频文件", bg="#ffe0e0")
                if hasattr(self.preview_label, 'image'):
                    del self.preview_label.image
        except Exception as e:
            self.video_info_label.configure(text=f"预览错误: {e}")

    def _browse_output(self):
        path = filedialog.asksaveasfilename(
            title="保存为",
            defaultextension=".gif",
            filetypes=[("GIF 动图", "*.gif"), ("所有文件", "*.*")]
        )
        if path:
            self.output_var.set(path)

    def _check_ffmpeg(self):
        if get_ffmpeg():
            return True
        messagebox.showerror('FFmpeg 未找到', '请将 ffmpeg.exe 放在工具旁或加入 PATH；源码版也可安装 requirements.txt。')
        return False

    def _start_convert(self):
        if self.running:
            return

        # 检查 FFmpeg
        if not self._check_ffmpeg():
            return

        input_path = self.input_var.get().strip()
        output_path = self.output_var.get().strip()

        if not input_path:
            messagebox.showwarning("提示", "请选择视频文件")
            return
        if not os.path.isfile(input_path):
            messagebox.showerror("错误", "视频文件不存在")
            return
        if not output_path:
            messagebox.showwarning("提示", "请设置输出路径")
            return

        # 解析参数
        try:
            start_time = self.start_var.get()
            duration = self.duration_var.get()
            fps = self.fps_var.get()
            width = self.width_var.get()
        except ValueError:
            messagebox.showerror("错误", "参数格式不正确")
            return

        self.running = True
        self.start_btn.configure(state="disabled", text="⏳ 转换中...")
        self.progress_var.set(0)
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

        self._log(f"[INFO] 视频: {input_path}")
        self._log(f"[INFO] 输出: {output_path}")
        self._log(f"[INFO] 起始={start_time}s, 时长={duration}s, FPS={fps}, 宽度={width}")
        self._log("-" * 40)

        def task():
            def progress_cb(current, total, msg):
                self.progress_var.set(int(current / total * 100) if total > 0 else 0)
                self._log(f"  {msg}")

            try:
                # 将秒数转为 HH:MM:SS 格式
                h = start_time // 3600
                m = (start_time % 3600) // 60
                s = start_time % 60
                start_str = f"{h:02d}:{m:02d}:{s:02d}"

                video_to_gif(
                    input_path, output_path,
                    start_time=start_str, duration=duration,
                    fps=fps, width=width,
                    progress_callback=progress_cb
                )
                self.root.after(0, lambda: self._log("[OK] 转换完成！"))
            except Exception as e:
                self.root.after(0, lambda: self._log(f"[FAIL] 错误: {e}"))
            finally:
                self.root.after(0, self._reset_btn)

        threading.Thread(target=task, daemon=True).start()

    def _reset_btn(self):
        self.running = False
        self.start_btn.configure(state="normal", text="▶ 开始转换")


# ============================================================
# 入口
# ============================================================

if __name__ == '__main__':
    if len(sys.argv) > 1:
        main()
    elif TK_AVAILABLE:
        root = tk.Tk()
        app = VideoToGifGUI(root)
        root.mainloop()
    else:
        print("[ERROR] Tkinter 不可用，请在命令行模式下使用参数运行")
        sys.exit(1)
