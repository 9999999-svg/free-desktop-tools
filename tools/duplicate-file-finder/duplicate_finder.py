"""Find duplicate file content, without deleting or modifying scanned files."""
import argparse
from collections import defaultdict
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

class Cancelled(Exception):
    pass

def check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise Cancelled('Scan cancelled.')

def is_link(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))

def fingerprint(info):
    return info.st_size, info.st_mtime_ns, info.st_dev, info.st_ino

def hash_file(path, original, cancel):
    digest = hashlib.sha256()
    if is_link(path.lstat()):
        raise OSError('File became a link/reparse point.')
    with path.open('rb') as file:
        if fingerprint(os.fstat(file.fileno())) != fingerprint(original):
            raise OSError('File changed after enumeration.')
        while True:
            check_cancel(cancel)
            block = file.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
        if fingerprint(os.fstat(file.fileno())) != fingerprint(original):
            raise OSError('File changed while hashing.')
    if fingerprint(path.lstat()) != fingerprint(original):
        raise OSError('File changed after hashing.')
    return digest.hexdigest()

def scan(root, min_size=1, cancel=None, progress=None):
    root = Path(root).absolute()
    if min_size < 0:
        raise ValueError('Minimum size must be non-negative.')
    if is_link(root.lstat()) or not root.is_dir():
        raise ValueError('Choose a real directory, not a link or junction.')
    sizes, identities, errors = defaultdict(list), set(), []
    count = skipped = aliases = 0

    def error(path, message):
        errors.append({'path': str(path), 'message': str(message)})

    for directory, folders, files in os.walk(root, followlinks=False, onerror=lambda exc: error(exc.filename, exc)):
        check_cancel(cancel)
        for name in list(folders):
            path = Path(directory) / name
            try:
                linked = is_link(path.lstat())
            except OSError as exc:
                error(path, exc)
                linked = True
            if linked:
                folders.remove(name)
                skipped += 1
        for name in files:
            check_cancel(cancel)
            path = Path(directory) / name
            try:
                info = path.lstat()
                if is_link(info) or not stat.S_ISREG(info.st_mode):
                    skipped += 1
                    continue
                count += 1
                if info.st_size < min_size:
                    continue
                identity = info.st_dev, info.st_ino
                if info.st_ino and identity in identities:
                    aliases += 1
                    continue
                if info.st_ino:
                    identities.add(identity)
                sizes[info.st_size].append((path, info))
            except OSError as exc:
                error(path, exc)
            if progress and count % 100 == 0:
                progress(f'已发现 {count} 个文件')
    groups = []
    candidates = [(size, members) for size, members in sizes.items() if len(members) > 1]
    total, done = sum(len(members) for _, members in candidates), 0
    for size, members in candidates:
        hashes = defaultdict(list)
        for path, info in members:
            check_cancel(cancel)
            if progress:
                progress(f'核对内容 {done + 1}/{total}：{path.name}')
            try:
                hashes[hash_file(path, info, cancel)].append(str(path))
            except OSError as exc:
                error(path, exc)
            done += 1
        for digest, paths in hashes.items():
            if len(paths) > 1:
                groups.append({'size': size, 'sha256': digest, 'paths': sorted(paths)})
    check_cancel(cancel)
    groups.sort(key=lambda group: (-group['size'] * (len(group['paths']) - 1), group['paths'][0]))
    return {'groups': groups, 'files_seen': count, 'links_skipped': skipped,
            'hardlinks_skipped': aliases, 'errors': errors,
            'extra_files': sum(len(group['paths']) - 1 for group in groups),
            'extra_bytes': sum(group['size'] * (len(group['paths']) - 1) for group in groups)}

def write_csv(result, destination):
    # UTF-8 BOM lets Windows spreadsheet apps open Chinese paths correctly.
    with Path(destination).open('x', encoding='utf-8-sig', newline='') as output:
        writer = csv.writer(output)
        writer.writerow(['group', 'size_bytes', 'sha256', 'path'])
        for number, group in enumerate(result['groups'], 1):
            writer.writerows((number, group['size'], group['sha256'], path) for path in group['paths'])

def summary(result):
    return (f"{len(result['groups'])} 组重复内容，{result['extra_files']} 个额外副本，"
            f"逻辑容量约 {result['extra_bytes'] / 1024**2:.2f} MiB；"
            f"跳过链接 {result['links_skipped']}、硬链接别名 {result['hardlinks_skipped']}、"
            f"错误 {len(result['errors'])}")

