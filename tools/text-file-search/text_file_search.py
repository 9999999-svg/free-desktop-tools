"""Read-only, literal text search with explicit encodings and CSV export."""
import argparse
from collections import Counter
import csv
import json
import os
from pathlib import Path
import queue
import stat
import sys
import threading

ENCODINGS = ['utf-8-sig', 'utf-8', 'gb18030', 'gbk', 'utf-16']
DEFAULT_EXTENSIONS = '.txt,.md,.csv,.log,.json,.ini,.py,.yaml,.yml,.xml,.html,.css,.js'
FIELDS = ['file', 'line', 'occurrences', 'text', 'status', 'detail']
MAX_BYTES = 50 * 1024 * 1024

def check_cancel(event):
    if event is not None and event.is_set():
        raise InterruptedError('已取消，未导出结果。')

def linked(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)

def identity(info):
    value = info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns
    return value if os.name == 'nt' else value + (info.st_ctime_ns,)

def read_text(path, encoding, event):
    before = path.lstat()
    if linked(before) or not stat.S_ISREG(before.st_mode):
        raise ValueError('链接、重解析点或非普通文件被跳过。')
    if before.st_size > MAX_BYTES:
        raise ValueError('超过单文件 50 MiB 上限。')
    with path.open('rb') as source:
        if identity(os.fstat(source.fileno())) != identity(before):
            raise OSError('文件在打开时发生变化。')
        data = bytearray()
        while block := source.read(1024 * 1024):
            check_cancel(event)
            data.extend(block)
            if len(data) > MAX_BYTES:
                raise ValueError('文件增长超过 50 MiB 上限。')
        if identity(os.fstat(source.fileno())) != identity(before):
            raise OSError('文件在读取时发生变化。')
    if identity(path.lstat()) != identity(before):
        raise OSError('文件在读取后发生变化。')
    text = bytes(data).decode(encoding, errors='strict')
    if '\x00' in text:
        raise ValueError('含 NUL 字符；可能为二进制文件或编码选择不正确。')
    return text

def search(folder, query, *, encoding='utf-8-sig', suffixes=DEFAULT_EXTENSIONS,
        case_sensitive=False, recursive=True, max_matches=10000, event=None):
    if not query or '\n' in query or '\r' in query:
        raise ValueError('关键词不能为空，且只能包含一行文本。')
    if encoding not in ENCODINGS or not 1 <= max_matches <= 100000:
        raise ValueError('编码不支持，或匹配行上限不在 1 至 100000 之间。')
    wanted = {item.strip().lower() for item in suffixes.replace(';', ',').split(',') if item.strip()}
    if any(not item.startswith('.') or any(c in item for c in '/\\*?') for item in wanted):
        raise ValueError('扩展名使用 .txt,.md 格式；留空表示所有普通文件。')
    root = Path(folder).absolute()
    info = root.lstat()
    if linked(info) or not stat.S_ISDIR(info.st_mode):
        raise ValueError('请选择普通文件夹，不能选择链接或目录联接。')
    needle = query if case_sensitive else query.casefold()
    rows, matched = [], 0
    def add(path, status, detail='', line='', count='', text=''):
        rows.append(dict(file=path.relative_to(root).as_posix(), line=line, occurrences=count,
            text=text[:1024], status=status, detail=detail))
    def failed(exc):
        add(Path(exc.filename or root), 'ERROR', str(exc))
    for directory, subdirs, files in os.walk(root, topdown=True, followlinks=False, onerror=failed):
        check_cancel(event)
        parent = Path(directory)
        try:
            info = parent.lstat()
            if linked(info) or not stat.S_ISDIR(info.st_mode):
                raise OSError('目录在扫描时发生变化。')
        except OSError as exc:
            subdirs[:] = []
            add(parent, 'ERROR', str(exc))
            continue
        kept = []
        if recursive:
            for name in sorted(subdirs, key=str.casefold):
                check_cancel(event)
                path = parent / name
                try:
                    item = path.lstat()
                    if linked(item):
                        add(path, 'SKIPPED', '链接或目录联接被跳过。')
                    else:
                        kept.append(name)
                except OSError as exc:
                    add(path, 'ERROR', str(exc))
        subdirs[:] = kept
        for name in sorted(files, key=str.casefold):
            check_cancel(event)
            path = parent / name
            if wanted and path.suffix.lower() not in wanted:
                continue
            try:
                text = read_text(path, encoding, event)
                # ponytail: explicit 50 MiB ceiling; stream decoding if larger files become necessary.
                for number, line in enumerate(text.splitlines(), 1):
                    check_cancel(event)
                    value = line if case_sensitive else line.casefold()
                    count = value.count(needle)
                    if count:
                        add(path, 'MATCH', '内容截断至 1024 字符。' if len(line) > 1024 else '',
                            line=number, count=count, text=line)
                        matched += 1
                        if matched >= max_matches:
                            add(path, 'LIMIT', '已达到匹配行上限，搜索提前结束；结果可能不完整。')
                            return rows
            except InterruptedError:
                raise
            except UnicodeError as exc:
                add(path, 'ERROR', f'无法用所选编码解码：{exc}')
            except ValueError as exc:
                add(path, 'SKIPPED', str(exc))
            except OSError as exc:
                add(path, 'ERROR', str(exc))
    check_cancel(event)
    return rows

