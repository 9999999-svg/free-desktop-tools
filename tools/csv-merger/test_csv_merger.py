"""Actual-file integration check for source or standalone EXE."""
import argparse
import csv
import io
import json
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
    command = [str(args.exe)] if args.exe else [sys.executable, str(Path(__file__).with_name('csv_merger.py'))]
    def run(*values, expected=0):
        result = subprocess.run(command + list(map(str, values)), capture_output=True, text=True,
            encoding='utf-8', errors='replace', env={**os.environ, 'PYTHONUTF8': '1'}, timeout=60)
        assert result.returncode == expected, (result.returncode, result.stdout, result.stderr)
        return json.loads(result.stdout) if expected == 0 else None
    def make(path, rows, encoding='utf-8-sig', delimiter=','):
        text = io.StringIO(newline='')
        csv.writer(text, delimiter=delimiter).writerows(rows)
        path.write_bytes(text.getvalue().encode(encoding))
    def read(path, delimiter=','):
        with path.open(encoding='utf-8-sig', newline='') as stream:
            return list(csv.reader(stream, delimiter=delimiter))
    csv.field_size_limit(50 * 1024 * 1024)
    with tempfile.TemporaryDirectory(prefix='合并检查-') as temporary:
        base = Path(temporary)
        a, b, output = base / '甲.csv', base / '乙.csv', base / '合并.csv'
        header = ['名称', '说明']
        first = [['甲', '逗号,引号"和\r\n多行'], ['乙', '=SUM(1,1)']]
        second = [['丙', '中文'], ['丁', '长字段' + 'x' * 140000]]
        make(a, [header] + first)
        make(b, [header] + second, encoding='utf-8')
        originals = {a: a.read_bytes(), b: b.read_bytes()}
        result = run(a, b, '--output', output)
        assert result['rows'] == 4 and result['files'] == 2 and result['columns'] == 2
        assert output.read_bytes().startswith(b'\xef\xbb\xbf')
        assert read(output) == [header] + first + second
        prior = output.read_bytes()
        run(a, b, '--output', output, expected=2)
        assert output.read_bytes() == prior
        run(a, b, '--output', a, expected=2)
        reversed_output = base / '逆序.csv'
        run(b, a, '--output', reversed_output)
        assert read(reversed_output) == [header] + second + first
        ga, gb = base / 'GBK甲.csv', base / 'GBK乙.csv'
        make(ga, [header] + first, encoding='gbk', delimiter=';')
        make(gb, [header] + [['中文', '分号;']], encoding='gbk', delimiter=';')
        gout = base / 'GBK合并.csv'
        run(ga, gb, '--encoding', 'gbk', '--delimiter', 'semicolon', '--output', gout)
        assert read(gout, ';') == [header] + first + [['中文', '分号;']]
        bad, invalid_output = base / '错误.csv', base / '不应创建.csv'
        for data in [b'', b'\xff\xfe\xff', '其他,表头\r\n1,2\r\n'.encode(),
                '名称,说明\r\n1,2,3\r\n'.encode(), '名称,说明\r\n"未闭合'.encode(),
                '名称,说明\r\n空,\x00\r\n'.encode()]:
            bad.write_bytes(data)
            run(a, bad, '--output', invalid_output, expected=2)
            assert not invalid_output.exists() and not list(base.glob('.csv-merge-*.tmp'))
        run(a, '--output', invalid_output, expected=2)
        run(a, a, '--output', invalid_output, expected=2)
        try:
            (base / '链接.csv').symlink_to(a)
        except OSError:
            print('Link fixture unavailable; link check skipped.')
        else:
            run(base / '链接.csv', b, '--output', invalid_output, expected=2)
        assert all(path.read_bytes() == data for path, data in originals.items())
        if not args.exe:
            import csv_merger as tool
            event = threading.Event()
            try:
                tool.merge([a, b], invalid_output, event=event, progress=lambda *_: event.set())
            except InterruptedError:
                pass
            else:
                raise AssertionError('Cancellation did not stop merge')
            assert not invalid_output.exists() and not list(base.glob('.csv-merge-*.tmp'))
        print('PASS: order, multiline/BOM/large fields, GBK, corrupt inputs, no overwrite, source preservation and cancellation cleanup.')

if __name__ == '__main__':
    main()
