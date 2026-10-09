#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量极速缩图 v3.0 - 带图形界面
功能：将图片缩放到指定正方形尺寸，保留EXIF信息。
支持：选择单个图片或整个目录，批量处理。
"""

import os
import sys

# Keep Chinese and emoji CLI output readable in redirected Windows consoles.
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
import argparse
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from pathlib import Path
from PIL import Image


def resize_images(input_paths, output_dir, target_size, overwrite=False,
                  progress_callback=None, log_callback=None):
    """
    批量缩放图片到正方形尺寸
    
    Args:
        input_paths: 文件路径列表 或 目录路径
        output_dir: 输出目录
        target_size: 目标尺寸（宽=高）
        overwrite: 覆盖已有文件
    """
    if target_size <= 0:
        raise ValueError('目标尺寸必须大于零')
    # 收集文件
    files = []
    for p in input_paths:
        p = Path(p)
        if p.is_dir():
            img_exts = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif'}
            files.extend([f for f in p.iterdir() if f.suffix.lower() in img_exts and f.is_file()])
        elif p.is_file():
            files.append(p)
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    if not files:
        msg = "未找到支持的图片文件"
        if log_callback: log_callback(f"[WARN] {msg}")
        else: print(f"[WARN] {msg}")
        return
    
    if log_callback: log_callback(f"找到 {len(files)} 张图片")
    
    success, skipped, errors = 0, 0, 0
    
    for i, img_file in enumerate(files, 1):
        out_file = output_path / img_file.name
        
        if out_file.exists() and not overwrite:
            if log_callback: log_callback(f"[{i}/{len(files)}] 跳过: {img_file.name} (已存在)")
            skipped += 1
            if progress_callback: progress_callback(i, len(files))
            continue
        
        try:
            with Image.open(img_file) as source:
                img = source.copy()
            exif = img.info.get('exif', b'')
            orig_w, orig_h = img.size
            
            # 正方形缩放：取长边缩放到 target_size，短边居中裁剪
            if orig_w >= orig_h:
                # 横向图：以高度为基准缩放，裁剪宽度
                ratio = target_size / orig_h
                new_w = int(orig_w * ratio)
                new_h = target_size
                resized = img.resize((new_w, new_h), Image.LANCZOS)
                left = (new_w - target_size) // 2
                resized = resized.crop((left, 0, left + target_size, target_size))
            else:
                # 纵向图：以宽度为基准缩放，裁剪高度
                ratio = target_size / orig_w
                new_w = target_size
                new_h = int(orig_h * ratio)
                resized = img.resize((new_w, new_h), Image.LANCZOS)
                top = (new_h - target_size) // 2
                resized = resized.crop((0, top, target_size, top + target_size))
            
            # 保存并保留EXIF
            save_kwargs = {'quality': 100}
            if exif:
                save_kwargs['exif'] = exif
            
            resized.save(out_file, **save_kwargs)
            
            if log_callback: log_callback(f"[OK] {img_file.name}  ({orig_w}x{orig_h} -> {target_size}x{target_size})")
            success += 1
            
        except Exception as e:
            if log_callback: log_callback(f"[FAIL] {img_file.name}: {e}")
            errors += 1
        
        if progress_callback: progress_callback(i, len(files))
    
    if log_callback: log_callback(f"完成: {success} 成功, {skipped} 跳过, {errors} 失败")


# =============================================
# GUI 界面
# =============================================

class ResizeGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("批量极速缩图")
        self.root.geometry("580x520")
        self.root.minsize(540, 480)
        self.root.configure(bg='#f0f2f5')
        
        self.input_mode = tk.StringVar(value="dir")  # dir or files
        self.input_dir = tk.StringVar()
        self.input_files = []
        self.output_dir = tk.StringVar(value=os.path.join(os.getcwd(), 'output'))
        self.target_size = tk.IntVar(value=512)
        self.is_running = False
        
        self._build_ui()
    
    def _build_ui(self):
        # Header
        header = tk.Frame(self.root, bg='#667eea', height=48)
        header.pack(fill='x')
        header.pack_propagate(False)
        tk.Label(header, text="批量极速缩图", fg='white', bg='#667eea',
                 font=('Microsoft YaHei', 14, 'bold')).pack(expand=True)
        
        main = ttk.Frame(self.root, padding=15)
        main.pack(fill='both', expand=True)
        main.columnconfigure(1, weight=1)
        
        # Input mode toggle
        row = 0
        mode_frame = ttk.Frame(main)
        mode_frame.grid(row=row, column=0, columnspan=3, sticky='ew', pady=(0,8))
        tk.Radiobutton(mode_frame, text="处理整个目录", variable=self.input_mode, value="dir",
                       command=self._toggle_mode, font=('Microsoft YaHei', 9)).pack(side='left', padx=5)
        tk.Radiobutton(mode_frame, text="选择单个图片", variable=self.input_mode, value="files",
                       command=self._toggle_mode, font=('Microsoft YaHei', 9)).pack(side='left', padx=5)
        
        # Input
        row = 1
        tk.Label(main, text="输入:", font=('Microsoft YaHei', 10)).grid(row=row, column=0, sticky='w', padx=(0,8), pady=4)
        self.input_entry = tk.Entry(main, font=('Microsoft YaHei', 9), relief='solid', bd=1)
        self.input_entry.grid(row=row, column=1, sticky='ew', padx=(0,5), pady=4)
        self.input_btn = tk.Button(main, text="浏览目录", command=self._browse_input,
                                   bg='#e0e0e0', relief='flat', cursor='hand2')
        self.input_btn.grid(row=row, column=2, pady=4)
        self.file_info = tk.Label(main, text="", font=('Microsoft YaHei', 8), fg='#888')
        self.file_info.grid(row=row+1, column=1, sticky='w')
        
        # Output
        row = 3
        tk.Label(main, text="输出目录:", font=('Microsoft YaHei', 10)).grid(row=row, column=0, sticky='w', padx=(0,8), pady=4)
        tk.Entry(main, textvariable=self.output_dir, font=('Microsoft YaHei', 9), relief='solid', bd=1).grid(row=row, column=1, sticky='ew', padx=(0,5), pady=4)
        tk.Button(main, text="浏览", command=lambda: self._browse('output'),
                  bg='#e0e0e0', relief='flat', cursor='hand2').grid(row=row, column=2, pady=4)
        
        # Target size
        row = 4
        ttk.Separator(main, orient='horizontal').grid(row=row, column=0, columnspan=3, sticky='ew', pady=10)
        
        row = 5
        size_frame = ttk.LabelFrame(main, text="缩放设置", padding=12)
        size_frame.grid(row=row, column=0, columnspan=3, sticky='ew', pady=5)
        
        tk.Label(size_frame, text="目标尺寸:", font=('Microsoft YaHei', 10)).pack(side='left')
        tk.Spinbox(size_frame, from_=16, to=4096, textvariable=self.target_size, width=8,
                   font=('Microsoft YaHei', 10), relief='solid', bd=1).pack(side='left', padx=8)
        tk.Label(size_frame, text="x", font=('Microsoft YaHei', 12)).pack(side='left')
        tk.Label(size_frame, text="像素 (正方形)", font=('Microsoft YaHei', 10)).pack(side='left', padx=5)
        
        # Run
        row = 6
        btn_frame = ttk.Frame(main)
        btn_frame.grid(row=row, column=0, columnspan=3, pady=12)
        self.run_btn = tk.Button(btn_frame, text="开始执行", command=self._run,
                                  bg='#667eea', fg='white', font=('Microsoft YaHei', 11, 'bold'),
                                  padx=35, pady=6, cursor='hand2', relief='flat')
        self.run_btn.pack(side='left', padx=5)
        tk.Button(btn_frame, text="退出", command=self.root.quit,
                  bg='#ff4757', fg='white', font=('Microsoft YaHei', 10),
                  padx=20, pady=4, cursor='hand2', relief='flat').pack(side='left', padx=5)
        
        # Progress
        row = 7
        self.progress = ttk.Progressbar(main, mode='determinate')
        self.progress.grid(row=row, column=0, columnspan=3, sticky='ew', pady=3)
        
        # Status
        row = 8
        self.status_var = tk.StringVar(value="就绪")
        status_frame = tk.Frame(main, bg='white', relief='sunken', bd=1)
        status_frame.grid(row=row, column=0, columnspan=3, sticky='ew', pady=2)
        tk.Label(status_frame, textvariable=self.status_var, anchor='w', padx=8, pady=3,
                 bg='white', font=('Microsoft YaHei', 9)).pack(fill='x')
        
        # Log
        row = 9
        log_frame = ttk.LabelFrame(main, text="运行日志", padding=5)
        log_frame.grid(row=row, column=0, columnspan=3, sticky='nsew', pady=(5,0))
        main.rowconfigure(row, weight=1)
        
        self.log_text = tk.Text(log_frame, height=7, font=('Consolas', 9), wrap='word',
                                 bg='#1e1e1e', fg='#d4d4d4', relief='flat', bd=2)
        self.log_text.pack(side='left', fill='both', expand=True)
        scrollbar = ttk.Scrollbar(log_frame, orient='vertical', command=self.log_text.yview)
        scrollbar.pack(side='right', fill='y')
        self.log_text.configure(yscrollcommand=scrollbar.set)
    
    def _toggle_mode(self):
        if self.input_mode.get() == 'dir':
            self.input_btn.config(text='浏览目录', command=self._browse_input)
            self.input_entry.config(state='normal')
        else:
            self.input_btn.config(text='选择文件', command=self._browse_files)
            self.input_entry.config(state='normal')
    
    def _browse_input(self):
        if self.input_mode.get() == 'dir':
            path = filedialog.askdirectory()
            if path:
                self.input_dir.set(path)
                self.input_entry.delete(0, 'end')
                self.input_entry.insert(0, path)
                self.file_info.config(text="")
        else:
            self._browse_files()
    
    def _browse_files(self):
        paths = filedialog.askopenfilenames(
            title="选择图片文件",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.webp *.bmp *.tiff *.tif")]
        )
        if paths:
            self.input_files = list(paths)
            self.input_entry.delete(0, 'end')
            if len(paths) == 1:
                self.input_entry.insert(0, paths[0])
                self.file_info.config(text=f"1 个文件")
            else:
                self.input_entry.insert(0, f"已选 {len(paths)} 个文件")
                self.file_info.config(text=f"{len(paths)} 个文件")
    
    def _browse(self, target):
        path = filedialog.askdirectory()
        if path:
            if target == 'output':
                self.output_dir.set(path)
    
    def log(self, msg):
        import datetime
        ts = datetime.datetime.now().strftime('%H:%M:%S')
        self.log_text.insert('end', f'[{ts}] {msg}\n')
        self.log_text.see('end')
        self.root.update()
    
    def _run(self):
        if self.is_running:
            return
        
        # Validate
        inputs = []
        if self.input_mode.get() == 'dir':
            path = self.input_entry.get().strip()
            if not path or not os.path.isdir(path):
                messagebox.showerror("错误", "请选择有效的输入目录")
                return
            inputs = [path]
        else:
            if not self.input_files:
                messagebox.showerror("错误", "请选择要处理的图片文件")
                return
            inputs = self.input_files
        
        out = self.output_dir.get().strip()
        if not out:
            messagebox.showerror("错误", "请选择输出目录")
            return
        
        size = self.target_size.get()
        if size < 1:
            messagebox.showerror("错误", "尺寸必须大于0")
            return
        
        self.is_running = True
        self.run_btn.config(state='disabled', text='执行中...')
        self.log_text.delete('1.0', 'end')
        self.progress['value'] = 0
        self.status_var.set("正在处理...")
        
        def task():
            try:
                def on_progress(current, total):
                    val = int(current / total * 100)
                    self.root.after(0, lambda: self.progress.configure(value=val))
                    self.root.after(0, lambda: self.status_var.set(f"处理中: {current}/{total}"))
                
                resize_images(inputs, out, target_size=size,
                             progress_callback=on_progress, log_callback=self.log)
            except Exception as e:
                self.log(f"[ERROR] {e}")
                import traceback
                self.log(traceback.format_exc())
            finally:
                self.is_running = False
                self.root.after(0, lambda: self.run_btn.config(state='normal', text='开始执行'))
                self.root.after(0, lambda: self.status_var.set("执行完毕"))
        
        threading.Thread(target=task, daemon=True).start()
    
    def start(self):
        self.root.mainloop()


def main():
    parser = argparse.ArgumentParser(description='批量极速缩图 - 将图片缩放到正方形尺寸')
    parser.add_argument('-i', '--input', nargs='+', help='输入图片路径或目录')
    parser.add_argument('-o', '--output', default='./output', help='输出目录')
    parser.add_argument('-s', '--size', type=int, default=512, help='目标尺寸(正方形像素)')
    
    args = parser.parse_args()
    
    if not args.input or len(sys.argv) == 1:
        gui = ResizeGUI()
        gui.start()
        return
    
    resize_images(args.input, args.output, target_size=args.size)


if __name__ == '__main__':
    main()
