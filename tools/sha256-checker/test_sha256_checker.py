"""Integrated checks for manifest formats, tampering, paths and CSV."""
import argparse
import csv
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
from sha256_checker import check_manifest, write_csv

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path)
    args = parser.parse_args()
    program = [str(args.exe.resolve())] if args.exe else [sys.executable, str(Path(__file__).with_name('sha256_checker.py'))]
    with tempfile.TemporaryDirectory(prefix='sha-check-') as directory:
        base = Path(directory)
        root = base / '中文 空格目录'
        root.mkdir()
        payload = '已验证的下载内容'.encode('utf-8')
        digest = hashlib.sha256(payload).hexdigest()
        first = root / '中文 文件.txt'
        first.write_bytes(payload)
        formula_name = root / '=text.txt'
        formula_name.write_bytes(payload)
        manifest = root / 'SHA256SUMS.txt'
        manifest.write_text(f'# downloaded files\n{digest.upper()}  中文 文件.txt\n{digest} *=text.txt\n', encoding='utf-8-sig')
        original = first.read_bytes()
        rows = check_manifest(manifest)
        assert [row['status'] for row in rows] == ['MATCH', 'MATCH']
        report = base / '校验报告.csv'
        subprocess.run(program + ['--help'], check=True, capture_output=True)
        run = subprocess.run(program + [str(manifest), '--csv', str(report)], check=True, capture_output=True)
        assert b'2/2' in run.stdout
        exported = list(csv.DictReader(report.open(encoding='utf-8-sig', newline='')))
        assert len(exported) == 2 and exported[0]['file'] == first.name
        assert exported[1]['file'] == "'=text.txt"  # Prevent spreadsheet formula execution.
        saved = report.read_bytes()
        refused = subprocess.run(program + [str(manifest), '--csv', str(report)], capture_output=True)
        assert refused.returncode == 1 and report.read_bytes() == saved
        first.write_bytes(b'tampered')
        mismatch_report = base / '不匹配.csv'
        wrong = subprocess.run(program + [str(manifest), '--csv', str(mismatch_report)], capture_output=True)
        assert wrong.returncode == 1 and b'MISMATCH' in wrong.stdout
        first.write_bytes(original)
        outside = base / 'outside.bin'
        outside.write_bytes(payload)
        unsafe = root / 'unsafe.txt'
        unsafe.write_text(f'{digest}  ../outside.bin\n{digest}  C:/outside.bin\n{digest}  missing.bin\nnot a digest\n', encoding='utf-8')
        statuses = [row['status'] for row in check_manifest(unsafe)]
        assert statuses == ['INVALID', 'INVALID', 'MISSING', 'INVALID']
        unsafe_report = base / '异常.csv'
        bad = subprocess.run(program + [str(unsafe), '--csv', str(unsafe_report)], capture_output=True)
        assert bad.returncode == 1
        bad_rows = list(csv.DictReader(unsafe_report.open(encoding='utf-8-sig', newline='')))
        assert [row['status'] for row in bad_rows] == statuses
        try:
            (root / 'outside-link').symlink_to(outside)
        except OSError:
            print('SKIP: symlink creation not permitted.')
        else:
            linked = root / 'links.txt'
            linked.write_text(f'{digest}  outside-link\n', encoding='utf-8')
            assert check_manifest(linked)[0]['status'] == 'INVALID'
        empty = root / 'empty.txt'
        empty.write_text('# no entries\n', encoding='utf-8')
        assert subprocess.run(program + [str(empty)], capture_output=True).returncode == 1
        assert first.read_bytes() == original and formula_name.read_bytes() == payload
        assert outside.read_bytes() == payload
        external_manifest = base / 'elsewhere.txt'
        external_manifest.write_bytes(manifest.read_bytes())
        assert all(row['status'] == 'MATCH' for row in check_manifest(external_manifest, root))
    print('PASS: SHA-256 match/tampering, BOM and GNU formats, Chinese paths, missing files, traversal/symlink guards, CSV and no overwrite.')

if __name__ == '__main__':
    main()
