#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量添加水印 v2.0 — 二进制 + LSB 隐写水印

功能一：二进制插入水印
  - 将自定义文字直接插入图片文件的二进制尾部
  - PNG 插在 IEND 块后，JPEG 插在文件末尾
  - 图片视觉完全不变，用二进制编辑器可读出
  - 格式标记: [WM]文字内容[/WM]

功能二：LSB 隐写水印
  - 将文字转为二进制，逐位写入像素 R/G/B 最低有效位
  - 人眼看不出变化
  - 仅适用于无损 PNG/BMP，不抗 JPEG 压缩或裁剪

依赖: Pillow, numpy
"""

import os
import sys

# Keep Chinese and emoji CLI output readable in redirected Windows consoles.
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
import argparse
import struct
import numpy as np
from pathlib import Path
from PIL import Image

# ================================================================
# 二进制插入水印
# ================================================================

WM_MARK_START = b'[WM]'
WM_MARK_END   = b'[/WM]'


def binary_embed(image_path: str, output_path: str, text: str) -> bool:
    """
    将文字以二进制形式插入图片文件尾部。
    PNG: 插入在 IEND 块之后
    JPEG/其他: 直接追加在文件末尾
    """
    try:
        with open(image_path, 'rb') as f:
            data = bytearray(f.read())

        ext = os.path.splitext(image_path)[1].lower()
        payload = WM_MARK_START + text.encode('utf-8') + WM_MARK_END

        if ext == '.png':
            # PNG: 寻找 IEND 块标记 (00 00 00 00 49 45 4E 44 AE 42 60 82)
            iend_marker = b'\x00\x00\x00\x00IEND\xae\x42\x60\x82'
            idx = data.rfind(iend_marker)
            if idx == -1:
                # 降级：找不到 IEND 则追加末尾
                data.extend(payload)
            else:
                # 在 IEND 后插入
                pos = idx + len(iend_marker)
                data[pos:pos] = payload
        else:
            # JPEG / 其他: 直接追加末尾
            # JPEG 尾部可能有 EOI 标记 0xFFD9，插在前
            eoi_marker = b'\xff\xd9'
            if data[-2:] == eoi_marker:
                data[-2:-2] = payload
            else:
                data.extend(payload)

        with open(output_path, 'wb') as f:
            f.write(data)
        return True
    except Exception as e:
        print(f"[FAIL] 二进制嵌入失败: {e}")
        return False


def binary_extract(image_path: str) -> str:
    """从图片文件中提取二进制嵌入的水印文字"""
    try:
        with open(image_path, 'rb') as f:
            data = f.read()

        start = data.find(WM_MARK_START)
        end = data.find(WM_MARK_END)

        if start == -1 or end == -1 or end <= start:
            return ""

        payload = data[start + len(WM_MARK_START):end]
        return payload.decode('utf-8', errors='replace')
    except Exception as e:
        print(f"[FAIL] 二进制提取失败: {e}")
        return ""


# ================================================================
# LSB 隐写水印
# ================================================================

def _text_to_bits(text: str) -> list:
    """将文字转为二进制位列表 (每字节8位, 以16位长度头标记)"""
    encoded = text.encode('utf-8')
    if len(encoded) > 65535:
        raise ValueError('UTF-8 内容不得超过 65535 字节')
    # 用 2 字节记录长度 (最多 65535 字节)
    length_bits = list(map(int, format(len(encoded), '016b')))
    data_bits = []
    for byte in encoded:
        for i in range(7, -1, -1):
            data_bits.append((byte >> i) & 1)
    return length_bits + data_bits


def _bits_to_text(bits: list) -> str:
    """将二进制位列表还原为文字"""
    if len(bits) < 16:
        return ""
    length = int(''.join(str(b) for b in bits[:16]), 2)
    if length == 0 or len(bits) < 16 + length * 8:
        return ""
    bytes_data = bytearray()
    for i in range(length):
        byte_val = 0
        for j in range(8):
            idx = 16 + i * 8 + j
            if idx < len(bits):
                byte_val = (byte_val << 1) | bits[idx]
        bytes_data.append(byte_val)
    return bytes_data.decode('utf-8', errors='replace')


def lsb_embed(image_path: str, output_path: str, text: str) -> bool:
    """
    LSB 隐写嵌入：将文字写入像素 R/G/B 的最低有效位。
    支持 PNG / BMP / JPEG (JPEG 保存为无损 PNG 再转 JPEG 时会丢数据)
    """
    try:
        if Path(output_path).suffix.lower() not in {'.png', '.bmp'}:
            raise ValueError('LSB 必须保存为 PNG/BMP，JPEG 等有损格式不能恢复文字')
        img = Image.open(image_path).convert('RGB')
        pixels = np.array(img, dtype=np.uint8)
        h, w, _ = pixels.shape

        bits = _text_to_bits(text)
        total_pixels = h * w * 3  # 总通道数 (R+G+B)
        if len(bits) > total_pixels:
            raise ValueError(f'文字需要 {len(bits)} bits，图片容量只有 {total_pixels} bits')

        # 逐位写入 LSB
        flat = pixels.ravel()
        for i, bit in enumerate(bits):
            flat[i] = (flat[i] & 0xFE) | bit

        result_img = Image.fromarray(flat.reshape(h, w, 3), 'RGB')
        result_img.save(output_path, quality = 100)

        written = len(bits)
        capacity = total_pixels
        print(f"[INFO] LSB 写入 {written} bits (文字 '{text}' 共 {len(text)} 字符)")
        print(f"[INFO] 可用容量 {capacity} bits, 使用率 {written/capacity*100:.1f}%")
        print('[NOTE] 重编码、压缩或裁剪可能移除隐藏文字')
        return True
    except Exception as e:
        print(f"[FAIL] LSB 嵌入失败: {e}")
        return False


def lsb_extract(image_path: str) -> str:
    """从图片像素 LSB 提取水印"""
    try:
        img = Image.open(image_path).convert('RGB')
        pixels = np.array(img, dtype=np.uint8)

        flat = pixels.ravel()
        bits = [flat[i] & 1 for i in range(min(len(flat), 16 + 65535 * 8))]

        text = _bits_to_text(bits)
        return text
    except Exception as e:
        print(f"[FAIL] LSB 提取失败: {e}")
        return ""


# ================================================================
# 批量处理
# ================================================================

SUPPORTED_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif'}


def process_images(input_path, output_dir, mode, text='水印', extract=False):
    """批量处理图片"""
    inp = Path(input_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if inp.is_file():
        files = [inp]
    else:
        files = [f for f in inp.iterdir() if f.suffix.lower() in SUPPORTED_EXTS and f.is_file()]

    if not files:
        print(f"[WARN] 未找到支持的图片文件: {input_path}")
        return

    print(f"[DIR] 找到 {len(files)} 张图片")
    mode_name = {'binary': '二进制插入', 'lsb': 'LSB隐写'}.get(mode, mode)
    action = "提取水印" if extract else f"写入水印 ({mode_name})"
    print(f"[MODE] {action}")
    print(f"{'-' * 50}")

    success = 0
    errors = 0
    for i, img_file in enumerate(files, 1):
        try:
            if extract:
                # === 提取模式 ===
                t_bin = binary_extract(str(img_file))
                t_lsb = lsb_extract(str(img_file))
                print(f"[{i}/{len(files)}] {img_file.name}")
                if t_bin:
                    print(f"   [二进制] {t_bin}")
                else:
                    print(f"   [二进制] (未找到)")
                if t_lsb:
                    print(f"   [LSB]    {t_lsb}")
                else:
                    print(f"   [LSB]    (未找到)")
                success += 1
            else:
                # === 嵌入模式 ===
                out_file = out / img_file.name
                if mode == 'lsb':
                    out_file = out_file.with_name(img_file.name + '.lsb.png')
                if out_file.resolve() == img_file.resolve():
                    print(f'[SKIP] 不覆盖输入原图: {img_file.name}')
                    continue
                if out_file.exists():
                    print(f'[SKIP] 输出已存在: {out_file.name}')
                    continue
                if mode == 'binary':
                    ok = binary_embed(str(img_file), str(out_file), text)
                else:  # lsb
                    ok = lsb_embed(str(img_file), str(out_file), text)

                if ok:
                    print(f"[{i}/{len(files)}] [OK] {img_file.name}")
                    success += 1
                else:
                    print(f"[{i}/{len(files)}] [FAIL] {img_file.name}")
                    errors += 1
        except Exception as e:
            print(f"[{i}/{len(files)}] [FAIL] {img_file.name}: {e}")
            errors += 1

    print(f"{'-' * 50}")
    print(f"[STAT] 完成: {success} 张成功, {errors} 张失败")


# ================================================================
# CLI
# ================================================================

def main_cli():
    parser = argparse.ArgumentParser(
        description='[WATR] 批量水印 v2.0 — 二进制插入 + LSB 隐写',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 二进制插入水印
  %(prog)s -i ./图片 -o ./输出 -m binary -t "版权信息"

  # LSB 隐写水印
  %(prog)s -i ./图片 -o ./输出 -m lsb -t "隐藏消息"

  # 提取水印（自动检测两种模式）
  %(prog)s -i ./图片 --extract

  # 单个文件
  %(prog)s -i photo.png -o out.png -m lsb -t "水印"
        """
    )
    parser.add_argument('-i', '--input', required=True, help='输入图片路径或目录')
    parser.add_argument('-o', '--output', default=None, help='输出目录 (默认: ./output)')
    parser.add_argument('-m', '--mode', choices=['binary', 'lsb'], default='binary',
                        help='模式: binary(二进制插入) / lsb(LSB隐写)')
    parser.add_argument('-t', '--text', default='水印', help='水印文字内容')
    parser.add_argument('--extract', action='store_true', help='提取水印模式')

    args = parser.parse_args()

    # 检测输入
    inp = Path(args.input)
    if not inp.exists():
        print(f"[FAIL] 输入不存在: {args.input}")
        sys.exit(1)

    out_dir = args.output
    if out_dir is None:
        if inp.is_file():
            out_dir = str(inp.parent / 'output')
        else:
            out_dir = str(inp / 'output')

    if args.extract:
        process_images(args.input, out_dir, args.mode, extract=True)
    else:
        process_images(args.input, out_dir, args.mode, text=args.text)


