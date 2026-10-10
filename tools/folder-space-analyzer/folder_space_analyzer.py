"""Read-only logical-size totals per immediate subfolder and largest files."""
import argparse
import csv
import heapq
import json
import os
from pathlib import Path
import queue
import stat
import sys
import tempfile
import threading

MAX_ENTRIES = 1000000
MAX_ISSUES = 1000
FIELDS = ['kind', 'path', 'bytes', 'files', 'share_percent', 'status', 'detail']

def cancel(event):
    if event is not None and event.is_set():
        raise InterruptedError('已取消，未导出报告。')

def linked(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)

def ordinary_directory(path):
    for parent in (path, *path.parents):
        info = parent.lstat()
        if linked(info) or not stat.S_ISDIR(info.st_mode):
            raise ValueError('根目录路径包含链接、目录联接或非文件夹。')

def scan(folder, *, top=50, event=None, progress=None):
    if not 1 <= top <= 1000:
        raise ValueError('大文件数量必须在 1 至 1000 之间。')
    root = Path(folder).absolute()
    ordinary_directory(root)
    root_info = root.lstat()
    stack = [(root, None, (root_info.st_dev, root_info.st_ino))]
    groups, heap, issues = {}, [], []
    visited, issue_count, skipped, errors, total, files = 0, 0, 0, 0, 0, 0
    limit = False
    def issue(path, status, detail):
        nonlocal issue_count, skipped, errors
        issue_count += 1
        skipped += status == 'SKIPPED'
        errors += status == 'ERROR'
        if len(issues) < MAX_ISSUES:
            issues.append({'path': path.relative_to(root).as_posix(), 'status': status, 'detail': detail})
    while stack and not limit:
        cancel(event)
        directory, group, expected = stack.pop()
        try:
            before = directory.lstat()
            if linked(before) or not stat.S_ISDIR(before.st_mode) or (before.st_dev, before.st_ino) != expected:
                issue(directory, 'ERROR', '目录在扫描前变化或变成链接。')
                continue
            with os.scandir(directory) as entries:
                for entry in entries:
                    cancel(event)
                    if visited >= MAX_ENTRIES:
                        limit = True
                        issue(directory, 'ERROR', '扫描达到 1000000 条目上限，统计不完整。')
                        break
                    visited += 1
                    path = directory / entry.name
                    try:
                        item = path.lstat()
                        if linked(item):
                            issue(path, 'SKIPPED', '跳过链接、重解析点或目录联接。')
                        elif stat.S_ISDIR(item.st_mode):
                            bucket = entry.name if directory == root else group
                            groups.setdefault(bucket, {'path': bucket, 'kind': 'folder', 'bytes': 0, 'files': 0})
                            stack.append((path, bucket, (item.st_dev, item.st_ino)))
                        elif stat.S_ISREG(item.st_mode):
                            bucket = group
                            value = groups.setdefault(bucket, {'path': '（根目录文件）' if bucket is None else bucket,
                                'kind': 'root-files' if bucket is None else 'folder', 'bytes': 0, 'files': 0})
                            value['bytes'] += item.st_size
                            value['files'] += 1
                            files += 1
                            total += item.st_size
                            candidate = item.st_size, path.relative_to(root).as_posix()
                            if len(heap) < top:
                                heapq.heappush(heap, candidate)
                            elif candidate > heap[0]:
                                heapq.heapreplace(heap, candidate)
                        else:
                            issue(path, 'SKIPPED', '非普通文件。')
                    except OSError as error:
                        issue(path, 'ERROR', str(error))
                    if progress and visited % 1000 == 0:
                        progress(visited, files, total)
            after = directory.lstat()
            if (before.st_dev, before.st_ino, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_mtime_ns) or linked(after):
                issue(directory, 'ERROR', '目录在枚举期间发生变化，统计不是一致快照。')
        except OSError as error:
            issue(directory, 'ERROR', str(error))
    cancel(event)
    rows = sorted(groups.values(), key=lambda row: (-row['bytes'], row['path'].casefold()))
    for row in rows:
        row['share_percent'] = round(100 * row['bytes'] / total, 3) if total else 0
    return {'root': str(root), 'total_bytes': total, 'files': files, 'visited_entries': visited,
        'complete': issue_count == 0, 'skipped': skipped, 'errors': errors, 'limit_reached': limit,
        'groups': rows, 'largest_files': [{'path': name, 'bytes': size} for size, name in sorted(heap, reverse=True)],
        'issues': issues, 'issue_count': issue_count, 'issues_truncated': issue_count > len(issues)}

