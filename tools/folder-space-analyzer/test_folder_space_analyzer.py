"""Actual aggregate, largest-file and CSV checks for source and --exe."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

def checks(executable=None):
    command = [str(executable)] if executable else [sys.executable, str(Path(__file__).with_name('folder_space_analyzer.py'))]
    def run(*args, code=0):
        result = subprocess.run(command + list(map(str, args)), capture_output=True, timeout=60)
        assert result.returncode == code, (args, result.returncode, result.stdout, result.stderr)
        return json.loads(result.stdout if code in {0, 1} else result.stderr)
    with tempfile.TemporaryDirectory(prefix='空间-中文-') as folder:
        root = Path(folder)
        source = root / '样本'
        source.mkdir()
        payloads = {'直属.bin': b'R' * 5, '资料/a.bin': b'A' * 10, '资料/嵌套/b.bin': b'B' * 30,
            '=1+1/c.bin': b'C' * 7, '零.txt': b''}
        for name, content in payloads.items():
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        (source / '空文件夹').mkdir()
        report_file = root / '统计.csv'
        report = run(source, '--top', 2, '--csv', report_file)
        assert report['complete'] and report['files'] == 5 and report['total_bytes'] == 52
        groups = {row['path']: row for row in report['groups']}
        assert groups['资料']['bytes'] == 40 and groups['资料']['files'] == 2
        assert groups['（根目录文件）']['bytes'] == 5 and groups['（根目录文件）']['files'] == 2
        assert groups['=1+1']['bytes'] == 7 and groups['空文件夹']['bytes'] == 0
        assert report['largest_files'] == [{'path': '资料/嵌套/b.bin', 'bytes': 30}, {'path': '资料/a.bin', 'bytes': 10}]
        assert abs(sum(row['share_percent'] for row in report['groups']) - 100) < .01
        assert report_file.read_bytes().startswith(b'\xef\xbb\xbf')
        with report_file.open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        assert rows[0]['kind'] == 'summary' and rows[0]['bytes'] == '52' and rows[0]['files'] == '5'
        assert any(row['path'] == "'=1+1" and row['kind'] == 'folder' for row in rows)
        original = report_file.read_bytes()
        run(source, '--csv', report_file, code=2)
        assert report_file.read_bytes() == original
        for name, content in payloads.items():
            assert (source / name).read_bytes() == content
        run(source, '--top', 0, code=2)
        run(source / '不存在', code=2)
        run(source / '直属.bin', code=2)
        empty = root / '完全空'
        empty.mkdir()
        empty_report = run(empty)
        assert empty_report['complete'] and empty_report['files'] == 0 and empty_report['total_bytes'] == 0
        link = source / '目录链接'
        try:
            link.symlink_to(source / '资料', target_is_directory=True)
        except OSError:
            print('SKIP: OS does not permit directory symlink fixture')
        else:
            incomplete = run(source, code=1)
            assert not incomplete['complete'] and incomplete['skipped'] == 1 and incomplete['total_bytes'] == 52
            assert any(row['path'] == '目录链接' and row['status'] == 'SKIPPED' for row in incomplete['issues'])
            run(link, code=2)
            link.unlink()
        hard = source / '硬链接.bin'
        try:
            os.link(source / '直属.bin', hard)
        except OSError:
            print('SKIP: OS does not permit hard-link fixture')
        else:
            counted = run(source)
            assert counted['total_bytes'] == 57 and counted['files'] == 6
            hard.unlink()
        if not executable:
            import folder_space_analyzer as tool
            event = threading.Event()
            event.set()
            try:
                tool.scan(source, event=event)
            except InterruptedError:
                pass
            else:
                raise AssertionError('Cancellation ignored')
            event.clear()
            old = tool.MAX_ENTRIES
            tool.MAX_ENTRIES = 2
            try:
                limited = tool.scan(source)
                assert not limited['complete'] and limited['limit_reached'] and limited['visited_entries'] == 2
            finally:
                tool.MAX_ENTRIES = old
            report = tool.scan(source)
            original_fsync = tool.os.fsync
            def cancel_after_flush(descriptor):
                original_fsync(descriptor)
                event.set()
            tool.os.fsync = cancel_after_flush
            try:
                try:
                    tool.write_csv(report, root / '取消.csv', event)
                except InterruptedError:
                    pass
                else:
                    raise AssertionError('Cancellation before publish ignored')
            finally:
                tool.os.fsync = original_fsync
            assert not (root / '取消.csv').exists()
        assert not list(root.glob('.folder-space-*.tmp'))
        print('PASS: actual recursive subfolder totals, top files, empty folders, CSV/BOM/formula guard, link skipping/hard-link counts/no overwrite/source unchanged', flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path)
    checks(parser.parse_args().exe)
