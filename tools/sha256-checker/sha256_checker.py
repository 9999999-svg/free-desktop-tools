"""Verify download files against a SHA256SUMS manifest; never execute them."""
import argparse
import csv
import hashlib
import os
from pathlib import Path, PureWindowsPath
import queue
import re
import stat
import sys
import threading

for stream in (sys.stdout, sys.stderr):
    if stream is not None and hasattr(stream, 'reconfigure'):
        stream.reconfigure(encoding='utf-8', errors='replace')

def file_hash(path):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
        raise ValueError('链接或重解析点被跳过。')
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('该路径不是普通文件。')
    def identity(value):
        return value.st_size, value.st_mtime_ns, value.st_dev, value.st_ino
    digest = hashlib.sha256()
    with path.open('rb') as source:
        if identity(os.fstat(source.fileno())) != identity(info):
            raise OSError('文件在开始读取前发生变化。')
        while block := source.read(1024 * 1024):
            digest.update(block)
        if identity(os.fstat(source.fileno())) != identity(info):
            raise OSError('文件在读取期间发生变化。')
    if identity(path.lstat()) != identity(info):
        raise OSError('文件在读取后发生变化。')
    return digest.hexdigest()

def check_manifest(manifest, base=None):
    manifest = Path(manifest).absolute()
    directory = Path(base).resolve() if base is not None else manifest.parent.resolve()
    if not directory.is_dir():
        raise ValueError('文件目录不存在。')
    rows = []
    for number, line in enumerate(manifest.read_text(encoding='utf-8-sig').splitlines(), 1):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        row = {'line': number, 'file': '', 'status': 'INVALID', 'expected_sha256': '', 'actual_sha256': '', 'error': ''}
        match = re.fullmatch(r'([0-9a-fA-F]{64}) [ *](.+)', line)
        if not match:
            row['error'] = '应为 64 位 SHA-256、两个空格（或空格和 *）、相对文件名。'
        else:
            expected, name = match.groups()
            row.update(file=name, expected_sha256=expected.lower())
            relative = PureWindowsPath(name)
            try:
                if relative.drive or relative.root or not relative.parts or '..' in relative.parts or any(':' in part for part in relative.parts):
                    raise ValueError('仅接受目录内的相对文件路径。')
                path = directory.joinpath(*relative.parts)
                if not path.resolve().is_relative_to(directory):
                    raise ValueError('解析后的文件路径位于指定目录外。')
            except (OSError, ValueError, RuntimeError) as exc:
                row['error'] = str(exc)
            else:
                try:
                    row['actual_sha256'] = file_hash(path)
                    row['status'] = 'MATCH' if row['actual_sha256'] == row['expected_sha256'] else 'MISMATCH'
                except FileNotFoundError:
                    row.update(status='MISSING', error='文件不存在。')
                except (OSError, ValueError) as exc:
                    row.update(status='ERROR', error=str(exc))
        rows.append(row)
    if not rows:
        raise ValueError('清单没有可校验的条目。')
    return rows

