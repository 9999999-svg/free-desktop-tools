"""Read-only comparison of two directory trees by relative path and SHA-256."""
import argparse
from collections import Counter
import csv
import hashlib
import os
from pathlib import Path
import queue
import stat
import sys
import threading

for stream in (sys.stdout, sys.stderr):
    if stream is not None and hasattr(stream, 'reconfigure'):
        stream.reconfigure(encoding='utf-8', errors='replace')

def linked(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)

def identity(info):
    return info.st_size, info.st_mtime_ns, info.st_dev, info.st_ino

def cancelled(event):
    if event is not None and event.is_set():
        raise InterruptedError('已取消，未生成完整比较结果。')

def index_folder(root, event=None):
    root = Path(root).absolute()
    if linked(root.lstat()) or not root.is_dir():
        raise ValueError('请选择普通文件夹，不能使用链接或重解析点作为根目录。')
    entries = {}
    def add(path, status='', error='', info=None):
        relative = path.relative_to(root).as_posix()
        key = os.path.normcase(relative)
        if key in entries:
            entries[key] = dict(file=relative, path=path, status='ERROR', error='相对路径大小写冲突。', info=None)
        else:
            entries[key] = dict(file=relative, path=path, status=status, error=error, info=info)
    def walk_error(exc):
        add(Path(exc.filename or root), 'ERROR', str(exc))
    for directory, folders, files in os.walk(root, followlinks=False, onerror=walk_error):
        cancelled(event)
        current = Path(directory)
        keep = []
        for name in folders:
            path = current / name
            try:
                if linked(path.lstat()):
                    add(path, 'SKIPPED', '文件夹链接或重解析点未遍历。')
                else:
                    keep.append(name)
            except OSError as exc:
                add(path, 'ERROR', str(exc))
        folders[:] = keep
        for name in files:
            cancelled(event)
            path = current / name
            try:
                info = path.lstat()
                if linked(info) or not stat.S_ISREG(info.st_mode):
                    add(path, 'SKIPPED', '链接、重解析点或非普通文件被跳过。')
                else:
                    add(path, info=info)
            except OSError as exc:
                add(path, 'ERROR', str(exc))
    return entries

def digest(entry, event=None):
    path, before = entry['path'], identity(entry['info'])
    if identity(path.lstat()) != before:
        raise OSError('文件在比较前发生变化。')
    result = hashlib.sha256()
    with path.open('rb') as source:
        if identity(os.fstat(source.fileno())) != before:
            raise OSError('文件在开始读取前发生变化。')
        while block := source.read(1024 * 1024):
            cancelled(event)
            result.update(block)
        if identity(os.fstat(source.fileno())) != before:
            raise OSError('文件在读取期间发生变化。')
    if identity(path.lstat()) != before:
        raise OSError('文件在读取后发生变化。')
    return result.hexdigest()

def compare(left, right, event=None):
    if Path(left).resolve() == Path(right).resolve():
        raise ValueError('请选择两个不同的文件夹。')
    first, second = index_folder(left, event), index_folder(right, event)
    rows = []
    for key in sorted(first.keys() | second.keys()):
        cancelled(event)
        a, b = first.get(key), second.get(key)
        row = dict(file=(a or b)['file'], status='', left_bytes=a['info'].st_size if a and a['info'] else '',
                   right_bytes=b['info'].st_size if b and b['info'] else '', error='')
        problems = [entry for entry in (a, b) if entry and entry['status']]
        if problems:
            row.update(status='ERROR' if any(p['status'] == 'ERROR' for p in problems) else 'SKIPPED',
                       error='; '.join(p['error'] for p in problems))
        elif a is None:
            row['status'] = 'RIGHT_ONLY'
        elif b is None:
            row['status'] = 'LEFT_ONLY'
        else:
            try:
                # Hash both versions even when sizes differ, detecting changes during the read.
                row['status'] = 'SAME' if digest(a, event) == digest(b, event) else 'CHANGED'
            except OSError as exc:
                if isinstance(exc, InterruptedError):
                    raise
                row.update(status='ERROR', error=str(exc))
        rows.append(row)
    return rows

LABELS = {'SAME': '相同', 'CHANGED': '内容不同', 'LEFT_ONLY': '仅左侧', 'RIGHT_ONLY': '仅右侧', 'SKIPPED': '跳过', 'ERROR': '错误'}

def summary(rows):
    counts = Counter(row['status'] for row in rows)
    return '；'.join(f'{label} {counts[key]}' for key, label in LABELS.items())

