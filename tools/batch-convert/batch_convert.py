#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量格式互转 v1.1
功能：批量转换图片格式，支持 PNG / JPEG / WebP / AVIF，可调压缩质量。
依赖：Pillow (pip install Pillow)
"""

import os
import sys

# Keep Chinese and emoji CLI output readable in redirected Windows consoles.
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
import argparse
from pathlib import Path
from PIL import Image


# 支持的格式及扩展名
FORMATS = {
    'png': {'ext': '.png', 'mode': 'RGBA'},
    'jpg': {'ext': '.jpg', 'mode': 'RGB'},
    'jpeg': {'ext': '.jpg', 'mode': 'RGB'},
    'webp': {'ext': '.webp', 'mode': 'RGB'},
    'avif': {'ext': '.avif', 'mode': 'RGB'},
    'bmp': {'ext': '.bmp', 'mode': 'RGB'},
    'tiff': {'ext': '.tiff', 'mode': 'RGB'},
}


def convert_images(input_dir, output_dir, target_format, quality=100, 
                   delete_original=False, overwrite=False):
    """
    批量转换图片格式
    
    Args:
        input_dir: 输入目录
        output_dir: 输出目录
        target_format: 目标格式 (png/jpg/webp/avif/bmp/tiff)
        quality: JPEG/WebP输出质量(1-100)
        delete_original: 删除原始文件
        overwrite: 覆盖已有文件
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 目标格式配置
    fmt = target_format.lower()
    if fmt not in FORMATS:
        print(f"[FAIL] 不支持的目标格式: {fmt}")
        print(f"   支持格式: {', '.join(FORMATS.keys())}")
        return
    
    target_ext = FORMATS[fmt]['ext']
    target_mode = FORMATS[fmt]['mode']
    
    # 支持的输入格式（所有常见图片格式）
    img_exts = {'.jpg', '.jpeg', '.png', '.webp', '.avif', '.bmp', '.tiff', '.tif'}
    # 排除与目标格式相同的扩展名（转同格式无意义）
    src_exts = img_exts - {target_ext, '.tif' if target_ext == '.tiff' else ''}
    
    files = []
    for f in input_path.iterdir():
        if f.suffix.lower() in img_exts and f.is_file():
            # 排除已经是目标格式的文件
            if f.suffix.lower() == target_ext:
                continue
            # tif 和 tiff 视为同一格式
            if target_ext == '.tiff' and f.suffix.lower() in ('.tiff', '.tif'):
                continue
            files.append(f)
    
    if not files:
        print(f"[WARN] 在 '{input_dir}' 中未找到需要转换的图片")
        return
    
    print(f"[DIR] 找到 {len(files)} 张待转换图片 → 目标格式: .{fmt}")
    print(f"{'-' * 50}")
    
    success = 0
    skipped = 0
    
    for i, img_file in enumerate(files, 1):
        # 输出文件名（保持原名，更换扩展名）
        out_name = img_file.stem + target_ext
        out_file = output_path / out_name
        
        if out_file.exists() and not overwrite:
            print(f"[{i}/{len(files)}] skip 跳过 (已存在): {out_name}")
            skipped += 1
            continue
        
        try:
            with Image.open(img_file) as source:
                img = source.copy()
            
            # 转换颜色模式
            if target_mode == 'RGB' and img.mode in ('RGBA', 'P', 'LA'):
                # 创建白色背景，合并透明度
                background = Image.new('RGB', img.size, (255, 255, 255))
                img = img.convert('RGBA')
                background.paste(img, mask=img.getchannel('A'))
                img = background
            elif target_mode == 'RGB' and img.mode != 'RGB':
                img = img.convert('RGB')
            elif target_mode == 'RGBA' and img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # 保存
            save_kwargs = {}
            if fmt in ('jpg', 'jpeg', 'webp'):
                save_kwargs['quality'] = quality
            
            img.save(out_file, **save_kwargs)
            
            print(f"[{i}/{len(files)}] [OK] {img_file.name} → {out_name}")
            success += 1
            
            # 删除原始文件
            if delete_original:
                img_file.unlink()
                print(f"       🗑 已删除原始文件: {img_file.name}")
            
        except Exception as e:
            print(f"[{i}/{len(files)}] [FAIL] {img_file.name}: {e}")
    
    print(f"{'-' * 50}")
    print(f"[STAT] 完成: {success} 张成功, {skipped} 张跳过, {len(files) - success - skipped} 张失败")


