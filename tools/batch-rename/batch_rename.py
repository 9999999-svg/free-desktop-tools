#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量重命名 v1.0
功能：按"日期+序号"或自定义规则批量重命名图片/视频文件。
依赖：无（仅使用 Python 标准库）
"""

import os
import sys

# Keep Chinese and emoji CLI output readable in redirected Windows consoles.
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
import re
import argparse
import datetime
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

# 模式名称映射：中文显示 → 内部值
MODE_MAP = {
    "日期+序号": "datetime",
    "纯序号": "serial",
    "自定义": "custom",
    "查找替换": "replace",
    "添加前后缀": "add",
}
# 反向映射：内部值 → 中文显示
MODE_REVERSE_MAP = {v: k for k, v in MODE_MAP.items()}


def get_file_date(file_path):
    """获取文件日期（优先使用修改时间）"""
    stat = file_path.stat()
    # 优先使用修改时间
    mtime = stat.st_mtime
    return datetime.datetime.fromtimestamp(mtime)


def safe_filename(filename, max_length=200):
    """清理文件名中的非法字符"""
    # 替换Windows非法字符
    illegal_chars = r'[<>:"/\\|?*\x00-\x1f]'
    safe = re.sub(illegal_chars, '_', filename)
    # 去除首尾空格和点
    safe = safe.strip('. ')
    # 限制长度
    if len(safe) > max_length:
        name, ext = os.path.splitext(safe)
        safe = name[:max_length - len(ext)] + ext
    return safe if safe else 'unnamed'


def rename_files(input_dir, mode='datetime', pattern=None, prefix='',
                 suffix='', start_num=1, digits=4, preview=False,
                 extensions=None, recursive=False, callback=None):
    """
    批量重命名文件
    
    Args:
        input_dir: 输入目录
        mode: 重命名模式
               datetime - 日期+序号 (20250101_0001.jpg)
               serial   - 纯序号 (0001.jpg)
               custom   - 自定义模式 (用 {n}/{d}/{y}/{m}/{day}/{old} 占位)
               replace  - 查找替换
               add      - 添加前缀/后缀
        pattern: 替换/自定义模式
        prefix: 前缀
        suffix: 后缀
        start_num: 起始序号
        digits: 序号位数
        preview: 仅预览不执行
        extensions: 文件扩展名过滤
        recursive: 递归子目录
        callback: 进度回调 callback(msg, progress)
    """
    input_path = Path(input_dir)
    
    if not input_path.is_dir():
        msg = f"目录不存在: {input_dir}"
        if callback:
            callback(msg, 0)
        else:
            print(f"[FAIL] {msg}")
        return
    
    # 文件扩展名过滤
    if extensions:
        ext_set = {'.' + e.lower().lstrip('.') for e in extensions}
    else:
        # 默认：常见图片和视频格式
        ext_set = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif',
                   '.avif', '.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm',
                   '.m4v', '.mpg', '.mpeg', '.heic', '.heif', '.raw', '.cr2', '.nef'}
    
    # 收集文件
    if recursive:
        files = sorted([f for f in input_path.rglob('*')
                       if f.is_file() and f.suffix.lower() in ext_set])
    else:
        files = sorted([f for f in input_path.iterdir()
                       if f.is_file() and f.suffix.lower() in ext_set])
    
    if not files:
        msg = f"在 '{input_dir}' 中未找到匹配的文件"
        if extensions:
            msg += f"\n   过滤扩展名: {', '.join(extensions)}"
        else:
            msg += "\n   支持格式: 常见图片和视频格式"
        if callback:
            callback(msg, 0)
        else:
            print(f"[WARN] {msg}")
        return
    
    total = len(files)
    
    if callback:
        callback(f"模式: {mode} | 找到 {total} 个文件", 0)
        if preview:
            callback("[FIND] 预览模式（不会实际执行）", 0)
    
    # 检查重名冲突
    rename_map = []
    name_counts = {}
    
    for i, file_path in enumerate(files):
        ext = file_path.suffix.lower()
        file_date = get_file_date(file_path)
        
        if mode == 'datetime':
            # 日期+序号: 20250101_0001.jpg
            date_str = file_date.strftime('%Y%m%d')
            new_name = f"{prefix}{date_str}_{suffix}{(start_num + i):0{digits}d}{ext}"
            
        elif mode == 'serial':
            # 纯序号: 0001.jpg
            new_name = f"{prefix}{(start_num + i):0{digits}d}{suffix}{ext}"
            
        elif mode == 'custom' and pattern:
            # 自定义模式
            new_name = pattern
            new_name = new_name.replace('{n}', str(start_num + i))
            new_name = re.sub(r'\{n:0([1-9][0-9]?)d\}',
                              lambda match: f'{start_num + i:0{int(match.group(1))}d}', new_name)
            new_name = new_name.replace('{d}', file_date.strftime('%Y%m%d'))
            new_name = new_name.replace('{y}', file_date.strftime('%Y'))
            new_name = new_name.replace('{m}', file_date.strftime('%m'))
            new_name = new_name.replace('{day}', file_date.strftime('%d'))
            new_name = new_name.replace('{h}', file_date.strftime('%H'))
            new_name = new_name.replace('{min}', file_date.strftime('%M'))
            new_name = new_name.replace('{s}', file_date.strftime('%S'))
            new_name = new_name.replace('{old}', file_path.stem)
            new_name = prefix + new_name + suffix + ext
            
        elif mode == 'replace' and pattern:
            # 查找替换
            old, new = pattern.split('|', 1) if '|' in pattern else (pattern, '')
            new_name = file_path.stem.replace(old, new)
            new_name = prefix + safe_filename(new_name) + suffix + ext
            
        elif mode == 'add':
            # 添加前缀/后缀
            stem = file_path.stem
            new_name = prefix + stem + suffix + ext
            
        else:
            if callback:
                callback(f"跳过 {file_path.name}: 无效的模式或参数", int(i / total * 100))
            continue
        
        new_name = safe_filename(new_name)
        new_path = file_path.parent / new_name
        
        # 计入重名统计
        name_counts[new_name] = name_counts.get(new_name, 0) + 1
        
        rename_map.append((file_path, new_path, file_date))
    
    # 检查重名冲突
    conflicts = [(name, count) for name, count in name_counts.items() if count > 1]
    if conflicts:
        conflict_msg = "发现重名冲突:"
        for name, count in conflicts:
            conflict_msg += f"\n   '{name}' 出现 {count} 次"
        conflict_msg += "\n建议调整参数或包含 {n} 占位符"
        if callback:
            callback(conflict_msg, 50)
    
    # 执行重命名
    renamed = 0
    skipped = 0
    errors = 0
    
    for i, (old_path, new_path, file_date) in enumerate(rename_map, 1):
        if old_path == new_path:
            if callback:
                callback(f"[{i}/{total}] 跳过 (相同): {old_path.name}", int(i / total * 100))
            skipped += 1
            continue
        
        if new_path.exists() and not preview:
            if callback:
                callback(f"[{i}/{total}] 跳过 (目标已存在): {new_path.name}", int(i / total * 100))
            skipped += 1
            continue
        
        if preview:
            date_str = file_date.strftime('%Y-%m-%d %H:%M')
            if callback:
                callback(f"[{i}/{total}] [预览] {old_path.name} -> {new_path.name} ({date_str})",
                        int(i / total * 100))
            renamed += 1
        else:
            try:
                old_path.rename(new_path)
                if callback:
                    callback(f"[{i}/{total}] [OK] {old_path.name} -> {new_path.name}",
                            int(i / total * 100))
                renamed += 1
            except Exception as e:
                if callback:
                    callback(f"[{i}/{total}] [FAIL] {old_path.name}: {e}",
                            int(i / total * 100))
                errors += 1
    
    if callback:
        if preview:
            callback(f"预览完成: {renamed} 个将重命名, {skipped} 个跳过", 100)
        else:
            callback(f"完成: {renamed} 个重命名, {skipped} 个跳过, {errors} 个失败", 100)


class BatchRenameGUI:
    """批量重命名 - 图形界面"""
    
    def __init__(self, master):
        self.master = master
        master.title("批量重命名 v1.0")
        master.geometry("800x700")
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
        style.configure('TSpinbox', font=('Microsoft YaHei', 10))
        style.configure('Horizontal.TProgressbar', background='#667eea', troughcolor='#e0e0e0')
        
        self.main_color = '#667eea'
        
        # --- 标题 ---
        title_frame = tk.Frame(master, bg='white')
        title_frame.pack(pady=(15, 10))
        tk.Label(title_frame, text="📄 批量重命名", font=('Microsoft YaHei', 18, 'bold'),
                fg=self.main_color, bg='white').pack()
        tk.Label(title_frame, text="按日期/序号/自定义规则批量重命名图片和视频文件",
                font=('Microsoft YaHei', 9), fg='#888', bg='white').pack()
        
        # --- 主内容区域 ---
        main_frame = tk.Frame(master, bg='white')
        main_frame.pack(fill='both', expand=True, padx=20, pady=5)
        
        # 输入目录
        tk.Label(main_frame, text="目标目录：", anchor='w', bg='white',
                font=('Microsoft YaHei', 10)).grid(row=0, column=0, sticky='w', pady=8)
        self.input_dir_var = tk.StringVar()
        tk.Entry(main_frame, textvariable=self.input_dir_var, font=('Microsoft YaHei', 10),
                width=55, relief='solid', bd=1).grid(row=0, column=1, padx=5, pady=8)
        tk.Button(main_frame, text="浏览", command=self.browse_input,
                 bg=self.main_color, fg='white', font=('Microsoft YaHei', 10),
                 relief='flat', cursor='hand2', padx=12).grid(row=0, column=2, padx=5, pady=8)
        
        # --- 模式切换（中文显示） ---
        tk.Label(main_frame, text="重命名模式：", anchor='w', bg='white',
                font=('Microsoft YaHei', 10)).grid(row=1, column=0, sticky='w', pady=8)
        self.mode_var = tk.StringVar(value='日期+序号')
        self.mode_menu = ttk.Combobox(main_frame, textvariable=self.mode_var,
                                      values=list(MODE_MAP.keys()),
                                      state='readonly', width=15, font=('Microsoft YaHei', 10))
        self.mode_menu.grid(row=1, column=1, sticky='w', padx=5, pady=8)
        self.mode_menu.bind('<<ComboboxSelected>>', self.on_mode_change)
        
        # --- 参数框架 ---
        self.params_frame = tk.LabelFrame(main_frame, text=" 参数设置 ", font=('Microsoft YaHei', 10, 'bold'),
                                         bg='white', fg=self.main_color, relief='groove', bd=1)
        self.params_frame.grid(row=2, column=0, columnspan=3, sticky='ew', pady=10)
        
        # 行0: 前缀
        tk.Label(self.params_frame, text="前缀：", bg='white', font=('Microsoft YaHei', 10)).grid(
            row=0, column=0, sticky='w', padx=10, pady=5)
        self.prefix_var = tk.StringVar()
        tk.Entry(self.params_frame, textvariable=self.prefix_var, font=('Microsoft YaHei', 10),
                width=18, relief='solid', bd=1).grid(row=0, column=1, sticky='w', padx=5, pady=5)
        
        # 行0: 后缀
        tk.Label(self.params_frame, text="后缀：", bg='white', font=('Microsoft YaHei', 10)).grid(
            row=0, column=2, sticky='w', padx=10, pady=5)
        self.suffix_var = tk.StringVar()
        tk.Entry(self.params_frame, textvariable=self.suffix_var, font=('Microsoft YaHei', 10),
                width=18, relief='solid', bd=1).grid(row=0, column=3, sticky='w', padx=5, pady=5)
        
        # 行1: 起始序号
        tk.Label(self.params_frame, text="起始序号：", bg='white', font=('Microsoft YaHei', 10)).grid(
            row=1, column=0, sticky='w', padx=10, pady=5)
        self.start_num_var = tk.IntVar(value=1)
        tk.Spinbox(self.params_frame, from_=0, to=99999, textvariable=self.start_num_var,
                  font=('Microsoft YaHei', 10), width=8, relief='solid', bd=1).grid(
            row=1, column=1, sticky='w', padx=5, pady=5)
        
        # 行1: 序号位数
        tk.Label(self.params_frame, text="序号位数：", bg='white', font=('Microsoft YaHei', 10)).grid(
            row=1, column=2, sticky='w', padx=10, pady=5)
        self.digits_var = tk.IntVar(value=4)
        tk.Spinbox(self.params_frame, from_=2, to=6, textvariable=self.digits_var,
                  font=('Microsoft YaHei', 10), width=8, relief='solid', bd=1).grid(
            row=1, column=3, sticky='w', padx=5, pady=5)
        
        # 行2: 自定义模式 (仅自定义显示)
        self.custom_label = tk.Label(self.params_frame, text="自定义模式：", bg='white',
                                     font=('Microsoft YaHei', 10))
        self.custom_label.grid(row=2, column=0, sticky='w', padx=10, pady=5)
        self.custom_var = tk.StringVar()
        self.custom_entry = tk.Entry(self.params_frame, textvariable=self.custom_var,
                                     font=('Microsoft YaHei', 10), width=40,
                                     relief='solid', bd=1)
        self.custom_entry.grid(row=2, column=1, columnspan=3, sticky='w', padx=5, pady=5)
        
        # 行3: 替换规则 (仅查找替换显示)
        self.replace_label = tk.Label(self.params_frame, text="替换规则 old|new：", bg='white',
                                      font=('Microsoft YaHei', 10))
        self.replace_label.grid(row=3, column=0, sticky='w', padx=10, pady=5)
        self.replace_var = tk.StringVar()
        self.replace_entry = tk.Entry(self.params_frame, textvariable=self.replace_var,
                                      font=('Microsoft YaHei', 10), width=40,
                                      relief='solid', bd=1)
        self.replace_entry.grid(row=3, column=1, columnspan=3, sticky='w', padx=5, pady=5)
        
        # 行4: 文件扩展名
        tk.Label(self.params_frame, text="扩展名过滤：", bg='white', font=('Microsoft YaHei', 10)).grid(
            row=4, column=0, sticky='w', padx=10, pady=5)
        self.ext_var = tk.StringVar()
        tk.Entry(self.params_frame, textvariable=self.ext_var, font=('Microsoft YaHei', 10),
                width=40, relief='solid', bd=1).grid(row=4, column=1, columnspan=3, sticky='w', padx=5, pady=5)
        tk.Label(self.params_frame, text="逗号分隔，留空=图片/视频", bg='white',
                font=('Microsoft YaHei', 8), fg='#888').grid(row=4, column=3, sticky='w', padx=5, pady=5)
        
        # 行5: 递归子目录
        self.recursive_var = tk.BooleanVar(value=False)
        tk.Checkbutton(self.params_frame, text="递归子目录", variable=self.recursive_var,
                      bg='white', font=('Microsoft YaHei', 10)).grid(
            row=5, column=0, columnspan=4, sticky='w', padx=10, pady=5)
        
        # --- 提示文字 (自定义模式提示占位符) ---
        self.custom_hint = tk.Label(self.params_frame, text="",
                                    bg='#fef9e7', fg='#856404',
                                    font=('Microsoft YaHei', 8), wraplength=500,
                                    anchor='w', justify='left')
        self.custom_hint.grid(row=6, column=0, columnspan=4, sticky='ew', padx=10, pady=2)
        
        # 初始模式状态
        self.on_mode_change()
        
        # --- 操作按钮 ---
        btn_frame = tk.Frame(main_frame, bg='white')
        btn_frame.grid(row=3, column=0, columnspan=3, pady=12)
        
        self.preview_btn = tk.Button(btn_frame, text="🔍 预览重命名", command=self.preview_rename,
                                     bg='#ff9800', fg='white',
                                     font=('Microsoft YaHei', 11, 'bold'),
                                     relief='flat', cursor='hand2', padx=20, pady=4)
        self.preview_btn.pack(side='left', padx=5)
        
        self.execute_btn = tk.Button(btn_frame, text="▶ 执行重命名", command=self.execute_rename,
                                     bg=self.main_color, fg='white',
                                     font=('Microsoft YaHei', 11, 'bold'),
                                     relief='flat', cursor='hand2', padx=20, pady=4)
        self.execute_btn.pack(side='left', padx=5)
        
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
        
        self.log_text = tk.Text(log_frame, height=14, width=85, font=('Consolas', 9),
                               bg='#f8f8f8', fg='#333', relief='solid', bd=1,
                               wrap='word', state='disabled')
        scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.config(yscrollcommand=scrollbar.set)
        self.log_text.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        scrollbar.pack(side='right', fill='y', pady=5)
    
    def browse_input(self):
        dir_path = filedialog.askdirectory(title="选择要重命名的目录")
        if dir_path:
            self.input_dir_var.set(dir_path)
    
    def on_mode_change(self, event=None):
        """切换模式时更新可见控件（基于中文显示值）"""
        mode_cn = self.mode_var.get()
        mode_en = MODE_MAP.get(mode_cn, 'datetime')
        
        # 隐藏所有模式专属控件
        self.custom_label.grid_remove()
        self.custom_entry.grid_remove()
        self.replace_label.grid_remove()
        self.replace_entry.grid_remove()
        self.custom_hint.config(text="")
        
        if mode_en == 'custom':
            self.custom_label.grid()
            self.custom_entry.grid()
            self.custom_hint.config(
                text="占位符: {n}=序号  {d}=YYYYMMDD  {y}/{m}/{day}=年/月/日  {h}/{min}/{s}=时/分/秒  {old}=原文件名  {n:04d}=4位序号"
            )
        elif mode_en == 'replace':
            self.replace_label.grid()
            self.replace_entry.grid()
            self.custom_hint.config(
                text="格式: 旧文字|新文字  (例如: DSC|IMG 将 DSC_001 改为 IMG_001)"
            )
    
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
    
    def get_params(self):
        """获取参数，将中文模式名转为内部英文值"""
        input_dir = self.input_dir_var.get().strip()
        mode_cn = self.mode_var.get()
        mode_en = MODE_MAP.get(mode_cn, 'datetime')
        prefix = self.prefix_var.get().strip()
        suffix = self.suffix_var.get().strip()
        start_num = self.start_num_var.get()
        digits = self.digits_var.get()
        recursive = self.recursive_var.get()
        
        # 扩展名过滤
        ext_raw = self.ext_var.get().strip()
        extensions = [e.strip() for e in ext_raw.split(',') if e.strip()] if ext_raw else None
        
        # 模式参数
        pattern = None
        if mode_en == 'custom':
            pattern = self.custom_var.get().strip()
        elif mode_en == 'replace':
            pattern = self.replace_var.get().strip()
        
        return input_dir, mode_en, pattern, prefix, suffix, start_num, digits, extensions, recursive
    
    def validate_params(self):
        input_dir, mode, pattern, prefix, suffix, start_num, digits, extensions, recursive = self.get_params()
        
        if not input_dir:
            messagebox.showwarning("提示", "请选择目标目录")
            return None
        if not os.path.isdir(input_dir):
            messagebox.showerror("错误", "目录不存在")
            return None
        
        if mode == 'custom' and not pattern:
            messagebox.showwarning("提示", "自定义模式需要填写模式字符串")
            return None
        if mode == 'replace' and not pattern:
            messagebox.showwarning("提示", "替换模式需要填写替换规则")
            return None
        
        return self.get_params()
    
    def preview_rename(self):
        params = self.validate_params()
        if not params:
            return
        
        self.preview_btn.config(state='disabled')
        self.execute_btn.config(state='disabled')
        self.progress['value'] = 0
        self.log_text.config(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.config(state='disabled')
        
        input_dir, mode, pattern, prefix, suffix, start_num, digits, extensions, recursive = params
        
        def task():
            try:
                rename_files(
                    input_dir, mode=mode, pattern=pattern,
                    prefix=prefix, suffix=suffix,
                    start_num=start_num, digits=digits,
                    preview=True, extensions=extensions,
                    recursive=recursive, callback=self.update_progress
                )
            finally:
                self.master.after(0, self.on_task_done)
        
        t = threading.Thread(target=task, daemon=True)
        t.start()
    
    def execute_rename(self):
        params = self.validate_params()
        if not params:
            return
        
        if not messagebox.askyesno("确认", "确定要执行重命名操作吗？\n此操作不可撤销！"):
            return
        
        self.preview_btn.config(state='disabled')
        self.execute_btn.config(state='disabled')
        self.progress['value'] = 0
        self.log_text.config(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.config(state='disabled')
        
        input_dir, mode, pattern, prefix, suffix, start_num, digits, extensions, recursive = params
        
        def task():
            try:
                rename_files(
                    input_dir, mode=mode, pattern=pattern,
                    prefix=prefix, suffix=suffix,
                    start_num=start_num, digits=digits,
                    preview=False, extensions=extensions,
                    recursive=recursive, callback=self.update_progress
                )
            finally:
                self.master.after(0, self.on_task_done)
        
        t = threading.Thread(target=task, daemon=True)
        t.start()
    
    def on_task_done(self):
        self.preview_btn.config(state='normal')
        self.execute_btn.config(state='normal')
        self.log("=" * 40)
        self.log("操作已完成")


def main():
    parser = argparse.ArgumentParser(
        description='[NAME] 批量重命名 - 按规则批量重命名图片/视频文件',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 日期+序号模式
  %(prog)s -i ./图片 -m datetime

  # 纯序号模式
  %(prog)s -i ./图片 -m serial --prefix "photo_" --start-num 1 --digits 3

  # 自定义模式（支持占位符）
  %(prog)s -i ./图片 -m custom -p "{y}-{m}-{day}_{n:04d}" --prefix "IMG_"

  # 查找替换
  %(prog)s -i ./图片 -m replace -p "old|new"

  # 添加前缀后缀
  %(prog)s -i ./图片 -m add --prefix "vacation_" --suffix "_edited"

  # 仅预览
  %(prog)s -i ./图片 -m datetime --preview

  # 占位符说明:
  {n}      序号 (如 1, 2, 3...)
  {n:04d}  序号指定位数 (如 0001)
  {d}      日期 YYYYMMDD
  {y}/{m}/{day} 年/月/日
  {h}/{min}/{s} 时/分/秒
  {old}    原文件名
        """
    )
    
    parser.add_argument('-i', '--input', required=True, help='输入目录')
    parser.add_argument('-m', '--mode',
                        choices=['datetime', 'serial', 'custom', 'replace', 'add'],
                        default='datetime',
                        help='重命名模式: datetime(日期+序号), serial(纯序号), custom(自定义), replace(查找替换), add(添加前后缀) (默认: datetime)')
    parser.add_argument('-p', '--pattern', default=None,
                        help='自定义模式或替换规则 (用于 custom/replace 模式)')
    parser.add_argument('--prefix', default='',
                        help='文件名前缀')
    parser.add_argument('--suffix', default='',
                        help='文件名后缀')
    parser.add_argument('--start-num', type=int, default=1,
                        help='起始序号 (默认: 1)')
    parser.add_argument('--digits', type=int, default=4,
                        help='序号位数 (默认: 4)')
    parser.add_argument('--ext', nargs='+', default=None,
                        help='文件扩展名过滤, 如 jpg png mp4')
    parser.add_argument('--recursive', action='store_true',
                        help='递归子目录')
    parser.add_argument('--preview', action='store_true',
                        help='仅预览不执行')
    
    args = parser.parse_args()
    
    if not os.path.isdir(args.input):
        print(f"[FAIL] 目录不存在: {args.input}")
        sys.exit(1)
    
    if args.mode in ('custom', 'replace') and not args.pattern:
        print(f"[FAIL] {args.mode} 模式需要 -p/--pattern 参数")
        sys.exit(1)
    
    rename_files(
        args.input, mode=args.mode, pattern=args.pattern,
        prefix=args.prefix, suffix=args.suffix,
        start_num=args.start_num, digits=args.digits,
        preview=args.preview, extensions=args.ext,
        recursive=args.recursive
    )


if __name__ == '__main__':
    if len(sys.argv) > 1:
        main()
    else:
        root = tk.Tk()
        app = BatchRenameGUI(root)
        root.mainloop()