def launch_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title('重复文件扫描器 · 免费开源')
    root.geometry('940x590')
    folder, minimum = tk.StringVar(), tk.StringVar(value='1')
    status = tk.StringVar(value='选择文件夹后扫描；本工具只读取文件，不执行删除。')
    messages, cancel, state = queue.Queue(), threading.Event(), {'result': None, 'running': False}
    controls = ttk.Frame(root, padding=12)
    controls.pack(fill='x')
    ttk.Label(controls, text='文件夹').grid(row=0, column=0, sticky='w')
    ttk.Entry(controls, textvariable=folder, width=80).grid(row=0, column=1, padx=8, sticky='ew')
    ttk.Button(controls, text='选择…', command=lambda: folder.set(filedialog.askdirectory() or folder.get())).grid(row=0, column=2)
    ttk.Label(controls, text='最小字节数').grid(row=1, column=0, pady=8, sticky='w')
    ttk.Entry(controls, textvariable=minimum, width=16).grid(row=1, column=1, sticky='w', padx=8)
    controls.columnconfigure(1, weight=1)
    buttons = ttk.Frame(root, padding=(12, 0))
    buttons.pack(fill='x')

    def worker(path, size):
        try:
            messages.put(('done', scan(path, size, cancel, lambda text: messages.put(('progress', text)))))
        except Cancelled:
            messages.put(('cancelled', '已取消，没有导出新报告。'))
        except (OSError, ValueError) as exc:
            messages.put(('error', str(exc)))

    def start():
        try:
            if not folder.get().strip():
                raise ValueError('请选择文件夹。')
            size = int(minimum.get())
            if size < 0:
                raise ValueError('最小字节数不能为负数。')
        except ValueError as exc:
            messagebox.showerror('输入有误', str(exc), parent=root)
            return
        state.update(result=None, running=True)
        cancel.clear()
        table.delete(*table.get_children())
        start_button.config(state='disabled')
        export_button.config(state='disabled')
        cancel_button.config(state='normal')
        status.set('扫描中…')
        threading.Thread(target=worker, args=(folder.get(), size), daemon=True).start()

    def export():
        path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV 报告', '*.csv')], confirmoverwrite=False)
        if path:
            try:
                write_csv(state['result'], path)
                status.set('CSV 已导出：' + path)
            except OSError as exc:
                messagebox.showerror('未导出', '已有文件不会被覆盖，请选新名称。\n' + str(exc), parent=root)

    start_button = ttk.Button(buttons, text='开始扫描', command=start)
    start_button.pack(side='left')
    cancel_button = ttk.Button(buttons, text='取消', state='disabled', command=cancel.set)
    cancel_button.pack(side='left', padx=8)
    export_button = ttk.Button(buttons, text='导出 CSV', state='disabled', command=export)
    export_button.pack(side='left')
    panel = ttk.Frame(root, padding=12)
    panel.pack(fill='both', expand=True)
    table = ttk.Treeview(panel, columns=('group', 'size', 'path'), show='headings')
    for name, label, width in [('group', '组', 50), ('size', '字节数', 120), ('path', '完整路径', 690)]:
        table.heading(name, text=label)
        table.column(name, width=width, stretch=name == 'path')
    vertical = ttk.Scrollbar(panel, command=table.yview)
    horizontal = ttk.Scrollbar(panel, orient='horizontal', command=table.xview)
    table.config(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
    table.grid(row=0, column=0, sticky='nsew')
    vertical.grid(row=0, column=1, sticky='ns')
    horizontal.grid(row=1, column=0, sticky='ew')
    panel.rowconfigure(0, weight=1)
    panel.columnconfigure(0, weight=1)
    ttk.Label(root, textvariable=status, padding=12, wraplength=900).pack(fill='x')

    def poll():
        latest = None
        try:
            while True:
                kind, value = messages.get_nowait()
                if kind == 'progress':
                    latest = value
                    continue
                state['running'] = False
                start_button.config(state='normal')
                cancel_button.config(state='disabled')
                latest = value if kind != 'done' else summary(value)
                if kind == 'done':
                    state['result'] = value
                    export_button.config(state='normal')
                    rows = [(number, group['size'], path) for number, group in enumerate(value['groups'], 1) for path in group['paths']]
                    # ponytail: cap preview at 1000 rows; CSV retains all results.
                    for row in rows[:1000]:
                        table.insert('', 'end', values=row)
                    if len(rows) > 1000:
                        latest += '；预览前 1000 个文件，CSV 含全部结果'
                    if value['errors']:
                        latest += '；首个错误：' + value['errors'][0]['message']
                elif kind == 'error':
                    messagebox.showerror('扫描失败', value, parent=root)
        except queue.Empty:
            pass
        if latest is not None:
            status.set(latest)
        root.after(150, poll)
    root.after(150, poll)
    root.mainloop()

def main():
    parser = argparse.ArgumentParser(description='只读扫描重复文件内容，支持中文路径和 CSV 导出。')
    parser.add_argument('folder', nargs='?', type=Path, help='扫描目录；不指定则打开图形界面')
    parser.add_argument('--csv', type=Path, help='新 CSV 报告路径，不覆盖已有文件')
    parser.add_argument('--min-size', type=int, default=1, help='最小文件字节数，默认 1；0 包含空文件')
    args = parser.parse_args()
    if args.folder is None:
        if args.csv or args.min_size != 1:
            parser.error('命令行导出或过滤时必须指定扫描目录。')
        launch_gui()
        return 0
    try:
        if args.csv and args.csv.exists():
            raise FileExistsError('报告已存在，请选新名称。')
        result = scan(args.folder, args.min_size)
        if args.csv:
            write_csv(result, args.csv)
        print(summary(result))
        for number, group in enumerate(result['groups'], 1):
            print(f"\n组 {number} · {group['size']} 字节 · SHA-256 {group['sha256']}")
            print('\n'.join(group['paths']))
        for error in result['errors']:
            print(f"跳过：{error['path']}：{error['message']}", file=sys.stderr)
        return 2 if result['errors'] else 0
    except (OSError, ValueError) as exc:
        print('错误：' + str(exc), file=sys.stderr)
        return 1
    except (Cancelled, KeyboardInterrupt):
        print('已取消。', file=sys.stderr)
        return 130

if __name__ == '__main__':
    raise SystemExit(main())
