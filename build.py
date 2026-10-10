"""Build one or all standalone tool EXEs. FFmpeg is an external dependency."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
TOOLS = {
    'batch-resize': ('batch_resize.py', 'BatchResize'),
    'batch-convert': ('batch_convert.py', 'BatchConvert'),
    'batch-watermark': ('batch_watermark.py', 'Watermark'),
    'video-to-gif': ('video_to_gif.py', 'Video2GIF'),
    'extract-audio': ('extract_audio.py', 'ExtractAudio'),
    'batch-rename': ('batch_rename.py', 'BatchRename'),
    'video-downloader': ('universal_downloader.py', 'UniversalDL'),
    'duplicate-file-finder': ('duplicate_finder.py', 'DuplicateFinder'),
    'sha256-checker': ('sha256_checker.py', 'SHA256Checker'),
    'folder-compare': ('folder_compare.py', 'FolderCompare'),
    'text-encoding-converter': ('text_encoding_converter.py', 'TextEncodingConverter'),
    'file-catalog': ('file_catalog.py', 'FileCatalog'),
    'file-chunker': ('file_chunker.py', 'FileChunker'),
    'csv-merger': ('csv_merger.py', 'CsvMerger'),
    'text-file-search': ('text_file_search.py', 'TextFileSearch'),
}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tool', nargs='?', choices=list(TOOLS))
    args = parser.parse_args()
    for slug in ([args.tool] if args.tool else TOOLS):
        script, name = TOOLS[slug]
        command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onefile',
                   '--console', '--name', name, '--distpath', str(ROOT / 'dist'),
                   '--workpath', str(ROOT / 'build' / slug),
                   '--specpath', str(ROOT / 'build'),
                   '--exclude-module', 'imageio_ffmpeg', '--exclude-module', 'cv2']
        if slug != 'batch-watermark':
            command += ['--exclude-module', 'numpy']
        if slug == 'video-downloader':
            command += ['--collect-all', 'yt_dlp']
        command.append(str(ROOT / 'tools' / slug / script))
        print(f'Building {name}...', flush=True)
        subprocess.run(command, cwd=ROOT, check=True)

if __name__ == '__main__':
    main()
