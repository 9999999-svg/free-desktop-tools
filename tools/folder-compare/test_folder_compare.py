"""One actual-files integration check, also runnable against a frozen EXE."""
import argparse
import csv
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import folder_compare as tool

parser = argparse.ArgumentParser()
parser.add_argument('--exe', type=Path)
args = parser.parse_args()
program = [str(args.exe.resolve())] if args.exe else [sys.executable, str(Path(__file__).with_name('folder_compare.py'))]
def run(*values, expected=0):
    result = subprocess.run(program + list(map(str, values)), capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == expected, (result.returncode, result.stdout, result.stderr)
    return result
with tempfile.TemporaryDirectory(prefix='目录对比 中文 ') as folder:
    root = Path(folder)
    left, right = root / '备份 A', root / '备份 B'
    for directory in (left, right):
        (directory / '子目录').mkdir(parents=True)
        (directory / '子目录/相同.txt').write_bytes('你好\r\n'.encode())
        (directory / '=calculation.txt').write_bytes(b'plain text')
        (directory / 'empty').write_bytes(b'')
    (left / 'Mixed.TXT').write_bytes(b'case')
    (right / 'mixed.txt').write_bytes(b'case')
    (left / '变化.txt').write_bytes(b'abcd')
    (right / '变化.txt').write_bytes(b'ABCD')
    (left / '只有左.txt').write_bytes(b'left')
    (right / '只有右.txt').write_bytes(b'right')
    before = {p: hashlib.sha256(p.read_bytes()).digest() for d in (left, right) for p in d.rglob('*') if p.is_file()}
    rows = tool.compare(left, right)
    states = {r['file']: r['status'] for r in rows}
    assert states['变化.txt'] == 'CHANGED' and states['只有左.txt'] == 'LEFT_ONLY' and states['只有右.txt'] == 'RIGHT_ONLY'
    assert states['子目录/相同.txt'] == states['empty'] == 'SAME'
    if os.name == 'nt':
        assert states['Mixed.TXT'] == 'SAME'
    report = root / '结果.csv'
    run('--help')
    run(left, right, '--csv', report, expected=1)
    records = list(csv.DictReader(report.open(encoding='utf-8-sig', newline='')))
    assert any(r['file'] == "'=calculation.txt" for r in records)
    assert {r['status'] for r in records} == {'SAME', 'CHANGED', 'LEFT_ONLY', 'RIGHT_ONLY'}
    saved = report.read_bytes()
    run(left, right, '--csv', report, expected=2)
    assert report.read_bytes() == saved
    run(left, left, expected=2)
    run(left, root / 'missing', expected=2)
    equal_a, equal_b = root / 'equal A', root / 'equal B'
    equal_a.mkdir(); equal_b.mkdir()
    (equal_a / 'file').write_bytes(b'unchanged')
    (equal_b / 'file').write_bytes(b'unchanged')
    run(equal_a, equal_b)
    run(equal_a, equal_b, '--csv', root / 'equal.csv')
    entry = next(iter(tool.index_folder(equal_a).values()))
    (equal_a / 'file').write_bytes(b'changed content')
    try:
        tool.digest(entry)
        raise AssertionError('Changed file was accepted')
    except OSError:
        pass
    event = threading.Event(); event.set()
    try:
        tool.compare(left, right, event)
        raise AssertionError('Cancellation was ignored')
    except InterruptedError:
        pass
    try:
        (left / 'outside-link').symlink_to(root / 'missing')
    except OSError:
        pass
    else:
        assert any(r['file'] == 'outside-link' and r['status'] == 'SKIPPED' for r in tool.compare(left, right))
        run(left, right, expected=2)
    assert all(hashlib.sha256(path.read_bytes()).digest() == digest for path, digest in before.items())
print('PASS: equal/different files, backup-only files, Chinese paths, CSV, no overwrite, cancellation and changed-file/link guards.')