def export_csv(rows, path):
    target = Path(path).absolute()
    # Exclusive creation prevents a report from replacing an input or existing file.
    with target.open('x', encoding='utf-8-sig', newline='') as destination:
        try:
            writer = csv.DictWriter(destination, fieldnames=FIELDS)
            writer.writeheader()
            for row in rows:
                # Spreadsheet formula protection affects reports only, never searched files.
                writer.writerow({key: ("'" + str(value) if str(value).lstrip().startswith(('=', '+', '-', '@')) else value)
                    for key, value in row.items()})
        except BaseException:
            destination.close()
            target.unlink()
            raise

def gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    root = tk.Tk()
    root.title('文本内容搜索器')
    root.geometry('1000x700')
    frame = ttk.Frame(root, padding=14)
    frame.pack(fill='both', expand=True)
    folder, query = tk.StringVar(), tk.StringVar()
    encoding, suffixes = tk.StringVar(value='utf-8-sig'), tk.StringVar(value=DEFAULT_EXTENSIONS)
    sensitive, recursive = tk.BooleanVar(value=False), tk.BooleanVar(value=True)
    maximum = tk.StringVar(value='10000')
    controls = []
    def field(label, variable, row):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky='w', pady=5)
        widget = ttk.Entry(frame, textvariable=variable)
        widget.grid(row=row, column=1, columnspan=2, sticky='ew', padx=8, pady=5)
        controls.append(widget)
        return widget
    field('搜索文件夹', folder, 0)
    def browse():
        value = filedialog.askdirectory(title='选择搜索文件夹')
        if value:
            folder.set(value)
    browse_button = ttk.Button(frame, text='选择', command=browse)
    browse_button.grid(row=0, column=3)
    controls.append(browse_button)
    field('文字关键词', query, 1)
    field('扩展名', suffixes, 2)
    options = ttk.Frame(frame)
    options.grid(row=3, column=0, columnspan=4, sticky='ew', pady=6)
    ttk.Label(options, text='编码').pack(side='left')
    encoding_box = ttk.Combobox(options, textvariable=encoding, values=ENCODINGS, state='readonly', width=15)
    encoding_box.pack(side='left', padx=8)
    controls.append(encoding_box)
    for label, variable in [('区分大小写', sensitive), ('包含子文件夹', recursive)]:
        widget = ttk.Checkbutton(options, text=label, variable=variable)
        widget.pack(side='left', padx=8)
        controls.append(widget)
    ttk.Label(options, text='匹配行上限').pack(side='left', padx=8)
    max_entry = ttk.Entry(options, textvariable=maximum, width=8)
    max_entry.pack(side='left')
    controls.append(max_entry)
    actions = ttk.Frame(frame)
    actions.grid(row=4, column=0, columnspan=4, sticky='ew', pady=8)
    result = ttk.Treeview(frame, columns=FIELDS, show='headings', height=20)
    for key, title, width in zip(FIELDS, ['相对路径', '行号', '次数', '内容（最多 1024 字符）', '状态', '说明'], [210, 55, 50, 350, 80, 190]):
        result.heading(key, text=title)
        result.column(key, width=width, stretch=key in ['file', 'text', 'detail'])
    result.grid(row=5, column=0, columnspan=4, sticky='nsew')
    scroll = ttk.Scrollbar(frame, orient='vertical', command=result.yview)
    scroll.grid(row=5, column=4, sticky='ns')
    result.configure(yscrollcommand=scroll.set)
    status = tk.StringVar(value='只读搜索；按所选编码解码，不自动猜测编码或搜索压缩包。')
    ttk.Label(frame, textvariable=status, wraplength=940).grid(row=6, column=0, columnspan=4, sticky='w', pady=10)
    frame.columnconfigure(1, weight=1)
    frame.rowconfigure(5, weight=1)
    rows, events, stop = [], queue.Queue(), threading.Event()
    busy, closing = False, False
    def invalidate(*_):
        if not busy:
            rows.clear()
            export_button.configure(state='disabled')
            result.delete(*result.get_children())
    for variable in [folder, query, encoding, suffixes, sensitive, recursive, maximum]:
        variable.trace_add('write', invalidate)
    def set_busy(value):
        for widget in controls:
            widget.configure(state='disabled' if value else ('readonly' if widget is encoding_box else 'normal'))
        start_button.configure(state='disabled' if value else 'normal')
        cancel_button.configure(state='normal' if value else 'disabled')
        export_button.configure(state='disabled')
    def start():
        nonlocal busy
        try:
            limit = int(maximum.get())
            if not 1 <= limit <= 100000:
                raise ValueError()
        except ValueError:
            messagebox.showerror('上限无效', '匹配行上限必须为 1 至 100000 的整数。')
            return
        args = (folder.get(), query.get(), encoding.get(), suffixes.get(), sensitive.get(), recursive.get(), limit)
        rows.clear()
        result.delete(*result.get_children())
        busy = True
        stop.clear()
        set_busy(True)
        status.set('正在搜索…')
        def worker():
            try:
                value = search(args[0], args[1], encoding=args[2], suffixes=args[3],
                    case_sensitive=args[4], recursive=args[5], max_matches=args[6], event=stop)
                events.put(('done', value))
            except (OSError, ValueError) as exc:
                events.put(('error', str(exc)))
        threading.Thread(target=worker, daemon=True).start()
    def save():
        value = filedialog.asksaveasfilename(title='保存搜索结果到新文件', defaultextension='.csv', filetypes=[('CSV 文件', '*.csv')])
        if value:
            try:
                export_csv(rows, value)
                status.set(f'已导出全部 {len(rows)} 条记录：{value}')
            except OSError as exc:
                messagebox.showerror('未导出', str(exc))
    start_button = ttk.Button(actions, text='开始搜索', command=start)
    start_button.pack(side='left')
    cancel_button = ttk.Button(actions, text='取消', command=stop.set, state='disabled')
    cancel_button.pack(side='left', padx=8)
    export_button = ttk.Button(actions, text='导出 CSV', command=save, state='disabled')
    export_button.pack(side='left')
    def poll():
        nonlocal busy
        try:
            kind, value = events.get_nowait()
            busy = False
            set_busy(False)
            if kind == 'done':
                rows.extend(value)
                for item in rows[:1000]:
                    result.insert('', 'end', values=[item[key] for key in FIELDS])
                counts = Counter(item['status'] for item in rows)
                status.set(f'匹配行 {counts["MATCH"]}；跳过 {counts["SKIPPED"]}；错误 {counts["ERROR"]}；上限停止 {counts["LIMIT"]}。界面最多显示 1000 行，CSV 导出全部记录。')
                export_button.configure(state='normal')
            else:
                status.set(value)
            if closing:
                root.destroy()
                return
        except queue.Empty:
            pass
        root.after(100, poll)
    def close():
        nonlocal closing
        if busy:
            closing = True
            stop.set()
            status.set('正在取消…')
        else:
            root.destroy()
    root.protocol('WM_DELETE_WINDOW', close)
    poll()
    root.mainloop()

