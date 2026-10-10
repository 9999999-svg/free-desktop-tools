# 技术检查记录

Python 3.14.6 与 3.11.9 源码、独立 Windows EXE 实际临时文件检查通过；样例包括中文路径。检查范围：递归清单、SHA-256、扩展名和层级筛选、中文 BOM CSV、公式转义、防覆盖、空文件夹、链接跳过和文件变化拒绝。真实 EXE GUI 扫描三项，实际导出 CSV 的三个完整哈希核对成功。

运行：`python test_file_catalog.py`；EXE：`python test_file_catalog.py --exe dist/FileCatalog.exe`。

Windows 的 stat/fstat ctime 字段曾不一致，当前用文件标识、大小和修改时间检查读取变化，内容使用 SHA-256。分割不锁定原文件，强制进程终止、断电、真实超大文件与满盘场景未执行；不宣称这些场景经过实测。
