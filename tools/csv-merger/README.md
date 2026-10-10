# CSV 合并器

把表头相同的 CSV 文件按所选顺序合并成一个新文件，适合汇总分批导出的表格、记录与报表。

[下载 Windows EXE](https://github.com/9999999-svg/csv-merger/releases/download/v1.0.0/CsvMerger.exe) · [下载 Python 源码](https://github.com/9999999-svg/csv-merger/releases/download/v1.0.0/csv-merger-source-v1.0.0.zip) · [全部下载](https://github.com/9999999-svg/csv-merger/releases/tag/v1.0.0)

## 使用

双击 `CsvMerger.exe`，添加 2 至 500 个文件，确认列表顺序，选择输入编码和分隔符，再填写新的输出文件名并开始合并。源文件保留，已有输出不会被覆盖。

支持 UTF-8、UTF-8 BOM、GBK、GB18030、UTF-16，逗号、分号和制表符。各文件使用同一编码及分隔符；输出使用 UTF-8 BOM，保留字段文字、引号和多行内容，只写一次表头。跳过空白记录。

源码运行：Python 3.11 或更新版本，含 Tkinter；无需安装第三方运行库。

```powershell
python csv_merger.py
python csv_merger.py "甲.csv" "乙.csv" --output "汇总.csv"
python csv_merger.py "甲.csv" "乙.csv" --encoding gbk --delimiter semicolon --output "汇总.csv"
```

## 限制

- 表头内容和列顺序必须完全相同，每条数据的列数必须一致。编码或格式错误时不会发布合并文件。
- 单文件上限 50 MiB；输入链接与重解析点被拒绝。不自动猜编码、不去重、不转换 Excel 工作簿。
- CSV 字段按原文保留，包括公式文字；用电子表格打开来源不明的 CSV 前请检查其内容。
- 合并可能改变 CSV 的引号样式、记录换行和编码，字段内容保留。读取变化会报错，但程序不锁定源文件。
- 正常取消或错误会清理临时文件；断电或强制终止可能留下 `.csv-merge-*.tmp`，由用户自行清理。

全部功能免费，自有源码采用 MIT。EXE 未签名，依赖及卸载见 [DEPENDENCIES.md](DEPENDENCIES.md)，第三方许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。构建：`python build.py`，输出 `dist/CsvMerger.exe`。

## 自愿赞助

赞助完全自愿，不解锁任何功能。

![请作者喝杯咖啡](assets/donate-wechat.png)
