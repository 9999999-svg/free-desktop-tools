# 文本内容搜索器

在文件夹中的文本文件里查找文字，显示相对路径、行号和每行出现次数，支持把结果导出为 CSV。适合查日志、配置、文档与源码。

[下载 Windows EXE](https://github.com/9999999-svg/text-file-search/releases/download/v1.0.0/TextFileSearch.exe) · [下载 Python 源码](https://github.com/9999999-svg/text-file-search/releases/download/v1.0.0/text-file-search-source-v1.0.0.zip) · [全部下载](https://github.com/9999999-svg/text-file-search/releases/tag/v1.0.0)

## 使用

双击 `TextFileSearch.exe`，选择搜索文件夹，输入文字关键词，设置编码、扩展名、大小写和子文件夹选项，再开始搜索。搜索过程只读，原文件不变；CSV 报告必须使用新文件名。

默认搜索 TXT、MD、CSV、LOG、JSON、INI、PY、YAML、YML、XML、HTML、CSS、JS。扩展名填写 `.txt,.md`；留空搜索所有普通文件。支持 UTF-8/BOM、GBK、GB18030、UTF-16，编码由用户明确选择。

源码运行：Python 3.11 或更新版本，含 Tkinter；无需第三方运行库。

```powershell
python text_file_search.py
python text_file_search.py "D:\资料" "错误" --csv "搜索结果.csv"
python text_file_search.py "D:\日志" "ERROR" --case-sensitive --extensions .log,.txt --encoding gbk --csv "日志结果.csv"
```

命令行退出码：0 为搜索完成；1 为包含跳过、错误或上限停止；2 为参数、文件夹或导出失败；130 为中断。零匹配会导出只有表头的报告。

## 限制

- 单行文字按字面匹配，不提供正则表达式、文件内容替换、压缩包或 Office/PDF 搜索。
- 不区分大小写时使用 Unicode casefold，次数为每行非重叠匹配数。行号从 1 开始。
- 单文件上限 50 MiB，链接、目录联接、重解析点和含 NUL 的文件跳过；解码错误单独列出。程序不自动猜编码，不锁定源文件。
- 匹配行上限默认 10000，可设 1 至 100000；达到上限会明确标注结果可能不完整。界面最多展示 1000 条，CSV 包含全部已收集记录。
- 每条内容保存前 1024 个字符，较长行注明截断；匹配次数仍根据整行计算。CSV 对可能成为公式的文本添加前导单引号，原文件保持不变。

全部功能免费，自有源码 MIT。EXE 未签名，依赖及卸载见 [DEPENDENCIES.md](DEPENDENCIES.md)，第三方许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。构建：`python build.py`，输出 `dist/TextFileSearch.exe`。

## 自愿赞助

赞助完全自愿，不解锁任何功能。

![请作者喝杯咖啡](assets/donate-wechat.png)
