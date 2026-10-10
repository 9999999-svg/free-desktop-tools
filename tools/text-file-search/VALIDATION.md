# 技术检查记录

Python 3.14.6 与 3.11.9 源码检查、独立 Windows EXE 实际文件检查通过。包括中文路径、原文件保留、行号与次数、递归及扩展名、大小写和 Unicode casefold、正则字符按字面匹配、UTF-8 BOM/GBK/UTF-16、零匹配、匹配上限、错误解码、NUL 与 50 MiB 超限跳过、长行截断、CSV 公式转义及拒绝覆盖。

源码检查还覆盖预设取消事件；链接样例可用时检查跳过，样例不可用时会明确报告。50 MiB 超限为稀疏测试文件，不宣称实测大型文本搜索吞吐。

真实 Windows EXE GUI 搜索中文目录中的“错误”，正确显示三条匹配记录、行号 1/3/1 和次数 1/2/1；通过原生保存框导出 CSV，记录内容与预期一致。截图和样例仅留本机。

运行 `python test_text_file_search.py`，独立 EXE 检查 `python test_text_file_search.py --exe dist/TextFileSearch.exe`。

没有执行权限受限目录、读取中实时并发修改、断电和满盘场景；这些处理不等于实测证明。