def main():
    parser = argparse.ArgumentParser(
        description='🔄 批量格式互转 - 批量转换图片格式 (PNG/JPEG/WebP/AVIF/BMP/TIFF)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  %(prog)s -i ./图片 -o ./输出 -f webp
  %(prog)s -i ./图片 -o ./输出 -f jpg --quality 85
  %(prog)s -i ./图片 -o ./输出 -f png --delete
  %(prog)s -i ./图片 -o ./输出 -f avif --overwrite
        """
    )
    
    parser.add_argument('-i', '--input', required=True, help='输入图片目录')
    parser.add_argument('-o', '--output', required=True, help='输出目录')
    parser.add_argument('-f', '--format', required=True, dest='target_format',
                        choices=list(FORMATS.keys()),
                        help=f"目标格式: {', '.join(FORMATS.keys())}")
    parser.add_argument('--quality', type=int, default=90, choices=range(1, 101), 
                        metavar='[1-100]', help='JPEG/WebP 质量 1-100 (默认: 90)')
    parser.add_argument('--delete', action='store_true', help='转换后删除原始文件')
    parser.add_argument('--overwrite', action='store_true', help='覆盖已有文件')
    
    args = parser.parse_args()
    
    if not os.path.isdir(args.input):
        print(f"[FAIL] 输入目录不存在: {args.input}")
        sys.exit(1)
    
    convert_images(
        args.input, args.output, args.target_format,
        quality=args.quality, delete_original=args.delete,
        overwrite=args.overwrite
    )


# ================================================================
# GUI (Tkinter)
# ================================================================

if __name__ == '__main__':
    # 有命令行参数 → CLI 模式
    if len(sys.argv) > 1:
        main()
    else:
        # 无参数 → GUI 模式
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox
        import threading
        import queue

        PRIMARY_COLOR = '#667eea'
        BG_COLOR = '#ffffff'
        FONT_FAMILY = 'Microsoft YaHei'

        class ConvertGUI:
            def __init__(self, root):
                self.root = root
                self.root.title('🔄 批量格式互转')
                self.root.geometry('820x680')
                self.root.configure(bg=BG_COLOR)
                self.root.resizable(True, True)
                
                self.input_dir = tk.StringVar()
                self.output_dir = tk.StringVar()
                self.target_format = tk.StringVar(value='png')
                self.quality = tk.IntVar(value=90)
                self.delete_original = tk.BooleanVar(value=False)
                self.running = False
                self.log_queue = queue.Queue()
                
                self._build_ui()
                self._poll_log()
            
            def _build_ui(self):
                # 标题栏
                title_frame = tk.Frame(self.root, bg=PRIMARY_COLOR, height=60)
                title_frame.pack(fill='x')
                title_frame.pack_propagate(False)
                tk.Label(title_frame, text='🔄 批量格式互转', 
                         fg='white', bg=PRIMARY_COLOR,
                         font=(FONT_FAMILY, 18, 'bold')).pack(pady=12)
                
                main_frame = tk.Frame(self.root, bg=BG_COLOR, padx=20, pady=15)
                main_frame.pack(fill='both', expand=True)
                
                # --- 目录选择 ---
                dir_frame = tk.LabelFrame(main_frame, text=' 目录选择 ', 
                                          bg=BG_COLOR, font=(FONT_FAMILY, 11, 'bold'),
                                          fg=PRIMARY_COLOR, padx=10, pady=10)
                dir_frame.pack(fill='x', pady=(0, 10))
                
                tk.Label(dir_frame, text='输入目录:', bg=BG_COLOR, 
                         font=(FONT_FAMILY, 10)).grid(row=0, column=0, sticky='w', padx=5)
                tk.Entry(dir_frame, textvariable=self.input_dir, width=50,
                         font=(FONT_FAMILY, 9)).grid(row=0, column=1, padx=5, pady=3)
                tk.Button(dir_frame, text='浏览', bg=PRIMARY_COLOR, fg='white',
                          font=(FONT_FAMILY, 9), command=self._browse_input).grid(row=0, column=2, padx=5)
                
                tk.Label(dir_frame, text='输出目录:', bg=BG_COLOR,
                         font=(FONT_FAMILY, 10)).grid(row=1, column=0, sticky='w', padx=5)
                tk.Entry(dir_frame, textvariable=self.output_dir, width=50,
                         font=(FONT_FAMILY, 9)).grid(row=1, column=1, padx=5, pady=3)
                tk.Button(dir_frame, text='浏览', bg=PRIMARY_COLOR, fg='white',
                          font=(FONT_FAMILY, 9), command=self._browse_output).grid(row=1, column=2, padx=5)
                
                # --- 参数设置 ---
                param_frame = tk.LabelFrame(main_frame, text=' 参数设置 ', 
                                            bg=BG_COLOR, font=(FONT_FAMILY, 11, 'bold'),
                                            fg=PRIMARY_COLOR, padx=10, pady=10)
                param_frame.pack(fill='x', pady=(0, 10))
                
                # 目标格式
                tk.Label(param_frame, text='目标格式:', bg=BG_COLOR,
                         font=(FONT_FAMILY, 10)).grid(row=0, column=0, sticky='w', padx=5)
                fmt_menu = ttk.Combobox(param_frame, textvariable=self.target_format,
                                        values=['png', 'jpg', 'webp', 'avif', 'bmp', 'tiff'],
                                        state='readonly', width=12, font=(FONT_FAMILY, 9))
                fmt_menu.grid(row=0, column=1, sticky='w', padx=5, pady=3)
                
                # 质量
                tk.Label(param_frame, text='质量:', bg=BG_COLOR,
                         font=(FONT_FAMILY, 10)).grid(row=1, column=0, sticky='w', padx=5, pady=(5,0))
                
                quality_frame = tk.Frame(param_frame, bg=BG_COLOR)
                quality_frame.grid(row=1, column=1, columnspan=2, sticky='w', padx=5, pady=(5,0))
                
                quality_slider = tk.Scale(quality_frame, from_=1, to=100, orient='horizontal',
                                          variable=self.quality, bg=BG_COLOR, fg=PRIMARY_COLOR,
                                          highlightbackground=BG_COLOR, length=250,
                                          font=(FONT_FAMILY, 8))
                quality_slider.pack(side='left')
                
                self.quality_label = tk.Label(quality_frame, textvariable=self.quality,
                                              bg=BG_COLOR, fg=PRIMARY_COLOR, width=4,
                                              font=(FONT_FAMILY, 10, 'bold'))
                self.quality_label.pack(side='left', padx=5)
                
                # 删除原始文件
                tk.Checkbutton(param_frame, text='转换后删除原始文件', 
                               variable=self.delete_original, bg=BG_COLOR,
                               font=(FONT_FAMILY, 10)).grid(row=2, column=0, columnspan=3, sticky='w', padx=5, pady=5)
                
                # --- 操作按钮 ---
                btn_frame = tk.Frame(main_frame, bg=BG_COLOR)
                btn_frame.pack(fill='x', pady=(0, 8))
                
                self.start_btn = tk.Button(btn_frame, text='▶ 开始转换', 
                                           bg=PRIMARY_COLOR, fg='white',
                                           font=(FONT_FAMILY, 12, 'bold'), padx=30, pady=6,
                                           command=self._start_convert)
                self.start_btn.pack(side='left', padx=5)
                
                # 进度条
                self.progress = ttk.Progressbar(main_frame, orient='horizontal',
                                                length=760, mode='determinate')
                self.progress.pack(fill='x', pady=(0, 8))
                
                # 日志输出
                log_frame = tk.LabelFrame(main_frame, text=' 运行日志 ', 
                                          bg=BG_COLOR, font=(FONT_FAMILY, 11, 'bold'),
                                          fg=PRIMARY_COLOR, padx=5, pady=5)
                log_frame.pack(fill='both', expand=True)
                
                self.log_text = tk.Text(log_frame, height=14, wrap='word',
                                        bg='#f8f9fa', fg='#333333',
                                        font=('Consolas', 9), relief='flat', borderwidth=1)
                self.log_text.pack(fill='both', expand=True, side='left')
                
                scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview)
                scrollbar.pack(side='right', fill='y')
                self.log_text.config(yscrollcommand=scrollbar.set)
                
                # 绑定                quality_slider.config(command=lambda v: self.quality_label.config(text=str(int(v))))
            
            def _browse_input(self):
                d = filedialog.askdirectory(title='选择输入图片目录')
                if d:
                    self.input_dir.set(d)
            
            def _browse_output(self):
                d = filedialog.askdirectory(title='选择输出目录')
                if d:
                    self.output_dir.set(d)
            
            def _log(self, msg):
                self.log_queue.put(msg)
            
            def _poll_log(self):
                try:
                    while True:
                        msg = self.log_queue.get_nowait()
                        self.log_text.insert('end', msg + '\n')
                        self.log_text.see('end')
                except queue.Empty:
                    pass
                self.root.after(100, self._poll_log)
            
            def _start_convert(self):
                if self.running:
                    return
                
                in_dir = self.input_dir.get().strip()
                out_dir = self.output_dir.get().strip()
                
                if not in_dir:
                    messagebox.showwarning('提示', '请选择输入目录')
                    return
                if not out_dir:
                    messagebox.showwarning('提示', '请选择输出目录')
                    return
                if not os.path.isdir(in_dir):
                    messagebox.showerror('错误', '输入目录不存在')
                    return
                
                self.running = True
                self.start_btn.config(state='disabled', text='⏳ 处理中...')
                self.progress['value'] = 0
                self.log_text.delete('1.0', 'end')
                
                t = threading.Thread(target=self._run_convert, daemon=True)
                t.start()
            
            def _run_convert(self):
                try:
                    in_dir = self.input_dir.get().strip()
                    out_dir = self.output_dir.get().strip()
                    fmt = self.target_format.get()
                    q = int(self.quality.get())
                    delete = self.delete_original.get()
                    
                    # 重定向 print 到日志
                    import io
                    old_stdout = sys.stdout
                    sys.stdout = io.StringIO()
                    
                    convert_images(in_dir, out_dir, fmt, quality=q, delete_original=delete)
                    
                    output = sys.stdout.getvalue()
                    sys.stdout = old_stdout
                    
                    lines = output.strip().split('\n')
                    total = len(lines)
                    for idx, line in enumerate(lines):
                        self._log(line)
                        pct = int((idx + 1) / total * 100) if total > 0 else 100
                        self.root.after(0, lambda v=pct: self.progress.config(value=v))
                    
                    self.root.after(0, lambda: self.progress.config(value=100))
                    self._log('[DONE] 转换完成！')
                    
                except Exception as e:
                    self._log(f'[ERROR] {e}')
                finally:
                    self.running = False
                    self.root.after(0, lambda: self.start_btn.config(state='normal', text='▶ 开始转换'))
            
        root = tk.Tk()
        app = ConvertGUI(root)
        root.mainloop()