def write_csv(rows, destination):
    with Path(destination).open('x', encoding='utf-8-sig', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=['file', 'status', 'left_bytes', 'right_bytes', 'error'])
        writer.writeheader()
        for row in rows:
            writer.writerow({key: "'" + value if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')) else value for key, value in row.items()})

def launch_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    root = tk.Tk()
    root.title('文件夹对比器 · 免费开源')
    root.geometry('920x540')
    paths = [tk.StringVar(), tk.StringVar()]
    status = tk.StringVar(value='只比较文件内容，不同步、不删除文件。')
    messages, stop, state = queue.Queue(), threading.Event(), {'rows': None}
    fields = ttk.Frame(root, padding=12)
    fields.pack(fill='x')
    for number, label in enumerate(['左侧文件夹', '右侧文件夹']):
        ttk.Label(fields, text=label).grid(row=number, column=0, sticky='w', pady=5)
        ttk.Entry(fields, textvariable=paths[number]).grid(row=number, column=1, padx=8, sticky='ew')
        ttk.Button(fields, text='选择…', command=lambda n=number: paths[n].set(filedialog.askdirectory() or paths[n].get())).grid(row=number, column=2)
    fields.columnconfigure(1, weight=1)
    buttons = ttk.Frame(root, padding=(12, 0))
    buttons.pack(fill='x')
    def worker(left, right):
        try:
            messages.put(('done', compare(left, right, stop)))
        except (OSError, ValueError) as exc:
            messages.put(('error', str(exc)))
    def start():
        if not all(value.get().strip() for value in paths):
            messagebox.showerror('未开始', '请选择左右两个文件夹。', parent=root)
            return
        stop.clear()
        state['rows'] = None
        table.delete(*table.get_children())
        begin.config(state='disabled')
        export.config(state='disabled')
        cancel.config(state='normal')
        status.set('比较中…')
        threading.Thread(target=worker, args=tuple(value.get() for value in paths), daemon=True).start()
    def save():
        path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV 报告', '*.csv')], confirmoverwrite=False)
        if path:
            try:
                write_csv(state['rows'], path)
                status.set('报告已保存：' + path)
            except OSError as exc:
                messagebox.showerror('未保存', str(exc), parent=root)
    begin = ttk.Button(buttons, text='开始比较', command=start)
    begin.pack(side='left')
    cancel = ttk.Button(buttons, text='取消', command=stop.set, state='disabled')
    cancel.pack(side='left', padx=8)
    export = ttk.Button(buttons, text='导出 CSV', command=save, state='disabled')
    export.pack(side='left')
    panel = ttk.Frame(root, padding=12)
    panel.pack(fill='both', expand=True)
    table = ttk.Treeview(panel, columns=('file', 'status', 'left', 'right'), show='headings')
    for name, title, width in [('file', '相对路径', 530), ('status', '结果', 110), ('left', '左侧字节', 115), ('right', '右侧字节', 115)]:
        table.heading(name, text=title)
        table.column(name, width=width, stretch=name == 'file')
    bar = ttk.Scrollbar(panel, command=table.yview)
    table.config(yscrollcommand=bar.set)
    table.pack(side='left', fill='both', expand=True)
    bar.pack(side='right', fill='y')
    ttk.Label(root, textvariable=status, padding=12, wraplength=890).pack(fill='x')
    def poll():
        try:
            kind, value = messages.get_nowait()
        except queue.Empty:
            pass
        else:
            begin.config(state='normal')
            cancel.config(state='disabled')
            if kind == 'done':
                state['rows'] = value
                export.config(state='normal')
                # ponytail: show at most 1000 rows; export retains the complete result.
                for row in value[:1000]:
                    table.insert('', 'end', values=(row['file'], LABELS[row['status']], row['left_bytes'], row['right_bytes']))
                status.set(summary(value) + ('；预览前 1000 项，CSV 含全部结果' if len(value) > 1000 else ''))
            else:
                status.set(value)
        root.after(150, poll)
    root.after(150, poll)
    root.mainloop()

def main():
    parser = argparse.ArgumentParser(description='按相对路径与 SHA-256 对比两份文件夹；只读，不同步、不删除。')
    parser.add_argument('left', nargs='?', type=Path)
    parser.add_argument('right', nargs='?', type=Path)
    parser.add_argument('--csv', type=Path, help='新 CSV 路径，拒绝覆盖已有文件')
    args = parser.parse_args()
    if args.left is None and args.right is None and args.csv is None:
        launch_gui()
        return 0
    if args.left is None or args.right is None:
        parser.error('请指定左右两个文件夹。')
    try:
        if args.csv and args.csv.exists():
            raise FileExistsError('报告已存在，请选择新路径。')
        rows = compare(args.left, args.right)
        if args.csv:
            write_csv(rows, args.csv)
        print(summary(rows))
        for row in rows:
            if row['status'] != 'SAME':
                print(f"{row['status']} · {row['file']} · {row['error']}")
        if any(row['status'] in {'SKIPPED', 'ERROR'} for row in rows):
            return 2
        return int(any(row['status'] != 'SAME' for row in rows))
    except KeyboardInterrupt:
        print('已取消。', file=sys.stderr)
        return 130
    except (OSError, ValueError) as exc:
        print('错误：' + str(exc), file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