def write_csv(rows, destination):
    columns = ['line', 'file', 'status', 'expected_sha256', 'actual_sha256', 'error']
    with Path(destination).open('x', encoding='utf-8-sig', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            # Treat filenames as text, including names Excel might interpret as formulas.
            escaped = {key: "'" + value if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')) else value for key, value in row.items()}
            writer.writerow(escaped)

def summary(rows):
    matched = sum(row['status'] == 'MATCH' for row in rows)
    return f'{matched}/{len(rows)} 项匹配；{len(rows) - matched} 项需检查'

def launch_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    root = tk.Tk()
    root.title('SHA-256 批量校验器 · 免费开源')
    root.geometry('900x520')
    manifest, directory = tk.StringVar(), tk.StringVar()
    status = tk.StringVar(value='选择 SHA256SUMS.txt；校验只读文件，不运行下载程序。')
    messages, state = queue.Queue(), {'rows': None}
    controls = ttk.Frame(root, padding=12)
    controls.pack(fill='x')
    ttk.Label(controls, text='SHA-256 清单').grid(row=0, column=0, sticky='w')
    ttk.Entry(controls, textvariable=manifest, width=70).grid(row=0, column=1, padx=8, sticky='ew')
    ttk.Button(controls, text='选择…', command=lambda: manifest.set(filedialog.askopenfilename() or manifest.get())).grid(row=0, column=2)
    ttk.Label(controls, text='文件目录（可空）').grid(row=1, column=0, pady=10, sticky='w')
    ttk.Entry(controls, textvariable=directory).grid(row=1, column=1, padx=8, sticky='ew')
    ttk.Button(controls, text='选择…', command=lambda: directory.set(filedialog.askdirectory() or directory.get())).grid(row=1, column=2)
    controls.columnconfigure(1, weight=1)
    buttons = ttk.Frame(root, padding=(12, 0))
    buttons.pack(fill='x')
    def worker(path, folder):
        try:
            messages.put(('done', check_manifest(path, folder or None)))
        except (OSError, ValueError, UnicodeError) as exc:
            messages.put(('error', str(exc)))
    def start():
        if not manifest.get().strip():
            messagebox.showerror('请选择清单', '请先选择 SHA256SUMS.txt。', parent=root)
            return
        state['rows'] = None
        table.delete(*table.get_children())
        start_button.config(state='disabled')
        export_button.config(state='disabled')
        status.set('校验中…')
        threading.Thread(target=worker, args=(manifest.get(), directory.get()), daemon=True).start()
    def export():
        path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV 报告', '*.csv')], confirmoverwrite=False)
        if path:
            try:
                write_csv(state['rows'], path)
                status.set('报告已保存：' + path)
            except OSError as exc:
                messagebox.showerror('未保存', str(exc), parent=root)
    start_button = ttk.Button(buttons, text='开始校验', command=start)
    start_button.pack(side='left')
    export_button = ttk.Button(buttons, text='导出 CSV', state='disabled', command=export)
    export_button.pack(side='left', padx=8)
    panel = ttk.Frame(root, padding=12)
    panel.pack(fill='both', expand=True)
    table = ttk.Treeview(panel, columns=('line', 'file', 'status'), show='headings')
    for name, label, width in [('line', '清单行', 70), ('file', '相对文件名', 630), ('status', '结果', 140)]:
        table.heading(name, text=label)
        table.column(name, width=width, stretch=name == 'file')
    scrollbar = ttk.Scrollbar(panel, command=table.yview)
    table.config(yscrollcommand=scrollbar.set)
    table.pack(side='left', fill='both', expand=True)
    scrollbar.pack(side='right', fill='y')
    ttk.Label(root, textvariable=status, padding=12, wraplength=870).pack(fill='x')
    labels = {'MATCH': '匹配', 'MISMATCH': '不匹配', 'MISSING': '缺失', 'INVALID': '清单有误', 'ERROR': '读取错误'}
    def poll():
        try:
            kind, value = messages.get_nowait()
        except queue.Empty:
            pass
        else:
            start_button.config(state='normal')
            if kind == 'done':
                state['rows'] = value
                export_button.config(state='normal')
                # ponytail: preview at most 1000 entries; CSV contains every result.
                for row in value[:1000]:
                    table.insert('', 'end', values=(row['line'], row['file'], labels[row['status']]))
                text = summary(value)
                if len(value) > 1000:
                    text += '；预览前 1000 项，CSV 包含全部结果'
                status.set(text)
            else:
                status.set('未完成校验。')
                messagebox.showerror('校验失败', value, parent=root)
        root.after(150, poll)
    root.after(150, poll)
    root.mainloop()

def main():
    parser = argparse.ArgumentParser(description='按 SHA256SUMS 清单批量核对下载完整性，只读、不执行文件。')
    parser.add_argument('manifest', nargs='?', type=Path)
    parser.add_argument('--base', type=Path, help='文件目录，默认清单所在目录')
    parser.add_argument('--csv', type=Path, help='新 CSV 报告路径，不覆盖已有文件')
    args = parser.parse_args()
    if args.manifest is None:
        if args.base or args.csv:
            parser.error('请指定清单文件。')
        launch_gui()
        return 0
    try:
        if args.csv and args.csv.exists():
            raise FileExistsError('报告已存在，请选新名称。')
        rows = check_manifest(args.manifest, args.base)
        if args.csv:
            write_csv(rows, args.csv)
        print(summary(rows))
        for row in rows:
            print(f"{row['status']} · 行 {row['line']} · {row['file']} · {row['error']}")
        return int(any(row['status'] != 'MATCH' for row in rows))
    except (OSError, ValueError, UnicodeError) as exc:
        print('错误：' + str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('已取消。', file=sys.stderr)
        return 130

if __name__ == '__main__':
    raise SystemExit(main())
