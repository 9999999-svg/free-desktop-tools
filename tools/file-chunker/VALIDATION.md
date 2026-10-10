# 技术检查记录

Python 3.14.6 与 3.11.9 源码、独立 Windows EXE 实际临时文件检查通过；样例包括中文路径。检查范围：二进制和空文件往返、缺失/损坏分块、错误整体哈希、清单路径跳转、链接、已有输出和取消行为。真实 EXE GUI 分割三块并合并，全部 2097161 字节与原文件一致，没有残留临时输出。

运行：`python test_file_chunker.py`；EXE：`python test_file_chunker.py --exe dist/FileChunker.exe`。

Windows 的 stat/fstat ctime 字段曾不一致，当前用文件标识、大小和修改时间检查读取变化，内容使用 SHA-256。分割不锁定原文件，强制进程终止、断电、真实超大文件与满盘场景未执行；不宣称这些场景经过实测。
