"""Merge CSV files with identical headers into a new UTF-8 BOM file."""
import argparse
import csv
import io
import json
import os
from pathlib import Path
import queue
import stat
import sys
import tempfile
import threading

ENCODINGS = ['utf-8-sig', 'utf-8', 'gb18030', 'gbk', 'utf-16']
SEPARATORS = {'逗号': ',', '分号': ';', '制表符': '\t'}
MAX_BYTES = 50 * 1024 * 1024
csv.field_size_limit(MAX_BYTES)

def check_cancel(event):
    if event is not None and event.is_set():
        raise InterruptedError('已取消，未发布合并文件。')

def linked(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)

def identity(info):
    value = info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns
    return value if os.name == 'nt' else value + (info.st_ctime_ns,)

def read_csv(path, event):
    check_cancel(event)
    before = path.lstat()
    if linked(before) or not stat.S_ISREG(before.st_mode):
        raise ValueError(f'不能读取链接或非普通文件：{path.name}')
    if before.st_size > MAX_BYTES:
        raise ValueError(f'单个文件上限 50 MiB：{path.name}')
    with path.open('rb') as source:
        if identity(os.fstat(source.fileno())) != identity(before):
            raise OSError(f'文件打开时发生变化：{path.name}')
        data = bytearray()
        while block := source.read(1024 * 1024):
            check_cancel(event)
            data.extend(block)
            if len(data) > MAX_BYTES:
                raise ValueError(f'文件增长超过 50 MiB：{path.name}')
        if identity(os.fstat(source.fileno())) != identity(before):
            raise OSError(f'文件读取时发生变化：{path.name}')
    if identity(path.lstat()) != identity(before):
        raise OSError(f'文件读取后发生变化：{path.name}')
    return bytes(data)

def merge(files, output, *, encoding='utf-8-sig', delimiter=',', event=None, progress=None):
    if encoding not in ENCODINGS or delimiter not in SEPARATORS.values():
        raise ValueError('不支持的编码或分隔符。')
    inputs = [Path(item).absolute() for item in files]
    if not 2 <= len(inputs) <= 500:
        raise ValueError('请选择 2 至 500 个 CSV 文件。')
    if len(set(inputs)) != len(inputs):
        raise ValueError('输入文件不能重复。')
    target = Path(output).absolute()
    if os.path.lexists(target):
        raise FileExistsError('输出文件已存在；请选择新文件名。')
    parent = target.parent.lstat()
    if linked(parent) or not stat.S_ISDIR(parent.st_mode):
        raise ValueError('输出位置必须是已存在的普通文件夹。')
    if any(target.resolve() == item.resolve() for item in inputs):
        raise ValueError('输出不能是输入文件。')
    check_cancel(event)
    fd, temp_name = tempfile.mkstemp(prefix='.csv-merge-', suffix='.tmp', dir=target.parent)
    temp = Path(temp_name)
    header, counts = None, []
    try:
        with os.fdopen(fd, 'w', encoding='utf-8-sig', newline='') as destination:
            writer = csv.writer(destination, delimiter=delimiter, lineterminator='\r\n')
            for index, path in enumerate(inputs, 1):
                text = read_csv(path, event).decode(encoding, errors='strict')
                if '\x00' in text:
                    raise ValueError(f'含 NUL 字符，请确认编码：{path.name}')
                reader = csv.reader(io.StringIO(text, newline=''), delimiter=delimiter, strict=True)
                current = next((row for row in reader if row), None)
                if not current:
                    raise ValueError(f'文件为空或缺少表头：{path.name}')
                if header is None:
                    header = current
                    writer.writerow(header)
                elif current != header:
                    raise ValueError(f'表头或列顺序不一致：{path.name}')
                count = 0
                for row in reader:
                    check_cancel(event)
                    if not row:
                        continue
                    if len(row) != len(header):
                        raise ValueError(f'{path.name} 第 {reader.line_num} 行列数不一致。')
                    writer.writerow(row)
                    count += 1
                counts.append({'file': path.name, 'rows': count})
                if progress:
                    progress(index, len(inputs), path.name)
            check_cancel(event)
            destination.flush()
            os.fsync(destination.fileno())
        check_cancel(event)
        # Native rename on Windows and link on POSIX both refuse an existing target.
        if os.name == 'nt':
            os.rename(temp, target)
        else:
            os.link(temp, target)
            temp.unlink()
        return {'output': str(target), 'files': len(inputs), 'rows': sum(x['rows'] for x in counts),
                'columns': len(header), 'inputs': counts}
    finally:
        if temp.exists():
            temp.unlink()

def gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    root = tk.Tk()
    root.title('CSV 合并器')
    root.geometry('850x630')
    frame = ttk.Frame(root, padding=16)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='按列表顺序合并；各文件表头与列顺序必须相同，输出为 UTF-8 BOM。').pack(anchor='w')
    paths = []
    listing = tk.Listbox(frame, height=13, selectmode='extended')
    listing.pack(fill='both', expand=True, pady=8)
    bar = ttk.Frame(frame)
    bar.pack(fill='x')
    def refresh():
        listing.delete(0, 'end')
        for value in paths:
            listing.insert('end', value)
    def add():
        for value in filedialog.askopenfilenames(title='选择 CSV 文件', filetypes=[('CSV 文件', '*.csv'), ('所有文件', '*.*')]):
            if value not in paths:
                paths.append(value)
        refresh()
    def remove():
        for index in reversed(listing.curselection()):
            paths.pop(index)
        refresh()
    add_button = ttk.Button(bar, text='添加 CSV', command=add)
    add_button.pack(side='left')
    remove_button = ttk.Button(bar, text='移除选中', command=remove)
    remove_button.pack(side='left', padx=6)
    options = ttk.Frame(frame)
    options.pack(fill='x', pady=12)
    ttk.Label(options, text='输入编码').pack(side='left')
    encoding = tk.StringVar(value='utf-8-sig')
    encoding_box = ttk.Combobox(options, textvariable=encoding, values=ENCODINGS, state='readonly', width=16)
    encoding_box.pack(side='left', padx=8)
    ttk.Label(options, text='分隔符').pack(side='left')
    separator = tk.StringVar(value='逗号')
    separator_box = ttk.Combobox(options, textvariable=separator, values=list(SEPARATORS), state='readonly', width=12)
    separator_box.pack(side='left', padx=8)
    output = tk.StringVar()
    output_row = ttk.Frame(frame)
    output_row.pack(fill='x')
    ttk.Label(output_row, text='新输出文件').pack(side='left')
    entry = ttk.Entry(output_row, textvariable=output)
    entry.pack(side='left', fill='x', expand=True, padx=8)
    def browse():
        value = filedialog.asksaveasfilename(title='选择新的合并文件', defaultextension='.csv', filetypes=[('CSV 文件', '*.csv')])
        if value:
            output.set(value)
    browse_button = ttk.Button(output_row, text='选择', command=browse)
    browse_button.pack(side='left')
    status = tk.StringVar(value='原文件保持不变；已有输出文件不会被覆盖。')
    ttk.Label(frame, textvariable=status, wraplength=800).pack(anchor='w', pady=12)
    events, stop = queue.Queue(), threading.Event()
    busy, closing = False, False
    buttons = ttk.Frame(frame)
    buttons.pack(fill='x')
    controls = [add_button, remove_button, encoding_box, separator_box, entry, browse_button]
    def enable(value):
        for widget in controls:
            widget.configure(state=('readonly' if widget in [encoding_box, separator_box] else 'normal') if value else 'disabled')
        start_button.configure(state='normal' if value else 'disabled')
        cancel_button.configure(state='disabled' if value else 'normal')
    def start():
        nonlocal busy
        if not output.get().strip():
            messagebox.showerror('请选择输出', '填写一个尚不存在的输出文件名。')
            return
        args = (list(paths), output.get(), encoding.get(), SEPARATORS[separator.get()])
        busy = True
        stop.clear()
        enable(False)
        status.set('正在合并…')
        def worker():
            try:
                result = merge(args[0], args[1], encoding=args[2], delimiter=args[3], event=stop,
                    progress=lambda done, total, name: events.put(('progress', f'{done}/{total}：{name}')))
                events.put(('done', f'完成：{result["files"]} 个文件，{result["rows"]} 条数据，{result["columns"]} 列。\n{result["output"]}'))
            except (OSError, ValueError, UnicodeError, csv.Error) as exc:
                events.put(('error', str(exc)))
        threading.Thread(target=worker, daemon=True).start()
    start_button = ttk.Button(buttons, text='开始合并', command=start)
    start_button.pack(side='left')
    cancel_button = ttk.Button(buttons, text='取消', command=stop.set, state='disabled')
    cancel_button.pack(side='left', padx=8)
    def poll():
        nonlocal busy
        try:
            while True:
                kind, value = events.get_nowait()
                status.set(value)
                if kind != 'progress':
                    busy = False
                    enable(True)
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
            status.set('正在取消并清理临时文件…')
        else:
            root.destroy()
    root.protocol('WM_DELETE_WINDOW', close)
    poll()
    root.mainloop()

def main():
    if len(sys.argv) == 1:
        gui()
        return 0
    parser = argparse.ArgumentParser(description='将表头相同的 CSV 合并为新文件；无参数打开图形界面。')
    parser.add_argument('files', nargs='+')
    parser.add_argument('--output', required=True)
    parser.add_argument('--encoding', choices=ENCODINGS, default='utf-8-sig')
    parser.add_argument('--delimiter', choices=['comma', 'semicolon', 'tab'], default='comma')
    args = parser.parse_args()
    try:
        result = merge(args.files, args.output, encoding=args.encoding,
            delimiter={'comma': ',', 'semicolon': ';', 'tab': '\t'}[args.delimiter])
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except KeyboardInterrupt:
        print('Cancelled', file=sys.stderr)
        return 130
    except (OSError, ValueError, UnicodeError, csv.Error) as exc:
        print(str(exc), file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
