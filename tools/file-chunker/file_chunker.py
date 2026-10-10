"""Split files and reassemble verified chunks; originals are never edited."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import stat
import sys
import tempfile
import threading
import time

MAX_CHUNK = 4 * 1024 ** 3
MAX_PARTS = 100000
BLOCK = 1024 * 1024
HEX = re.compile(r'[0-9a-f]{64}')

def cancelled(event):
    if event is not None and event.is_set():
        raise InterruptedError('已取消；原文件未改动。')

def identity(info):
    value = info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns
    # Windows stat/fstat can expose different ctime semantics for the same unchanged file.
    return value if os.name == 'nt' else value + (info.st_ctime_ns,)

def linked(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)

def regular_file(path):
    info = path.lstat()
    if linked(info) or not stat.S_ISREG(info.st_mode):
        raise ValueError('只接受普通文件，拒绝链接或重解析点：' + str(path))
    return info

def stable(path, file, before):
    if identity(os.fstat(file.fileno())) != identity(before) or identity(path.lstat()) != identity(before):
        raise OSError('输入文件在操作期间发生变化：' + str(path))

def publish_file(temporary, output):
    # Windows rename refuses an existing target; hard-link publication does the same on POSIX.
    if os.name == 'nt':
        os.rename(temporary, output)
    else:
        os.link(temporary, output)
        os.unlink(temporary)

def split_file(source, destination, chunk_bytes, *, event=None, progress=None):
    source, destination = Path(source).absolute(), Path(destination).absolute()
    before = regular_file(source)
    if type(chunk_bytes) is not int or not 1 <= chunk_bytes <= MAX_CHUNK:
        raise ValueError('分块大小必须为 1 字节至 4 GiB。')
    count = max(1, (before.st_size + chunk_bytes - 1) // chunk_bytes)
    if count > MAX_PARTS:
        raise ValueError('分块超过 100000 个，请增大每块大小。')
    cancelled(event)
    destination.mkdir()  # Exclusive new directory: no existing files can be overwritten.
    parts, whole, done = [], hashlib.sha256(), 0
    with source.open('rb') as input_file:
        stable(source, input_file, before)
        for number in range(1, count + 1):
            cancelled(event)
            name = f'part-{number:06d}.bin'
            digest, size = hashlib.sha256(), 0
            with (destination / name).open('xb') as output_file:
                remaining = min(chunk_bytes, before.st_size - done)
                while remaining:
                    cancelled(event)
                    block = input_file.read(min(BLOCK, remaining))
                    if not block:
                        raise OSError('输入文件提前结束。')
                    output_file.write(block)
                    digest.update(block)
                    whole.update(block)
                    remaining -= len(block)
                    size += len(block)
                    done += len(block)
                    if progress:
                        progress(done, before.st_size)
            parts.append(dict(name=name, bytes=size, sha256=digest.hexdigest()))
        if input_file.read(1):
            raise OSError('输入文件长度在分割期间增加。')
        stable(source, input_file, before)
    cancelled(event)
    manifest = dict(format='file-chunker', version=1, original_name=source.name,
        original_bytes=before.st_size, original_sha256=whole.hexdigest(), chunk_bytes=chunk_bytes, parts=parts)
    temporary = destination / 'manifest.json.tmp'
    with temporary.open('x', encoding='utf-8', newline='\n') as output_file:
        json.dump(manifest, output_file, ensure_ascii=False, indent=2)
        output_file.write('\n')
    publish_file(temporary, destination / 'manifest.json')
    return manifest

def read_manifest(path):
    path = Path(path).absolute()
    root = path.parent
    root_info = root.lstat()
    if linked(root_info) or not stat.S_ISDIR(root_info.st_mode):
        raise ValueError('分块文件夹不能是链接或目录联接。')
    before = regular_file(path)
    if before.st_size > 16 * 1024 ** 2:
        raise ValueError('清单超过 16 MiB。')
    with path.open('rb') as input_file:
        stable(path, input_file, before)
        data = input_file.read(16 * 1024 ** 2 + 1)
        stable(path, input_file, before)
    if len(data) > 16 * 1024 ** 2:
        raise ValueError('清单超过 16 MiB。')
    try:
        manifest = json.loads(data.decode('utf-8-sig'))
    except (ValueError, RecursionError) as exc:
        raise ValueError('清单不是有效的 UTF-8 JSON。') from exc
    if not isinstance(manifest, dict) or manifest.get('format') != 'file-chunker' or type(manifest.get('version')) is not int or manifest['version'] != 1:
        raise ValueError('不支持的分块清单格式。')
    size, chunk = manifest.get('original_bytes'), manifest.get('chunk_bytes')
    if type(size) is not int or size < 0 or type(chunk) is not int or not 1 <= chunk <= MAX_CHUNK:
        raise ValueError('清单的文件大小或分块大小无效。')
    parts = manifest.get('parts')
    if not isinstance(parts, list) or not 1 <= len(parts) <= MAX_PARTS or len(parts) != max(1, (size + chunk - 1) // chunk):
        raise ValueError('清单的分块数量不符合文件大小。')
    if not isinstance(manifest.get('original_sha256'), str) or not HEX.fullmatch(manifest['original_sha256']):
        raise ValueError('完整文件的 SHA-256 无效。')
    checked = []
    for number, part in enumerate(parts, 1):
        if not isinstance(part, dict) or part.get('name') != f'part-{number:06d}.bin':
            raise ValueError('分块名称或顺序无效；不允许清单跳转路径。')
        expected = min(chunk, size - (number - 1) * chunk)
        if type(part.get('bytes')) is not int or part['bytes'] != expected:
            raise ValueError('清单中的分块大小无效。')
        if not isinstance(part.get('sha256'), str) or not HEX.fullmatch(part['sha256']):
            raise ValueError('分块 SHA-256 无效。')
        location = root / part['name']
        info = regular_file(location)
        if info.st_size != part['bytes']:
            raise ValueError('分块大小不符合清单：' + part['name'])
        checked.append((part, location, info))
    return manifest, checked

def join_file(manifest_path, output, *, event=None, progress=None):
    output = Path(output).absolute()
    if os.path.lexists(output):
        raise FileExistsError('输出文件已存在，请选择新路径。')
    manifest, parts = read_manifest(manifest_path)
    if output.parent.resolve() == Path(manifest_path).parent.resolve():
        raise ValueError('请将合并文件保存到分块文件夹之外。')
    cancelled(event)
    temporary = None
    whole, done = hashlib.sha256(), 0
    try:
        with tempfile.NamedTemporaryFile(mode='wb', prefix='.file-chunker-', suffix='.tmp', dir=output.parent, delete=False) as target:
            temporary = Path(target.name)
            for part, location, before in parts:
                cancelled(event)
                digest, size = hashlib.sha256(), 0
                with location.open('rb') as source:
                    stable(location, source, before)
                    while block := source.read(BLOCK):
                        cancelled(event)
                        target.write(block)
                        digest.update(block)
                        whole.update(block)
                        size += len(block)
                        done += len(block)
                        if progress:
                            progress(done, manifest['original_bytes'])
                    stable(location, source, before)
                if size != part['bytes'] or digest.hexdigest() != part['sha256']:
                    raise ValueError('分块内容校验失败：' + part['name'])
            if done != manifest['original_bytes'] or whole.hexdigest() != manifest['original_sha256']:
                raise ValueError('合并文件的大小或 SHA-256 不符合清单。')
            cancelled(event)
            target.flush()
            os.fsync(target.fileno())
        publish_file(temporary, output)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return manifest

def launch_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    root = tk.Tk()
    root.title('大文件分割与合并器 · 免费开源')
    root.geometry('860x450')
    status = tk.StringVar(value='分割写入新文件夹；合并校验所有分块后保存新文件。原文件保持不变。')
    messages, stop = queue.Queue(), threading.Event()
    state = {'busy': False, 'closing': False}
    controls, begin_buttons = [], []
    notebook = ttk.Notebook(root)
    notebook.pack(fill='both', expand=True, padx=12, pady=12)
    values = [tk.StringVar() for _ in range(4)]
    chunk = tk.StringVar(value='100')
    def select_source():
        path = filedialog.askopenfilename()
        if path:
            values[0].set(path)
            values[1].set(path + '.parts')
    def select_manifest():
        path = filedialog.askopenfilename(filetypes=[('分块清单', '*.json'), ('所有文件', '*')])
        if path:
            values[2].set(path)
            values[3].set(str(Path(path).parent.parent / '合并后的文件.bin'))
    def select_destination():
        path = filedialog.askdirectory()
        if path:
            values[1].set(str(Path(path) / '新分块文件夹'))
    selectors = [select_source, select_destination, select_manifest,
        lambda: values[3].set(filedialog.asksaveasfilename(confirmoverwrite=False) or values[3].get())]
    for tab, title, labels, offset in [(ttk.Frame(notebook, padding=18), '分割', ['原文件', '新的分块文件夹'], 0),
            (ttk.Frame(notebook, padding=18), '合并', ['manifest.json 清单', '新的输出文件'], 2)]:
        notebook.add(tab, text=title)
        tab.columnconfigure(1, weight=1)
        for row, label in enumerate(labels):
            index = offset + row
            ttk.Label(tab, text=label).grid(row=row, column=0, sticky='w', pady=8)
            field = ttk.Entry(tab, textvariable=values[index])
            field.grid(row=row, column=1, sticky='ew', padx=8)
            choose = ttk.Button(tab, text='选择…', command=selectors[index])
            choose.grid(row=row, column=2)
            controls.extend([field, choose])
        if offset == 0:
            ttk.Label(tab, text='每块 MiB').grid(row=2, column=0, sticky='w', pady=8)
            field = ttk.Entry(tab, textvariable=chunk, width=12)
            field.grid(row=2, column=1, sticky='w', padx=8)
            controls.append(field)
            ttk.Label(tab, text='1–4096 MiB；1 MiB = 1048576 字节').grid(row=3, column=1, sticky='w', padx=8)
        else:
            ttk.Label(tab, text='将 manifest.json 与全部 part-*.bin 放在同一文件夹。\n可自行选择输出文件名和扩展名。清单不是身份认证或加密。').grid(row=2, column=1, sticky='w', padx=8, pady=8)
        button = ttk.Button(tab, text='开始分割' if offset == 0 else '校验并合并', command=lambda mode=offset: start(mode))
        button.grid(row=4, column=1, sticky='w', padx=8, pady=12)
        begin_buttons.append(button)
    bar = ttk.Progressbar(root, maximum=100)
    bar.pack(fill='x', padx=18)
    cancel = ttk.Button(root, text='取消', command=stop.set, state='disabled')
    cancel.pack(pady=8)
    ttk.Label(root, textvariable=status, padding=12, wraplength=825).pack(fill='x')
    def worker(mode, source, target, size):
        last = [0.0]
        def progress(done, total):
            now = time.monotonic()
            if now - last[0] >= 0.15 or done == total:
                messages.put(('progress', (done, total)))
                last[0] = now
        try:
            result = split_file(source, target, size, event=stop, progress=progress) if mode == 0 else join_file(source, target, event=stop, progress=progress)
            messages.put(('done', f"完成：{len(result['parts'])} 块，{result['original_bytes']:,} 字节\n输出：{target}"))
        except (OSError, ValueError) as exc:
            note = '；分割未完成时，新文件夹中的部分分块保留，可手动删除。' if mode == 0 else ''
            messages.put(('error', str(exc) + note))
    def start(mode):
        source, target = values[mode].get(), values[mode + 1].get()
        try:
            size = int(chunk.get()) * 1024 ** 2 if mode == 0 else 0
            if mode == 0 and not 1024 ** 2 <= size <= MAX_CHUNK:
                raise ValueError('每块大小应为 1–4096 MiB 的整数。')
            if not source.strip() or not target.strip():
                raise ValueError('请选择输入与新的输出路径。')
        except ValueError as exc:
            messagebox.showerror('未开始', str(exc), parent=root)
            return
        stop.clear()
        state['busy'] = True
        for widget in controls + begin_buttons:
            widget.config(state='disabled')
        cancel.config(state='normal')
        bar['value'] = 0
        status.set('分割中…' if mode == 0 else '校验并合并中…')
        threading.Thread(target=worker, args=(mode, source, target, size), daemon=True).start()
    def close():
        if state['busy']:
            state['closing'] = True
            stop.set()
            status.set('取消中，清理临时输出后关闭…')
        else:
            root.destroy()
    def poll():
        while True:
            try:
                kind, value = messages.get_nowait()
            except queue.Empty:
                break
            if kind == 'progress':
                done, total = value
                bar['value'] = 100 * done / total if total else 100
            else:
                state['busy'] = False
                for widget in controls + begin_buttons:
                    widget.config(state='normal')
                cancel.config(state='disabled')
                status.set(value)
                if kind == 'done':
                    bar['value'] = 100
                if state['closing']:
                    root.destroy()
                    return
        root.after(150, poll)
    root.protocol('WM_DELETE_WINDOW', close)
    root.after(150, poll)
    root.mainloop()

def main():
    parser = argparse.ArgumentParser(description='免费大文件分割与校验合并；拒绝覆盖已有输出。')
    sub = parser.add_subparsers(dest='action')
    splitter = sub.add_parser('split', help='分割到新的文件夹')
    splitter.add_argument('source', type=Path)
    splitter.add_argument('destination', type=Path)
    splitter.add_argument('--chunk-mib', type=int, default=100, help='每块 1–4096 MiB，默认 100')
    joiner = sub.add_parser('join', help='校验清单和分块，合并到新文件')
    joiner.add_argument('manifest', type=Path)
    joiner.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.action is None:
        launch_gui()
        return 0
    try:
        if args.action == 'split':
            if not 1 <= args.chunk_mib <= 4096:
                raise ValueError('每块大小应为 1–4096 MiB。')
            result = split_file(args.source, args.destination, args.chunk_mib * 1024 ** 2)
        else:
            result = join_file(args.manifest, args.output)
        print(f"完成：{len(result['parts'])} 块，{result['original_bytes']:,} 字节；SHA-256 {result['original_sha256']}")
        return 0
    except KeyboardInterrupt:
        print('已取消。分割时的部分输出保留；合并临时输出已清理。', file=sys.stderr)
        return 130
    except (OSError, ValueError) as exc:
        print('错误：' + str(exc), file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
