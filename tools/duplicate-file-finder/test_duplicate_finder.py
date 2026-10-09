"""One integration check for source and optional frozen EXE."""
import argparse
import csv
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from duplicate_finder import Cancelled, scan, write_csv

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='duplicate-check-') as directory:
        base = Path(directory)
        root = base / '中文 测试目录'
        root.mkdir()
        nested = root / '子目录'
        nested.mkdir()
        payload = '内容相同，但文件名不同。'.encode('utf-8')
        first, second = root / '甲.txt', nested / '另一个名字.bin'
        first.write_bytes(payload)
        second.write_bytes(payload)
        (nested / '甲.txt').write_bytes(bytes([1]) * len(payload))
        (root / '空一').touch()
        (root / '空二').touch()
        (root / 'unique').write_bytes(b'unique')
        link_count = hardlink_count = 0
        try:
            os.link(first, root / '硬链接.txt')
            hardlink_count = 1
        except OSError:
            print('SKIP: filesystem does not support hard links.')
        outside = base / '目录外'
        outside.mkdir()
        (outside / 'outside-copy').write_bytes(payload)
        try:
            (root / '文件链接').symlink_to(first)
            (root / '目录链接').symlink_to(outside, target_is_directory=True)
            link_count = 2
        except OSError:
            # Some Windows configurations prohibit symlink creation.
            link_count = sum(path.is_symlink() for path in root.iterdir())
            print('SKIP: one or more symlinks could not be created.')
        before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in root.rglob('*') if path.is_file() and not path.is_symlink()}
        result = scan(root)
        assert len(result['groups']) == 1
        assert set(result['groups'][0]['paths']) == {str(first), str(second)}
        assert result['extra_files'] == 1 and result['extra_bytes'] == len(payload)
        assert result['hardlinks_skipped'] == hardlink_count
        assert result['links_skipped'] == link_count and not result['errors']
        assert len(scan(root, min_size=0)['groups']) == 2
        assert not scan(root, min_size=len(payload) + 1)['groups']
        cancel = threading.Event()
        cancel.set()
        try:
            scan(root, cancel=cancel)
            raise AssertionError('Cancellation ignored.')
        except Cancelled:
            pass
        changed = False
        def progress(message):
            nonlocal changed
            if not changed and message.startswith('核对内容'):
                first.write_bytes(payload + b'changed')
                changed = True
        raced = scan(root, progress=progress)
        assert raced['errors'] and not raced['groups']
        first.write_bytes(payload)
        report = base / '结果.csv'
        program = [str(args.exe.resolve())] if args.exe else [sys.executable, str(Path(__file__).with_name('duplicate_finder.py'))]
        subprocess.run(program + ['--help'], check=True, capture_output=True)
        completed = subprocess.run(program + [str(root), '--csv', str(report)], check=True, capture_output=True)
        assert '1 组'.encode('utf-8') in completed.stdout
        with report.open(encoding='utf-8-sig', newline='') as file:
            rows = list(csv.DictReader(file))
        assert {row['path'] for row in rows} == {str(first), str(second)}
        assert all(row['sha256'] == hashlib.sha256(payload).hexdigest() for row in rows)
        saved = report.read_bytes()
        refused = subprocess.run(program + [str(root), '--csv', str(report)], capture_output=True)
        assert refused.returncode == 1 and report.read_bytes() == saved
        invalid = subprocess.run(program + [str(root), '--min-size', '-1'], capture_output=True)
        assert invalid.returncode == 1
        empty_report = base / '空结果.csv'
        write_csv(scan(outside), empty_report)
        assert len(empty_report.read_text(encoding='utf-8-sig').splitlines()) == 1
        after = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in root.rglob('*') if path.is_file() and not path.is_symlink()}
        assert before == after, 'Scanned files were modified.'
    print('PASS: content matching, Chinese paths, CSV, size filter, empty files, links, cancellation, changed-file and overwrite guards.')

if __name__ == '__main__':
    main()
