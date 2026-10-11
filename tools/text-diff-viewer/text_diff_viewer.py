"""Compare two ordinary text files and export a new unified diff."""
import argparse
import difflib
import json
import os
from pathlib import Path
import queue
import re
import stat
import sys
import tempfile
import threading

MAX_INPUT = 1024 * 1024
MAX_LINES = 10000
MAX_LINE = 10000
MAX_OUTPUT = 10 * 1024 * 1024
ENCODINGS = ['utf-8-sig', 'gbk', 'gb18030', 'utf-16']

def cancel(event):
    if event is not None and event.is_set():
        raise InterruptedError('已取消，未保存差异文件。')

def linked(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)

def ordinary_directory(path):
    for parent in (path, *path.parents):
        info = parent.lstat()
        if linked(info) or not stat.S_ISDIR(info.st_mode):
            raise ValueError('路径包含链接、目录联接或非文件夹。')

def identity(info):
    value = info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns
    return value if os.name == 'nt' else value + (info.st_ctime_ns,)

def read_lines(path, encoding, event):
    ordinary_directory(path.parent)
    before = path.lstat()
    if linked(before) or not stat.S_ISREG(before.st_mode) or before.st_size > MAX_INPUT:
        raise ValueError('输入必须是普通文件，最多 1 MiB。')
    cancel(event)
    with path.open('rb') as stream:
        if identity(os.fstat(stream.fileno())) != identity(before):
            raise OSError('输入在打开时发生变化。')
        data = stream.read(MAX_INPUT + 1)
        if len(data) > MAX_INPUT or identity(os.fstat(stream.fileno())) != identity(before):
            raise OSError('输入在读取期间变化或超限。')
    if identity(path.lstat()) != identity(before):
        raise OSError('输入在读取后发生变化。')
    text = data.decode(encoding, errors='strict')
    if '\x00' in text:
        raise ValueError('文本含 NUL，可能是二进制文件。')
    parts = re.split(r'\r\n|\r|\n', text)
    ended = text.endswith(('\r', '\n'))
    if ended:
        parts.pop()
    if not text:
        parts = []
    if len(parts) > MAX_LINES or any(len(line) > MAX_LINE for line in parts):
        raise ValueError('最多 10000 行，每行最多 10000 字符。')
    lines = [line + '\n' for line in parts]
    if lines and not ended:
        lines[-1] = lines[-1][:-1]
    cancel(event)
    return lines

def compare(left, right, output=None, *, left_encoding='utf-8-sig', right_encoding='utf-8-sig', context=3, event=None):
    if left_encoding not in ENCODINGS or right_encoding not in ENCODINGS:
        raise ValueError('编码不在支持列表中。')
    if not 0 <= context <= 20:
        raise ValueError('上下文行数必须在 0 至 20 之间。')
    paths = Path(left).absolute(), Path(right).absolute()
    target = Path(output).absolute() if output is not None else None
    if target is not None:
        ordinary_directory(target.parent)
        if os.path.lexists(target):
            raise FileExistsError('输出已存在，请选择新文件名。')
    a = read_lines(paths[0], left_encoding, event)
    b = read_lines(paths[1], right_encoding, event)
    pieces, size = [], 0
    for line in difflib.unified_diff(a, b, fromfile='left', tofile='right', n=context):
        cancel(event)
        if not line.endswith('\n'):
            line += '\n\\ No newline at end of file\n'
        size += len(line.encode('utf-8'))
        if size > MAX_OUTPUT:
            raise ValueError('差异输出超过 10 MiB。')
        pieces.append(line)
    payload = ''.join(pieces).encode('utf-8')
    cancel(event)
    report = {'same': a == b, 'left_lines': len(a), 'right_lines': len(b),
        'diff_bytes': len(payload), 'preview': payload.decode('utf-8')[:50000]}
    if target is not None:
        fd, name = tempfile.mkstemp(prefix='.text-diff-', suffix='.tmp', dir=target.parent)
        temporary = Path(name)
        try:
            with os.fdopen(fd, 'wb') as stream:
                for start in range(0, len(payload), 1024 * 1024):
                    cancel(event)
                    stream.write(payload[start:start + 1024 * 1024])
                stream.flush()
                os.fsync(stream.fileno())
            cancel(event)
            if os.name == 'nt':
                os.rename(temporary, target)
            else:
                os.link(temporary, target)
                temporary.unlink()
            report['output'] = str(target)
        finally:
            if temporary.exists():
                temporary.unlink()
    return report

def gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    root = tk.Tk()
    root.title('文本差异查看器')
    root.geometry('960x700')
    frame = ttk.Frame(root, padding=16)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='比较两份文本的内容和末行换行；CRLF/LF/CR 样式差异忽略，源文件保留。').pack(anchor='w')
    paths, encodings, controls = [], [], []
    for label in ['左侧输入', '右侧输入']:
        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=8)
        ttk.Label(bar, text=label, width=9).pack(side='left')
        value, encoding = tk.StringVar(), tk.StringVar(value='utf-8-sig')
        paths.append(value)
        encodings.append(encoding)
        entry = ttk.Entry(bar, textvariable=value)
        entry.pack(side='left', fill='x', expand=True)
        def choose(v=value):
            selected = filedialog.askopenfilename()
            if selected:
                v.set(selected)
        button = ttk.Button(bar, text='选择', command=choose)
        button.pack(side='left', padx=8)
        box = ttk.Combobox(bar, textvariable=encoding, values=ENCODINGS, state='readonly', width=12)
        box.pack(side='left')
        controls.extend([entry, button, box])
    preview = tk.Text(frame, wrap='none', state='disabled')
    preview.pack(fill='both', expand=True, pady=8)
    status = tk.StringVar(value='每份最多 1 MiB/10000 行；上下文 3 行，预览最多 50000 字符。保存时重新比较。')
    ttk.Label(frame, textvariable=status, wraplength=910).pack(anchor='w', pady=8)
    messages, event = queue.Queue(), threading.Event()
    state = {'busy': False, 'closing': False}
    def start(save=False):
        if not all(p.get().strip() for p in paths):
            messagebox.showerror('缺少输入', '请选择两份文本文件。')
            return
        target = filedialog.asksaveasfilename(title='保存到新的差异文件', defaultextension='.diff') if save else None
        if save and not target:
            return
        args = paths[0].get(), paths[1].get(), target
        kwargs = dict(left_encoding=encodings[0].get(), right_encoding=encodings[1].get(), event=event)
        state['busy'] = True
        event.clear()
        for control in controls:
            control.configure(state='disabled')
        stop.configure(state='normal')
        status.set('正在读取并比较文本…')
        def worker():
            try:
                messages.put(('ok', compare(*args, **kwargs)))
            except Exception as error:
                messages.put(('error', str(error)))
        threading.Thread(target=worker, daemon=True).start()
    bar = ttk.Frame(frame)
    bar.pack(fill='x')
    for label, save in [('比较 / 预览', False), ('导出新差异文件', True)]:
        button = ttk.Button(bar, text=label, command=lambda s=save: start(s))
        button.pack(side='left', padx=4)
        controls.append(button)
    stop = ttk.Button(bar, text='取消', command=event.set, state='disabled')
    stop.pack(side='left', padx=4)
    def close():
        if state['busy']:
            state['closing'] = True
            event.set()
            status.set('正在取消，等待比较及临时文件清理…')
        else:
            root.destroy()
    def poll():
        try:
            kind, data = messages.get_nowait()
        except queue.Empty:
            root.after(100, poll)
            return
        state['busy'] = False
        if state['closing']:
            root.destroy()
            return
        for control in controls:
            control.configure(state='readonly' if isinstance(control, ttk.Combobox) else 'normal')
        stop.configure(state='disabled')
        preview.configure(state='normal')
        preview.delete('1.0', 'end')
        if kind == 'error':
            status.set(data)
        else:
            preview.insert('1.0', data['preview'])
            status.set(('文本相同。' if data['same'] else f"文本不同，差异 {data['diff_bytes']} 字节。") + ('已保存：' + data['output'] if 'output' in data else '预览完成。'))
        preview.configure(state='disabled')
        root.after(100, poll)
    root.protocol('WM_DELETE_WINDOW', close)
    root.after(100, poll)
    root.mainloop()

def main():
    parser = argparse.ArgumentParser(description='只读比较两份文本，导出新 unified diff。')
    parser.add_argument('left')
    parser.add_argument('right')
    parser.add_argument('--output')
    parser.add_argument('--left-encoding', choices=ENCODINGS, default='utf-8-sig')
    parser.add_argument('--right-encoding', choices=ENCODINGS, default='utf-8-sig')
    parser.add_argument('--context', type=int, default=3)
    args = parser.parse_args()
    try:
        report = compare(args.left, args.right, args.output, left_encoding=args.left_encoding, right_encoding=args.right_encoding, context=args.context)
        print(json.dumps(report, ensure_ascii=True))
        return 0 if report['same'] else 1
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=True), file=sys.stderr)
        return 2

if __name__ == '__main__':
    if len(sys.argv) == 1:
        gui()
    else:
        raise SystemExit(main())
