"""Verify released SWF/EXE, bytecode semantics and safe CLI behavior."""
import argparse
import hashlib
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from patch_mana import PATCHES, PATCHED_SHA256, projector_prefix, transform

def evaluate(code, properties, delta=0):
    stack, position = [], 0
    while position < len(code):
        opcode = code[position]
        position += 1
        if opcode in (0x25, 0x60, 0x66):
            operand = shift = 0
            while True:
                byte = code[position]
                position += 1
                operand |= (byte & 127) << shift
                shift += 7
                if byte < 128:
                    break
            if opcode == 0x25:
                stack.append(operand)
            elif opcode == 0x60:
                stack.append(properties[operand])
            else:
                stack.append(stack.pop()[operand])
        elif opcode == 0x24:
            operand = code[position]
            position += 1
            stack.append(operand if operand < 128 else operand - 256)
        elif opcode == 0xD1:
            stack.append(delta)
        elif opcode in (0xA0, 0xA2):
            right, left = stack.pop(), stack.pop()
            stack.append(left + right if opcode == 0xA0 else left * right)
        elif opcode != 0x02:
            raise AssertionError(f'Unsupported opcode: {opcode:#x}')
    assert len(stack) == 1
    return stack[0]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('swf', type=Path)
    parser.add_argument('exe', type=Path)
    args = parser.parse_args()
    swf, executable = args.swf.read_bytes(), args.exe.read_bytes()
    assert hashlib.sha256(swf).hexdigest() == PATCHED_SHA256
    original = transform(swf, restore=True)
    assert transform(original) == swf
    assert sum(a != b for a, b in zip(original, swf)) == 16
    reproduced = projector_prefix(executable) + swf + struct.pack('<II', 0xFA123456, len(swf))
    assert reproduced == executable
    assert evaluate(PATCHES[0][1], {982: {1938: 1}}) == 60
    assert evaluate(PATCHES[1][1], {739: 60}, -20) == 40
    for level in range(1, 41):
        maximum = evaluate(PATCHES[0][2], {982: {1938: level}})
        assert maximum == 9999999
        for current in (0, 1, 60, maximum):
            for delta in (-9999999, -60, -20, -10, 0, 1, 9999999):
                assert evaluate(PATCHES[1][2], {739: current, 795: maximum}, delta) == maximum
    with tempfile.TemporaryDirectory(prefix='mana-') as directory:
        root = Path(directory)
        protected = root / 'existing.swf'
        protected.write_bytes(b'keep')
        invalid = root / 'invalid.swf'
        invalid.write_bytes(b'invalid')
        script = Path(__file__).with_name('patch_mana.py')
        refusal = subprocess.run([sys.executable, str(script), str(args.swf.resolve()), str(protected), '--restore'], capture_output=True)
        assert refusal.returncode != 0 and protected.read_bytes() == b'keep'
        rejected = root / 'rejected.swf'
        result = subprocess.run([sys.executable, str(script), str(invalid), str(rejected)], capture_output=True)
        assert result.returncode != 0 and not rejected.exists()
    print('PASS: identical SWF/EXE, reversible 16-byte patch, 40 levels and 1120 mana changes, overwrite/version guards.')

if __name__ == '__main__':
    main()
