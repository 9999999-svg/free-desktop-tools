#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
提取视频音频 v1.0
功能：从视频文件中提取音频，输出 MP3 或 M4A 格式。
依赖：FFmpeg（需单独安装并添加到 PATH）
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
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path


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


def check_ffmpeg():
    return get_ffmpeg() is not None


def extract_audio_batch(input_dir, output_dir, format='mp3',
                         sample_rate=44100, bit_rate='192k',
                         channels=2, overwrite=False, callback=None):
    """
    批量提取视频音频
    
    Args:
        input_dir: 输入视频目录
        output_dir: 输出音频目录
        format: 输出格式 (mp3/m4a/wav/flac/ogg)
        sample_rate: 采样率 (Hz)
        bit_rate: 比特率 (如 192k, 320k)
        channels: 声道数 (1=单声道, 2=立体声)
        overwrite: 覆盖已有文件
        callback: 进度回调函数 callback(msg, progress)
    """
    ffmpeg = get_ffmpeg()
    if not ffmpeg:
        raise RuntimeError('FFmpeg 未找到；请将 ffmpeg.exe 放在工具旁或加入 PATH')
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 支持的视频格式
    video_exts = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm',
                  '.m4v', '.mpg', '.mpeg', '.ts', '.3gp', '.ogv', '.mts'}
    
    # 格式到编码器的映射
    codec_map = {
        'mp3': 'libmp3lame',
        'm4a': 'aac',
        'wav': 'pcm_s16le',
        'flac': 'flac',
        'ogg': 'libvorbis',
    }
    
    # 格式到扩展名
    ext_map = {
        'mp3': '.mp3',
        'm4a': '.m4a',
        'wav': '.wav',
        'flac': '.flac',
        'ogg': '.ogg',
    }
    
    audio_codec = codec_map.get(format, 'libmp3lame')
    output_ext = ext_map.get(format, f'.{format}')
    
    # 收集视频文件
    files = [f for f in input_path.iterdir()
             if f.suffix.lower() in video_exts and f.is_file()]
    
    if not files:
        msg = f"在 '{input_dir}' 中未找到视频文件\n支持格式: {', '.join(sorted(video_exts))}"
        if callback:
            callback(msg, 0)
        else:
            print(f"[WARN] {msg}")
        return
    
    total = len(files)
    if callback:
        callback(f"找到 {total} 个视频文件\n输出格式: .{format} | 采样率: {sample_rate}Hz | 比特率: {bit_rate} | 声道: {'立体声' if channels==2 else '单声道'}", 0)
    
    success = 0
    errors = 0
    
    for i, video_file in enumerate(files, 1):
        out_name = video_file.stem + output_ext
        out_file = output_path / out_name
        
        if out_file.exists() and not overwrite:
            if callback:
                callback(f"[{i}/{total}] 跳过 (已存在): {out_name}", int(i / total * 100))
            else:
                print(f"[{i}/{total}] skip 跳过 (已存在): {out_name}")
            success += 1
            continue
        
        cmd = [
            ffmpeg, '-y',
            '-i', str(video_file),
            '-vn',  # 不处理视频
            '-acodec', audio_codec,
            '-ar', str(sample_rate),
            '-ac', str(channels),
        ]
        
        if format in ('mp3', 'm4a'):
            cmd.extend(['-b:a', bit_rate])
        
        if format == 'mp3':
            cmd.extend(['-id3v2_version', '3'])  # 兼容性更好的 ID3 标签
        
        cmd.append(str(out_file))
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=600)  # 10分钟超时
            
            if result.returncode != 0:
                error_msg = result.stderr.strip()[-200:] if result.stderr else '未知错误'
                if callback:
                    callback(f"[{i}/{total}] 失败: {video_file.name}: {error_msg}", int(i / total * 100))
                else:
                    print(f"[{i}/{total}] [FAIL] {video_file.name}: {error_msg}")
                errors += 1
            else:
                file_size = out_file.stat().st_size
                if file_size > 1024 * 1024:
                    size_str = f"{file_size / 1024 / 1024:.1f} MB"
                else:
                    size_str = f"{file_size / 1024:.1f} KB"
                if callback:
                    callback(f"[{i}/{total}] 完成: {video_file.name} -> {out_name} ({size_str})", int(i / total * 100))
                else:
                    print(f"[{i}/{total}] [OK] {video_file.name} -> {out_name} ({size_str})")
                success += 1
                
        except subprocess.TimeoutExpired:
            if callback:
                callback(f"[{i}/{total}] 失败: {video_file.name}: 处理超时 (>10分钟)", int(i / total * 100))
            else:
                print(f"[{i}/{total}] [FAIL] {video_file.name}: 处理超时 (>10分钟)")
            errors += 1
        except Exception as e:
            if callback:
                callback(f"[{i}/{total}] 失败: {video_file.name}: {e}", int(i / total * 100))
            else:
                print(f"[{i}/{total}] [FAIL] {video_file.name}: {e}")
            errors += 1
    
    if callback:
        callback(f"完成: {success} 个成功, {errors} 个失败\n输出目录: {output_path}", 100)


