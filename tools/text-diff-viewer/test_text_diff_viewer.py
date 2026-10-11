"""Actual input/output checks for source and --exe."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

def checks(executable=None):
    command = [str(executable)] if executable else [sys.executable, str(Path(__file__).with_name('text_diff_viewer.py'))]
    def run(*args, code=0):
        result = subprocess.run(command + list(map(str, args)), capture_output=True, timeout=60)
        assert result.returncode == code, (args, result.returncode, result.stdout, result.stderr)
        return json.loads(result.stderr if code == 2 else result.stdout)
    with tempfile.TemporaryDirectory(prefix='差异-中文-') as name:
        root = Path(name)
        left, right, output = root / '原文.txt', root / '新文.txt', root / '差异.diff'
        raw = '标题\r\n旧行\r\n结束\r\n'.encode('utf-8-sig')
        left.write_bytes(raw)
        right.write_text('标题\n新行\n新增\n结束\n', encoding='utf-8')
        target_raw = right.read_bytes()
        result = run(left, right, '--output', output, code=1)
        expected = '--- left\n+++ right\n@@ -1,3 +1,4 @@\n 标题\n-旧行\n+新行\n+新增\n 结束\n'
        assert output.read_bytes() == expected.encode('utf-8')
        assert result['left_lines'] == 3 and result['right_lines'] == 4 and not result['same']
        run(left, right, '--output', output, code=2)
        run(left, right, '--output', left, code=2)
        assert left.read_bytes() == raw and right.read_bytes() == target_raw
        gbk = root / 'GBK.txt'
        gbk.write_bytes('标题\n旧行\n结束\n'.encode('gbk'))
        same = run(left, gbk, '--right-encoding', 'gbk')
        assert same['same'] and same['diff_bytes'] == 0
        utf16 = root / 'UTF16.txt'
        utf16.write_bytes('标题\r旧行\r结束\r'.encode('utf-16'))
        assert run(gbk, utf16, '--left-encoding', 'gbk', '--right-encoding', 'utf-16')['same']
        right.write_bytes('标题\n旧行\n结束'.encode())
        eof = run(left, right, '--context', 0, code=1)
        assert eof['preview'] == '--- left\n+++ right\n@@ -3 +3 @@\n-结束\n+结束\n\\ No newline at end of file\n'
        left.write_bytes(b'')
        right.write_bytes(b'')
        empty = root / '空差异.diff'
        assert run(left, right, '--output', empty)['same'] and empty.read_bytes() == b''
        right.write_bytes(b'x\n')
        assert '@@ -0,0 +1 @@' in run(left, right, code=1)['preview']
        assert '@@ -1 +0,0 @@' in run(right, left, code=1)['preview']
        right.write_bytes(b'\xff')
        run(left, right, code=2)
        right.write_bytes(b'\x00binary')
        run(left, right, code=2)
        right.write_bytes(b'x' * 10001)
        run(left, right, code=2)
        right.write_bytes(b'\n' * 10001)
        run(left, right, code=2)
        with right.open('wb') as stream:
            stream.truncate(1024 * 1024 + 1)
        run(left, right, code=2)
        right.write_bytes(b'ok\n')
        run(left, right, '--context', 21, code=2)
        run(root, right, code=2)
        symlink = root / '链接.txt'
        try:
            symlink.symlink_to(right)
        except OSError:
            print('SKIP: OS does not permit symlink fixture')
        else:
            run(left, symlink, code=2)
        if not executable:
            import text_diff_viewer as tool
            event = threading.Event()
            event.set()
            try:
                tool.compare(left, right, root / 'cancelled.diff', event=event)
            except InterruptedError:
                pass
            else:
                raise AssertionError('Cancellation ignored')
            event.clear()
            original = tool.os.fsync
            def cancel_after_flush(fd):
                original(fd)
                event.set()
            tool.os.fsync = cancel_after_flush
            try:
                try:
                    tool.compare(left, right, root / 'cancelled-write.diff', event=event)
                except InterruptedError:
                    pass
                else:
                    raise AssertionError('Cancellation before publish ignored')
            finally:
                tool.os.fsync = original
            assert not (root / 'cancelled-write.diff').exists()
            assert not list(root.glob('.text-diff-*.tmp'))
        print('PASS: actual unified diff bytes, encodings/Unicode/BOM/newline/EOF/empty input, refusal limits, source unchanged', flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path)
    args = parser.parse_args()
    checks(args.exe)