def main():
    if len(sys.argv) == 1:
        gui()
        return 0
    parser = argparse.ArgumentParser(description='只读搜索文件夹内的文字内容；无参数打开图形界面。')
    parser.add_argument('folder')
    parser.add_argument('query')
    parser.add_argument('--csv', required=True)
    parser.add_argument('--encoding', choices=ENCODINGS, default='utf-8-sig')
    parser.add_argument('--extensions', default=DEFAULT_EXTENSIONS)
    parser.add_argument('--case-sensitive', action='store_true')
    parser.add_argument('--top-only', action='store_true')
    parser.add_argument('--max-matches', type=int, default=10000)
    args = parser.parse_args()
    try:
        if os.path.lexists(args.csv):
            raise FileExistsError('报告已存在，请使用新文件名。')
        rows = search(args.folder, args.query, encoding=args.encoding, suffixes=args.extensions,
            case_sensitive=args.case_sensitive, recursive=not args.top_only, max_matches=args.max_matches)
        export_csv(rows, args.csv)
        counts = dict(Counter(row['status'] for row in rows))
        print(json.dumps(counts, ensure_ascii=True))
        return 1 if any(row['status'] != 'MATCH' for row in rows) else 0
    except KeyboardInterrupt:
        print('Cancelled', file=sys.stderr)
        return 130
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
