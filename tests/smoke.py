"""Real file smoke checks; --exe-dir tests the built executables as well."""
import argparse
import contextlib
import http.server
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

from PIL import Image
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
TOOLS = {
    'batch-resize': ('batch_resize.py', 'BatchResize'),
    'batch-convert': ('batch_convert.py', 'BatchConvert'),
    'batch-watermark': ('batch_watermark.py', 'Watermark'),
    'video-to-gif': ('video_to_gif.py', 'Video2GIF'),
    'extract-audio': ('extract_audio.py', 'ExtractAudio'),
    'batch-rename': ('batch_rename.py', 'BatchRename'),
    'video-downloader': ('universal_downloader.py', 'UniversalDL'),
}

def module(slug):
    spec = importlib.util.spec_from_file_location(slug, ROOT / 'tools' / slug / TOOLS[slug][0])
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

def run(slug, args, exe_dir=None):
    script, exe = TOOLS[slug]
    prefix = [str(exe_dir / f'{exe}.exe')] if exe_dir else [sys.executable, str(ROOT / 'tools' / slug / script)]
    result = subprocess.run(prefix + [str(a) for a in args], capture_output=True,
                            encoding='utf-8', errors='replace', timeout=90)
    assert result.returncode == 0, f'{slug}: {result.stdout}\n{result.stderr}'
    return result.stdout

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe-dir', type=Path)
    opts = parser.parse_args()
    for slug in TOOLS:
        assert 'usage:' in run(slug, ['--help'], opts.exe_dir).lower(), slug
    with tempfile.TemporaryDirectory(prefix='tool-smoke-') as temporary:
        work = Path(temporary)
        pictures = work / '图片'
        pictures.mkdir()
        source = pictures / '中文.png'
        Image.new('RGBA', (120, 80), (255, 0, 0, 0)).save(source)
        resized = work / '缩图'
        run('batch-resize', ['-i', pictures, '-o', resized, '--size', 64], opts.exe_dir)
        with Image.open(resized / source.name) as img:
            assert img.size == (64, 64)
        converted = work / '转换'
        run('batch-convert', ['-i', pictures, '-o', converted, '-f', 'jpg'], opts.exe_dir)
        with Image.open(converted / '中文.jpg') as img:
            assert min(img.getpixel((0, 0))) > 245, 'transparent background must be white'
        marked = work / '标记'
        run('batch-watermark', ['-i', pictures, '-o', marked, '-m', 'binary', '-t', '测试中文'], opts.exe_dir)
        watermark = module('batch-watermark')
        assert watermark.binary_extract(marked / source.name) == '测试中文'
        marked_lsb = work / '隐写'
        run('batch-watermark', ['-i', pictures, '-o', marked_lsb, '-m', 'lsb', '-t', '测试中文'], opts.exe_dir)
        assert watermark.lsb_extract(marked_lsb / (source.name + '.lsb.png')) == '测试中文'
        rejected = work / 'invalid.jpg'
        assert not watermark.lsb_embed(source, rejected, 'test'), 'lossy LSB output must be rejected'
        assert not rejected.exists()
        small = work / 'tiny.png'
        Image.new('RGB', (1, 1)).save(small)
        assert not watermark.lsb_embed(small, work / 'too-small.png', 'too long')
        rename_dir = work / '重命名'
        rename_dir.mkdir()
        (rename_dir / 'original.jpg').write_bytes(b'unchanged')
        run('batch-rename', ['-i', rename_dir, '-m', 'custom', '-p', '{n:04d}', '--preview'], opts.exe_dir)
        assert (rename_dir / 'original.jpg').exists(), 'preview changed source'
        run('batch-rename', ['-i', rename_dir, '-m', 'custom', '-p', '{n:04d}'], opts.exe_dir)
        assert (rename_dir / '0001.jpg').read_bytes() == b'unchanged'
        videos = work / '视频'
        videos.mkdir()
        video = videos / 'test.mp4'
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        subprocess.run([ffmpeg, '-y', '-f', 'lavfi', '-i', 'testsrc=size=96x64:rate=10',
                        '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100',
                        '-t', '1', '-pix_fmt', 'yuv420p', str(video)],
                       check=True, capture_output=True, timeout=30)
        gif = work / '预览.gif'
        run('video-to-gif', ['-i', video, '-o', gif, '-t', '0.5', '--width', '64'], opts.exe_dir)
        with Image.open(gif) as img:
            assert img.width == 64 and img.n_frames >= 2
        audio = work / '音频'
        run('extract-audio', ['-i', videos, '-o', audio, '-f', 'wav'], opts.exe_dir)
        assert (audio / 'test.wav').stat().st_size > 1000
        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(videos), **kwargs)
            def log_message(self, *args):
                pass
        with http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            downloads = work / '下载'
            run('video-downloader', ['-u', f'http://127.0.0.1:{server.server_port}/test.mp4',
                                    '-o', downloads], opts.exe_dir)
            assert any(f.stat().st_size > 1000 for f in downloads.glob('*.mp4'))
            server.shutdown()
    print('PASS: 7 tools, CLI help, Chinese paths, image output, watermark recovery and validation, rename preview/template, GIF, WAV, local HTTP download')

if __name__ == '__main__':
    main()
