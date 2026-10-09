"""Reproduce the full-mana modification using only Python's standard library."""
import argparse
import hashlib
from pathlib import Path
import struct

ORIGINAL_SHA256 = '3f633169368ff02907553f3145775379c3c7409489f9d9f0f67aa954a5559a6e'
PATCHED_SHA256 = '20d87769708dc9c71152564ddd9b897c97351e1cd77638bfaa9b77d4e6c63dc7'
PATCHES = (
    (227639, bytes.fromhex('243260d60766920f240aa2a0'), bytes.fromhex('258f4e25e807a225e707a002')),
    (238506, bytes.fromhex('60e305d1a0'), bytes.fromhex('609b060202')),
)

def transform(data, restore=False):
    expected_input, expected_output = (PATCHED_SHA256, ORIGINAL_SHA256) if restore else (ORIGINAL_SHA256, PATCHED_SHA256)
    if hashlib.sha256(data).hexdigest() != expected_input:
        raise ValueError('Input SHA-256 does not match the supported game version.')
    if data[:3] != b'FWS' or len(data) != int.from_bytes(data[4:8], 'little'):
        raise ValueError('Expected the supported uncompressed SWF.')
    output = bytearray(data)
    for offset, before, after in PATCHES:
        before, after = (after, before) if restore else (before, after)
        if len(before) != len(after) or data[offset:offset + len(before)] != before:
            raise ValueError('Unexpected bytecode at patch location.')
        output[offset:offset + len(after)] = after
    result = bytes(output)
    if hashlib.sha256(result).hexdigest() != expected_output:
        raise ValueError('Output verification failed.')
    return result

def projector_prefix(data):
    if len(data) < 8:
        raise ValueError('Invalid standalone projector.')
    magic, size = struct.unpack('<II', data[-8:])
    if magic != 0xFA123456 or size > len(data) - 8 or not data.startswith(b'MZ'):
        raise ValueError('Invalid standalone projector.')
    embedded = data[-8-size:-8]
    if hashlib.sha256(embedded).hexdigest() not in (ORIGINAL_SHA256, PATCHED_SHA256):
        raise ValueError('Projector contains a different SWF.')
    return data[:-8-size]

def main():
    parser = argparse.ArgumentParser(description='Apply or restore the full-mana SWF patch. Existing output files are refused.')
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--restore', action='store_true', help='Restore the original SWF from the released full-mana SWF.')
    parser.add_argument('--projector', type=Path, help='Existing released standalone EXE; reuse its player prefix.')
    parser.add_argument('--exe-output', type=Path, help='Also create a standalone EXE using --projector.')
    args = parser.parse_args()
    if bool(args.projector) != bool(args.exe_output):
        parser.error('--projector and --exe-output must be provided together.')
    destinations = [args.output] + ([args.exe_output] if args.exe_output else [])
    if len({p.resolve() for p in destinations}) != len(destinations):
        parser.error('Output paths must be different.')
    if any(path.exists() for path in destinations):
        parser.error('An output already exists; choose new paths.')
    try:
        swf = transform(args.input.read_bytes(), args.restore)
        executable = None
        if args.projector:
            executable = projector_prefix(args.projector.read_bytes()) + swf + struct.pack('<II', 0xFA123456, len(swf))
        for path in destinations:
            if not path.parent.is_dir():
                raise ValueError('Output parent directory does not exist.')
        with args.output.open('xb') as output:
            output.write(swf)
        if executable is not None:
            with args.exe_output.open('xb') as output:
                output.write(executable)
    except (OSError, ValueError) as error:
        parser.exit(1, f'Error: {error}\n')
    print('SHA-256:', hashlib.sha256(swf).hexdigest())
    if executable is not None:
        print('EXE SHA-256:', hashlib.sha256(executable).hexdigest())

if __name__ == '__main__':
    main()
