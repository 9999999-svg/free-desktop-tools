"""Actual-file integration check for source or standalone EXE."""
import argparse
import csv
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
    command = [str(args.exe)] if args.exe else [sys.executable, str(Path(__file__).with_name('text_file_search.py'))]
    def run(*values, expected=0):
        result = subprocess.run(command + list(map(str, values)), capture_output=True, text=True,
            encoding='utf-8', errors='replace', env={**os.environ, 'PYTHONUTF8': '1'}, timeout=60)
        assert result.returncode == expected, (result.returncode, result.stdout, result.stderr)
        return json.loads(result.stdout) if expected in (0, 1) else None
    def read(path):
        with path.open(encoding='utf-8-sig', newline='') as stream:
            return list(csv.DictReader(stream))
    with tempfile.TemporaryDirectory(prefix='搜索检查-') as temporary:
        base = Path(temporary)
        folder = base / '资料'
        (folder / '子目录').mkdir(parents=True)
        originals = {'说明.TXT': '中文 Alpha alpha\r\n无匹配\n=ALPHA\n.* 字面量\nStraße\n'.encode('utf-8-sig'),
            '子目录/日志.md': 'alpha\n'.encode(), '其他.bin': b'alpha', '空.txt': b''}
        for name, data in originals.items():
            (folder / name).write_bytes(data)
        full = base / '完整.csv'
        assert run(folder, 'alpha', '--csv', full) == {'MATCH': 3}
        assert full.read_bytes().startswith(b'\xef\xbb\xbf')
        rows = read(full)
        assert [(r['file'], r['line'], r['occurrences']) for r in rows] == [
            ('说明.TXT', '1', '2'), ('说明.TXT', '3', '1'), ('子目录/日志.md', '1', '1')]
        assert rows[1]['text'] == "'=ALPHA"
        prior = full.read_bytes()
        run(folder, 'alpha', '--csv', full, expected=2)
        assert full.read_bytes() == prior
        strict = base / '区分.csv'
        run(folder, 'Alpha', '--case-sensitive', '--csv', strict)
        assert len(read(strict)) == 1
        top = base / '顶层.csv'
        run(folder, 'alpha', '--top-only', '--csv', top)
        assert len(read(top)) == 2
        literal = base / '字面.csv'
        run(folder, '.*', '--csv', literal)
        assert read(literal)[0]['line'] == '4' and len(read(literal)) == 1
        folded = base / '大小写.csv'
        run(folder, 'STRASSE', '--csv', folded)
        assert read(folded)[0]['text'] == 'Straße'
        limited = base / '上限.csv'
        assert run(folder, 'alpha', '--max-matches', 1, '--csv', limited, expected=1) == {'MATCH': 1, 'LIMIT': 1}
        assert read(limited)[-1]['status'] == 'LIMIT'
        no_match = base / '零匹配.csv'
        run(folder, '不存在', '--csv', no_match)
        assert read(no_match) == []
        invalid_output = base / '不应创建.csv'
        run(folder, '', '--csv', invalid_output, expected=2)
        run(folder, 'alpha', '--extensions', '*.txt', '--csv', invalid_output, expected=2)
        assert not invalid_output.exists()
        enc = base / '编码'
        enc.mkdir()
        (enc / 'GBK.txt').write_bytes('中文搜索\r\n'.encode('gbk'))
        gbk = base / 'GBK.csv'
        run(enc, '中文', '--encoding', 'gbk', '--csv', gbk)
        assert read(gbk)[0]['text'] == '中文搜索'
        wrong = base / '错误编码.csv'
        run(enc, '中文', '--csv', wrong, expected=1)
        assert read(wrong)[0]['status'] == 'ERROR'
        (enc / 'GBK.txt').unlink()
        (enc / 'UTF16.txt').write_bytes('中文搜索'.encode('utf-16'))
        utf16 = base / 'UTF16.csv'
        run(enc, '中文', '--encoding', 'utf-16', '--csv', utf16)
        assert read(utf16)[0]['text'] == '中文搜索'
        special = base / '边界'
        special.mkdir()
        (special / '二进制.txt').write_bytes(b'alpha\x00')
        (special / '长行.txt').write_text('alpha' + 'x' * 2000, encoding='utf-8')
        with (special / '超限.txt').open('wb') as stream:
            stream.truncate(50 * 1024 * 1024 + 1)
        skipped = base / '跳过.csv'
        run(special, 'alpha', '--csv', skipped, expected=1)
        records = read(skipped)
        assert sum(r['status'] == 'SKIPPED' for r in records) == 2
        assert len(next(r['text'] for r in records if r['status'] == 'MATCH')) == 1024
        try:
            (folder / '链接.txt').symlink_to(folder / '说明.TXT')
        except OSError:
            print('Link fixture unavailable; link check skipped.')
        else:
            link_report = base / '链接.csv'
            run(folder, 'alpha', '--csv', link_report, expected=1)
            assert any(r['status'] == 'SKIPPED' for r in read(link_report))
        assert all((folder / name).read_bytes() == data for name, data in originals.items())
        if not args.exe:
            import text_file_search as tool
            event = threading.Event()
            event.set()
            try:
                tool.search(folder, 'alpha', event=event)
            except InterruptedError:
                pass
            else:
                raise AssertionError('Cancellation did not stop search')
        print('PASS: literal/casefold search, line counts, filtering, BOM/GBK/UTF16, limits/errors, formula protection and unchanged originals.')

if __name__ == '__main__':
    main()