def write_csv(report, output, event=None):
    target = Path(output).absolute()
    ordinary_directory(target.parent)
    if os.path.lexists(target):
        raise FileExistsError('CSV 已存在；请选择新文件名。')
    cancel(event)
    fd, name = tempfile.mkstemp(prefix='.folder-space-', suffix='.tmp', dir=target.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8-sig', newline='') as destination:
            writer = csv.DictWriter(destination, fieldnames=FIELDS)
            writer.writeheader()
            def emit(values):
                cancel(event)
                writer.writerow({key: "'" + value if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')) else value for key, value in values.items()})
            emit({'kind': 'summary', 'path': report['root'], 'bytes': report['total_bytes'], 'files': report['files'],
                'status': 'OK' if report['complete'] else 'INCOMPLETE',
                'detail': f"跳过 {report['skipped']}；错误 {report['errors']}；问题记录 {len(report['issues'])}/{report['issue_count']}；逻辑大小，硬链接按路径重复计数。"})
            for row in report['groups']:
                emit({**row, 'status': 'OK' if report['complete'] else 'INCOMPLETE'})
            for row in report['largest_files']:
                emit({**row, 'kind': 'large-file', 'status': 'OK'})
            for row in report['issues']:
                emit({**row, 'kind': 'issue'})
            destination.flush()
            os.fsync(destination.fileno())
        cancel(event)
        if os.name == 'nt':
            os.rename(temporary, target)
        else:
            os.link(temporary, target)
            temporary.unlink()
    finally:
        if temporary.exists():
            temporary.unlink()

def gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    root = tk.Tk()
    root.title('文件夹空间分析器')
    root.geometry('960x680')
    frame = ttk.Frame(root, padding=16)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='按直接子文件夹汇总所有后代文件的逻辑大小，并列出大文件；只读扫描。').pack(anchor='w')
    folder, top = tk.StringVar(), tk.StringVar(value='50')
    bar = ttk.Frame(frame)
    bar.pack(fill='x', pady=10)
    entry = ttk.Entry(bar, textvariable=folder)
    entry.pack(side='left', fill='x', expand=True)
    def choose():
        value = filedialog.askdirectory(title='选择要分析的文件夹')
        if value:
            folder.set(value)
    choose_button = ttk.Button(bar, text='选择文件夹', command=choose)
    choose_button.pack(side='left', padx=8)
    ttk.Label(bar, text='大文件数量').pack(side='left')
    box = ttk.Spinbox(bar, from_=1, to=1000, textvariable=top, width=6)
    box.pack(side='left', padx=8)
    notebook = ttk.Notebook(frame)
    notebook.pack(fill='both', expand=True)
    trees = []
    for label in ['子文件夹汇总', '大文件', '跳过与错误']:
        page = ttk.Frame(notebook)
        notebook.add(page, text=label)
        tree = ttk.Treeview(page, columns=('bytes', 'files', 'detail'), show='tree headings')
        tree.heading('#0', text='名称或相对路径')
        tree.column('#0', width=390)
        for key, title, width in [('bytes', '字节', 130), ('files', '文件数', 70), ('detail', '占比 / 状态', 230)]:
            tree.heading(key, text=title)
            tree.column(key, width=width)
        scroll = ttk.Scrollbar(page, command=tree.yview)
        scroll.pack(side='right', fill='y')
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(fill='both', expand=True)
        trees.append(tree)
    status = tk.StringVar(value='不是物理磁盘占用；硬链接按路径计数，链接/重解析点跳过，最多扫描 1000000 条目。')
    ttk.Label(frame, textvariable=status, wraplength=900).pack(anchor='w', pady=8)
    ttk.Label(frame, text='各表最多显示 1000 行；CSV 包含全部汇总、选定数量的大文件和最多 1000 条问题记录。').pack(anchor='w')
    messages, event = queue.Queue(), threading.Event()
    state = {'busy': False, 'closing': False, 'report': None}
    controls = [entry, choose_button, box]
    def invalidate(*args):
        if not state['busy']:
            state['report'] = None
            export.configure(state='disabled')
            for tree in trees:
                tree.delete(*tree.get_children())
            status.set('路径或数量已变化，请重新分析。')
    def start():
        if not folder.get().strip():
            messagebox.showerror('缺少路径', '请选择文件夹。')
            return
        try:
            count = int(top.get())
            if not 1 <= count <= 1000:
                raise ValueError()
        except ValueError:
            messagebox.showerror('数量错误', '大文件数量必须是 1 至 1000。')
            return
        path = folder.get()
        state['busy'], state['report'] = True, None
        event.clear()
        for control in controls:
            control.configure(state='disabled')
        export.configure(state='disabled')
        stop.configure(state='normal')
        status.set('正在扫描文件元数据…')
        for tree in trees:
            tree.delete(*tree.get_children())
        def progress(visited, files, size):
            messages.put(('progress', (visited, files, size)))
        def worker():
            try:
                report = scan(path, top=count, event=event, progress=progress)
                messages.put(('scan', report))
            except Exception as error:
                messages.put(('error', str(error)))
        threading.Thread(target=worker, daemon=True).start()
    def save():
        value = filedialog.asksaveasfilename(title='导出到尚不存在的新 CSV', defaultextension='.csv')
        if not value:
            return
        report = state['report']
        state['busy'] = True
        event.clear()
        for control in controls:
            control.configure(state='disabled')
        export.configure(state='disabled')
        stop.configure(state='normal')
        def worker():
            try:
                write_csv(report, value, event)
                messages.put(('saved', value))
            except Exception as error:
                messages.put(('error', str(error)))
        threading.Thread(target=worker, daemon=True).start()
    bar = ttk.Frame(frame)
    bar.pack(fill='x', pady=10)
    button = ttk.Button(bar, text='开始分析', command=start)
    button.pack(side='left', padx=4)
    controls.append(button)
    export = ttk.Button(bar, text='导出 CSV', command=save, state='disabled')
    export.pack(side='left', padx=4)
    stop = ttk.Button(bar, text='取消', command=event.set, state='disabled')
    stop.pack(side='left', padx=4)
    folder.trace_add('write', invalidate)
    top.trace_add('write', invalidate)
    def close():
        if state['busy']:
            state['closing'] = True
            event.set()
            status.set('正在取消，等待操作结束…')
        else:
            root.destroy()
    def poll():
        try:
            kind, data = messages.get_nowait()
        except queue.Empty:
            root.after(100, poll)
            return
        if kind == 'progress':
            # Drain queued progress instead of delaying a finished result by
            # one timer tick per thousand entries.
            while True:
                status.set(f'已扫描 {data[0]} 条，{data[1]} 个文件，{data[2]} 字节…')
                try:
                    kind, data = messages.get_nowait()
                except queue.Empty:
                    root.after(100, poll)
                    return
                if kind != 'progress':
                    break
        if kind != 'progress':
            state['busy'] = False
            if state['closing']:
                root.destroy()
                return
            for control in controls:
                control.configure(state='normal')
            stop.configure(state='disabled')
            if kind == 'scan':
                state['report'] = data
                for tree in trees:
                    tree.delete(*tree.get_children())
                for row in data['groups'][:1000]:
                    trees[0].insert('', 'end', text=row['path'], values=(f"{row['bytes']:,}", row['files'], f"{row['share_percent']}%"))
                for row in data['largest_files']:
                    trees[1].insert('', 'end', text=row['path'], values=(f"{row['bytes']:,}", '', ''))
                for row in data['issues']:
                    trees[2].insert('', 'end', text=row['path'], values=('', '', row['status'] + ': ' + row['detail']))
                status.set(f"{data['files']} 个文件，{data['total_bytes']:,} 字节；跳过 {data['skipped']}，错误 {data['errors']}。" + ('完成。' if data['complete'] else '结果不完整，请查看问题页。'))
            elif kind == 'saved':
                status.set('CSV 已保存：' + data)
            else:
                status.set(data)
            export.configure(state='normal' if state['report'] is not None else 'disabled')
        root.after(100, poll)
    root.protocol('WM_DELETE_WINDOW', close)
    root.after(100, poll)
    root.mainloop()

def main():
    parser = argparse.ArgumentParser(description='文件夹逻辑空间汇总及大文件列表，只读元数据扫描。')
    parser.add_argument('folder')
    parser.add_argument('--top', type=int, default=50)
    parser.add_argument('--csv', help='导出新 CSV，拒绝覆盖')
    args = parser.parse_args()
    try:
        report = scan(args.folder, top=args.top)
        if args.csv:
            write_csv(report, args.csv)
        print(json.dumps(report, ensure_ascii=True))
        return 0 if report['complete'] else 1
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
