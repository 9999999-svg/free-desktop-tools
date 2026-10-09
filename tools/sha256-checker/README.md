# SHA-256 批量校验器

免费开源的下载文件完整性校验工具。选择发布者提供的 `SHA256SUMS.txt`，一次核对多个 EXE、ZIP 或资料，区分匹配、不匹配、缺失和清单错误，导出中文 CSV 报告。只读取待检文件，不执行下载程序。

## 下载和 GUI

[下载 Windows EXE](https://github.com/9999999-svg/sha256-checker/releases/download/v1.0.0/SHA256Checker.exe) · [下载 Python 源码 ZIP](https://github.com/9999999-svg/sha256-checker/archive/refs/heads/main.zip) · [查看源码](sha256_checker.py)

双击运行。选择校验清单，文件目录为空时自动使用清单所在目录，点击“开始校验”。核对完成后可以导出 CSV；已有报告不会被覆盖。

把需要核对的发行文件和对应 `SHA256SUMS.txt` 放到同一个目录即可。例如可以检查本账号发布的免费工具下载包。GUI 预览最多 1000 项，CSV 包含全部结果。

## Python 和命令行

源码只使用 Python 标准库，不需要 pip 依赖。

```powershell
python sha256_checker.py
python sha256_checker.py "D:\下载\SHA256SUMS.txt" --csv "D:\校验报告.csv"
SHA256Checker.exe "D:\下载\SHA256SUMS.txt" --base "D:\待检文件"
SHA256Checker.exe --help
```

支持 UTF-8、UTF-8 BOM 和常见 GNU SHA-256 清单格式：64 位十六进制散列值、两个空格或空格加星号、相对文件名。文件名可以有中文、空格和子目录。空行及 `#` 注释忽略；GNU 转义文件名行不支持。

```text
<64位SHA-256>  example.exe
<64位SHA-256> *子目录/中文 文件.zip
```

绝对路径、父目录跳转、越出指定目录的链接都拒绝；其他文件链接或重解析点跳过。CSV 使用 UTF-8 BOM，并将可能被表格软件当成公式的字段按文本处理。校验通过说明文件与提供的散列值一致，**不等于软件没有病毒**；清单也应来自可信发布者。

退出码：0 全部匹配；1 有未匹配条目或读写错误；2 命令行格式错误；130 用户中断。读取期间检测到的文件变化会报错。

## 构建

构建环境为 Windows x64、Python 3.14.6、PyInstaller 6.21.0。依赖大小与卸载见 [DEPENDENCIES.md](DEPENDENCIES.md)。

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.venv\Scripts\python.exe build.py
```

EXE 未签名。自有代码采用 MIT，第三方许可保留于 `licenses/` 和 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 自愿赞助

下载、功能和源码全部免费，赞助完全自愿。

<img src="assets/donate-wechat.png" alt="自愿微信赞助二维码" width="280">
