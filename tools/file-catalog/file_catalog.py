"""Read-only folder inventory, with optional SHA-256 and a CSV report."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import queue
import stat
import sys
import threading

FIELDS = ['file', 'bytes', 'modified_utc', 'sha256', 'status', 'detail']

def cancelled(event):
    if event is not None and event.is_set():
        raise InterruptedError('已取消，未导出清单。')

def linked(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)

def identity(info):
    value = info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns
    # Windows stat/fstat can expose different ctime semantics for the same unchanged file.
    return value if os.name == 'nt' else value + (info.st_ctime_ns,)

def file_digest(path, before, event):
    value = hashlib.sha256()
    if identity(path.lstat()) != identity(before):
        raise OSError('文件在读取前发生变化。')
    with path.open('rb') as source:
        if identity(os.fstat(source.fileno())) != identity(before):
            raise OSError('文件在打开时发生变化。')
        while block := source.read(1024 * 1024):
            cancelled(event)
            value.update(block)
        if identity(os.fstat(source.fileno())) != identity(before):
            raise OSError('文件在读取时发生变化。')
    if identity(path.lstat()) != identity(before):
        raise OSError('文件在读取后发生变化。')
    return value.hexdigest()

def extensions(text):
    items = {item.strip().lower() for item in text.replace(';', ',').split(',') if item.strip()}
    if any(not item.startswith('.') or any(char in item for char in '/\\*?') for item in items):
        raise ValueError('扩展名用 .jpg,.png 格式；留空表示所有文件。')
    return items

def scan(folder, *, recursive=True, hashes=False, suffixes='', event=None):
    root = Path(folder).absolute()
    info = root.lstat()
    if linked(info) or not stat.S_ISDIR(info.st_mode):
        raise ValueError('请选择普通文件夹，不能选择链接或目录联接。')
    wanted = extensions(suffixes)
    rows = []
    def add(path, status='OK', detail='', info=None, value=''):
        rows.append(dict(file=path.relative_to(root).as_posix(),
            bytes=info.st_size if info and stat.S_ISREG(info.st_mode) else '',
            modified_utc=datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat(timespec='seconds') if info else '',
            sha256=value, status=status, detail=detail))
    def failed(exc):
        add(Path(exc.filename or root), 'ERROR', str(exc))
    for directory, subdirs, files in os.walk(root, topdown=True, followlinks=False, onerror=failed):
        cancelled(event)
        parent = Path(directory)
        # A directory replaced during enumeration is an incomplete result, not an empty folder.
        parent_info = parent.lstat()
        if linked(parent_info) or not stat.S_ISDIR(parent_info.st_mode):
            subdirs[:] = []
            add(parent, 'ERROR', '目录在扫描时发生变化。')
            continue
        kept = []
        for name in sorted(subdirs, key=str.casefold):
            cancelled(event)
            path = parent / name
            try:
                item = path.lstat()
                if linked(item):
                    add(path, 'SKIPPED', '链接或目录联接被跳过。')
                elif recursive:
                    kept.append(name)
            except OSError as exc:
                add(path, 'ERROR', str(exc))
        subdirs[:] = kept
        for name in sorted(files, key=str.casefold):
            cancelled(event)
            path = parent / name
            if wanted and path.suffix.lower() not in wanted:
                continue
            try:
                item = path.lstat()
                if linked(item) or not stat.S_ISREG(item.st_mode):
                    add(path, 'SKIPPED', '链接、重解析点或非普通文件被跳过。')
                else:
                    value = file_digest(path, item, event) if hashes else ''
                    add(path, info=item, value=value)
            except InterruptedError:
                raise
            except (OSError, ValueError) as exc:
                add(path, 'ERROR', str(exc))
    return sorted(rows, key=lambda row: row['file'].casefold())

def summary(rows):
    counts = Counter(row['status'] for row in rows)
    total = sum(row['bytes'] for row in rows if row['status'] == 'OK')
    return f"文件 {counts['OK']}；合计 {total:,} 字节；跳过 {counts['SKIPPED']}；错误 {counts['ERROR']}"

def write_csv(rows, destination):
    with Path(destination).open('x', encoding='utf-8-sig', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: "'" + value if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')) else value for key, value in row.items()})

def launch_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    root = tk.Tk()
    root.title('文件清单导出器 · 免费开源')
    root.geometry('960x560')
    folder, suffixes = tk.StringVar(), tk.StringVar()
    recursive, hashes = tk.BooleanVar(value=True), tk.BooleanVar(value=False)
    status = tk.StringVar(value='只读扫描；可选 SHA-256；CSV 拒绝覆盖已有文件。')
    messages, stop = queue.Queue(), threading.Event()
    state = {'rows': None, 'busy': False}
    controls = []
    fields = ttk.Frame(root, padding=12)
    fields.pack(fill='x')
    ttk.Label(fields, text='文件夹').grid(row=0, column=0, sticky='w')
    entry = ttk.Entry(fields, textvariable=folder)
    entry.grid(row=0, column=1, sticky='ew', padx=8, pady=5)
    choose = ttk.Button(fields, text='选择…', command=lambda: folder.set(filedialog.askdirectory() or folder.get()))
    choose.grid(row=0, column=2)
    ttk.Label(fields, text='扩展名筛选').grid(row=1, column=0, sticky='w')
    suffix_entry = ttk.Entry(fields, textvariable=suffixes)
    suffix_entry.grid(row=1, column=1, sticky='ew', padx=8, pady=5)
    ttk.Label(fields, text='如 .jpg,.png；空白为全部').grid(row=1, column=2)
    controls.extend([entry, choose, suffix_entry])
    fields.columnconfigure(1, weight=1)
    buttons = ttk.Frame(root, padding=(12, 0))
    buttons.pack(fill='x')
    for title, variable in [('包含子文件夹', recursive), ('计算 SHA-256（较慢）', hashes)]:
        check = ttk.Checkbutton(buttons, text=title, variable=variable)
        check.pack(side='left', padx=(0, 10))
        controls.append(check)
    def worker(path, recurse, hash_files, filter_text):
        try:
            messages.put(('done', scan(path, recursive=recurse, hashes=hash_files, suffixes=filter_text, event=stop)))
        except (OSError, ValueError) as exc:
            messages.put(('error', str(exc)))
    def start():
        if not folder.get().strip():
            messagebox.showerror('未开始', '请选择文件夹。', parent=root)
            return
        stop.clear()
        state.update(rows=None, busy=True)
        table.delete(*table.get_children())
        for widget in controls + [begin, export]:
            widget.config(state='disabled')
        cancel.config(state='normal')
        status.set('扫描中…')
        threading.Thread(target=worker, args=(folder.get(), recursive.get(), hashes.get(), suffixes.get()), daemon=True).start()
    def save():
        path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV 清单', '*.csv')], confirmoverwrite=False)
        if path:
            try:
                write_csv(state['rows'], path)
                status.set('清单已保存：' + path)
            except OSError as exc:
                messagebox.showerror('未保存', str(exc), parent=root)
    begin = ttk.Button(buttons, text='扫描', command=start)
    begin.pack(side='left')
    cancel = ttk.Button(buttons, text='取消', command=stop.set, state='disabled')
    cancel.pack(side='left', padx=8)
    export = ttk.Button(buttons, text='导出 CSV', command=save, state='disabled')
    export.pack(side='left')
    panel = ttk.Frame(root, padding=12)
    panel.pack(fill='both', expand=True)
    table = ttk.Treeview(panel, columns=('file', 'bytes', 'modified', 'status'), show='headings')
    for name, title, width in [('file', '相对路径', 430), ('bytes', '字节', 130), ('modified', '修改时间 UTC', 210), ('status', '结果', 90)]:
        table.heading(name, text=title)
        table.column(name, width=width, stretch=name == 'file')
    bar = ttk.Scrollbar(panel, command=table.yview)
    table.config(yscrollcommand=bar.set)
    table.pack(side='left', fill='both', expand=True)
    bar.pack(side='right', fill='y')
    ttk.Label(root, textvariable=status, padding=12, wraplength=930).pack(fill='x')
    def changed(*_):
        if not state['busy']:
            state['rows'] = None
            export.config(state='disabled')
            status.set('选项已改变，请重新扫描。')
    for variable in (folder, suffixes, recursive, hashes):
        variable.trace_add('write', changed)
    def poll():
        try:
            kind, value = messages.get_nowait()
        except queue.Empty:
            pass
        else:
            state['busy'] = False
            for widget in controls + [begin]:
                widget.config(state='normal')
            cancel.config(state='disabled')
            if kind == 'done':
                state['rows'] = value
                export.config(state='normal')
                for row in value[:1000]:
                    table.insert('', 'end', values=(row['file'], row['bytes'], row['modified_utc'], row['status']))
                status.set(summary(value) + ('；界面预览前 1000 项，CSV 包含全部结果' if len(value) > 1000 else ''))
            else:
                status.set(value)
        root.after(150, poll)
    root.after(150, poll)
    root.mainloop()

def main():
    parser = argparse.ArgumentParser(description='只读导出文件夹的路径、大小、修改时间与可选 SHA-256。')
    parser.add_argument('folder', nargs='?', type=Path)
    parser.add_argument('--csv', type=Path, help='新 CSV 文件路径，不覆盖')
    parser.add_argument('--sha256', action='store_true', help='计算每个文件的 SHA-256')
    parser.add_argument('--top-only', action='store_true', help='仅当前层')
    parser.add_argument('--extensions', default='', help='扩展名筛选，例如 .jpg,.png')
    args = parser.parse_args()
    if len(sys.argv) == 1:
        launch_gui()
        return 0
    if args.folder is None:
        parser.error('请指定文件夹。')
    try:
        if args.csv and os.path.lexists(args.csv):
            raise FileExistsError('清单已存在，请选择新路径。')
        rows = scan(args.folder, recursive=not args.top_only, hashes=args.sha256, suffixes=args.extensions)
        if args.csv:
            write_csv(rows, args.csv)
        print(summary(rows))
        if not args.csv:
            for row in rows:
                print(f"{row['status']}\t{row['bytes']}\t{row['sha256']}\t{row['file']}\t{row['detail']}")
        return int(any(row['status'] != 'OK' for row in rows))
    except KeyboardInterrupt:
        print('已取消。', file=sys.stderr)
        return 130
    except (OSError, ValueError) as exc:
        print('错误：' + str(exc), file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
