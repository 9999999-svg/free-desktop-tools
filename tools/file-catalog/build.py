from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onefile', '--console',
    '--name', 'FileCatalog', '--distpath', str(root / 'dist'), '--workpath', str(root / 'build'),
    '--specpath', str(root / 'build'), '--exclude-module', 'numpy', '--exclude-module', 'cv2',
    '--exclude-module', 'imageio_ffmpeg', str(root / 'file_catalog.py')], cwd=root, check=True)