# ================================================================
# GUI (Tkinter)
# ================================================================

if __name__ == '__main__':
    if len(sys.argv) > 1:
        main_cli()
    else:
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox
        import threading
        import queue

        PRIMARY_COLOR = '#667eea'
        BG_COLOR = '#ffffff'
        FONT_FAMILY = 'Microsoft YaHei'

        class WatermarkGUI:
            def __init__(self, root):
                self.root = root
                self.root.title('💧 批量水印 v2.0 — 二进制 + LSB隐写')
                self.root.geometry('700x650')
                self.root.configure(bg=BG_COLOR)
                self.root.resizable(True, True)

                self.input_path = tk.StringVar()
                self.output_dir = tk.StringVar()
                self.mode = tk.StringVar(value='binary')
                self.wm_text = tk.StringVar(value='水印')

                self.running = False
                self.log_queue = queue.Queue()

                self._build_ui()
                self._poll_log()

            def _build_ui(self):
                # 标题栏
                title_frame = tk.Frame(self.root, bg=PRIMARY_COLOR, height=55)
                title_frame.pack(fill='x')
                title_frame.pack_propagate(False)
                tk.Label(title_frame, text='💧 批量水印 — 二进制 + LSB 隐写',
                         fg='white', bg=PRIMARY_COLOR,
                         font=(FONT_FAMILY, 16, 'bold')).pack(pady=10)

                main_frame = tk.Frame(self.root, bg=BG_COLOR, padx=20, pady=12)
                main_frame.pack(fill='both', expand=True)

                # --- 输入选择 ---
                io_frame = tk.LabelFrame(main_frame, text=' 文件选择 ',
                                         bg=BG_COLOR, font=(FONT_FAMILY, 11, 'bold'),
                                         fg=PRIMARY_COLOR, padx=10, pady=10)
                io_frame.pack(fill='x', pady=(0, 8))

                tk.Label(io_frame, text='输入:', bg=BG_COLOR,
                         font=(FONT_FAMILY, 10)).grid(row=0, column=0, sticky='w', padx=3)
                tk.Entry(io_frame, textvariable=self.input_path, width=45,
                         font=(FONT_FAMILY, 9)).grid(row=0, column=1, padx=5, pady=2)
                btn_frame = tk.Frame(io_frame, bg=BG_COLOR)
                btn_frame.grid(row=0, column=2, padx=3)
                tk.Button(btn_frame, text='选择文件', bg=PRIMARY_COLOR, fg='white',
                          font=(FONT_FAMILY, 9), command=self._browse_file).pack(side='left', padx=2)
                tk.Button(btn_frame, text='选择目录', bg=PRIMARY_COLOR, fg='white',
                          font=(FONT_FAMILY, 9), command=self._browse_dir).pack(side='left', padx=2)

                tk.Label(io_frame, text='输出:', bg=BG_COLOR,
                         font=(FONT_FAMILY, 10)).grid(row=1, column=0, sticky='w', padx=3)
                tk.Entry(io_frame, textvariable=self.output_dir, width=45,
                         font=(FONT_FAMILY, 9)).grid(row=1, column=1, padx=5, pady=2)
                tk.Button(io_frame, text='浏览', bg=PRIMARY_COLOR, fg='white',
                          font=(FONT_FAMILY, 9), command=self._browse_output).grid(row=1, column=2, padx=3)

                # --- 模式选择 ---
                mode_frame = tk.LabelFrame(main_frame, text=' 模式设置 ',
                                           bg=BG_COLOR, font=(FONT_FAMILY, 11, 'bold'),
                                           fg=PRIMARY_COLOR, padx=10, pady=10)
                mode_frame.pack(fill='x', pady=(0, 8))

                rb_frame = tk.Frame(mode_frame, bg=BG_COLOR)
                rb_frame.pack(anchor='w', pady=3)
                tk.Radiobutton(rb_frame, text='🔧 二进制插入（文件尾部标记 [WM]...[/WM]）',
                               variable=self.mode, value='binary',
                               bg=BG_COLOR, font=(FONT_FAMILY, 10)).pack(anchor='w')
                tk.Radiobutton(rb_frame, text='🔍 LSB 隐写（写入像素最低有效位，肉眼不可见）',
                               variable=self.mode, value='lsb',
                               bg=BG_COLOR, font=(FONT_FAMILY, 10)).pack(anchor='w')

                # 文字内容
                text_frame = tk.Frame(mode_frame, bg=BG_COLOR)
                text_frame.pack(fill='x', pady=(8, 2))
                tk.Label(text_frame, text='文字内容:', bg=BG_COLOR,
                         font=(FONT_FAMILY, 10)).pack(side='left')
                tk.Entry(text_frame, textvariable=self.wm_text, width=50,
                         font=(FONT_FAMILY, 9)).pack(side='left', padx=10)

                # --- 操作按钮 ---
                btn_frame2 = tk.Frame(main_frame, bg=BG_COLOR)
                btn_frame2.pack(fill='x', pady=5)

                self.embed_btn = tk.Button(btn_frame2, text='✏️ 写入水印',
                                           bg=PRIMARY_COLOR, fg='white',
                                           font=(FONT_FAMILY, 11, 'bold'), padx=20, pady=5,
                                           command=self._start_embed)
                self.embed_btn.pack(side='left', padx=5)

                self.extract_btn = tk.Button(btn_frame2, text='🔍 提取水印',
                                             bg='#28a745', fg='white',
                                             font=(FONT_FAMILY, 11, 'bold'), padx=20, pady=5,
                                             command=self._start_extract)
                self.extract_btn.pack(side='left', padx=5)

                # --- 进度条 ---
                self.progress = ttk.Progressbar(main_frame, orient='horizontal',
                                                length=660, mode='determinate')
                self.progress.pack(fill='x', pady=5)

                # --- 日志 ---
                log_frame = tk.LabelFrame(main_frame, text=' 运行日志 ',
                                          bg=BG_COLOR, font=(FONT_FAMILY, 11, 'bold'),
                                          fg=PRIMARY_COLOR, padx=5, pady=5)
                log_frame.pack(fill='both', expand=True)

                self.log_text = tk.Text(log_frame, height=12, wrap='word',
                                        bg='#f8f9fa', fg='#333',
                                        font=('Consolas', 9), relief='flat', borderwidth=1)
                self.log_text.pack(fill='both', expand=True, side='left')
                scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview)
                scrollbar.pack(side='right', fill='y')
                self.log_text.config(yscrollcommand=scrollbar.set)

            def _log(self, msg):
                self.log_queue.put(msg)

            def _poll_log(self):
                try:
                    while True:
                        msg = self.log_queue.get_nowait()
                        self.log_text.insert('end', msg + '\n')
                        self.log_text.see('end')
                except queue.Empty:
                    pass
                self.root.after(100, self._poll_log)

            def _browse_file(self):
                f = filedialog.askopenfilename(
                    title='选择图片文件',
                    filetypes=[('图片文件', '*.png *.jpg *.jpeg *.bmp *.webp *.tiff'), ('所有文件', '*.*')]
                )
                if f:
                    self.input_path.set(f)

            def _browse_dir(self):
                d = filedialog.askdirectory(title='选择图片目录')
                if d:
                    self.input_path.set(d)

            def _browse_output(self):
                d = filedialog.askdirectory(title='选择输出目录')
                if d:
                    self.output_dir.set(d)

            def _get_io(self):
                inp = self.input_path.get().strip()
                out = self.output_dir.get().strip()
                if not inp:
                    messagebox.showwarning('提示', '请选择输入文件或目录')
                    return None, None
                if not out:
                    p = Path(inp)
                    if p.is_file():
                        out = str(p.parent / 'output')
                    else:
                        out = str(p / 'output')
                    self.output_dir.set(out)
                return inp, out

            def _start_embed(self):
                if self.running:
                    return
                inp, out = self._get_io()
                if inp is None:
                    return
                text = self.wm_text.get().strip()
                if not text:
                    messagebox.showwarning('提示', '请输入水印文字内容')
                    return
                mode = self.mode.get()
                self.running = True
                self.embed_btn.config(state='disabled', text='⏳ 处理中...')
                self.extract_btn.config(state='disabled')
                self.progress['value'] = 0
                self.log_text.delete('1.0', 'end')

                t = threading.Thread(target=self._run_embed, args=(inp, out, mode, text), daemon=True)
                t.start()

            def _run_embed(self, inp, out, mode, text):
                try:
                    import io as _io
                    old = sys.stdout
                    sys.stdout = _io.StringIO()

                    process_images(inp, out, mode, text=text, extract=False)

                    output = sys.stdout.getvalue()
                    sys.stdout = old
                    lines = output.strip().split('\n')
                    for i, line in enumerate(lines):
                        self._log(line)
                        pct = int((i + 1) / len(lines) * 100) if lines else 100
                        self.root.after(0, lambda v=pct: self.progress.config(value=v))
                    self.root.after(0, lambda: self.progress.config(value=100))
                    self._log('[DONE] 写入完成！')
                except Exception as e:
                    self._log(f'[ERROR] {e}')
                finally:
                    self.running = False
                    self.root.after(0, lambda: self.embed_btn.config(state='normal', text='✏️ 写入水印'))
                    self.root.after(0, lambda: self.extract_btn.config(state='normal'))

            def _start_extract(self):
                if self.running:
                    return
                inp, out = self._get_io()
                if inp is None:
                    return
                self.running = True
                self.embed_btn.config(state='disabled')
                self.extract_btn.config(state='disabled', text='⏳ 提取中...')
                self.progress['value'] = 0
                self.log_text.delete('1.0', 'end')

                t = threading.Thread(target=self._run_extract, args=(inp, out), daemon=True)
                t.start()

            def _run_extract(self, inp, out):
                try:
                    import io as _io
                    old = sys.stdout
                    sys.stdout = _io.StringIO()

                    process_images(inp, out, 'binary', extract=True)

                    output = sys.stdout.getvalue()
                    sys.stdout = old
                    lines = output.strip().split('\n')
                    for i, line in enumerate(lines):
                        self._log(line)
                        pct = int((i + 1) / len(lines) * 100) if lines else 100
                        self.root.after(0, lambda v=pct: self.progress.config(value=v))
                    self.root.after(0, lambda: self.progress.config(value=100))
                    self._log('[DONE] 提取完成！')
                except Exception as e:
                    self._log(f'[ERROR] {e}')
                finally:
                    self.running = False
                    self.root.after(0, lambda: self.extract_btn.config(state='normal', text='🔍 提取水印'))
                    self.root.after(0, lambda: self.embed_btn.config(state='normal'))

        root = tk.Tk()
        app = WatermarkGUI(root)
        root.mainloop()
