"""One real-files integration check, for source or a standalone EXE."""
import argparse
import csv
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path)
    args = parser.parse_args()
    command = [str(args.exe)] if args.exe else [sys.executable, str(Path(__file__).with_name('file_catalog.py'))]
    def run(*values, expected=0):
        result = subprocess.run(command + list(map(str, values)), capture_output=True, text=True,
            encoding='utf-8', errors='replace', env={**os.environ, 'PYTHONUTF8': '1'}, timeout=60)
        assert result.returncode == expected, (result.returncode, result.stdout, result.stderr)
    with tempfile.TemporaryDirectory(prefix='清单检查-') as temporary:
        base = Path(temporary)
        folder = base / '资料'
        (folder / '子目录').mkdir(parents=True)
        expected = {'说明.txt': '中文与换行\r\n'.encode(), '子目录/照片.JPG': b'picture-bytes',
                    '=SUM(1,1).txt': b'csv-formula-name', '空文件.bin': b''}
        for name, data in expected.items():
            (folder / name).write_bytes(data)
        report = base / '完整清单.csv'
        run(folder, '--sha256', '--csv', report)
        assert report.read_bytes().startswith(b'\xef\xbb\xbf')
        rows = list(csv.DictReader(report.open(encoding='utf-8-sig', newline='')))
        assert len(rows) == 4
        for row in rows:
            name = row['file'].removeprefix("'")
            assert row['status'] == 'OK' and int(row['bytes']) == len(expected[name])
            assert row['sha256'] == hashlib.sha256(expected[name]).hexdigest()
            assert row['modified_utc'].endswith('+00:00')
        assert next(row['file'] for row in rows if 'SUM' in row['file']).startswith("'=")
        prior = report.read_bytes()
        run(folder, '--csv', report, expected=2)
        assert report.read_bytes() == prior
        filtered = base / '图片.csv'
        run(folder, '--extensions', '.jpg', '--csv', filtered)
        records = list(csv.DictReader(filtered.open(encoding='utf-8-sig')))
        assert len(records) == 1 and records[0]['file'] == '子目录/照片.JPG' and records[0]['sha256'] == ''
        top = base / '顶层.csv'
        run(folder, '--top-only', '--csv', top)
        assert len(list(csv.DictReader(top.open(encoding='utf-8-sig')))) == 3
        run(folder, '--extensions', '*.txt', expected=2)
        empty = base / '空目录'
        empty.mkdir()
        empty_report = base / '空.csv'
        run(empty, '--csv', empty_report)
        assert len(list(csv.DictReader(empty_report.open(encoding='utf-8-sig')))) == 0
        try:
            (folder / '链接.txt').symlink_to(folder / '说明.txt')
        except OSError:
            print('Link fixture unavailable; link check skipped.')
        else:
            link_report = base / '链接.csv'
            run(folder, '--sha256', '--csv', link_report, expected=1)
            assert any(row['status'] == 'SKIPPED' for row in csv.DictReader(link_report.open(encoding='utf-8-sig')))
            (folder / '链接.txt').unlink()
        assert all((folder / name).read_bytes() == data for name, data in expected.items())
        if not args.exe:
            import file_catalog as tool
            event = threading.Event()
            event.set()
            try:
                tool.scan(folder, event=event)
            except InterruptedError:
                pass
            else:
                raise AssertionError('Cancellation did not stop scan')
            changing = base / '变化.txt'
            changing.write_bytes(b'before')
            before = changing.lstat()
            changing.write_bytes(b'longer after')
            try:
                tool.file_digest(changing, before, None)
            except OSError:
                pass
            else:
                raise AssertionError('Changed source was not rejected')
    print('PASS: inventory, hashes, filters, Chinese paths, BOM CSV, formula escaping, no overwrite, original bytes.')

if __name__ == '__main__':
    main()
