"""Real-file round trip and damaged-package checks for source or a frozen EXE."""
import argparse
import hashlib
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
    command = [str(args.exe)] if args.exe else [sys.executable, str(Path(__file__).with_name('file_chunker.py'))]
    def run(*values, expected=0):
        result = subprocess.run(command + list(map(str, values)), capture_output=True, text=True,
            encoding='utf-8', errors='replace', env={**os.environ, 'PYTHONUTF8': '1'}, timeout=90)
        assert result.returncode == expected, (result.returncode, result.stdout, result.stderr)
    with tempfile.TemporaryDirectory(prefix='分块检查-') as temporary:
        base = Path(temporary)
        source, parts = base / '大文件中文.dat', base / '新分块'
        data = bytes(range(256)) * 8192 + b'last part: Chinese \xe4\xb8\xad\xe6\x96\x87'
        source.write_bytes(data)
        run('split', source, parts, '--chunk-mib', '1')
        manifest_path = parts / 'manifest.json'
        original_json = manifest_path.read_bytes()
        manifest = json.loads(original_json)
        assert len(manifest['parts']) == 3 and manifest['original_bytes'] == len(data)
        assert manifest['original_sha256'] == hashlib.sha256(data).hexdigest()
        assert b''.join((parts / part['name']).read_bytes() for part in manifest['parts']) == data
        output = base / '恢复文件.dat'
        run('join', manifest_path, output)
        assert output.read_bytes() == data and source.read_bytes() == data
        run('split', source, parts, '--chunk-mib', '1', expected=2)
        run('join', manifest_path, output, expected=2)
        assert output.read_bytes() == data and manifest_path.read_bytes() == original_json
        assert not list(base.glob('.file-chunker-*.tmp'))
        part = parts / manifest['parts'][0]['name']
        part_bytes = part.read_bytes()
        part.write_bytes(b'X' + part_bytes[1:])
        rejected = base / '损坏不应输出.dat'
        run('join', manifest_path, rejected, expected=2)
        assert not rejected.exists() and not list(base.glob('.file-chunker-*.tmp'))
        part.write_bytes(part_bytes)
        missing = parts / manifest['parts'][-1]['name']
        saved = missing.read_bytes()
        missing.unlink()
        run('join', manifest_path, rejected, expected=2)
        assert not rejected.exists()
        missing.write_bytes(saved)
        manifest['parts'][0]['name'] = '../大文件中文.dat'
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        run('join', manifest_path, rejected, expected=2)
        assert not rejected.exists()
        manifest_path.write_bytes(original_json)
        manifest = json.loads(original_json)
        manifest['original_sha256'] = '0' * 64
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        run('join', manifest_path, rejected, expected=2)
        assert not rejected.exists() and not list(base.glob('.file-chunker-*.tmp'))
        manifest_path.write_bytes(original_json)
        try:
            link = parts / 'link.bin'
            link.symlink_to(part)
        except OSError:
            print('Link fixture unavailable; link check skipped.')
        else:
            part.rename(parts / 'saved.bin')
            part.symlink_to(parts / 'saved.bin')
            run('join', manifest_path, rejected, expected=2)
            part.unlink()
            (parts / 'saved.bin').rename(part)
            link.unlink()
        run('join', manifest_path, parts / '内置输出.dat', expected=2)
        run('split', source, base / 'invalid', '--chunk-mib', '0', expected=2)
        assert not (base / 'invalid').exists()
        empty, empty_parts = base / '空文件', base / '空分块'
        empty.write_bytes(b'')
        run('split', empty, empty_parts, '--chunk-mib', '1')
        run('join', empty_parts / 'manifest.json', base / '恢复空文件')
        assert (base / '恢复空文件').read_bytes() == b''
        assert source.read_bytes() == data
        if not args.exe:
            import file_chunker as tool
            event = threading.Event()
            def stop_after_read(done, total):
                event.set()
            interrupted_parts = base / '取消分割'
            try:
                tool.split_file(source, interrupted_parts, 1024 ** 2, event=event, progress=stop_after_read)
            except InterruptedError:
                pass
            else:
                raise AssertionError('Split cancellation did not stop')
            assert not (interrupted_parts / 'manifest.json').exists()
            event.clear()
            cancelled_output = base / '取消合并.dat'
            try:
                tool.join_file(manifest_path, cancelled_output, event=event, progress=stop_after_read)
            except InterruptedError:
                pass
            else:
                raise AssertionError('Join cancellation did not stop')
            assert not cancelled_output.exists() and not list(base.glob('.file-chunker-*.tmp'))
    print('PASS: binary/empty round trips, Chinese paths, all hashes, missing/corrupt parts, traversal rejection, no overwrite, original bytes.')

if __name__ == '__main__':
    main()