class ExtractAudioGUI:
    """提取视频音频 - 图形界面"""
    
    def __init__(self, master):
        self.master = master
        master.title("提取视频音频 v1.0")
        master.geometry("720x620")
        master.configure(bg="white")
        
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TLabel', background='white', font=('Microsoft YaHei', 10))
        style.configure('TButton', font=('Microsoft YaHei', 10))
        style.configure('TCheckbutton', background='white', font=('Microsoft YaHei', 10))
        style.configure('TFrame', background='white')
        style.configure('TLabelframe', background='white')
        style.configure('TLabelframe.Label', background='white', font=('Microsoft YaHei', 10))
        style.configure('TCombobox', font=('Microsoft YaHei', 10))
        style.configure('Horizontal.TProgressbar', background='#667eea', troughcolor='#e0e0e0')
        
        self.main_color = '#667eea'
        
        # --- 标题 ---
        title_frame = tk.Frame(master, bg='white')
        title_frame.pack(pady=(15, 10))
        tk.Label(title_frame, text="▶ 提取视频音频", font=('Microsoft YaHei', 18, 'bold'),
                fg=self.main_color, bg='white').pack()
        tk.Label(title_frame, text="从视频文件中提取音频 (支持 MP3/M4A/WAV/FLAC/OGG)",
                font=('Microsoft YaHei', 9), fg='#888', bg='white').pack()
        
        # --- 检测 FFmpeg ---
        self.ffmpeg_status = tk.Label(master, text="", font=('Microsoft YaHei', 9), bg='white')
        self.ffmpeg_status.pack()
        if check_ffmpeg():
            self.ffmpeg_status.config(text="✓ FFmpeg 已就绪", fg='green')
        else:
            self.ffmpeg_status.config(text="✗ FFmpeg 未安装！请从 https://ffmpeg.org/download.html 下载", fg='red')
        
        # --- 主内容区域 ---
        main_frame = tk.Frame(master, bg='white')
        main_frame.pack(fill='both', expand=True, padx=20, pady=5)
        
        # 输入目录
        tk.Label(main_frame, text="输入视频目录：", anchor='w', bg='white',
                font=('Microsoft YaHei', 10)).grid(row=0, column=0, sticky='w', pady=8)
        self.input_dir_var = tk.StringVar()
        tk.Entry(main_frame, textvariable=self.input_dir_var, font=('Microsoft YaHei', 10),
                width=50, relief='solid', bd=1).grid(row=0, column=1, padx=5, pady=8)
        tk.Button(main_frame, text="浏览", command=self.browse_input,
                 bg=self.main_color, fg='white', font=('Microsoft YaHei', 10),
                 relief='flat', cursor='hand2', padx=12).grid(row=0, column=2, padx=5, pady=8)
        
        # 输出目录
        tk.Label(main_frame, text="输出音频目录：", anchor='w', bg='white',
                font=('Microsoft YaHei', 10)).grid(row=1, column=0, sticky='w', pady=8)
        self.output_dir_var = tk.StringVar()
        tk.Entry(main_frame, textvariable=self.output_dir_var, font=('Microsoft YaHei', 10),
                width=50, relief='solid', bd=1).grid(row=1, column=1, padx=5, pady=8)
        tk.Button(main_frame, text="浏览", command=self.browse_output,
                 bg=self.main_color, fg='white', font=('Microsoft YaHei', 10),
                 relief='flat', cursor='hand2', padx=12).grid(row=1, column=2, padx=5, pady=8)
        
        # --- 参数框架 ---
        params_frame = tk.LabelFrame(main_frame, text=" 参数设置 ", font=('Microsoft YaHei', 10, 'bold'),
                                    bg='white', fg=self.main_color, relief='groove', bd=1)
        params_frame.grid(row=2, column=0, columnspan=3, sticky='ew', pady=10)
        
        # 输出格式
        tk.Label(params_frame, text="输出格式：", bg='white', font=('Microsoft YaHei', 10)).grid(
            row=0, column=0, sticky='w', padx=10, pady=5)
        self.format_var = tk.StringVar(value='mp3')
        fmt_menu = ttk.Combobox(params_frame, textvariable=self.format_var,
                               values=['mp3', 'm4a', 'wav', 'flac', 'ogg'],
                               state='readonly', width=10, font=('Microsoft YaHei', 10))
        fmt_menu.grid(row=0, column=1, sticky='w', padx=5, pady=5)
        
        # 采样率
        tk.Label(params_frame, text="采样率 (Hz)：", bg='white', font=('Microsoft YaHei', 10)).grid(
            row=0, column=2, sticky='w', padx=10, pady=5)
        self.sr_var = tk.StringVar(value='44100')
        sr_menu = ttk.Combobox(params_frame, textvariable=self.sr_var,
                              values=['8000', '11025', '16000', '22050', '44100', '48000', '96000'],
                              state='readonly', width=10, font=('Microsoft YaHei', 10))
        sr_menu.grid(row=0, column=3, sticky='w', padx=5, pady=5)
        
        # 比特率
        tk.Label(params_frame, text="比特率：", bg='white', font=('Microsoft YaHei', 10)).grid(
            row=1, column=0, sticky='w', padx=10, pady=5)
        self.br_var = tk.StringVar(value='192k')
        br_menu = ttk.Combobox(params_frame, textvariable=self.br_var,
                               values=['128k', '192k', '256k', '320k'],
                               state='readonly', width=10, font=('Microsoft YaHei', 10))
        br_menu.grid(row=1, column=1, sticky='w', padx=5, pady=5)
        
        # 声道
        tk.Label(params_frame, text="声道：", bg='white', font=('Microsoft YaHei', 10)).grid(
            row=1, column=2, sticky='w', padx=10, pady=5)
        self.ch_var = tk.StringVar(value='立体声')
        ch_menu = ttk.Combobox(params_frame, textvariable=self.ch_var,
                               values=['立体声', '单声道'],
                               state='readonly', width=10, font=('Microsoft YaHei', 10))
        ch_menu.grid(row=1, column=3, sticky='w', padx=5, pady=5)
        
        # 覆盖已有文件
        self.overwrite_var = tk.BooleanVar(value=False)
        tk.Checkbutton(params_frame, text="覆盖已有文件", variable=self.overwrite_var,
                      bg='white', font=('Microsoft YaHei', 10)).grid(
            row=2, column=0, columnspan=4, sticky='w', padx=10, pady=5)
        
        # --- 开始按钮 ---
        btn_frame = tk.Frame(main_frame, bg='white')
        btn_frame.grid(row=3, column=0, columnspan=3, pady=10)
        
        self.start_btn = tk.Button(btn_frame, text="▶ 开始提取", command=self.start_extract,
                                  bg=self.main_color, fg='white',
                                  font=('Microsoft YaHei', 12, 'bold'),
                                  relief='flat', cursor='hand2', padx=30, pady=5)
        self.start_btn.pack()
        
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
    
    def browse_input(self):
        dir_path = filedialog.askdirectory(title="选择视频目录")
        if dir_path:
            self.input_dir_var.set(dir_path)
    
    def browse_output(self):
        dir_path = filedialog.askdirectory(title="选择输出音频目录")
        if dir_path:
            self.output_dir_var.set(dir_path)
    
    def log(self, msg):
        self.log_text.config(state='normal')
        self.log_text.insert('end', msg + '\n')
        self.log_text.see('end')
        self.log_text.config(state='disabled')
        self.master.update_idletasks()
    
    def update_progress(self, msg, progress):
        self.log(msg)
        self.progress['value'] = progress
        self.master.update_idletasks()
    
    def start_extract(self):
        input_dir = self.input_dir_var.get().strip()
        output_dir = self.output_dir_var.get().strip()
        
        if not input_dir:
            messagebox.showwarning("提示", "请选择输入视频目录")
            return
        if not output_dir:
            messagebox.showwarning("提示", "请选择输出音频目录")
            return
        if not os.path.isdir(input_dir):
            messagebox.showerror("错误", "输入目录不存在")
            return
        
        if not check_ffmpeg():
            messagebox.showerror("错误", "FFmpeg 未安装或未添加到 PATH\n请从 https://ffmpeg.org/download.html 下载")
            return
        
        fmt = self.format_var.get()
        sr = int(self.sr_var.get())
        br = self.br_var.get()
        ch = 2 if self.ch_var.get() == '立体声' else 1
        overwrite = self.overwrite_var.get()
        
        self.start_btn.config(state='disabled', text='⏳ 处理中...')
        self.progress['value'] = 0
        self.log_text.config(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.config(state='disabled')
        
        def task():
            try:
                extract_audio_batch(
                    input_dir, output_dir,
                    format=fmt, sample_rate=sr, bit_rate=br,
                    channels=ch, overwrite=overwrite,
                    callback=self.update_progress
                )
            finally:
                self.master.after(0, self.on_complete)
        
        t = threading.Thread(target=task, daemon=True)
        t.start()
    
    def on_complete(self):
        self.start_btn.config(state='normal', text='▶ 开始提取')
        self.log("=" * 40)
        self.log("所有任务已完成")


def main():
    parser = argparse.ArgumentParser(
        description='[AUD] 提取视频音频 - 从视频文件中提取音频（MP3/M4A/WAV/FLAC/OGG）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  %(prog)s -i ./视频目录 -o ./音频目录
  %(prog)s -i ./视频目录 -o ./音频目录 -f m4a --bit-rate 320k
  %(prog)s -i ./视频目录 -o ./音频目录 -f wav --sample-rate 48000
  %(prog)s -i ./视频目录 -o ./音频目录 -f mp3 --channels 1 (单声道)
        """
    )
    
    parser.add_argument('-i', '--input', required=True, help='输入视频目录')
    parser.add_argument('-o', '--output', required=True, help='输出音频目录')
    parser.add_argument('-f', '--format', choices=['mp3', 'm4a', 'wav', 'flac', 'ogg'],
                        default='mp3', help='输出音频格式 (默认: mp3)')
    parser.add_argument('--sample-rate', type=int, default=44100,
                        choices=[8000, 11025, 16000, 22050, 44100, 48000, 96000],
                        help='采样率 Hz (默认: 44100)')
    parser.add_argument('--bit-rate', default='192k',
                        choices=['128k', '192k', '256k', '320k'],
                        help='比特率 (默认: 192k，仅mp3/m4a有效)')
    parser.add_argument('--channels', type=int, default=2, choices=[1, 2],
                        help='声道数: 2=立体声, 1=单声道 (默认: 2)')
    parser.add_argument('--overwrite', action='store_true', help='覆盖已有文件')
    
    args = parser.parse_args()
    
    # 检查 FFmpeg
    if not check_ffmpeg():
        print("[FAIL] FFmpeg 未安装或未添加到 PATH")
        print("   请从 https://ffmpeg.org/download.html 下载并安装")
        sys.exit(1)
    
    if not os.path.isdir(args.input):
        print(f"[FAIL] 输入目录不存在: {args.input}")
        sys.exit(1)
    
    extract_audio_batch(
        args.input, args.output,
        format=args.format, sample_rate=args.sample_rate,
        bit_rate=args.bit_rate, channels=args.channels,
        overwrite=args.overwrite
    )


if __name__ == '__main__':
    if len(sys.argv) > 1:
        main()
    else:
        root = tk.Tk()
        app = ExtractAudioGUI(root)
        root.mainloop()
